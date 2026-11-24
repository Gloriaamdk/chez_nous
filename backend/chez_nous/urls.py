from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("logements", views.LogementViewSet, basename="logement")
router.register("reservations", views.ReservationViewSet, basename="reservation")
router.register("paiements", views.PaiementViewSet, basename="paiement")
router.register("depenses", views.DepenseViewSet, basename="depense")

urlpatterns = [
    path("status/", views.status, name="status"),
    path("referentiels/", views.referentiels, name="referentiels"),
    path("disponibilites/", views.disponibilites, name="disponibilites"),
    path("synthese/", views.synthese, name="synthese"),
    path("rapports/", views.rapport, name="rapport"),
    path("", include(router.urls)),
]
