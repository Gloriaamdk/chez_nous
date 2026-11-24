from rest_framework.exceptions import NotAuthenticated
from rest_framework.views import exception_handler


def gestionnaire(exc, context):
    reponse = exception_handler(exc, context)
    if reponse is not None and isinstance(exc, NotAuthenticated):
        reponse.data["detail"] = "Connexion requise."
    return reponse
