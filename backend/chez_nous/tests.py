from datetime import date

from rest_framework.test import APITestCase

from chez_nous.models import Logement


class LogementAPITests(APITestCase):
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


class SejourAPITests(APITestCase):
    def setUp(self):
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


class RapportAPITests(APITestCase):
    def setUp(self):
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
