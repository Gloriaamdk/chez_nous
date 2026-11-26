from django import forms
from django.contrib import admin

from .models import (
    MESSAGE_LOGEMENT_OCCUPE,
    Depense,
    Echeance,
    Logement,
    Paiement,
    Reservation,
    nuits_prises,
)
from .pays import pays_francais


class LogementAdminForm(forms.ModelForm):
    pays = forms.ChoiceField(
        choices=(("", "---------"), *pays_francais()),
        required=False,
        label="Pays",
    )

    class Meta:
        model = Logement
        fields = ("nom", "type", "pays", "ville", "url_ical_airbnb", "annonce_airbnb")


@admin.register(Logement)
class LogementAdmin(admin.ModelAdmin):
    form = LogementAdminForm
    list_display = ("nom", "type", "ville", "pays", "id")


class ReservationAdminForm(forms.ModelForm):
    class Meta:
        model = Reservation
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        if self.errors or cleaned.get("annulee"):
            return cleaned
        logement = cleaned.get("logement")
        arrivee = cleaned.get("date_arrivee")
        depart = cleaned.get("date_depart")
        if logement and arrivee and depart and nuits_prises(
            logement.pk,
            arrivee,
            depart,
            exclure=self.instance.pk,
        ):
            raise forms.ValidationError(MESSAGE_LOGEMENT_OCCUPE)
        return cleaned


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    form = ReservationAdminForm
    list_display = (
        "client_nom",
        "logement",
        "date_arrivee",
        "date_depart",
        "mode",
        "canal",
        "montant_prevu",
        "annulee",
        "blocage",
        "code_airbnb",
        "nombre_voyageurs",
    )


@admin.register(Echeance)
class EcheanceAdmin(admin.ModelAdmin):
    list_display = ("reservation", "date", "montant")


@admin.register(Paiement)
class PaiementAdmin(admin.ModelAdmin):
    list_display = ("reservation", "date", "nature", "montant")


@admin.register(Depense)
class DepenseAdmin(admin.ModelAdmin):
    list_display = ("logement", "date", "libelle", "montant")
