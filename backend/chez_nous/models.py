import uuid

from django.db import models

from .sejours import dates_echeances


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

    class Meta:
        ordering = ["date_arrivee", "id"]
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
        self.echeances.all().delete()
        Echeance.objects.bulk_create(
            [
                Echeance(reservation=self, date=jour, montant=self.montant_prevu)
                for jour in dates_echeances(self.mode, self.date_arrivee, self.date_depart)
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
