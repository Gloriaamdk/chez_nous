# Application de gestion locative

## Objectif
Créer une application en français pour une propriétaire qui gère plusieurs
logements dans plusieurs villes et pays. Le studio et le chambre-salon sont
ses deux premiers logements. Elle peut en ajouter d’autres depuis son téléphone.
Elle loue à la nuitée et au mois. Ses réservations proviennent d’Airbnb, de
WhatsApp et du téléphone.

## Organisation du projet
- backend/ contient l’API en Python avec Django et Django REST Framework.
- frontend/ contient l’interface en React avec Vite.
- Django gère la base de données, les disponibilités et les calculs financiers.
- React affiche les données de l’API et les formulaires de saisie.
- Garder AGENTS.md à la racine du projet, à côté de backend/ et frontend/.

## Expérience utilisateur
- Concevoir les écrans en priorité pour le téléphone, en français et en FCFA.
- Faire du tableau de bord l’écran d’accueil.
- Pendant un appel, la propriétaire doit pouvoir choisir deux dates, voir quel
  logement est libre, confirmer le séjour et enregistrer l’acompte.
- Conserver les dates et le logement choisis quand elle passe du calendrier
  au formulaire de réservation.

## Fonctionnalités prévues
- Tableau de bord : ajouter et modifier les logements (nom, type, ville et pays),
  filtrer les cartes par pays, puis voir le statut de chaque logement, les
  prochaines arrivées et départs, les encaissements, les dépenses et les sommes
  restant à recevoir.
- Calendrier : afficher les logements et empêcher les doubles réservations.
  Un départ et une arrivée le même jour sont possibles pour un même logement.
- Réservations : gérer les séjours à la nuitée et au mois, le contact du client,
  le canal de réservation, les acomptes et les échéances mensuelles.
- Finances : distinguer le montant prévu du montant réellement encaissé.
  Rattacher chaque paiement à sa réservation et chaque dépense au logement concerné.
- Rapports : générer automatiquement un bilan hebdomadaire et mensuel avec
  l’occupation, les encaissements et les dépenses, par logement et au total.
  Permettre de comparer les résultats à la période précédente.
- Airbnb : prévoir la remontée automatique des réservations et la mise à jour
  des disponibilités après une réservation directe. Le partenaire reste à choisir.
  Afficher la date de la dernière synchronisation réussie.

## Méthode de travail
Avancer étape par étape. Après chaque étape, expliquer en français ce qui a été
créé, comment le vérifier sur Windows et quelle est la prochaine étape.
Mettre à jour la section Avancement après chaque vérification.

## Avancement
- Terminé : version de Python vérifiée sur le PC (Python 3.14.0).
- Terminé : backend Django initialisé et vérifié.
  - Environnement virtuel : `backend/.venv/`.
  - Django 5.2.19 et Django REST Framework 3.18.3, enregistrés dans `backend/requirements.txt`.
  - Projet : `backend/manage.py` et `backend/config/settings.py`.
  - `rest_framework` et `chez_nous` activés dans `INSTALLED_APPS`.
  - Base locale SQLite : `backend/db.sqlite3`.
  - Migrations appliquées : admin, auth, contenttypes, sessions.
- Terminé : structure de travail créée et vérifiée.
  - Application métier `backend/chez_nous/` : `apps.py`, `models.py`, `views.py`, `serializers.py`, `urls.py`, `admin.py`, `migrations/`.
  - `GET /api/status/` renvoie `{"status": "ok"}`.
  - Frontend React + Vite (Node.js 26.1.0, npm 12.0.2) dans `frontend/`.
  - Cinq pages en français, tableau de bord en premier, navigation en bas d’écran.
  - Le tableau de bord affiche la connexion : `Connexion établie : {"status":"ok"}`.
  - `manage.py check` : aucun problème (0 silenced).
  - `npm run build` : compilation réussie.
- Terminé : logements gérés depuis le téléphone, vérifié.
  - Modèle `Logement` : identifiant stable, nom, type, pays et ville.
  - Types : Studio, Chambre-salon, Appartement, Maison, Autre.
  - Pays proposés avec leurs libellés français.
  - API : lister, ajouter et modifier. Un logement incomplet affiche « Localisation à compléter ».
  - Tableau de bord : bouton « Ajouter un logement », cartes, modification et filtre « Tous les pays ».
  - Exemples de deux studios (France et Cameroun) créés seulement dans une base de test.
  - La base de travail `backend/db.sqlite3` ne contient aucun logement inventé.
- Terminé : réservations, paiements et dépenses, vérifiés.
  - Séjour à la nuitée ou au mois, avec client, téléphone et canal (Airbnb, WhatsApp, téléphone).
  - Un départ et une arrivée le même jour sont possibles ; un chevauchement est refusé.
  - Le calendrier garde les dates et le logement choisis pour le formulaire de réservation.
  - L’acompte est un encaissement. Le prévu, l’encaissé et le reste sont calculés par Django, en FCFA.
  - Une location au mois crée une échéance par mois. Une dépense est rattachée à un logement.
  - Essai dans le navigateur, puis effacé : la base de travail ne contient pas cet exemple.
- Prochaine étape : les rapports hebdomadaires et mensuels.