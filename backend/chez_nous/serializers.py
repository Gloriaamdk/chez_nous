from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework import serializers

from .models import Depense, Echeance, Logement, Paiement, Reservation
from .pays import PAYS_PAR_CODE
from .sejours import dates_echeances


class LogementSerializer(serializers.ModelSerializer):
    type_libelle = serializers.CharField(source="get_type_display", read_only=True)
    pays_libelle = serializers.SerializerMethodField()
    localisation_a_completer = serializers.BooleanField(read_only=True)

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
        ]
        read_only_fields = ["id"]

    def get_pays_libelle(self, logement):
        return PAYS_PAR_CODE.get(logement.pays, "")

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
            "echeances",
        ]
        read_only_fields = ["id"]

    def get_montant_total_prevu(self, reservation):
        return sum(echeance.montant for echeance in reservation.echeances.all())

    def get_montant_encaisse(self, reservation):
        return sum(paiement.montant for paiement in reservation.paiements.all())

    def get_reste_a_recevoir(self, reservation):
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
            raise serializers.ValidationError(
                "Ce logement est déjà réservé sur ces dates."
            )

        if mode and montant and arrivee and depart:
            total = montant * len(dates_echeances(mode, arrivee, depart))
            if acompte > total:
                raise serializers.ValidationError(
                    {"acompte": "L’acompte ne peut pas dépasser le montant prévu."}
                )
        return attrs

    def _occupe(self, logement, arrivee, depart):
        reservations = Reservation.objects.filter(
            logement=logement,
            date_arrivee__lt=depart,
            date_depart__gt=arrivee,
        )
        if self.instance is not None:
            reservations = reservations.exclude(pk=self.instance.pk)
        return reservations.exists()

    def create(self, validated_data):
        acompte = validated_data.pop("acompte", 0) or 0
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
        return reservation

    def update(self, instance, validated_data):
        validated_data.pop("acompte", None)
        for champ, valeur in validated_data.items():
            setattr(instance, champ, valeur)
        with transaction.atomic():
            instance.save()
            instance.generer_echeances()
        return instance


def synthese_financiere():
    prevu = Echeance.objects.aggregate(total=Sum("montant"))["total"] or 0
    encaisse = Paiement.objects.aggregate(total=Sum("montant"))["total"] or 0
    depenses = Depense.objects.aggregate(total=Sum("montant"))["total"] or 0
    return {
        "montant_prevu": prevu,
        "montant_encaisse": encaisse,
        "reste_a_recevoir": prevu - encaisse,
        "depenses": depenses,
    }
