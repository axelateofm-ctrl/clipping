"""Configuration de l'application, pilotée par variables d'environnement."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


def _get_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on", "oui"}


def _get_int(name: str, default: int) -> int:
    val = os.getenv(name)
    if val is None or val.strip() == "":
        return default
    try:
        return int(val)
    except ValueError:
        return default


def _get_float(name: str, default: float) -> float:
    val = os.getenv(name)
    if val is None or val.strip() == "":
        return default
    try:
        return float(val)
    except ValueError:
        return default


class Settings:
    """Paramètres de l'application.

    Toutes les valeurs sont surchargeables via l'environnement, ce qui est
    adapté au déploiement Railway.
    """

    def __init__(self) -> None:
        # Réseau — Railway fournit PORT.
        self.host: str = os.getenv("HOST", "0.0.0.0")
        self.port: int = _get_int("PORT", 8000)

        # Répertoire de travail. Sur Railway, monter un volume ici pour
        # survivre aux redéploiements (sinon stockage éphémère).
        self.data_dir: Path = Path(os.getenv("DATA_DIR", "/tmp/axie_splitter")).resolve()

        # Limites.
        self.max_upload_mb: int = _get_int("MAX_UPLOAD_MB", 4096)  # 4 Go par défaut
        self.max_concurrency: int = _get_int("MAX_CONCURRENCY", 1)
        self.min_free_disk_mb: int = _get_int("MIN_FREE_DISK_MB", 1024)
        # Marge de sécurité disque : on exige ~ 1.6x la taille source pour un
        # export (segments + zip) avant de lancer un traitement.
        self.export_space_factor: float = _get_float("EXPORT_SPACE_FACTOR", 1.6)

        # Durée de conservation des fichiers (minutes) avant nettoyage auto.
        self.retention_minutes: int = _get_int("RETENTION_MINUTES", 120)
        self.cleanup_interval_minutes: int = _get_int("CLEANUP_INTERVAL_MINUTES", 15)

        # Découpage — valeurs par défaut.
        self.default_target: float = _get_float("DEFAULT_TARGET", 70.0)
        self.default_window: float = _get_float("DEFAULT_WINDOW", 10.0)
        self.default_silence_db: float = _get_float("DEFAULT_SILENCE_DB", -35.0)
        self.default_silence_min: float = _get_float("DEFAULT_SILENCE_MIN", 0.25)

        # Encodage précis (ré-encodage).
        self.x264_crf: int = _get_int("X264_CRF", 18)
        self.x264_preset: str = os.getenv("X264_PRESET", "medium")
        self.audio_bitrate: str = os.getenv("AUDIO_BITRATE", "192k")

        # Binaires FFmpeg (surchargeables si installés ailleurs).
        self.ffmpeg_bin: str = os.getenv("FFMPEG_BIN", "ffmpeg")
        self.ffprobe_bin: str = os.getenv("FFPROBE_BIN", "ffprobe")

        # Protection d'accès simple (facultative). Si défini, l'UI et l'API
        # exigent ce mot de passe. Vide => accès libre (usage perso local).
        self.app_password: str = os.getenv("APP_PASSWORD", "")

        # Origines autorisées pour CORS (dev). En prod, le frontend est servi
        # par le backend donc CORS est généralement inutile.
        self.cors_origins: list[str] = [
            o.strip()
            for o in os.getenv("CORS_ORIGINS", "").split(",")
            if o.strip()
        ]

        # Chemin des fichiers statiques du frontend compilé.
        self.static_dir: Path = Path(
            os.getenv("STATIC_DIR", str(Path(__file__).resolve().parent.parent / "static"))
        )

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
