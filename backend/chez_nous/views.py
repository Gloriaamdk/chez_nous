from datetime import datetime

from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from .models import Depense, Logement, Paiement, Reservation
from .pays import PAYS_PAR_CODE, pays_francais
from .rapports import construire_rapport
from .serializers import (
    DepenseSerializer,
    LogementSerializer,
    PaiementSerializer,
    ReservationSerializer,
    synthese_financiere,
)


def _date(valeur):
    try:
        return datetime.strptime(valeur, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


@api_view(["GET"])
def status(request):
    return Response({"status": "ok"})


@api_view(["GET"])
def referentiels(request):
    return Response(
        {
            "types": [
                {"valeur": valeur, "libelle": libelle}
                for valeur, libelle in Logement.Type.choices
            ],
            "pays": [
                {"code": code, "libelle": libelle} for code, libelle in pays_francais()
            ],
            "canaux": [
                {"valeur": valeur, "libelle": libelle}
                for valeur, libelle in Reservation.Canal.choices
            ],
            "modes": [
                {"valeur": valeur, "libelle": libelle}
                for valeur, libelle in Reservation.Mode.choices
            ],
            "natures_paiement": [
                {"valeur": valeur, "libelle": libelle}
                for valeur, libelle in Paiement.Nature.choices
            ],
        }
    )


@api_view(["GET"])
def disponibilites(request):
    arrivee = _date(request.query_params.get("arrivee"))
    depart = _date(request.query_params.get("depart"))
    if not arrivee or not depart:
        return Response(
            {"detail": "Indiquez une date d’arrivée et une date de départ."},
            status=400,
        )
    if depart <= arrivee:
        return Response(
            {"detail": "Le départ doit être après l’arrivée."},
            status=400,
        )

    logements = []
    for logement in Logement.objects.all():
        occupe = Reservation.objects.filter(
            logement=logement,
            date_arrivee__lt=depart,
            date_depart__gt=arrivee,
        ).exists()
        logements.append(
            {
                "id": logement.id,
                "nom": logement.nom,
                "type_libelle": logement.get_type_display(),
                "ville": logement.ville,
                "pays_libelle": PAYS_PAR_CODE.get(logement.pays, ""),
                "libre": not occupe,
            }
        )
    return Response({"arrivee": arrivee, "depart": depart, "logements": logements})


@api_view(["GET"])
def synthese(request):
    return Response(synthese_financiere())


@api_view(["GET"])
def rapport(request):
    periode = request.query_params.get("periode", "mois")
    if periode not in {"semaine", "mois"}:
        return Response(
            {"detail": "Choisissez une période : semaine ou mois."},
            status=400,
        )
    jour = _date(request.query_params.get("date")) or timezone.localdate()
    logements = list(Logement.objects.all())
    reservations = list(Reservation.objects.all())
    paiements = list(Paiement.objects.select_related("reservation"))
    depenses = list(Depense.objects.all())
    return Response(
        construire_rapport(logements, reservations, paiements, depenses, periode, jour)
    )


class LogementViewSet(ModelViewSet):
    queryset = Logement.objects.all()
    serializer_class = LogementSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]


class ReservationViewSet(ModelViewSet):
    queryset = Reservation.objects.select_related("logement").prefetch_related(
        "echeances",
        "paiements",
    )
    serializer_class = ReservationSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]


class PaiementViewSet(ModelViewSet):
    queryset = Paiement.objects.select_related("reservation__logement")
    serializer_class = PaiementSerializer
    http_method_names = ["get", "post", "head", "options"]


class DepenseViewSet(ModelViewSet):
    queryset = Depense.objects.select_related("logement")
    serializer_class = DepenseSerializer
    http_method_names = ["get", "post", "head", "options"]
