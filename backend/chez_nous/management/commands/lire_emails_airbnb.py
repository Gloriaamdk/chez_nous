from django.core.management.base import BaseCommand

from chez_nous.lecture_emails import executer_lecture


class Command(BaseCommand):
    help = (
        "Lit les e-mails de confirmation Airbnb et complète les réservations. "
        "Aucun message n’est supprimé."
    )

    def handle(self, *args, **options):
        resultat = executer_lecture()
        self.stdout.write(resultat["resume"])
        for note in resultat["notes"]:
            self.stdout.write(f"  - {note}")
