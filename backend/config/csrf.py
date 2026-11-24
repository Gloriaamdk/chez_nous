from django.http import JsonResponse


def echec_csrf(request, reason=""):
    """Réponse JSON : le front ne sait pas afficher la page HTML de Django."""
    return JsonResponse(
        {"detail": "La page a expiré. Rechargez-la, puis réessayez."},
        status=403,
    )
