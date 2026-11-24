from django.apps import AppConfig


class ChezNousConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'chez_nous'

    def ready(self):
        from .models import Logement
        from .pays import pays_francais

        Logement._meta.get_field("pays").choices = (("", ""), *pays_francais())
