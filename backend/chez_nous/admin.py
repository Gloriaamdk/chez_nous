from django import forms
from django.contrib import admin

from .models import Depense, Echeance, Logement, Paiement, Reservation
from .pays import pays_francais


class LogementAdminForm(forms.ModelForm):
    pays = forms.ChoiceField(
        choices=(("", "---------"), *pays_francais()),
        required=False,
        label="Pays",
    )

    class Meta:
        model = Logement
        fields = ("nom", "type", "pays", "ville")


@admin.register(Logement)
class LogementAdmin(admin.ModelAdmin):
    form = LogementAdminForm
    list_display = ("nom", "type", "ville", "pays", "id")


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = (
        "client_nom",
        "logement",
        "date_arrivee",
        "date_depart",
        "mode",
        "canal",
        "montant_prevu",
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
