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

Si l'environnement virtuel existe déjà, activez-le et relancez `python -m pip install -r requirements.txt` pour installer `django-environ`.

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

Pour un autre compte (une personne de confiance), connectez-vous à http://127.0.0.1:8000/admin/ avec le compte créé ci-dessus, puis ajoutez un utilisateur. Cochez « Statut équipe » seulement si cette personne doit aussi ouvrir l'administration. Tout compte actif peut utiliser l'application. Il n'y a pas de mot de passe par défaut : sans compte, personne ne voit les noms, les téléphones ni les montants.

## Lancement du frontend

Dans un autre terminal, à la racine du projet :

```bat
cd frontend
npm install
npm run dev
```

Vite sert l'interface, en général sur http://localhost:5173 . Ouvrez cette adresse dans le navigateur, y compris sur le téléphone : c'est elle qui envoie le cookie de connexion. Le proxy défini dans `frontend/vite.config.js` transmet les adresses qui commencent par `/api` vers Django sur http://127.0.0.1:8000 . Lancez le backend avant d'utiliser l'interface.

Si Vite n'utilise pas le port 5173, ou si le téléphone ouvre une adresse du type `http://192.168.1.12:5173`, ajoutez cette origine dans `backend/.env` (sans espace après les virgules), puis relancez Django :

```
CSRF_TRUSTED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://192.168.1.12:5173
```

## Tests

Avec l'environnement virtuel activé, depuis `backend` :

```bat
python manage.py test
```

## Langue et heure

Les textes Django sont en français (`fr-fr`). Les dates utilisent le fuseau de Lomé (`Africa/Lome`). Le Togo reste à UTC+0 toute l'année, et `USE_TZ` reste activé : les dates déjà enregistrées ne se décalent pas.
