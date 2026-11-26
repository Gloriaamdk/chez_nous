from datetime import date, timedelta
from email.message import EmailMessage
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from icalendar import Calendar
from rest_framework.test import APITestCase

from chez_nous.airbnb import ErreurCalendrier, extraire_code, recuperer_flux, synchroniser_logement
from chez_nous.emails_airbnb import analyser_email
from chez_nous.lecture_emails import executer_lecture, lire_boite
from chez_nous.models import (
    LectureEmails,
    Logement,
    MessageEmailTraite,
    NuitOccupee,
    Paiement,
    Reservation,
)
from chez_nous.test_authentification import MOT_DE_PASSE
from django.contrib.auth.models import User

PHRASE_SECRETE = "PHRASE-SECRETE-QUI-NE-DOIT-PAS-ETRE-STOCKEE"
URL_AIRBNB = "https://www.airbnb.com/calendar/ical/123.ics?s=jeton-fictif"


def flux_ical(evenements):
    lignes = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Airbnb Inc//Hosting Calendar 0.8.8//EN",
        "CALSCALE:GREGORIAN",
    ]
    for evenement in evenements:
        lignes.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{evenement['uid']}",
                f"SUMMARY:{evenement.get('summary', 'Reserved')}",
                f"DTSTART;VALUE=DATE:{evenement['debut'].strftime('%Y%m%d')}",
                f"DTEND;VALUE=DATE:{evenement['fin'].strftime('%Y%m%d')}",
            ]
        )
        if evenement.get("description"):
            lignes.append(f"DESCRIPTION:{evenement['description']}")
        if evenement.get("url"):
            lignes.append(f"URL:{evenement['url']}")
        lignes.append("END:VEVENT")
    lignes.append("END:VCALENDAR")
    return "\r\n".join(lignes).encode()


def message_brut(sujet, corps, identifiant="<message-fictif@exemple.test>"):
    message = EmailMessage()
    message["Subject"] = sujet
    message["From"] = "Airbnb <automated@airbnb.com>"
    message["Message-ID"] = identifiant
    message.set_content(f"{corps}\n{PHRASE_SECRETE}\n")
    return message.as_bytes()


CONFIRMATION_FR = """
Réservation confirmée

Awa Mensah arrive le 1 décembre 2026.

Annonce : Studio Lomé

Arrivée
1 décembre 2026

Départ
4 décembre 2026

Voyageurs
2 voyageurs

Code de confirmation
HMTEST01

Vous gagnerez
45 000 FCFA
"""

CONFIRMATION_EN = """
Reservation confirmed

Guest: Koffi Amegbo
2 guests

Listing: Studio Lomé

Check-in
December 10, 2026

Checkout
December 12, 2026

Confirmation code
HMTEST02

You earn
XOF 30,000
"""

ANNULATION_FR = """
Réservation annulée

Code de confirmation
HMTEST01

Annonce : Studio Lomé
"""

MODIFICATION_EN = """
Reservation updated

Guest: Koffi Amegbo

Listing: Studio Lomé

Check-in
December 11, 2026

Checkout
December 14, 2026

Confirmation code
HMTEST02

3 guests

You earn
XOF 40,000
"""


class AnalyseEmailTests(TestCase):
    def test_confirmation_en_francais(self):
        analyse = analyser_email(message_brut("Réservation confirmée", CONFIRMATION_FR))
        self.assertEqual(analyse.type, "confirmation")
        self.assertEqual(analyse.voyageur, "Awa Mensah")
        self.assertEqual(analyse.nombre_voyageurs, 2)
        self.assertEqual(analyse.arrivee, date(2026, 12, 1))
        self.assertEqual(analyse.depart, date(2026, 12, 4))
        self.assertEqual(analyse.annonce, "Studio Lomé")
        self.assertEqual(analyse.code, "HMTEST01")
        self.assertEqual(analyse.montant_fcfa, 45000)
        self.assertEqual(analyse.devise_autre, "")

    def test_confirmation_en_anglais(self):
        analyse = analyser_email(message_brut("Reservation confirmed", CONFIRMATION_EN))
        self.assertEqual(analyse.type, "confirmation")
        self.assertEqual(analyse.voyageur, "Koffi Amegbo")
        self.assertEqual(analyse.nombre_voyageurs, 2)
        self.assertEqual(analyse.arrivee, date(2026, 12, 10))
        self.assertEqual(analyse.depart, date(2026, 12, 12))
        self.assertEqual(analyse.montant_fcfa, 30000)
        self.assertEqual(analyse.code, "HMTEST02")

    def test_annulation_et_modification(self):
        annulation = analyser_email(message_brut("Réservation annulée", ANNULATION_FR))
        self.assertEqual(annulation.type, "annulation")
        self.assertEqual(annulation.code, "HMTEST01")
        modification = analyser_email(message_brut("Reservation updated", MODIFICATION_EN))
        self.assertEqual(modification.type, "modification")
        self.assertEqual(modification.arrivee, date(2026, 12, 11))
        self.assertEqual(modification.depart, date(2026, 12, 14))
        self.assertEqual(modification.nombre_voyageurs, 3)
        self.assertEqual(modification.montant_fcfa, 40000)

    def test_une_devise_etrangere_n_est_pas_convertie(self):
        analyse = analyser_email(
            message_brut(
                "Reservation confirmed",
                "Guest: Awa Diallo\nListing: Studio Lomé\nYou earn\n€120.00\n",
            )
        )
        self.assertIsNone(analyse.montant_fcfa)
        self.assertIn("EUR", analyse.devise_autre)

    def test_un_montant_absent_reste_vide(self):
        analyse = analyser_email(
            message_brut(
                "Réservation confirmée",
                "Awa Diallo arrive le 2 janvier 2027.\nAnnonce : Studio Lomé\n"
                "Arrivée\n2 janvier 2027\nDépart\n5 janvier 2027\n",
            )
        )
        self.assertIsNone(analyse.montant_fcfa)
        self.assertEqual(analyse.voyageur, "Awa Diallo")


class CalendrierAPITests(APITestCase):
    def setUp(self):
        super().setUp()
        self.proprietaire = User.objects.create_user("proprietaire", password=MOT_DE_PASSE)
        self.client.force_login(self.proprietaire)
        self.logement = Logement.objects.create(
            nom="Studio",
            type=Logement.Type.STUDIO,
            pays="TG",
            ville="Lomé",
            annonce_airbnb="Studio Lomé",
            url_ical_airbnb=URL_AIRBNB,
        )

    def importer(self, evenements):
        with patch("chez_nous.airbnb.urlopen") as urlopen:
            resultat = synchroniser_logement(self.logement, contenu=flux_ical(evenements))
            urlopen.assert_not_called()
        self.logement.refresh_from_db()
        return resultat

    def test_import_cree_un_sejour_et_un_blocage_sans_doublon(self):
        resultat = self.importer(
            [
                {"uid": "sejour-1@airbnb.com", "debut": date(2026, 12, 10), "fin": date(2026, 12, 15)},
                {
                    "uid": "blocage-1@airbnb.com",
                    "debut": date(2026, 12, 20),
                    "fin": date(2026, 12, 22),
                    "summary": "Not available",
                },
            ]
        )
        self.assertEqual(resultat["creees"], 2)
        self.assertEqual(resultat["conflits"], [])
        sejour = Reservation.objects.get(uid_ical="sejour-1@airbnb.com")
        self.assertEqual(sejour.client_nom, "Client Airbnb")
        self.assertEqual(sejour.client_telephone, "À compléter")
        self.assertEqual(sejour.canal, "airbnb")
        self.assertEqual(sejour.montant_prevu, 0)
        self.assertFalse(sejour.blocage)
        blocage = Reservation.objects.get(uid_ical="blocage-1@airbnb.com")
        self.assertTrue(blocage.blocage)
        self.assertEqual(blocage.client_nom, "Indisponible Airbnb")

        encore = self.importer(
            [
                {"uid": "sejour-1@airbnb.com", "debut": date(2026, 12, 10), "fin": date(2026, 12, 15)},
                {
                    "uid": "blocage-1@airbnb.com",
                    "debut": date(2026, 12, 20),
                    "fin": date(2026, 12, 22),
                    "summary": "Not available",
                },
            ]
        )
        self.assertEqual(encore["creees"], 0)
        self.assertEqual(encore["modifiees"], 0)
        self.assertEqual(Reservation.objects.count(), 2)

    def test_changement_de_dates_garde_le_nom_deja_saisi(self):
        self.importer(
            [{"uid": "sejour-1@airbnb.com", "debut": date(2026, 12, 10), "fin": date(2026, 12, 12)}]
        )
        sejour = Reservation.objects.get(uid_ical="sejour-1@airbnb.com")
        reponse = self.client.patch(
            f"/api/reservations/{sejour.id}/",
            {
                "client_nom": "Awa Mensah",
                "client_telephone": "90000000",
                "montant_prevu": 45000,
            },
            format="json",
        )
        self.assertEqual(reponse.status_code, 200, reponse.data)

        resultat = self.importer(
            [{"uid": "sejour-1@airbnb.com", "debut": date(2026, 12, 11), "fin": date(2026, 12, 14)}]
        )
        self.assertEqual(resultat["modifiees"], 1)
        sejour.refresh_from_db()
        self.assertEqual(sejour.client_nom, "Awa Mensah")
        self.assertEqual(sejour.client_telephone, "90000000")
        self.assertEqual(sejour.montant_prevu, 45000)
        self.assertEqual(sejour.date_arrivee, date(2026, 12, 11))
        self.assertEqual(sejour.date_depart, date(2026, 12, 14))
        self.assertEqual(sejour.echeances.get().montant, 45000)
        self.assertEqual(sejour.echeances.get().date, date(2026, 12, 11))

    def test_un_evenement_disparu_annule_et_conserve_le_paiement(self):
        self.importer(
            [
                {"uid": "sejour-1@airbnb.com", "debut": date(2026, 12, 10), "fin": date(2026, 12, 12)},
                {"uid": "sejour-2@airbnb.com", "debut": date(2026, 12, 20), "fin": date(2026, 12, 22)},
            ]
        )
        sejour = Reservation.objects.get(uid_ical="sejour-1@airbnb.com")
        paiement = self.client.post(
            "/api/paiements/",
            {
                "reservation": str(sejour.id),
                "montant": 10000,
                "date": "2026-12-10",
                "nature": "acompte",
            },
            format="json",
        )
        self.assertEqual(paiement.status_code, 201, paiement.data)
        Reservation.objects.create(
            logement=self.logement,
            client_nom="Saisie à la main",
            client_telephone="90000000",
            canal="airbnb",
            mode="nuitee",
            date_arrivee=date(2027, 1, 4),
            date_depart=date(2027, 1, 6),
            montant_prevu=20000,
        )

        resultat = self.importer(
            [{"uid": "sejour-2@airbnb.com", "debut": date(2026, 12, 20), "fin": date(2026, 12, 22)}]
        )
        self.assertEqual(resultat["annulees"], 1)
        sejour.refresh_from_db()
        self.assertTrue(sejour.annulee)
        self.assertEqual(Paiement.objects.filter(reservation=sejour).count(), 1)
        self.assertEqual(NuitOccupee.objects.filter(reservation=sejour).count(), 0)
        self.assertFalse(Reservation.objects.get(client_nom="Saisie à la main").annulee)
        synthese = self.client.get("/api/synthese/")
        self.assertEqual(synthese.data["montant_encaisse_annule"], 10000)

    def test_un_conflit_est_signale_sans_ecraser_le_sejour_local(self):
        local = self.client.post(
            "/api/reservations/",
            {
                "logement": str(self.logement.id),
                "client_nom": "Awa",
                "client_telephone": "90000000",
                "canal": "whatsapp",
                "mode": "nuitee",
                "date_arrivee": "2026-12-01",
                "date_depart": "2026-12-05",
                "montant_prevu": 40000,
                "acompte": 0,
            },
            format="json",
        )
        self.assertEqual(local.status_code, 201, local.data)
        resultat = self.importer(
            [
                {"uid": "chevauche@airbnb.com", "debut": date(2026, 12, 3), "fin": date(2026, 12, 8)},
                {"uid": "libre@airbnb.com", "debut": date(2026, 12, 20), "fin": date(2026, 12, 22)},
            ]
        )
        self.assertEqual(resultat["creees"], 1)
        self.assertEqual(len(resultat["conflits"]), 1)
        self.assertIn("déjà réservé", resultat["conflits"][0]["message"])
        self.assertFalse(Reservation.objects.filter(uid_ical="chevauche@airbnb.com").exists())
        self.assertTrue(Reservation.objects.filter(uid_ical="libre@airbnb.com").exists())
        self.assertEqual(Reservation.objects.get(pk=local.data["id"]).client_nom, "Awa")

        self.importer(
            [{"uid": "suite@airbnb.com", "debut": date(2026, 12, 5), "fin": date(2026, 12, 7)}]
        )
        self.assertTrue(Reservation.objects.filter(uid_ical="suite@airbnb.com").exists())

    def test_un_blocage_ne_compte_ni_dans_le_prevu_ni_dans_l_occupation(self):
        self.importer(
            [
                {
                    "uid": "blocage-1@airbnb.com",
                    "debut": date(2026, 12, 10),
                    "fin": date(2026, 12, 15),
                    "summary": "Not available",
                }
            ]
        )
        synthese = self.client.get("/api/synthese/")
        self.assertEqual(synthese.data["montant_prevu"], 0)
        rapport = self.client.get("/api/rapports/", {"periode": "mois", "date": "2026-12-12"})
        ligne = next(item for item in rapport.data["logements"] if item["nom"] == "Studio")
        self.assertEqual(ligne["nuits_occupees"], 0)
        libre = self.client.get(
            "/api/disponibilites/",
            {"arrivee": "2026-12-12", "depart": "2026-12-13"},
        )
        studio = next(item for item in libre.data["logements"] if item["nom"] == "Studio")
        self.assertFalse(studio["libre"])

    def test_export_avec_jeton_et_refus_sans_jeton(self):
        self.client.post(
            "/api/reservations/",
            {
                "logement": str(self.logement.id),
                "client_nom": "Awa Mensah",
                "client_telephone": "90000000",
                "canal": "whatsapp",
                "mode": "nuitee",
                "date_arrivee": "2026-12-01",
                "date_depart": "2026-12-05",
                "montant_prevu": 40000,
                "acompte": 0,
            },
            format="json",
        )
        self.client.post(
            "/api/reservations/",
            {
                "logement": str(self.logement.id),
                "client_nom": "Koffi",
                "client_telephone": "91000000",
                "canal": "telephone",
                "mode": "nuitee",
                "date_arrivee": "2026-12-10",
                "date_depart": "2026-12-12",
                "montant_prevu": 20000,
                "acompte": 0,
            },
            format="json",
        )
        self.importer(
            [{"uid": "airbnb-1@airbnb.com", "debut": date(2027, 1, 2), "fin": date(2027, 1, 4)}]
        )
        annulee = self.client.post(
            "/api/reservations/",
            {
                "logement": str(self.logement.id),
                "client_nom": "Binta",
                "client_telephone": "92000000",
                "canal": "whatsapp",
                "mode": "nuitee",
                "date_arrivee": "2027-02-01",
                "date_depart": "2027-02-03",
                "montant_prevu": 15000,
                "acompte": 0,
            },
            format="json",
        )
        self.client.post(f"/api/reservations/{annulee.data['id']}/annuler/", {}, format="json")

        anonyme = self.client_class()
        mauvais = anonyme.get(
            f"/api/logements/{self.logement.id}/calendrier/pas-le-bon-jeton.ics"
        )
        self.assertEqual(mauvais.status_code, 404)
        self.assertNotIn(b"Awa", mauvais.content)
        self.assertNotIn(b"90000000", mauvais.content)

        bon = anonyme.get(f"/api/logements/{self.logement.id}/calendrier/{self.logement.jeton_ical}.ics")
        self.assertEqual(bon.status_code, 200)
        self.assertIn("text/calendar", bon["Content-Type"])
        texte = bon.content.decode()
        self.assertNotIn("Awa", texte)
        self.assertNotIn("Koffi", texte)
        self.assertNotIn("90000000", texte)
        self.assertNotIn("Binta", texte)
        calendrier = Calendar.from_ical(bon.content)
        resumes = [str(composant.get("summary")) for composant in calendrier.walk("VEVENT")]
        self.assertEqual(resumes, ["Réservé", "Réservé"])
        self.assertIn(b"DTSTART;VALUE=DATE:20261201", bon.content)
        self.assertIn(b"DTSTART;VALUE=DATE:20261210", bon.content)

        nouveau = self.client.post(f"/api/logements/{self.logement.id}/nouveau-lien-ical/", {}, format="json")
        self.assertEqual(nouveau.status_code, 200, nouveau.data)
        ancien = anonyme.get(f"/api/logements/{self.logement.id}/calendrier/{self.logement.jeton_ical}.ics")
        self.assertEqual(ancien.status_code, 404)
        self.logement.refresh_from_db()
        encore = anonyme.get(f"/api/logements/{self.logement.id}/calendrier/{self.logement.jeton_ical}.ics")
        self.assertEqual(encore.status_code, 200)

    def test_une_adresse_etrangere_est_refusee_sans_reseau(self):
        with patch("chez_nous.airbnb.urlopen") as urlopen:
            reponse = self.client.patch(
                f"/api/logements/{self.logement.id}/",
                {"url_ical_airbnb": "https://example.com/calendrier.ics"},
                format="json",
            )
            self.assertEqual(reponse.status_code, 400, reponse.data)
            with self.assertRaises(ErreurCalendrier):
                recuperer_flux("https://example.com/calendrier.ics")
            urlopen.assert_not_called()

    def test_le_bouton_et_la_commande_signalent_le_conflit(self):
        self.client.post(
            "/api/reservations/",
            {
                "logement": str(self.logement.id),
                "client_nom": "Awa",
                "client_telephone": "90000000",
                "canal": "telephone",
                "mode": "nuitee",
                "date_arrivee": "2026-12-01",
                "date_depart": "2026-12-05",
                "montant_prevu": 40000,
                "acompte": 0,
            },
            format="json",
        )
        contenu = flux_ical(
            [{"uid": "chevauche@airbnb.com", "debut": date(2026, 12, 2), "fin": date(2026, 12, 6)}]
        )
        with patch("chez_nous.airbnb.recuperer_flux", return_value=contenu) as recuperer:
            reponse = self.client.post(
                f"/api/logements/{self.logement.id}/synchroniser/",
                {},
                format="json",
            )
            recuperer.assert_called_once()
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(len(reponse.data["synchro_resultat"]["conflits"]), 1)
        self.assertIn("déjà réservé", reponse.data["synchro_resultat"]["conflits"][0]["message"])
        self.assertIn("conflit", reponse.data["synchro_resultat"]["resume"])

        sortie = StringIO()
        with patch("chez_nous.airbnb.recuperer_flux", return_value=contenu):
            call_command("synchro_airbnb", "--logement", str(self.logement.id), stdout=sortie)
        self.assertIn("Studio", sortie.getvalue())
        self.assertIn("déjà réservé", sortie.getvalue())

    def test_une_lecture_impossible_n_annule_pas_les_sejours(self):
        self.importer(
            [{"uid": "sejour-1@airbnb.com", "debut": date(2026, 12, 10), "fin": date(2026, 12, 12)}]
        )
        self.logement.url_ical_airbnb = "https://example.com/mauvais.ics"
        self.logement.save(update_fields=["url_ical_airbnb"])
        resultat = synchroniser_logement(self.logement)
        self.assertIn("airbnb.com", resultat["erreur"])
        self.assertEqual(resultat["annulees"], 0)
        self.assertFalse(Reservation.objects.get(uid_ical="sejour-1@airbnb.com").annulee)


class EmailsReservationTests(APITestCase):
    def setUp(self):
        super().setUp()
        self.proprietaire = User.objects.create_user("proprietaire", password=MOT_DE_PASSE)
        self.client.force_login(self.proprietaire)
        self.logement = Logement.objects.create(
            nom="Studio",
            type=Logement.Type.STUDIO,
            pays="TG",
            ville="Lomé",
            annonce_airbnb="Studio Lomé",
            url_ical_airbnb=URL_AIRBNB,
        )

    def lire(self, sujet, corps, identifiant):
        with patch("chez_nous.lecture_emails._ouvrir_imap") as ouvrir:
            resultat = executer_lecture(
                messages=[message_brut(sujet, corps, identifiant)]
            )
            ouvrir.assert_not_called()
        return resultat

    def test_l_email_avant_l_ical_ne_cree_pas_de_doublon(self):
        resultat = self.lire("Réservation confirmée", CONFIRMATION_FR, "<fr-1@exemple.test>")
        self.assertEqual(resultat["creees"], 1)
        sejour = Reservation.objects.get()
        self.assertEqual(sejour.client_nom, "Awa Mensah")
        self.assertEqual(sejour.code_airbnb, "HMTEST01")
        self.assertEqual(sejour.nombre_voyageurs, 2)
        self.assertEqual(sejour.montant_prevu, 45000)
        self.assertEqual(sejour.echeances.get().montant, 45000)
        self.assertEqual(sejour.uid_ical, "")
        self.assertNotIn(PHRASE_SECRETE, str(resultat))
        self.assertFalse(
            MessageEmailTraite.objects.filter(message_id__contains=PHRASE_SECRETE).exists()
        )
        lecture = LectureEmails.objects.get()
        self.assertNotIn(PHRASE_SECRETE, str(lecture.resultat))

        contenu = flux_ical(
            [
                {
                    "uid": "ical-1@airbnb.com",
                    "debut": date(2026, 12, 1),
                    "fin": date(2026, 12, 4),
                    "description": "Reservation URL: https://www.airbnb.com/reservation/itinerary?code=HMTEST01",
                }
            ]
        )
        synchro = synchroniser_logement(self.logement, contenu=contenu)
        self.assertEqual(synchro["creees"], 0)
        self.assertEqual(synchro["modifiees"], 1)
        self.assertEqual(Reservation.objects.count(), 1)
        sejour.refresh_from_db()
        self.assertEqual(sejour.uid_ical, "ical-1@airbnb.com")
        self.assertEqual(sejour.client_nom, "Awa Mensah")
        self.assertEqual(sejour.montant_prevu, 45000)
        self.assertEqual(extraire_code("https://www.airbnb.com/reservation/itinerary?code=HMTEST01"), "HMTEST01")

    def test_l_ical_avant_l_email_est_complete(self):
        synchroniser_logement(
            self.logement,
            contenu=flux_ical(
                [{"uid": "ical-2@airbnb.com", "debut": date(2026, 12, 10), "fin": date(2026, 12, 12)}]
            ),
        )
        resultat = self.lire("Reservation confirmed", CONFIRMATION_EN, "<en-1@exemple.test>")
        self.assertEqual(resultat["completees"], 1)
        self.assertEqual(Reservation.objects.count(), 1)
        sejour = Reservation.objects.get()
        self.assertEqual(sejour.client_nom, "Koffi Amegbo")
        self.assertEqual(sejour.montant_prevu, 30000)
        self.assertEqual(sejour.code_airbnb, "HMTEST02")
        self.assertEqual(sejour.nombre_voyageurs, 2)
        self.assertEqual(sejour.uid_ical, "ical-2@airbnb.com")

        modification = self.lire("Reservation updated", MODIFICATION_EN, "<en-2@exemple.test>")
        self.assertEqual(modification["modifiees"], 1)
        sejour.refresh_from_db()
        self.assertEqual(sejour.date_arrivee, date(2026, 12, 11))
        self.assertEqual(sejour.date_depart, date(2026, 12, 14))
        self.assertEqual(sejour.montant_prevu, 40000)
        self.assertEqual(Reservation.objects.count(), 1)

    def test_l_annulation_garde_l_encaissement_et_n_est_pas_relue(self):
        self.lire("Réservation confirmée", CONFIRMATION_FR, "<fr-1@exemple.test>")
        sejour = Reservation.objects.get()
        Paiement.objects.create(
            reservation=sejour,
            montant=5000,
            date=date(2026, 12, 1),
            nature=Paiement.Nature.ACOMPTE,
        )
        resultat = self.lire("Réservation annulée", ANNULATION_FR, "<fr-annule@exemple.test>")
        self.assertEqual(resultat["annulees"], 1)
        sejour.refresh_from_db()
        self.assertTrue(sejour.annulee)
        self.assertEqual(Paiement.objects.filter(reservation=sejour).count(), 1)
        self.assertEqual(NuitOccupee.objects.filter(reservation=sejour).count(), 0)

        encore = self.lire("Réservation confirmée", CONFIRMATION_FR, "<fr-1@exemple.test>")
        self.assertEqual(encore["rien_de_nouveau"], True)
        self.assertEqual(Reservation.objects.count(), 1)

    def test_une_annonce_inconnue_ne_cree_rien(self):
        resultat = self.lire(
            "Reservation confirmed",
            "Guest: Inconnu Test\nListing: Villa inventée\n"
            "Check-in\nJanuary 2, 2027\nCheckout\nJanuary 4, 2027\n"
            "Confirmation code\nHMTEST99\nYou earn\nXOF 10,000\n",
            "<inconnu@exemple.test>",
        )
        self.assertEqual(resultat["creees"], 0)
        self.assertEqual(Reservation.objects.count(), 0)
        self.assertTrue(any("non reconnue" in note for note in resultat["notes"]))

    def test_la_lecture_s_affiche_et_reste_reservee(self):
        self.lire("Réservation confirmée", CONFIRMATION_FR, "<fr-1@exemple.test>")
        anonyme = self.client_class()
        self.assertEqual(anonyme.get("/api/airbnb/lecture/").status_code, 401)
        lecture = self.client.get("/api/airbnb/lecture/")
        self.assertEqual(lecture.status_code, 200, lecture.data)
        self.assertIn("créée", lecture.data["resultat"]["resume"])
        self.assertNotIn(PHRASE_SECRETE, str(lecture.data))


class BoucleTests(TestCase):
    def test_un_intervalle_hors_plage_ne_boucle_pas(self):
        with patch("chez_nous.management.commands.synchro_airbnb.time.sleep") as dormir:
            call_command("synchro_airbnb", "--boucle", "--intervalle", "10", stderr=StringIO())
            dormir.assert_not_called()

    def test_la_boucle_enchaîne_un_passage_puis_attend(self):
        sortie = StringIO()
        with patch(
            "chez_nous.management.commands.synchro_airbnb.time.sleep",
            side_effect=KeyboardInterrupt,
        ) as dormir:
            call_command("synchro_airbnb", "--boucle", "--intervalle", "15", stdout=sortie)
        dormir.assert_called_once_with(15 * 60)
        self.assertIn("15 minutes", sortie.getvalue())
        self.assertIn("arrêtée", sortie.getvalue())
        self.assertIn("E-mails Airbnb", sortie.getvalue())


class ImapLectureSeuleTests(TestCase):
    def test_la_boite_est_ouverte_en_lecture_seule(self):
        brut = message_brut("Réservation confirmée", CONFIRMATION_FR, "<imap@exemple.test>")

        class FauxImap:
            def __init__(self):
                self.readonly = None
                self.methodes = []

            def login(self, utilisateur, mot_de_passe):
                self.methodes.append("login")
                return "OK", []

            def select(self, dossier, readonly=False):
                self.methodes.append("select")
                self.readonly = readonly
                return "OK", [b"1"]

            def search(self, charset, *criteres):
                self.methodes.append("search")
                return "OK", [b"1"]

            def fetch(self, numero, quoi):
                self.methodes.append(quoi)
                if "HEADER" in quoi:
                    entete = b"From: automated@airbnb.com\r\nMessage-ID: <imap@exemple.test>\r\n"
                    return "OK", [(b"1", entete)]
                return "OK", [(b"1", brut)]

            def store(self, *args):
                raise AssertionError("aucun message ne doit être modifié")

            def expunge(self):
                raise AssertionError("aucun message ne doit être supprimé")

            def logout(self):
                self.methodes.append("logout")
                return "OK", []

        faux = FauxImap()
        messages = lire_boite(
            {
                "hote": "imap.exemple.test",
                "port": 993,
                "utilisateur": "gloria@exemple.test",
                "mot_de_passe": "mot-de-passe-application",
                "dossier": "INBOX",
                "expediteurs": ["automated@airbnb.com"],
            },
            ouvrir=lambda config: faux,
        )
        self.assertTrue(faux.readonly)
        self.assertNotIn("store", faux.methodes)
        self.assertEqual(messages, [brut])


class StatutBlocageTests(APITestCase):
    def setUp(self):
        super().setUp()
        self.proprietaire = User.objects.create_user("proprietaire", password=MOT_DE_PASSE)
        self.client.force_login(self.proprietaire)
        self.logement = Logement.objects.create(
            nom="Studio",
            type=Logement.Type.STUDIO,
            pays="TG",
            ville="Lomé",
        )

    def test_un_blocage_du_jour_s_affiche_comme_indisponible(self):
        jour = timezone.localdate()
        synchroniser_logement(
            self.logement,
            contenu=flux_ical(
                [
                    {
                        "uid": "blocage-jour@airbnb.com",
                        "debut": jour,
                        "fin": jour + timedelta(days=2),
                        "summary": "Airbnb (Not available)",
                    }
                ]
            ),
        )
        carte = self.client.get("/api/logements/").data[0]["statut_du_jour"]
        self.assertEqual(carte["etat"], "blocage")
        self.assertEqual(carte["libelle"], "Indisponible · Airbnb")
        tableau = self.client.get("/api/tableau-de-bord/")
        self.assertIn("indisponible", tableau.data["phrase"])
        self.assertEqual(tableau.data["prochaines_arrivees"], [])
