from django.core.exceptions import ValidationError as ErreurDjango
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework import serializers

from .models import (
    MESSAGE_LOGEMENT_OCCUPE,
    Depense,
    Echeance,
    Logement,
    Paiement,
    Reservation,
    nuits_prises,
)
from .occupations import statut_du_jour
from .pays import PAYS_PAR_CODE
from .sejours import dates_echeances


class LogementSerializer(serializers.ModelSerializer):
    type_libelle = serializers.CharField(source="get_type_display", read_only=True)
    pays_libelle = serializers.SerializerMethodField()
    localisation_a_completer = serializers.BooleanField(read_only=True)
    statut_du_jour = serializers.SerializerMethodField()

    class Meta:
        model = Logement
        fields = [
            "id",
            "nom",
            "type",
            "type_libelle",
            "pays",
            "pays_libelle",
            "ville",
            "localisation_a_completer",
            "statut_du_jour",
        ]
        read_only_fields = ["id"]

    def get_pays_libelle(self, logement):
        return PAYS_PAR_CODE.get(logement.pays, "")

    def get_statut_du_jour(self, logement):
        reservations = getattr(logement, "reservations_actives", None)
        if reservations is None:
            reservations = list(logement.reservations.filter(annulee=False))
        return statut_du_jour(reservations, timezone.localdate())

    def validate_nom(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Indiquez le nom du logement.")
        return value

    def validate_ville(self, value):
        return value.strip()

    def validate_pays(self, value):
        value = (value or "").strip().upper()
        if not value:
            if self.instance is None:
                raise serializers.ValidationError("Indiquez le pays.")
            return ""
        if value not in PAYS_PAR_CODE:
            raise serializers.ValidationError("Choisissez un pays de la liste.")
        return value

    def validate(self, attrs):
        if self.instance is not None:
            return attrs
        erreurs = {}
        if not attrs.get("pays"):
            erreurs["pays"] = "Indiquez le pays."
        if not attrs.get("ville"):
            erreurs["ville"] = "Indiquez la ville."
        if erreurs:
            raise serializers.ValidationError(erreurs)
        return attrs


class EcheanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Echeance
        fields = ["id", "date", "montant"]


class PaiementSerializer(serializers.ModelSerializer):
    nature_libelle = serializers.CharField(source="get_nature_display", read_only=True)
    client_nom = serializers.CharField(source="reservation.client_nom", read_only=True)
    logement_nom = serializers.CharField(source="reservation.logement.nom", read_only=True)

    class Meta:
        model = Paiement
        fields = [
            "id",
            "reservation",
            "client_nom",
            "logement_nom",
            "montant",
            "date",
            "nature",
            "nature_libelle",
        ]
        read_only_fields = ["id"]

    def validate_montant(self, value):
        if value <= 0:
            raise serializers.ValidationError("Indiquez un montant encaissé.")
        return value

    def validate_reservation(self, reservation):
        if reservation.annulee:
            raise serializers.ValidationError(
                "Cette réservation est annulée. L’encaissement déjà enregistré est conservé."
            )
        return reservation


class DepenseSerializer(serializers.ModelSerializer):
    logement_nom = serializers.CharField(source="logement.nom", read_only=True)

    class Meta:
        model = Depense
        fields = ["id", "logement", "logement_nom", "libelle", "montant", "date"]
        read_only_fields = ["id"]

    def validate_libelle(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Indiquez le libellé de la dépense.")
        return value

    def validate_montant(self, value):
        if value <= 0:
            raise serializers.ValidationError("Indiquez le montant de la dépense.")
        return value


class ReservationSerializer(serializers.ModelSerializer):
    logement_nom = serializers.CharField(source="logement.nom", read_only=True)
    canal_libelle = serializers.CharField(source="get_canal_display", read_only=True)
    mode_libelle = serializers.CharField(source="get_mode_display", read_only=True)
    echeances = EcheanceSerializer(many=True, read_only=True)
    montant_total_prevu = serializers.SerializerMethodField()
    montant_encaisse = serializers.SerializerMethodField()
    reste_a_recevoir = serializers.SerializerMethodField()
    acompte = serializers.IntegerField(write_only=True, required=False, min_value=0)
    annulee = serializers.BooleanField(read_only=True)
    annulee_le = serializers.DateField(read_only=True)

    class Meta:
        model = Reservation
        fields = [
            "id",
            "logement",
            "logement_nom",
            "client_nom",
            "client_telephone",
            "canal",
            "canal_libelle",
            "mode",
            "mode_libelle",
            "date_arrivee",
            "date_depart",
            "montant_prevu",
            "acompte",
            "montant_total_prevu",
            "montant_encaisse",
            "reste_a_recevoir",
            "annulee",
            "annulee_le",
            "echeances",
        ]
        read_only_fields = ["id", "annulee", "annulee_le"]

    def get_montant_total_prevu(self, reservation):
        if reservation.annulee:
            return 0
        return sum(echeance.montant for echeance in reservation.echeances.all())

    def get_montant_encaisse(self, reservation):
        return sum(paiement.montant for paiement in reservation.paiements.all())

    def get_reste_a_recevoir(self, reservation):
        if reservation.annulee:
            return 0
        return self.get_montant_total_prevu(reservation) - self.get_montant_encaisse(reservation)

    def validate_client_nom(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Indiquez le nom du client.")
        return value

    def validate_client_telephone(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Indiquez le téléphone du client.")
        return value

    def validate_montant_prevu(self, value):
        if value <= 0:
            raise serializers.ValidationError("Indiquez le montant prévu.")
        return value

    def validate(self, attrs):
        instance = self.instance
        if instance is not None and instance.annulee:
            raise serializers.ValidationError("Cette réservation est annulée.")
        arrivee = attrs.get("date_arrivee", getattr(instance, "date_arrivee", None))
        depart = attrs.get("date_depart", getattr(instance, "date_depart", None))
        logement = attrs.get("logement", getattr(instance, "logement", None))
        mode = attrs.get("mode", getattr(instance, "mode", None))
        montant = attrs.get("montant_prevu", getattr(instance, "montant_prevu", None))
        acompte = attrs.get("acompte", 0) or 0

        if arrivee and depart and depart <= arrivee:
            raise serializers.ValidationError(
                {"date_depart": "Le départ doit être après l’arrivée."}
            )

        if logement and arrivee and depart and self._occupe(logement, arrivee, depart):
            raise serializers.ValidationError(MESSAGE_LOGEMENT_OCCUPE)

        if mode and montant and arrivee and depart:
            total = montant * len(dates_echeances(mode, arrivee, depart))
            if acompte > total:
                raise serializers.ValidationError(
                    {"acompte": "L’acompte ne peut pas dépasser le montant prévu."}
                )
        return attrs

    def _occupe(self, logement, arrivee, depart):
        return nuits_prises(
            logement.pk,
            arrivee,
            depart,
            exclure=self.instance.pk if self.instance is not None else None,
        )

    def create(self, validated_data):
        acompte = validated_data.pop("acompte", 0) or 0
        try:
            with transaction.atomic():
                reservation = Reservation.objects.create(**validated_data)
                reservation.generer_echeances()
                if acompte:
                    Paiement.objects.create(
                        reservation=reservation,
                        montant=acompte,
                        date=timezone.localdate(),
                        nature=Paiement.Nature.ACOMPTE,
                    )
        except ErreurDjango as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return reservation

    def update(self, instance, validated_data):
        validated_data.pop("acompte", None)
        avant = (
            instance.mode,
            instance.date_arrivee,
            instance.date_depart,
            instance.montant_prevu,
        )
        for champ, valeur in validated_data.items():
            setattr(instance, champ, valeur)
        try:
            with transaction.atomic():
                instance.save()
                apres = (
                    instance.mode,
                    instance.date_arrivee,
                    instance.date_depart,
                    instance.montant_prevu,
                )
                if apres != avant:
                    instance.generer_echeances()
                    cache = getattr(instance, "_prefetched_objects_cache", None)
                    if cache is not None:
                        cache.pop("echeances", None)
        except ErreurDjango as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return instance


def synthese_financiere():
    # Une réservation annulée ne compte plus dans le prévu ni dans le reste.
    # L'argent déjà encaissé sur ce séjour est isolé : il ne diminue pas
    # ce que les autres séjours doivent encore rapporter.
    confirmees = {"reservation__annulee": False}
    prevu = Echeance.objects.filter(**confirmees).aggregate(total=Sum("montant"))["total"] or 0
    encaisse = Paiement.objects.filter(**confirmees).aggregate(total=Sum("montant"))["total"] or 0
    encaisse_annule = (
        Paiement.objects.filter(reservation__annulee=True).aggregate(total=Sum("montant"))["total"]
        or 0
    )
    depenses = Depense.objects.aggregate(total=Sum("montant"))["total"] or 0
    return {
        "montant_prevu": prevu,
        "montant_encaisse": encaisse,
        "reste_a_recevoir": prevu - encaisse,
        "depenses": depenses,
        "montant_encaisse_annule": encaisse_annule,
    }
