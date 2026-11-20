# syntax=docker/dockerfile:1

############################################
# Étape 1 — Build du frontend (Vite)
############################################
FROM node:20-slim AS frontend
WORKDIR /frontend

# Dépendances (cache efficace). package*.json inclut le lock s'il existe.
COPY frontend/package*.json ./
RUN npm install

# Code source + build
COPY frontend/ ./
RUN npm run build


############################################
# Étape 2 — Runtime Python + FFmpeg
############################################
FROM python:3.11-slim AS runtime

# FFmpeg + FFprobe (traitement vidéo côté serveur)
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/data \
    STATIC_DIR=/app/static

WORKDIR /app

# Dépendances Python
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Code backend
COPY backend/app ./app

# Frontend compilé -> servi par FastAPI
COPY --from=frontend /frontend/dist ./static

# Répertoire de travail des vidéos (volume Railway recommandé ici)
RUN mkdir -p /data

EXPOSE 8000

# Railway fournit $PORT. On écoute sur toutes les interfaces.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
