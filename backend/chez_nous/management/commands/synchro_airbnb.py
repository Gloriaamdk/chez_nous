import time

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand

from chez_nous.airbnb import phrase_conflit, synchroniser_logement
from chez_nous.lecture_emails import executer_lecture
from chez_nous.models import Logement


class Command(BaseCommand):
    help = (
        "Récupère les calendriers iCal Airbnb, lit les e-mails de confirmation "
        "et met à jour les réservations. "
        "Avec --boucle, recommence toutes les 15 à 30 minutes."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--logement",
            help=(
                "Identifiant d’un seul logement pour le calendrier. "
                "Sans cet argument, chaque logement qui a une adresse Airbnb est traité."
            ),
        )
        parser.add_argument(
            "--boucle",
            action="store_true",
            help="Recommence sans s’arrêter. Laissez la fenêtre ouverte.",
        )
        parser.add_argument(
            "--intervalle",
            type=int,
            default=20,
            help="Minutes entre deux passages en mode boucle, de 15 à 30. Défaut : 20.",
        )

    def handle(self, *args, **options):
        if options["boucle"]:
            intervalle = options["intervalle"]
            if intervalle < 15 or intervalle > 30:
                self.stderr.write("L’intervalle doit être entre 15 et 30 minutes.")
                return
            self.stdout.write(
                f"Synchronisation automatique toutes les {intervalle} minutes "
                "(calendriers et e-mails). Laissez cette fenêtre ouverte. "
                "Ctrl+C pour arrêter."
            )
            try:
                while True:
                    self._une_fois(options.get("logement"))
                    time.sleep(intervalle * 60)
            except KeyboardInterrupt:
                self.stdout.write("Synchronisation arrêtée.")
            return
        self._une_fois(options.get("logement"))

    def _une_fois(self, identifiant):
        self._calendriers(identifiant)
        self._emails()

    def _calendriers(self, identifiant):
        logements = Logement.objects.all().order_by("nom", "id")
        identifiant = (identifiant or "").strip()
        if identifiant:
            try:
                logements = list(logements.filter(pk=identifiant))
            except ValidationError:
                self.stderr.write("Cet identifiant de logement n’est pas valide.")
                return
            if not logements:
                self.stderr.write("Aucun logement ne correspond à cet identifiant.")
                return
        else:
            logements = list(logements)

        relies = [
            logement
            for logement in logements
            if (logement.url_ical_airbnb or "").strip()
        ]
        if identifiant and not relies:
            self.stdout.write("Ce logement n’a pas d’adresse Airbnb.")
            return
        if not relies:
            self.stdout.write(
                "Aucun logement n’a d’adresse Airbnb. "
                "Ajoutez-la dans la fiche du logement."
            )
        else:
            for logement in relies:
                resultat = synchroniser_logement(logement)
                self.stdout.write(f"{logement.nom} : {resultat['resume']}")
                for conflit in resultat["conflits"]:
                    self.stdout.write(f"  - {phrase_conflit(conflit)}")

        if not identifiant:
            ignores = len(logements) - len(relies)
            if ignores == 1:
                self.stdout.write("1 logement sans adresse Airbnb.")
            elif ignores > 1:
                self.stdout.write(f"{ignores} logements sans adresse Airbnb.")

    def _emails(self):
        resultat = executer_lecture()
        self.stdout.write(f"E-mails Airbnb : {resultat['resume']}")
        for note in resultat["notes"]:
            self.stdout.write(f"  - {note}")
