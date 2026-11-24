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

L'API écoute sur http://127.0.0.1:8000 . http://127.0.0.1:8000/api/status/ renvoie `{"status": "ok"}`.

Si l'environnement virtuel existe déjà, activez-le et relancez `python -m pip install -r requirements.txt` pour installer `django-environ`.

`SECRET_KEY`, `DEBUG` et `ALLOWED_HOSTS` sont lus dans `backend/.env`. Sans variable `DEBUG`, le mode débogage est désactivé. Le fichier d'exemple le laisse activé en local, comme auparavant, et autorise `localhost`, `127.0.0.1` et `[::1]`.

## Lancement du frontend

Dans un autre terminal, à la racine du projet :

```bat
cd frontend
npm install
npm run dev
```

Vite sert l'interface, en général sur http://localhost:5173 . Le proxy défini dans `frontend/vite.config.js` transmet les adresses qui commencent par `/api` vers Django sur http://127.0.0.1:8000 . Lancez le backend avant d'utiliser l'interface.

## Tests

Avec l'environnement virtuel activé, depuis `backend` :

```bat
python manage.py test
```

## Langue et heure

Les textes Django sont en français (`fr-fr`). Les dates utilisent le fuseau de Lomé (`Africa/Lome`). Le Togo reste à UTC+0 toute l'année, et `USE_TZ` reste activé : les dates déjà enregistrées ne se décalent pas.
