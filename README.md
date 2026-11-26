# Chez nous

Application de gestion locative, en français et en FCFA. Le backend Django est dans `backend/`. L'interface React est dans `frontend/`.

## Clé secrète compromise

La clé Django était écrite dans `backend/config/settings.py` (elle commençait par `django-insecure-`) et a été publiée avec le dépôt. Elle est compromise. Ne la réutilisez pas.

Créez un fichier `backend/.env`, qui n'est pas versionné, et mettez-y une clé neuve. Tant que `SECRET_KEY` est vide, Django démarre avec une clé temporaire qui change à chaque lancement : les sessions ne sont alors pas stables.

## Installation du backend

Sur Windows, à la racine du projet :

```bat
cd backend
py -3 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
copy .env.example .env
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Collez la clé affichée dans `backend/.env`, entre les guillemets de `SECRET_KEY=""`.

Puis :

```bat
python manage.py migrate
python manage.py runserver
```

L'API écoute sur http://127.0.0.1:8000 . http://127.0.0.1:8000/api/status/ renvoie `{"status": "ok"}`. Cette adresse de contrôle reste publique. Tout le reste (logements, réservations, paiements, dépenses, rapports) exige une connexion.

Si l'environnement virtuel existe déjà, activez-le et relancez `python -m pip install -r requirements.txt`. Cela installe les nouveautés, dont `django-environ` et `icalendar`. Puis :

```bat
python manage.py migrate
```

`SECRET_KEY`, `DEBUG` et `ALLOWED_HOSTS` sont lus dans `backend/.env`. Sans variable `DEBUG`, le mode débogage est désactivé. Le fichier d'exemple le laisse activé en local, comme auparavant, et autorise `localhost`, `127.0.0.1` et `[::1]`.

Gardez `DEBUG=True` sur le PC. Si vous le passez à `False` alors que le site est encore en `http`, le navigateur n'enregistre pas le cookie de session et la connexion échoue. Renseignez aussi `SECRET_KEY` : sans clé stable, la session est perdue à chaque redémarrage de Django.

## Compte de la propriétaire

Toujours dans `backend`, avec l'environnement virtuel activé et les migrations appliquées :

```bat
python manage.py createsuperuser
```

Django demande, en français :

1. le nom d'utilisateur (c'est l'identifiant de connexion) ;
2. l'adresse e-mail, qui peut rester vide ;
3. le mot de passe, deux fois. Il doit être assez long et ne pas ressembler à un mot trop courant.

Ouvrez ensuite l'interface (voir ci-dessous) et connectez-vous avec ces identifiants. Le bouton « Se déconnecter » est en haut de l'écran. Si la session expire, l'écran de connexion revient.

Les écrans sont : Accueil, Réservations, Logements, Argent, et Plus. Le calendrier (pour un appel) et les rapports sont dans Plus. Sur un ordinateur, ce menu est à gauche. Sur le téléphone, il est en bas.

Pour un autre compte (une personne de confiance), connectez-vous à http://127.0.0.1:8000/admin/ avec le compte créé ci-dessus, puis ajoutez un utilisateur. Cochez « Statut équipe » seulement si cette personne doit aussi ouvrir l'administration. Tout compte actif peut utiliser l'application. Il n'y a pas de mot de passe par défaut : sans compte, personne ne voit les noms, les téléphones ni les montants.

## Lancement du frontend

Dans un autre terminal, à la racine du projet :

```bat
cd frontend
npm install
npm run dev
```

Vite sert l'interface, en général sur http://localhost:5173 . Ouvrez cette adresse dans le navigateur, y compris sur le téléphone : c'est elle qui envoie le cookie de connexion. Le proxy défini dans `frontend/vite.config.js` transmet les adresses qui commencent par `/api` vers Django sur http://127.0.0.1:8000 . Lancez le backend avant d'utiliser l'interface.

Cette étape visuelle n'ajoute aucun paquet npm. Les polices sont déjà dans `frontend/src/fonts/`. Si `frontend/node_modules` existe, relancez seulement `npm run dev`. Sinon, faites `npm install` une fois, puis `npm run dev`.

## Sur le téléphone

Dans Safari (iPhone) ou Chrome (Android), ouvrez le site puis « Ajouter à l'écran d'accueil » (ou « Sur l'écran d'accueil »). Le nom affiché est « Chez Nous », avec le logo. Il n'y a rien à installer depuis un magasin d'applications, et pas de service en arrière-plan : l'icône ouvre simplement le site.

Si Vite n'utilise pas le port 5173, ou si le téléphone ouvre une adresse du type `http://192.168.1.12:5173`, ajoutez cette origine dans `backend/.env` (sans espace après les virgules), puis relancez Django :

```
CSRF_TRUSTED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://192.168.1.12:5173
```

## Calendriers Airbnb

Airbnb n’ouvre pas d’API aux petits hôtes. On utilise les liens de calendrier `.ics`, dans les deux sens. Rien à ressaisir : la commande automatique et les e-mails s’en chargent.

### Recevoir les séjours Airbnb dans Chez Nous

1. Sur Airbnb, ouvrez le calendrier du logement, puis Disponibilité, puis **Exporter le calendrier**.
2. Copiez le lien (il commence par `https://www.airbnb.com/`).
3. Dans Chez Nous, ouvrez le logement, collez ce lien dans « Lien d’export Airbnb », et enregistrez.
4. Indiquez aussi le **nom de l’annonce**, exactement comme dans les e-mails Airbnb (par exemple `Studio Lomé`). C’est ce qui rattache le bon message au bon logement.
5. Appuyez sur **Synchroniser maintenant**, ou laissez la commande automatique le faire.

Chaque séjour arrive avec le nom « Client Airbnb » et un téléphone « À compléter ». Le blocage « Not available » occupe les dates, sans montant à recevoir. Si ces dates sont déjà prises chez vous (WhatsApp ou téléphone), la synchro ne plante pas : elle affiche le conflit, sur l’écran et dans la commande. L’argent déjà encaissé n’est pas effacé.

### Bloquer ces dates sur Airbnb

1. Dans la fiche du logement, copiez « Lien à coller dans Airbnb ».
2. Sur Airbnb : Calendrier, Disponibilité, **Importer un calendrier**, collez le lien.
3. Airbnb bloque alors les nuits déjà réservées par WhatsApp ou par téléphone. Le fichier ne contient aucun nom ni téléphone, seulement « Réservé ».

Ce lien contient un jeton secret. Le bouton **Nouveau lien** l’invalide : il faudra alors recoller le nouveau dans Airbnb.

Airbnb ne peut lire ce lien que si Chez Nous est joignable sur internet. Tant que l’application n’est que sur le PC, l’import (Airbnb vers Chez Nous) fonctionne ; l’export (Chez Nous vers Airbnb) attend une adresse publique.

### Lancer la synchronisation toute seule

Une seule commande lit les calendriers **et** les e-mails, puis recommence. L’intervalle est entre 15 et 30 minutes. 20 est un bon choix : assez souvent pour un appel, sans interroger Airbnb en permanence.

Dans `backend`, environnement virtuel activé :

```bat
python manage.py synchro_airbnb --boucle --intervalle 20
```

Laissez cette fenêtre ouverte. `Ctrl+C` arrête. Pour un seul passage : `python manage.py synchro_airbnb`. Pour ne lire que les e-mails : `python manage.py lire_emails_airbnb`.

Pourquoi une boucle, et pas seulement une tâche planifiée : c’est la même commande sur Windows et sur un serveur, elle fait les calendriers et les e-mails ensemble, et on voit le résultat dans la fenêtre. Aucun service supplémentaire à installer.

Pour qu’elle démarre avec Windows, créez une tâche planifiée :

1. Ouvrez le menu Démarrer, cherchez **Planificateur de tâches**, puis **Créer une tâche**.
2. Déclencheur : **À l’ouverture de session**.
3. Action : **Démarrer un programme**.
4. Programme : le `python.exe` de l’environnement virtuel, par exemple `C:\chemin\chez_nous\backend\.venv\Scripts\python.exe`.
5. Arguments : `manage.py synchro_airbnb --boucle --intervalle 20`.
6. « Commencer dans » : le dossier `backend`, par exemple `C:\chemin\chez_nous\backend`.

Autre possibilité, sans fenêtre ouverte : une tâche qui se répète toutes les 20 minutes, avec les arguments `manage.py synchro_airbnb` (sans `--boucle`).

Sur un serveur Linux, la même boucle, ou une ligne cron :

```cron
*/20 * * * * cd /chemin/chez_nous/backend && .venv/bin/python manage.py synchro_airbnb
```

### E-mails de confirmation

Les e-mails remplissent le nom du voyageur, le nombre de voyageurs, le code (par exemple `HMTEST01`) et le versement. Le versement est enregistré comme **montant prévu**, pas comme argent déjà encaissé : quand l’argent arrive vraiment, enregistrez l’encaissement comme d’habitude. Si un champ manque dans le message, il reste à compléter et le reste continue. Une annulation libère les dates et garde l’historique, y compris un encaissement déjà saisi.

La boîte est lue seule : aucun e-mail n’est supprimé. Seuls les champs utiles sont gardés, pas le texte complet du message. Le format des e-mails Airbnb change parfois : si un vrai message n’est plus reconnu, le parseur (`backend/chez_nous/emails_airbnb.py`) sera à ajuster avec ce message.

Dans `backend/.env` :

```text
AIRBNB_IMAP_HOTE=imap.gmail.com
AIRBNB_IMAP_PORT=993
AIRBNB_IMAP_UTILISATEUR=gloria@gmail.com
AIRBNB_IMAP_MOT_DE_PASSE=le-mot-de-passe-application
AIRBNB_IMAP_DOSSIER=INBOX
AIRBNB_IMAP_EXPEDITEURS=automated@airbnb.com,express@airbnb.com
```

Pour Outlook, l’hôte est souvent `outlook.office365.com`, le port `993`, et l’utilisateur est l’adresse Outlook complète. Le mot de passe normal du compte ne convient pas.

#### Mot de passe d’application Gmail

1. Ouvrez [https://myaccount.google.com/security](https://myaccount.google.com/security).
2. Activez la **validation en deux étapes** si ce n’est pas déjà fait.
3. Cherchez **Mots de passe des applications** (parfois dans la recherche du compte Google).
4. Créez un mot de passe nommé `Chez Nous`.
5. Google affiche 16 lettres. Copiez-les dans `AIRBNB_IMAP_MOT_DE_PASSE`, sans espaces.
6. `AIRBNB_IMAP_HOTE` vaut `imap.gmail.com`, l’utilisateur est l’adresse Gmail complète.

#### Mot de passe d’application Outlook

1. Ouvrez [https://account.microsoft.com/security](https://account.microsoft.com/security).
2. Activez la **validation en deux étapes**.
3. Ouvrez **Mot de passe d’application** et créez-en un pour `Chez Nous`.
4. Collez-le dans `AIRBNB_IMAP_MOT_DE_PASSE`.
5. Hôte : `outlook.office365.com`. Utilisateur : l’adresse Outlook complète.

Relancez Django après avoir enregistré `.env`. Le tableau de bord affiche le résultat de la dernière lecture (« 1 créée, 1 complétée… »).

## Tests

Avec l'environnement virtuel activé, depuis `backend` :

```bat
python manage.py test
```

## Langue et heure

Les textes Django sont en français (`fr-fr`). Les dates utilisent le fuseau de Lomé (`Africa/Lome`). Le Togo reste à UTC+0 toute l'année, et `USE_TZ` reste activé : les dates déjà enregistrées ne se décalent pas.
