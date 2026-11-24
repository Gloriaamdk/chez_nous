from django.contrib.auth.models import User
from rest_framework.test import APIClient, APITestCase

MOT_DE_PASSE = "mot-de-passe-solide"

LECTURES = [
    "/api/logements/",
    "/api/reservations/",
    "/api/paiements/",
    "/api/depenses/",
    "/api/referentiels/",
    "/api/disponibilites/?arrivee=2026-12-01&depart=2026-12-05",
    "/api/synthese/",
    "/api/rapports/",
    "/api/auth/moi/",
]


class AuthentificationAPITests(APITestCase):
    def setUp(self):
        super().setUp()
        self.proprietaire = User.objects.create_user(
            username="proprietaire",
            password=MOT_DE_PASSE,
            first_name="Ama",
            last_name="Koffi",
            is_staff=True,
        )

    def test_le_statut_reste_public(self):
        reponse = self.client.get("/api/status/")
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.data["status"], "ok")

    def test_les_donnees_sont_refusees_sans_connexion(self):
        for url in LECTURES:
            reponse = self.client.get(url)
            self.assertEqual(reponse.status_code, 401, url)
            self.assertEqual(reponse.data["detail"], "Connexion requise.")

    def test_ecriture_refusee_sans_connexion(self):
        for url in (
            "/api/logements/",
            "/api/reservations/",
            "/api/paiements/",
            "/api/depenses/",
            "/api/auth/deconnexion/",
        ):
            reponse = self.client.post(url, {}, format="json")
            self.assertEqual(reponse.status_code, 401, url)

        logement = self.client.patch("/api/logements/1/", {}, format="json")
        self.assertEqual(logement.status_code, 401)

    def test_une_session_autorise_la_lecture(self):
        self.client.login(username="proprietaire", password=MOT_DE_PASSE)
        for url in LECTURES:
            reponse = self.client.get(url)
            self.assertEqual(reponse.status_code, 200, url)

    def test_connexion_ouvre_la_session_et_moi_renvoie_le_profil(self):
        avant = self.client.get("/api/auth/moi/")
        self.assertEqual(avant.status_code, 401)

        reponse = self.client.post(
            "/api/auth/connexion/",
            {"identifiant": " proprietaire ", "mot_de_passe": MOT_DE_PASSE},
            format="json",
        )
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data["identifiant"], "proprietaire")
        self.assertEqual(reponse.data["prenom"], "Ama")
        self.assertEqual(reponse.data["nom"], "Koffi")
        self.assertTrue(reponse.data["est_admin"])

        moi = self.client.get("/api/auth/moi/")
        self.assertEqual(moi.status_code, 200)
        self.assertEqual(moi.data["identifiant"], "proprietaire")
        self.assertEqual(self.client.get("/api/logements/").status_code, 200)

    def test_identifiants_incorrects_ne_donnent_aucun_acces(self):
        reponse = self.client.post(
            "/api/auth/connexion/",
            {"identifiant": "proprietaire", "mot_de_passe": "faux-mot-de-passe"},
            format="json",
        )
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(reponse.data["detail"], "Identifiant ou mot de passe incorrect.")
        self.assertEqual(self.client.get("/api/logements/").status_code, 401)
        self.assertEqual(self.client.get("/api/auth/moi/").status_code, 401)

    def test_champs_vides(self):
        reponse = self.client.post(
            "/api/auth/connexion/",
            {"identifiant": "", "mot_de_passe": ""},
            format="json",
        )
        self.assertEqual(reponse.status_code, 400)
        self.assertIn("identifiant", reponse.data["detail"])

    def test_un_compte_cree_sans_etre_administrateur_peut_lire(self):
        User.objects.create_user(username="aide", password="autre-mot-de-passe")
        self.assertTrue(self.client.login(username="aide", password="autre-mot-de-passe"))
        moi = self.client.get("/api/auth/moi/")
        self.assertEqual(moi.status_code, 200)
        self.assertEqual(moi.data["identifiant"], "aide")
        self.assertFalse(moi.data["est_admin"])
        self.assertEqual(self.client.get("/api/reservations/").status_code, 200)
        self.assertEqual(self.client.get("/api/synthese/").status_code, 200)

    def test_deconnexion_ferme_la_session(self):
        self.client.login(username="proprietaire", password=MOT_DE_PASSE)
        self.assertEqual(self.client.get("/api/paiements/").status_code, 200)

        depart = self.client.post("/api/auth/deconnexion/", {}, format="json")
        self.assertEqual(depart.status_code, 200)

        self.assertEqual(self.client.get("/api/paiements/").status_code, 401)
        self.assertEqual(self.client.get("/api/auth/moi/").status_code, 401)
        self.assertEqual(self.client.get("/api/depenses/").status_code, 401)

    def test_la_connexion_exige_le_jeton_csrf_et_accepte_lorigine_vite(self):
        client = APIClient(enforce_csrf_checks=True)
        sans_jeton = client.post(
            "/api/auth/connexion/",
            {"identifiant": "proprietaire", "mot_de_passe": MOT_DE_PASSE},
            format="json",
            HTTP_ORIGIN="http://localhost:5173",
        )
        self.assertEqual(sans_jeton.status_code, 403)
        self.assertIn("expiré", sans_jeton.json()["detail"])

        jeton = client.get("/api/auth/csrf/")
        self.assertEqual(jeton.status_code, 200)
        self.assertTrue(jeton.data["csrfToken"])

        origine_inconnue = client.post(
            "/api/auth/connexion/",
            {"identifiant": "proprietaire", "mot_de_passe": MOT_DE_PASSE},
            format="json",
            HTTP_X_CSRFTOKEN=jeton.data["csrfToken"],
            HTTP_ORIGIN="http://evil.example",
        )
        self.assertEqual(origine_inconnue.status_code, 403)

        reponse = client.post(
            "/api/auth/connexion/",
            {"identifiant": "proprietaire", "mot_de_passe": MOT_DE_PASSE},
            format="json",
            HTTP_X_CSRFTOKEN=jeton.data["csrfToken"],
            HTTP_ORIGIN="http://127.0.0.1:5173",
        )
        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.assertEqual(client.get("/api/auth/moi/").status_code, 200)
