from rest_framework.authentication import SessionAuthentication


class AuthentificationSession(SessionAuthentication):
    def authenticate_header(self, request):
        # Schéma inconnu du navigateur : la réponse reste 401, sans fenêtre native.
        return "Session"
