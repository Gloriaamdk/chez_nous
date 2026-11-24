from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response


def profil(utilisateur):
    return {
        "identifiant": utilisateur.get_username(),
        "prenom": utilisateur.first_name,
        "nom": utilisateur.last_name,
        "est_admin": bool(utilisateur.is_staff),
    }


@ensure_csrf_cookie
@api_view(["GET"])
@permission_classes([AllowAny])
def jeton_csrf(request):
    return Response({"csrfToken": get_token(request)})


@api_view(["POST"])
@permission_classes([AllowAny])
@csrf_protect
def connexion(request):
    identifiant = str(request.data.get("identifiant") or "").strip()
    mot_de_passe = request.data.get("mot_de_passe")
    if not identifiant or not isinstance(mot_de_passe, str) or not mot_de_passe:
        return Response(
            {"detail": "Indiquez l’identifiant et le mot de passe."},
            status=400,
        )

    utilisateur = authenticate(request, username=identifiant, password=mot_de_passe)
    if utilisateur is None:
        return Response(
            {"detail": "Identifiant ou mot de passe incorrect."},
            status=400,
        )

    login(request, utilisateur)
    return Response(profil(utilisateur))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def deconnexion(request):
    logout(request)
    return Response({"detail": "Vous êtes déconnectée."})


@ensure_csrf_cookie
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def moi(request):
    return Response(profil(request.user))
