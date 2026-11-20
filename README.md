# AXIE Video Splitter

Application web de découpage automatique de vidéos MP4 longues en séquences
d'environ 70 secondes, en privilégiant les silences naturels entre les phrases.
Pensée pour préparer rapidement des rushes destinés à des montages TikTok
(CapCut), tout en préservant au maximum la qualité d'origine.

Le traitement vidéo est **100 % côté serveur** (FFmpeg). Le navigateur ne fait
jamais d'encodage.

---

## Sommaire

- [Fonctionnalités](#fonctionnalités)
- [Architecture](#architecture)
- [Arborescence](#arborescence)
- [Démarrage local](#démarrage-local)
- [Déploiement Railway](#déploiement-railway) → voir aussi [`DEPLOY_RAILWAY.md`](DEPLOY_RAILWAY.md)
- [Variables d'environnement](#variables-denvironnement)
- [Fonctionnement du découpage](#fonctionnement-du-découpage)
- [Préservation de la qualité](#préservation-de-la-qualité)
- [Tests](#tests)
- [Limites connues](#limites-connues)

---

## Fonctionnalités

- **Import** glisser-déposer de plusieurs MP4, avec progression réelle d'envoi,
  annulation et métadonnées réelles (ffprobe : durée, résolution, format, FPS,
  codecs, présence audio) + aperçu lecteur HTML5.
- **Découpage intelligent** : analyse des silences (`silencedetect`), calcul de
  frontières temporelles continues couvrant toute la vidéo, coupe au plus près
  d'une pause naturelle dans une fenêtre configurable, repli temporel sinon.
- **Prévisualisation** avant export : timeline proportionnelle, miniatures,
  lecture bornée de chaque séquence, distinction visuelle coupe « silence » /
  coupe « durée ».
- **Export** : format **16:9** ou **9:16** (adaptation sans déformation, marges
  neutres centrées, aucun flou), qualité d'origine privilégiée, nommage
  personnalisé (`Nom_01.mp4`, `Nom_02.mp4`…), ZIP groupé + téléchargements
  individuels.
- **Traitement par lots** avec file d'attente à concurrence limitée, états par
  vidéo, progression FFmpeg réelle et **annulation effective** côté serveur.
- **Robustesse** : tâches asynchrones (jamais dans la requête HTTP), nettoyage
  automatique des fichiers, vérification ffprobe des exports avant de déclarer
  « terminé ».
- **Sécurité** : validation réelle des formats, noms assainis, chemins confinés
  par session, aucune injection shell (arguments FFmpeg en liste), protection
  d'accès par mot de passe facultative.

## Architecture

| Couche | Technologie |
|---|---|
| Frontend | React + TypeScript + Vite + Tailwind CSS |
| Backend | Python + FastAPI (ASGI, Uvicorn) |
| Vidéo | FFmpeg / FFprobe |
| Silences | filtre `silencedetect` |
| Progression | polling REST + endpoint SSE |
| Déploiement | Docker (multi-étapes) sur Railway |

Le backend sert aussi le frontend compilé : **un seul service** à déployer.

> ⚠️ L'état des tâches est conservé **en mémoire** → le service tourne avec
> **un seul worker** (`--workers 1`). C'est volontaire et adapté à un usage
> personnel.

## Arborescence

```
AXIE VIDEO SPLITTER/
├── Dockerfile                 # build frontend + runtime python/ffmpeg
├── railway.json               # config de déploiement Railway
├── .env.example               # variables d'environnement documentées
├── README.md
├── DEPLOY_RAILWAY.md          # guide pas à pas Railway
├── backend/
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── pytest.ini
│   ├── app/
│   │   ├── main.py            # app FastAPI, santé, statique, nettoyage
│   │   ├── config.py          # configuration via variables d'env
│   │   ├── models.py          # schémas Pydantic + états
│   │   ├── security.py        # noms de fichiers, chemins, tokens
│   │   ├── storage.py         # répertoires de session, disque, nettoyage
│   │   ├── ffmpeg.py          # ffprobe, silencedetect, découpe, progression
│   │   ├── splitter.py        # calcul PUR des frontières (testable)
│   │   ├── jobs.py            # file d'attente, analyse/export, annulation
│   │   ├── routes.py          # API REST (upload, analyze, export, download…)
│   │   └── deps.py            # singletons + authentification
│   └── tests/                 # tests pytest (logique + intégration ffmpeg)
└── frontend/
    ├── package.json, vite.config.ts, tailwind.config.js, …
    └── src/
        ├── App.tsx            # orchestration, polling, uploads
        ├── api.ts, types.ts, utils.ts
        └── components/        # Import, VideoCard, Timeline, ExportModal, …
```

## Démarrage local

### Prérequis
- **FFmpeg et FFprobe** installés et accessibles dans le `PATH`
  (`brew install ffmpeg` sur macOS).
- Python 3.11+ et Node 20+.

### Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend (dev)
```bash
cd frontend
npm install
npm run dev
```
Ouvrez http://localhost:5173 (le dev server proxifie `/api` vers le port 8000).

### Tout-en-un via Docker (comme en production)
```bash
docker build -t axie-splitter .
docker run --rm -p 8000:8000 -v "$PWD/data:/data" axie-splitter
```
Ouvrez http://localhost:8000.

## Déploiement Railway

Guide détaillé : **[`DEPLOY_RAILWAY.md`](DEPLOY_RAILWAY.md)**. En résumé :

1. Poussez ce dossier sur un dépôt Git.
2. Sur Railway : **New Project → Deploy from GitHub repo**.
3. Railway détecte le `Dockerfile` (confirmé par `railway.json`).
4. Ajoutez un **Volume** monté sur `/data` (persistance des fichiers).
5. Variables d'environnement utiles (voir ci-dessous). `PORT` est fourni
   automatiquement par Railway.
6. Déployez. Le healthcheck interroge `/healthz`.

## Variables d'environnement

Voir [`.env.example`](.env.example) pour la liste commentée. Les plus utiles :

| Variable | Défaut | Rôle |
|---|---|---|
| `DATA_DIR` | `/data` | Répertoire de travail (monter un volume ici) |
| `MAX_UPLOAD_MB` | `4096` | Taille max d'un import |
| `MAX_CONCURRENCY` | `1` | Traitements FFmpeg simultanés |
| `RETENTION_MINUTES` | `120` | Durée de conservation avant nettoyage |
| `APP_PASSWORD` | *(vide)* | Protège l'accès si défini |
| `X264_CRF` / `X264_PRESET` | `18` / `medium` | Qualité du ré-encodage |

## Fonctionnement du découpage

1. **Analyse des silences** avec `silencedetect=noise=<dB>:d=<durée>`.
2. Parcours continu : chaque segment démarre là où le précédent finit.
3. Pour un segment, on cherche un silence dans la fenêtre
   `[cible - fenêtre, cible]` (par défaut **60–70 s**) et on prend la pause la
   plus proche possible de la durée maximale.
4. Sans silence pertinent → **coupe temporelle** à la durée cible.
5. La **dernière séquence** conserve sa durée réelle, même courte.
6. Les frontières couvrent toute la vidéo, **sans trou ni chevauchement**.

> Une détection de silence **ne garantit pas** qu'une phrase soit terminée.
> L'outil est une aide, jamais une certitude : une coupe de secours à la durée
> maximale est toujours disponible.

## Préservation de la qualité

- **Découpage rapide** : copie directe des flux (`-c copy`) quand le format
  n'est pas modifié → pas de ré-encodage, qualité d'origine. La précision des
  coupes dépend alors des images clés.
- **Découpage précis** : ré-encodage H.264 (CRF 18 par défaut) + AAC, imposé
  dès qu'un changement de format est demandé, ou activable pour des coupes à
  l'image près.
- **Adaptation de format** sans déformation : mise à l'échelle qui tient dans le
  cadre + marges neutres centrées (pas de flou, pas d'étirement, pas
  d'agrandissement artificiel au-delà de la définition source).
- Le volume, la vitesse et le contenu audio ne sont **jamais** modifiés.

## Tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

- Les tests de **logique de découpage** (frontières, continuité, dernier
  segment, absence de silence, nombreux silences, etc.) tournent **sans
  FFmpeg**.
- Les tests d'**intégration FFmpeg** (export réel, 16:9 ↔ 9:16, vérification
  ffprobe des sorties) se lancent automatiquement **si FFmpeg est présent**,
  sinon ils sont ignorés (`skipped`).

## Limites connues

- État en mémoire → un seul worker ; un redémarrage interrompt les tâches en
  cours (elles ne sont pas reprises, ce qui est annoncé honnêtement à
  l'utilisateur plutôt que simulé).
- En mode copie directe, la précision des coupes est bornée par les images clés
  du fichier source (limite intrinsèque aux codecs).
- Le stockage Railway est éphémère sans volume : montez `/data` sur un volume
  pour conserver les fichiers entre redéploiements.
- Le navigateur ne peut pas choisir un dossier de destination arbitraire sur
  macOS : les fichiers passent par le dossier de téléchargement du navigateur.
