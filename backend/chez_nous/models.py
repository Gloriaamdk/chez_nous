import uuid
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, models, transaction
from django.db.models import F

from .sejours import dates_echeances

MESSAGE_LOGEMENT_OCCUPE = "Ce logement est déjà réservé sur ces dates."


class Logement(models.Model):
    class Type(models.TextChoices):
        STUDIO = "studio", "Studio"
        CHAMBRE_SALON = "chambre_salon", "Chambre-salon"
        APPARTEMENT = "appartement", "Appartement"
        MAISON = "maison", "Maison"
        AUTRE = "autre", "Autre"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom = models.CharField("nom d'affichage", max_length=120)
    type = models.CharField("type", max_length=32, choices=Type.choices)
    pays = models.CharField("pays", max_length=2, blank=True)
    ville = models.CharField("ville", max_length=120, blank=True)

    class Meta:
        ordering = ["nom", "id"]
        verbose_name = "logement"
        verbose_name_plural = "logements"

    def __str__(self):
        return self.nom

    @property
    def localisation_a_completer(self):
        return not self.pays or not self.ville


def iter_nuits(arrivee, depart):
    jour = arrivee
    while jour < depart:
        yield jour
        jour += timedelta(days=1)


def nuits_prises(logement_id, arrivee, depart, exclure=None):
    if not logement_id or not arrivee or not depart:
        return False
    nuits = NuitOccupee.objects.filter(
        logement_id=logement_id,
        date__gte=arrivee,
        date__lt=depart,
    )
    if exclure is not None:
        nuits = nuits.exclude(reservation_id=exclure)
    return nuits.exists()


def verrouiller_logement(logement_id):
    if connection.features.has_select_for_update:
        Logement.objects.select_for_update().get(pk=logement_id)
        return
    Logement.objects.filter(pk=logement_id).update(nom=F("nom"))


def conflit_de_nuit(exc):
    message = str(exc).lower()
    return "une_nuit_par_logement" in message or "chez_nous_nuitoccupee" in message


class Reservation(models.Model):
    class Canal(models.TextChoices):
        AIRBNB = "airbnb", "Airbnb"
        WHATSAPP = "whatsapp", "WhatsApp"
        TELEPHONE = "telephone", "Téléphone"

    class Mode(models.TextChoices):
        NUITEE = "nuitee", "Nuitée"
        MOIS = "mois", "Au mois"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    logement = models.ForeignKey(
        Logement,
        on_delete=models.PROTECT,
        related_name="reservations",
    )
    client_nom = models.CharField("client", max_length=120)
    client_telephone = models.CharField("téléphone", max_length=30)
    canal = models.CharField("canal", max_length=20, choices=Canal.choices)
    mode = models.CharField("mode", max_length=20, choices=Mode.choices)
    date_arrivee = models.DateField("arrivée")
    date_depart = models.DateField("départ")
    montant_prevu = models.PositiveIntegerField("montant prévu")
    annulee = models.BooleanField("annulée", default=False)
    annulee_le = models.DateField("annulée le", null=True, blank=True)

    class Meta:
        ordering = ["annulee", "date_arrivee", "id"]
        verbose_name = "réservation"
        verbose_name_plural = "réservations"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(date_depart__gt=models.F("date_arrivee")),
                name="reservation_depart_apres_arrivee",
            ),
        ]

    def __str__(self):
        return f"{self.client_nom} — {self.logement}"

    def generer_echeances(self):
        """Recrée les échéances prévues.

        Les paiements ne sont pas liés aux échéances : ils restent attachés
        à la réservation et ne sont ni supprimés ni recréés ici.
        """
        self.echeances.all().delete()
        Echeance.objects.bulk_create(
            [
                Echeance(reservation=self, date=jour, montant=self.montant_prevu)
                for jour in dates_echeances(self.mode, self.date_arrivee, self.date_depart)
            ]
        )

    def save(self, *args, **kwargs):
        try:
            with transaction.atomic():
                self._verrouiller_logements()
                if not self.annulee and nuits_prises(
                    self.logement_id,
                    self.date_arrivee,
                    self.date_depart,
                    exclure=self.pk,
                ):
                    raise ValidationError(MESSAGE_LOGEMENT_OCCUPE)
                super().save(*args, **kwargs)
                self._sync_nuits()
        except IntegrityError as exc:
            if not conflit_de_nuit(exc):
                raise
            raise ValidationError(MESSAGE_LOGEMENT_OCCUPE) from exc

    def _logements_concernes(self):
        identifiants = {self.logement_id}
        if self.pk and not self._state.adding:
            ancien = (
                type(self)
                .objects.filter(pk=self.pk)
                .values_list("logement_id", flat=True)
                .first()
            )
            if ancien:
                identifiants.add(ancien)
        return identifiants

    def _verrouiller_logements(self):
        """Sérialise les écritures qui concernent les mêmes logements.

        PostgreSQL verrouille la réservation, puis chaque ligne de logement
        (SELECT FOR UPDATE). SQLite n'a pas ce verrou : une écriture sur la
        ligne du logement prend le verrou d'écriture de la base avant le
        contrôle des nuits. L'unicité (logement, nuit) reste le filet, sur
        les deux moteurs.
        """
        if self.pk and not self._state.adding and connection.features.has_select_for_update:
            list(type(self).objects.select_for_update().filter(pk=self.pk))
        for identifiant in sorted(self._logements_concernes(), key=str):
            verrouiller_logement(identifiant)

    def _sync_nuits(self):
        self.nuits.all().delete()
        if self.annulee:
            return
        NuitOccupee.objects.bulk_create(
            [
                NuitOccupee(logement_id=self.logement_id, reservation=self, date=jour)
                for jour in iter_nuits(self.date_arrivee, self.date_depart)
            ]
        )


class Echeance(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name="echeances",
    )
    date = models.DateField("date d'échéance")
    montant = models.PositiveIntegerField("montant prévu")

    class Meta:
        ordering = ["date", "id"]
        verbose_name = "échéance"
        verbose_name_plural = "échéances"


class Paiement(models.Model):
    class Nature(models.TextChoices):
        ACOMPTE = "acompte", "Acompte"
        ECHEANCE = "echeance", "Échéance"
        AUTRE = "autre", "Autre"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name="paiements",
    )
    montant = models.PositiveIntegerField("montant encaissé")
    date = models.DateField("date d'encaissement")
    nature = models.CharField("nature", max_length=20, choices=Nature.choices)

    class Meta:
        ordering = ["date", "id"]
        verbose_name = "paiement"
        verbose_name_plural = "paiements"


class NuitOccupee(models.Model):
    """Une nuit réservée, du soir de l'arrivée jusqu'à la veille du départ.

    Le jour du départ n'est pas occupé : une arrivée ce jour-là reste possible.
    L'unicité (logement, date) est imposée par SQLite aujourd'hui et par
    PostgreSQL plus tard. Une réservation annulée n'a plus de lignes ici.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    logement = models.ForeignKey(
        Logement,
        on_delete=models.CASCADE,
        related_name="nuits",
    )
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name="nuits",
    )
    date = models.DateField("nuit")

    class Meta:
        ordering = ["date", "id"]
        verbose_name = "nuit occupée"
        verbose_name_plural = "nuits occupées"
        constraints = [
            models.UniqueConstraint(
                fields=["logement", "date"],
                name="une_nuit_par_logement",
            ),
        ]

    def __str__(self):
        return f"{self.logement} · {self.date}"


class Depense(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    logement = models.ForeignKey(
        Logement,
        on_delete=models.PROTECT,
        related_name="depenses",
    )
    libelle = models.CharField("libellé", max_length=160)
    montant = models.PositiveIntegerField("montant")
    date = models.DateField("date")

    class Meta:
        ordering = ["-date", "id"]
        verbose_name = "dépense"
        verbose_name_plural = "dépenses"
