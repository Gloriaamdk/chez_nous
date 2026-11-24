from datetime import date, timedelta
from threading import Barrier, Lock, Thread
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import connections
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from chez_nous.models import Logement, NuitOccupee, Paiement, Reservation
from chez_nous.occupations import date_fr, libelle_jour


class APIAuthentifiee(APITestCase):
    def setUp(self):
        super().setUp()
        self.proprietaire = User.objects.create_user(
            username="proprietaire",
            password="mot-de-passe-solide",
        )
        self.client.force_login(self.proprietaire)


class LogementAPITests(APIAuthentifiee):
    def test_deux_studios_dans_des_pays_differents_restent_distincts(self):
        france = self.client.post(
            "/api/logements/",
            {"nom": "Studio", "type": "studio", "pays": "FR", "ville": "Lyon"},
            format="json",
        )
        cameroun = self.client.post(
            "/api/logements/",
            {"nom": "Studio", "type": "studio", "pays": "CM", "ville": "Douala"},
            format="json",
        )

        self.assertEqual(france.status_code, 201)
        self.assertEqual(cameroun.status_code, 201)
        self.assertNotEqual(france.data["id"], cameroun.data["id"])

        rechargement = self.client.get("/api/logements/")
        self.assertEqual(rechargement.status_code, 200)
        par_id = {logement["id"]: logement for logement in rechargement.data}
        self.assertEqual(par_id[france.data["id"]]["pays_libelle"], "France")
        self.assertEqual(par_id[cameroun.data["id"]]["pays_libelle"], "Cameroun")
        self.assertEqual(par_id[france.data["id"]]["ville"], "Lyon")
        self.assertEqual(par_id[cameroun.data["id"]]["ville"], "Douala")

        seulement_france = [
            logement for logement in rechargement.data if logement["pays"] == "FR"
        ]
        seulement_cameroun = [
            logement for logement in rechargement.data if logement["pays"] == "CM"
        ]
        self.assertEqual(len(seulement_france), 1)
        self.assertEqual(len(seulement_cameroun), 1)

    def test_nouveau_logement_exige_nom_type_pays_et_ville(self):
        reponse = self.client.post(
            "/api/logements/",
            {"nom": "Maison bleue", "type": "maison"},
            format="json",
        )
        self.assertEqual(reponse.status_code, 400)
        self.assertIn("pays", reponse.data)
        self.assertIn("ville", reponse.data)
        self.assertEqual(Logement.objects.count(), 0)

    def test_localisation_manquante_se_complete_sans_changer_l_identifiant(self):
        logement = Logement.objects.create(nom="Studio", type=Logement.Type.STUDIO)
        identifiant = str(logement.id)

        lecture = self.client.get(f"/api/logements/{identifiant}/")
        self.assertEqual(lecture.status_code, 200)
        self.assertTrue(lecture.data["localisation_a_completer"])
        self.assertEqual(lecture.data["pays"], "")
        self.assertEqual(lecture.data["ville"], "")

        mise_a_jour = self.client.patch(
            f"/api/logements/{identifiant}/",
            {"pays": "SN", "ville": "Dakar"},
            format="json",
        )
        self.assertEqual(mise_a_jour.status_code, 200)
        self.assertEqual(mise_a_jour.data["id"], identifiant)
        self.assertEqual(mise_a_jour.data["pays_libelle"], "Sénégal")
        self.assertFalse(mise_a_jour.data["localisation_a_completer"])

    def test_referentiels_proposent_les_types_et_les_pays_en_francais(self):
        reponse = self.client.get("/api/referentiels/")
        self.assertEqual(reponse.status_code, 200)
        libelles_types = {item["libelle"] for item in reponse.data["types"]}
        self.assertEqual(
            libelles_types,
            {"Studio", "Chambre-salon", "Appartement", "Maison", "Autre"},
        )
        pays = {item["code"]: item["libelle"] for item in reponse.data["pays"]}
        self.assertEqual(pays["FR"], "France")
        self.assertEqual(pays["CM"], "Cameroun")
        self.assertGreater(len(pays), 100)


class SejourAPITests(APIAuthentifiee):
    def setUp(self):
        super().setUp()
        self.logement = Logement.objects.create(
            nom="Studio",
            type=Logement.Type.STUDIO,
            pays="FR",
            ville="Lyon",
        )
        self.autre = Logement.objects.create(
            nom="Chambre-salon",
            type=Logement.Type.CHAMBRE_SALON,
            pays="CM",
            ville="Douala",
        )

    def reserver(self, **extra):
        donnees = {
            "logement": str(self.logement.id),
            "client_nom": "Awa",
            "client_telephone": "0600000000",
            "canal": "whatsapp",
            "mode": "nuitee",
            "date_arrivee": "2026-12-01",
            "date_depart": "2026-12-05",
            "montant_prevu": 40000,
            "acompte": 10000,
        }
        donnees.update(extra)
        return self.client.post("/api/reservations/", donnees, format="json")

    def test_nuitee_avec_acompte_distingue_prevu_et_encaisse(self):
        creation = self.reserver()
        self.assertEqual(creation.status_code, 201, creation.data)
        self.assertEqual(creation.data["montant_total_prevu"], 40000)
        self.assertEqual(creation.data["montant_encaisse"], 10000)
        self.assertEqual(creation.data["reste_a_recevoir"], 30000)
        self.assertEqual(len(creation.data["echeances"]), 1)

        relecture = self.client.get(f"/api/reservations/{creation.data['id']}/")
        self.assertEqual(relecture.data["reste_a_recevoir"], 30000)

        synthese = self.client.get("/api/synthese/")
        self.assertEqual(synthese.data["montant_prevu"], 40000)
        self.assertEqual(synthese.data["montant_encaisse"], 10000)
        self.assertEqual(synthese.data["reste_a_recevoir"], 30000)

    def test_le_meme_logement_refuse_un_chevauchement_mais_accepte_le_jour_du_depart(self):
        premiere = self.reserver(acompte=0)
        self.assertEqual(premiere.status_code, 201, premiere.data)

        conflit = self.reserver(
            date_arrivee="2026-12-04",
            date_depart="2026-12-08",
            acompte=0,
        )
        self.assertEqual(conflit.status_code, 400)

        enchainement = self.reserver(
            date_arrivee="2026-12-05",
            date_depart="2026-12-07",
            acompte=0,
        )
        self.assertEqual(enchainement.status_code, 201, enchainement.data)

        autre_logement = self.reserver(
            logement=str(self.autre.id),
            date_arrivee="2026-12-01",
            date_depart="2026-12-05",
            acompte=0,
        )
        self.assertEqual(autre_logement.status_code, 201, autre_logement.data)

    def test_disponibilites_et_sejour_au_mois(self):
        self.reserver(acompte=0)
        libre = self.client.get(
            "/api/disponibilites/",
            {"arrivee": "2026-12-02", "depart": "2026-12-04"},
        )
        self.assertEqual(libre.status_code, 200)
        par_nom = {item["nom"]: item["libre"] for item in libre.data["logements"]}
        self.assertFalse(par_nom["Studio"])
        self.assertTrue(par_nom["Chambre-salon"])

        mois = self.reserver(
            logement=str(self.autre.id),
            mode="mois",
            date_arrivee="2026-01-15",
            date_depart="2026-04-15",
            montant_prevu=150000,
            acompte=50000,
        )
        self.assertEqual(mois.status_code, 201, mois.data)
        self.assertEqual(len(mois.data["echeances"]), 3)
        self.assertEqual(
            [echeance["date"] for echeance in mois.data["echeances"]],
            ["2026-01-15", "2026-02-15", "2026-03-15"],
        )
        self.assertEqual(mois.data["montant_total_prevu"], 450000)
        self.assertEqual(mois.data["montant_encaisse"], 50000)
        self.assertEqual(mois.data["reste_a_recevoir"], 400000)

    def test_depense_rattachee_au_logement_et_paiement_a_la_reservation(self):
        reservation = self.reserver(acompte=0)
        paiement = self.client.post(
            "/api/paiements/",
            {
                "reservation": reservation.data["id"],
                "montant": 15000,
                "date": "2026-12-02",
                "nature": "echeance",
            },
            format="json",
        )
        self.assertEqual(paiement.status_code, 201, paiement.data)
        self.assertEqual(paiement.data["logement_nom"], "Studio")

        depense = self.client.post(
            "/api/depenses/",
            {
                "logement": str(self.logement.id),
                "libelle": "Eau",
                "montant": 8000,
                "date": "2026-12-03",
            },
            format="json",
        )
        self.assertEqual(depense.status_code, 201, depense.data)
        synthese = self.client.get("/api/synthese/")
        self.assertEqual(synthese.data["depenses"], 8000)
        self.assertEqual(synthese.data["montant_encaisse"], 15000)
        self.assertEqual(date.fromisoformat(paiement.data["date"]), date(2026, 12, 2))


class RapportAPITests(APIAuthentifiee):
    def setUp(self):
        super().setUp()
        self.logement = Logement.objects.create(
            nom="Studio",
            type=Logement.Type.STUDIO,
            pays="FR",
            ville="Lyon",
        )
        self.autre = Logement.objects.create(
            nom="Chambre-salon",
            type=Logement.Type.CHAMBRE_SALON,
            pays="CM",
            ville="Douala",
        )

    def test_bilan_mensuel_compare_la_periode_precedente(self):
        from chez_nous.models import Depense, Paiement, Reservation

        studio = Reservation.objects.create(
            logement=self.logement,
            client_nom="Awa",
            client_telephone="0600000000",
            canal="whatsapp",
            mode="nuitee",
            date_arrivee=date(2026, 12, 10),
            date_depart=date(2026, 12, 14),
            montant_prevu=40000,
        )
        studio.generer_echeances()
        Paiement.objects.create(
            reservation=studio,
            montant=10000,
            date=date(2026, 12, 11),
            nature="acompte",
        )
        Paiement.objects.create(
            reservation=studio,
            montant=5000,
            date=date(2026, 11, 20),
            nature="acompte",
        )
        Depense.objects.create(
            logement=self.logement,
            libelle="Eau",
            montant=8000,
            date=date(2026, 12, 12),
        )
        Depense.objects.create(
            logement=self.autre,
            libelle="Peinture",
            montant=2000,
            date=date(2026, 11, 2),
        )

        reponse = self.client.get("/api/rapports/", {"periode": "mois", "date": "2026-12-18"})
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.data["libelle"], "décembre 2026")
        self.assertEqual(reponse.data["precedente"]["libelle"], "novembre 2026")
        self.assertEqual(reponse.data["total"]["nuits_occupees"], 4)
        self.assertEqual(reponse.data["total"]["encaissements"], 10000)
        self.assertEqual(reponse.data["total"]["depenses"], 8000)
        self.assertEqual(reponse.data["total"]["precedent"]["encaissements"], 5000)
        self.assertEqual(reponse.data["total"]["precedent"]["depenses"], 2000)
        self.assertEqual(reponse.data["total"]["ecart"]["encaissements"], 5000)

        par_nom = {ligne["nom"]: ligne for ligne in reponse.data["logements"]}
        self.assertEqual(par_nom["Studio"]["nuits_occupees"], 4)
        self.assertEqual(par_nom["Studio"]["encaissements"], 10000)
        self.assertEqual(par_nom["Chambre-salon"]["nuits_occupees"], 0)
        self.assertEqual(par_nom["Chambre-salon"]["precedent"]["depenses"], 2000)

        semaine = self.client.get("/api/rapports/", {"periode": "semaine", "date": "2026-12-10"})
        self.assertEqual(semaine.status_code, 200)
        self.assertEqual(semaine.data["debut"], date(2026, 12, 7))
        self.assertEqual(semaine.data["fin"], date(2026, 12, 14))
        self.assertEqual(semaine.data["total"]["nuits_occupees"], 4)
        self.assertEqual(semaine.data["total"]["encaissements"], 10000)

    def test_une_reservation_annulee_libere_les_nuits_mais_garde_l_encaissement(self):
        studio = Reservation.objects.create(
            logement=self.logement,
            client_nom="Awa",
            client_telephone="0600000000",
            canal="whatsapp",
            mode="nuitee",
            date_arrivee=date(2026, 12, 10),
            date_depart=date(2026, 12, 14),
            montant_prevu=40000,
        )
        studio.generer_echeances()
        Paiement.objects.create(
            reservation=studio,
            montant=10000,
            date=date(2026, 12, 11),
            nature="acompte",
        )

        annulation = self.client.post(f"/api/reservations/{studio.id}/annuler/", {}, format="json")
        self.assertEqual(annulation.status_code, 200, annulation.data)
        self.assertTrue(annulation.data["annulee"])

        reponse = self.client.get("/api/rapports/", {"periode": "mois", "date": "2026-12-18"})
        self.assertEqual(reponse.data["total"]["nuits_occupees"], 0)
        self.assertEqual(reponse.data["total"]["encaissements"], 10000)


class ReservationModificationTests(APIAuthentifiee):
    def setUp(self):
        super().setUp()
        self.logement = Logement.objects.create(
            nom="Studio",
            type=Logement.Type.STUDIO,
            pays="FR",
            ville="Lyon",
        )
        self.autre = Logement.objects.create(
            nom="Chambre-salon",
            type=Logement.Type.CHAMBRE_SALON,
            pays="CM",
            ville="Douala",
        )

    def reserver(self, **extra):
        donnees = {
            "logement": str(self.logement.id),
            "client_nom": "Awa",
            "client_telephone": "0600000000",
            "canal": "whatsapp",
            "mode": "nuitee",
            "date_arrivee": "2026-12-01",
            "date_depart": "2026-12-05",
            "montant_prevu": 40000,
            "acompte": 10000,
        }
        donnees.update(extra)
        return self.client.post("/api/reservations/", donnees, format="json")

    def test_modifier_conserve_les_paiements_quand_les_echeances_changent(self):
        creation = self.reserver()
        self.assertEqual(creation.status_code, 201, creation.data)
        ancienne_echeance = creation.data["echeances"][0]["id"]
        acompte = self.client.get("/api/paiements/").data[0]
        supplement = self.client.post(
            "/api/paiements/",
            {
                "reservation": creation.data["id"],
                "montant": 15000,
                "date": "2026-12-02",
                "nature": "echeance",
            },
            format="json",
        )
        self.assertEqual(supplement.status_code, 201, supplement.data)

        modification = self.client.patch(
            f"/api/reservations/{creation.data['id']}/",
            {
                "client_nom": "Awa Diallo",
                "date_arrivee": "2026-12-02",
                "date_depart": "2026-12-06",
                "montant_prevu": 45000,
            },
            format="json",
        )
        self.assertEqual(modification.status_code, 200, modification.data)
        self.assertEqual(modification.data["client_nom"], "Awa Diallo")
        self.assertEqual(modification.data["montant_total_prevu"], 45000)
        self.assertEqual(modification.data["montant_encaisse"], 25000)
        self.assertEqual(modification.data["reste_a_recevoir"], 20000)
        self.assertEqual(modification.data["echeances"][0]["montant"], 45000)
        self.assertNotEqual(modification.data["echeances"][0]["id"], ancienne_echeance)

        paiements = self.client.get("/api/paiements/").data
        self.assertEqual(
            sorted(paiement["id"] for paiement in paiements),
            sorted([acompte["id"], supplement.data["id"]]),
        )
        self.assertEqual(sum(paiement["montant"] for paiement in paiements), 25000)
        self.assertEqual(
            list(
                NuitOccupee.objects.filter(reservation_id=creation.data["id"])
                .order_by("date")
                .values_list("date", flat=True)
            ),
            [date(2026, 12, 2), date(2026, 12, 3), date(2026, 12, 4), date(2026, 12, 5)],
        )

    def test_un_changement_de_contact_ne_recrée_pas_les_echeances(self):
        creation = self.reserver()
        echeance_id = creation.data["echeances"][0]["id"]
        paiement_id = self.client.get("/api/paiements/").data[0]["id"]

        modification = self.client.patch(
            f"/api/reservations/{creation.data['id']}/",
            {"client_telephone": "0700000000"},
            format="json",
        )
        self.assertEqual(modification.status_code, 200, modification.data)
        self.assertEqual(modification.data["client_telephone"], "0700000000")
        self.assertEqual(modification.data["echeances"][0]["id"], echeance_id)
        self.assertEqual(self.client.get("/api/paiements/").data[0]["id"], paiement_id)
        self.assertEqual(modification.data["montant_encaisse"], 10000)

    def test_une_modification_en_conflit_laisse_le_sejour_et_les_paiements_intacts(self):
        premiere = self.reserver()
        seconde = self.reserver(
            client_nom="Koffi",
            date_arrivee="2026-12-10",
            date_depart="2026-12-12",
            acompte=0,
        )
        self.assertEqual(seconde.status_code, 201, seconde.data)

        conflit = self.client.patch(
            f"/api/reservations/{seconde.data['id']}/",
            {"date_arrivee": "2026-12-04", "date_depart": "2026-12-08"},
            format="json",
        )
        self.assertEqual(conflit.status_code, 400)

        relu = self.client.get(f"/api/reservations/{seconde.data['id']}/")
        self.assertEqual(relu.data["date_arrivee"], "2026-12-10")
        self.assertEqual(relu.data["date_depart"], "2026-12-12")
        self.assertEqual(relu.data["client_nom"], "Koffi")
        self.assertEqual(
            list(
                NuitOccupee.objects.filter(reservation_id=seconde.data["id"])
                .order_by("date")
                .values_list("date", flat=True)
            ),
            [date(2026, 12, 10), date(2026, 12, 11)],
        )
        self.assertEqual(Paiement.objects.filter(reservation_id=premiere.data["id"]).count(), 1)

        enchainement = self.client.patch(
            f"/api/reservations/{seconde.data['id']}/",
            {"date_arrivee": "2026-12-05", "date_depart": "2026-12-08"},
            format="json",
        )
        self.assertEqual(enchainement.status_code, 200, enchainement.data)
        self.assertEqual(
            list(
                NuitOccupee.objects.filter(reservation_id=seconde.data["id"])
                .order_by("date")
                .values_list("date", flat=True)
            ),
            [date(2026, 12, 5), date(2026, 12, 6), date(2026, 12, 7)],
        )

    def test_annuler_garde_l_historique_libere_les_dates_et_retire_le_prevu(self):
        creation = self.reserver()
        identifiant = creation.data["id"]
        self.assertEqual(NuitOccupee.objects.filter(reservation_id=identifiant).count(), 4)

        occupe = self.client.get(
            "/api/disponibilites/",
            {"arrivee": "2026-12-01", "depart": "2026-12-05"},
        )
        par_nom = {item["nom"]: item["libre"] for item in occupe.data["logements"]}
        self.assertFalse(par_nom["Studio"])

        annulation = self.client.post(f"/api/reservations/{identifiant}/annuler/", {}, format="json")
        self.assertEqual(annulation.status_code, 200, annulation.data)
        self.assertTrue(annulation.data["annulee"])
        self.assertEqual(annulation.data["annulee_le"], timezone.localdate().isoformat())
        self.assertEqual(annulation.data["montant_total_prevu"], 0)
        self.assertEqual(annulation.data["montant_encaisse"], 10000)
        self.assertEqual(annulation.data["reste_a_recevoir"], 0)
        self.assertEqual(len(annulation.data["echeances"]), 1)
        self.assertEqual(NuitOccupee.objects.filter(reservation_id=identifiant).count(), 0)

        libre = self.client.get(
            "/api/disponibilites/",
            {"arrivee": "2026-12-01", "depart": "2026-12-05"},
        )
        par_nom = {item["nom"]: item["libre"] for item in libre.data["logements"]}
        self.assertTrue(par_nom["Studio"])

        synthese = self.client.get("/api/synthese/")
        self.assertEqual(synthese.data["montant_prevu"], 0)
        self.assertEqual(synthese.data["montant_encaisse"], 0)
        self.assertEqual(synthese.data["reste_a_recevoir"], 0)
        self.assertEqual(synthese.data["montant_encaisse_annule"], 10000)

        suite = self.reserver(client_nom="Koffi", acompte=0)
        self.assertEqual(suite.status_code, 201, suite.data)

        paiement = self.client.post(
            "/api/paiements/",
            {
                "reservation": identifiant,
                "montant": 5000,
                "date": "2026-12-02",
                "nature": "autre",
            },
            format="json",
        )
        self.assertEqual(paiement.status_code, 400)

        historique = self.client.get("/api/reservations/")
        annulee = next(item for item in historique.data if item["id"] == identifiant)
        self.assertTrue(annulee["annulee"])
        self.assertEqual(annulee["montant_encaisse"], 10000)
        self.assertEqual(Paiement.objects.filter(reservation_id=identifiant).count(), 1)

        reservation = Reservation.objects.get(pk=identifiant)
        reservation.annulee_le = date(2020, 1, 1)
        reservation.save(update_fields=["annulee_le"])
        encore = self.client.post(f"/api/reservations/{identifiant}/annuler/", {}, format="json")
        self.assertEqual(encore.status_code, 200, encore.data)
        self.assertEqual(encore.data["annulee_le"], "2020-01-01")

        modification = self.client.patch(
            f"/api/reservations/{identifiant}/",
            {"client_nom": "Autre"},
            format="json",
        )
        self.assertEqual(modification.status_code, 400)

    def test_la_base_refuse_deux_nuits_meme_si_le_controle_applicatif_est_contourne(self):
        premiere = self.reserver(acompte=0)
        self.assertEqual(premiere.status_code, 201, premiere.data)

        with (
            patch("chez_nous.serializers.nuits_prises", return_value=False),
            patch("chez_nous.models.nuits_prises", return_value=False),
        ):
            conflit = self.reserver(
                date_arrivee="2026-12-03",
                date_depart="2026-12-06",
                acompte=0,
            )
        self.assertEqual(conflit.status_code, 400, conflit.data)
        self.assertEqual(Reservation.objects.count(), 1)
        self.assertEqual(NuitOccupee.objects.count(), 4)

    def test_le_modele_refuse_un_chevauchement_sans_passer_par_le_serializer(self):
        self.reserver(acompte=0)
        with self.assertRaises(ValidationError):
            Reservation.objects.create(
                logement=self.logement,
                client_nom="Koffi",
                client_telephone="0600000000",
                canal="telephone",
                mode="nuitee",
                date_arrivee=date(2026, 12, 4),
                date_depart=date(2026, 12, 8),
                montant_prevu=20000,
            )
        self.assertEqual(Reservation.objects.count(), 1)


class TableauDeBordAPITests(APIAuthentifiee):
    def setUp(self):
        super().setUp()
        self.jour = timezone.localdate()
        self.studio = Logement.objects.create(
            nom="Studio",
            type=Logement.Type.STUDIO,
            pays="FR",
            ville="Lyon",
        )
        self.salon = Logement.objects.create(
            nom="Chambre-salon",
            type=Logement.Type.CHAMBRE_SALON,
            pays="CM",
            ville="Douala",
        )
        self.maison = Logement.objects.create(
            nom="Maison",
            type=Logement.Type.MAISON,
            pays="SN",
            ville="Dakar",
        )
        self.libre = Logement.objects.create(
            nom="Appartement",
            type=Logement.Type.APPARTEMENT,
            pays="FR",
            ville="Lille",
        )

    def reserver(self, logement, client, arrivee, depart):
        reponse = self.client.post(
            "/api/reservations/",
            {
                "logement": str(logement.id),
                "client_nom": client,
                "client_telephone": "0600000000",
                "canal": "telephone",
                "mode": "nuitee",
                "date_arrivee": arrivee.isoformat(),
                "date_depart": depart.isoformat(),
                "montant_prevu": 30000,
                "acompte": 0,
            },
            format="json",
        )
        self.assertEqual(reponse.status_code, 201, reponse.data)
        return reponse

    def test_chaque_carte_affiche_le_statut_calcule_par_django(self):
        self.reserver(self.studio, "Awa", self.jour - timedelta(days=2), self.jour + timedelta(days=3))
        self.reserver(self.salon, "Koffi", self.jour, self.jour + timedelta(days=2))
        self.reserver(self.maison, "Binta", self.jour - timedelta(days=3), self.jour)
        self.reserver(
            self.studio,
            "Plus tard",
            self.jour + timedelta(days=10),
            self.jour + timedelta(days=12),
        )

        cartes = {item["nom"]: item["statut_du_jour"] for item in self.client.get("/api/logements/").data}
        self.assertEqual(
            cartes["Studio"]["libelle"],
            f"Occupé · Awa · départ le {date_fr(self.jour + timedelta(days=3))}",
        )
        self.assertEqual(cartes["Studio"]["etat"], "occupe")
        self.assertEqual(cartes["Studio"]["client_nom"], "Awa")
        self.assertEqual(
            cartes["Chambre-salon"]["libelle"],
            f"Arrivée aujourd’hui · Koffi · départ le {date_fr(self.jour + timedelta(days=2))}",
        )
        self.assertEqual(cartes["Chambre-salon"]["etat"], "arrivee")
        self.assertEqual(cartes["Maison"]["libelle"], "Départ aujourd’hui · Binta")
        self.assertEqual(cartes["Maison"]["etat"], "depart")
        self.assertEqual(cartes["Appartement"], {"etat": "libre", "libelle": "Libre", "client_nom": "", "date_depart": None, "date_depart_libelle": "", "client_depart": ""})

        annulation = self.client.post(
            f"/api/reservations/{Reservation.objects.get(client_nom='Awa').id}/annuler/",
            {},
            format="json",
        )
        self.assertEqual(annulation.status_code, 200, annulation.data)
        studio = next(
            item["statut_du_jour"]
            for item in self.client.get("/api/logements/").data
            if item["nom"] == "Studio"
        )
        self.assertEqual(studio["etat"], "libre")

    def test_le_resume_annonce_les_mouvements_et_les_montants(self):
        self.reserver(self.studio, "Awa", self.jour - timedelta(days=1), self.jour + timedelta(days=2))
        self.client.post(
            "/api/depenses/",
            {
                "logement": str(self.studio.id),
                "libelle": "Eau",
                "montant": 8000,
                "date": self.jour.isoformat(),
            },
            format="json",
        )
        tableau = self.client.get("/api/tableau-de-bord/")
        self.assertEqual(tableau.status_code, 200, tableau.data)
        self.assertEqual(tableau.data["date"], self.jour.isoformat())
        self.assertEqual(tableau.data["libelle_date"], libelle_jour(self.jour))
        self.assertEqual(tableau.data["logements_occupes"], 1)
        self.assertEqual(tableau.data["logements_libres"], 3)
        self.assertEqual(tableau.data["phrase"], "Aujourd’hui : 3 logements libres, 1 occupé.")
        self.assertEqual(tableau.data["depenses"], 8000)
        self.assertEqual(tableau.data["montant_prevu"], 30000)
        self.assertEqual(tableau.data["prochaines_arrivees"], [])
        self.assertEqual(tableau.data["departs_aujourdhui"], [])
        self.assertEqual(len(tableau.data["prochains_departs"]), 1)
        self.assertEqual(tableau.data["prochains_departs"][0]["client_nom"], "Awa")

    def test_une_rotation_le_meme_jour_est_un_depart_puis_une_arrivee(self):
        self.reserver(self.studio, "Awa", self.jour - timedelta(days=2), self.jour)
        self.reserver(self.studio, "Koffi", self.jour, self.jour + timedelta(days=3))
        statut = next(
            item["statut_du_jour"]
            for item in self.client.get("/api/logements/").data
            if item["nom"] == "Studio"
        )
        self.assertEqual(statut["etat"], "rotation")
        self.assertEqual(statut["client_nom"], "Koffi")
        self.assertEqual(statut["client_depart"], "Awa")
        self.assertIn("Départ de Awa et arrivée de Koffi", statut["libelle"])
        self.assertIn(date_fr(self.jour + timedelta(days=3)), statut["libelle"])

        tableau = self.client.get("/api/tableau-de-bord/")
        self.assertEqual(tableau.data["phrase"], "Aujourd’hui : 3 logements libres, 1 arrivée, 1 départ.")
        self.assertEqual(tableau.data["logements_occupes"], 1)
        self.assertEqual(tableau.data["logements_libres"], 3)
        self.assertEqual(tableau.data["arrivees_aujourdhui"][0]["client_nom"], "Koffi")
        self.assertEqual(tableau.data["departs_aujourdhui"][0]["client_nom"], "Awa")


class ChevauchementConcurrentTests(TransactionTestCase):
    def test_deux_creations_simultanees_ne_reservent_qu_une_fois(self):
        proprietaire = User.objects.create_user(
            username="proprietaire",
            password="mot-de-passe-solide",
        )
        logement = Logement.objects.create(
            nom="Studio",
            type=Logement.Type.STUDIO,
            pays="FR",
            ville="Lyon",
        )
        clients = []
        for _ in range(2):
            client = APIClient()
            client.force_login(proprietaire)
            clients.append(client)
        connections.close_all()

        barriere = Barrier(2)
        resultats = []
        verrou = Lock()

        def creer(client):
            barriere.wait(timeout=10)
            try:
                reponse = client.post(
                    "/api/reservations/",
                    {
                        "logement": str(logement.id),
                        "client_nom": "Awa",
                        "client_telephone": "0600000000",
                        "canal": "whatsapp",
                        "mode": "nuitee",
                        "date_arrivee": "2026-12-01",
                        "date_depart": "2026-12-05",
                        "montant_prevu": 40000,
                        "acompte": 0,
                    },
                    format="json",
                )
                with verrou:
                    resultats.append(reponse.status_code)
            finally:
                connections.close_all()

        fils = [Thread(target=creer, args=(client,)) for client in clients]
        for fil in fils:
            fil.start()
        for fil in fils:
            fil.join(timeout=20)

        self.assertTrue(all(not fil.is_alive() for fil in fils))
        self.assertEqual(sorted(resultats), [201, 400])
        self.assertEqual(Reservation.objects.count(), 1)
        self.assertEqual(
            list(NuitOccupee.objects.order_by("date").values_list("date", flat=True)),
            [date(2026, 12, 1), date(2026, 12, 2), date(2026, 12, 3), date(2026, 12, 4)],
        )
