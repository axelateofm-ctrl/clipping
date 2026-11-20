# Déployer AXIE Video Splitter sur Railway — pas à pas

Ce guide part de zéro et aboutit à une application en ligne, accessible depuis
votre Mac dans un navigateur.

---

## 1. Préparer le dépôt Git

Le projet se déploie tel quel (le `Dockerfile` est à la racine du dossier
`AXIE VIDEO SPLITTER`).

```bash
cd "AXIE VIDEO SPLITTER"
git init
git add .
git commit -m "AXIE Video Splitter — version initiale"
```

Créez un dépôt sur GitHub (privé de préférence) puis :

```bash
git branch -M main
git remote add origin git@github.com:VOTRE_COMPTE/axie-video-splitter.git
git push -u origin main
```

> Si vous préférez sans GitHub, vous pouvez aussi utiliser la CLI Railway
> (`railway up`) depuis ce dossier. Voir l'étape 7.

---

## 2. Créer le projet sur Railway

1. Connectez-vous sur https://railway.app.
2. **New Project** → **Deploy from GitHub repo**.
3. Autorisez Railway à accéder au dépôt, puis sélectionnez-le.
4. Railway détecte automatiquement le `Dockerfile` (confirmé par
   `railway.json`). Laissez le builder sur **Dockerfile**.

Le `Dockerfile` :
- compile le frontend React (étape Node),
- installe **FFmpeg + FFprobe** et les dépendances Python,
- sert le tout via un seul service FastAPI.

---

## 3. Ajouter un volume (recommandé)

Le stockage par défaut de Railway est **éphémère**. Pour conserver les vidéos et
les ZIP entre redéploiements :

1. Dans le service → onglet **Variables / Settings** → **Volumes**.
2. **Add Volume**, point de montage : **`/data`**.

L'application écrit déjà dans `/data` (variable `DATA_DIR`, définie dans le
`Dockerfile`).

---

## 4. Configurer les variables d'environnement

Onglet **Variables**. `PORT` est fourni **automatiquement** par Railway — ne le
définissez pas. Variables conseillées :

| Variable | Valeur suggérée | Pourquoi |
|---|---|---|
| `APP_PASSWORD` | *(un mot de passe)* | Protéger l'accès public |
| `MAX_UPLOAD_MB` | `4096` | Limiter la taille des imports |
| `RETENTION_MINUTES` | `120` | Nettoyage auto des fichiers |
| `MAX_CONCURRENCY` | `1` | Éviter de saturer le service |
| `DATA_DIR` | `/data` | (déjà par défaut) |

> Astuce : collez le contenu de `.env.example` dans l'éditeur « Raw » des
> variables Railway, puis ajustez.

---

## 5. Déployer

Railway lance le build dès le premier import du repo (ou via **Deploy**).
Suivez les logs : le build peut prendre quelques minutes (compilation frontend +
installation FFmpeg).

Quand le service est **Active**, ouvrez l'URL publique (onglet **Settings** →
**Networking** → **Generate Domain** si aucun domaine n'existe).

---

## 6. Vérifier

- `https://VOTRE-APP.up.railway.app/healthz` doit répondre
  `{"status":"ok"}` (FFmpeg détecté).
- La page d'accueil affiche le tableau de bord AXIE Video Splitter.
- Importez un petit MP4, lancez l'analyse, prévisualisez, exportez en 9:16,
  téléchargez le ZIP.

Le healthcheck configuré (`railway.json`) interroge `/healthz` : si FFmpeg
manque, le déploiement est signalé comme dégradé.

---

## 7. Variante sans GitHub (CLI Railway)

```bash
npm i -g @railway/cli
railway login
cd "AXIE VIDEO SPLITTER"
railway init          # créer/associer un projet
railway up            # build & deploy depuis le Dockerfile local
```

Ajoutez ensuite le volume et les variables depuis le dashboard comme ci-dessus.

---

## Dépannage

| Symptôme | Cause probable | Solution |
|---|---|---|
| `/healthz` = `degraded` | FFmpeg absent | Vérifier que le build utilise bien le `Dockerfile` |
| Upload refusé (413) | Fichier > `MAX_UPLOAD_MB` | Augmenter la variable |
| Fichiers disparus après redéploiement | Pas de volume | Monter un volume sur `/data` |
| Export lent | Ré-encodage (changement de format) | Normal ; utiliser 16:9 si la source est déjà 16:9 |
| « Espace disque insuffisant » | Volume trop petit | Agrandir le volume ou baisser `RETENTION_MINUTES` |

---

## Notes importantes

- **Un seul worker** : l'état des tâches est en mémoire. Ne pas augmenter le
  nombre de workers Uvicorn, sinon les suivis de progression se perdent.
- **Ressources** : le découpage avec ré-encodage est gourmand en CPU. Pour de
  longues vidéos, prévoyez un plan Railway adapté et gardez `MAX_CONCURRENCY=1`.
- **Évolutivité** : l'architecture de stockage est isolée par tâche et peut
  évoluer vers un stockage objet compatible S3 si le besoin apparaît.
