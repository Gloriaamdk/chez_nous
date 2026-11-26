from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import authentification, views

router = DefaultRouter()
router.register("logements", views.LogementViewSet, basename="logement")
router.register("reservations", views.ReservationViewSet, basename="reservation")
router.register("paiements", views.PaiementViewSet, basename="paiement")
router.register("depenses", views.DepenseViewSet, basename="depense")

urlpatterns = [
    path("status/", views.status, name="status"),
    path(
        "logements/<uuid:logement_id>/calendrier/<str:jeton>.ics",
        views.calendrier_public,
        name="calendrier-public",
    ),
    path("auth/csrf/", authentification.jeton_csrf, name="jeton-csrf"),
    path("auth/connexion/", authentification.connexion, name="connexion"),
    path("auth/deconnexion/", authentification.deconnexion, name="deconnexion"),
    path("auth/moi/", authentification.moi, name="moi"),
    path("referentiels/", views.referentiels, name="referentiels"),
    path("disponibilites/", views.disponibilites, name="disponibilites"),
    path("synthese/", views.synthese, name="synthese"),
    path("tableau-de-bord/", views.tableau_de_bord, name="tableau-de-bord"),
    path("rapports/", views.rapport, name="rapport"),
    path("airbnb/lecture/", views.lecture_emails, name="lecture-emails"),
    path("", include(router.urls)),
]
