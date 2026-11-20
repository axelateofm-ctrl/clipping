"""Gestion du stockage disque : répertoires de session isolés et nettoyage."""

from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Optional

from .config import Settings
from .security import is_within


class Storage:
    """Encapsule l'arborescence de travail.

    Structure::

        DATA_DIR/
          jobs/
            <video_id>/
              source/      fichier d'origine
              segments/    séquences générées
              out.zip      archive de téléchargement
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.root = settings.data_dir
        self.jobs_dir = self.root / "jobs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)

    # --- chemins -----------------------------------------------------------
    def job_dir(self, video_id: str) -> Path:
        d = self.jobs_dir / video_id
        if not is_within(self.jobs_dir, d):
            raise ValueError("Identifiant de job invalide.")
        return d

    def source_dir(self, video_id: str) -> Path:
        return self.job_dir(video_id) / "source"

    def segments_dir(self, video_id: str) -> Path:
        return self.job_dir(video_id) / "segments"

    def zip_path(self, video_id: str) -> Path:
        return self.job_dir(video_id) / "out.zip"

    def ensure_job(self, video_id: str) -> Path:
        d = self.job_dir(video_id)
        (d / "source").mkdir(parents=True, exist_ok=True)
        (d / "segments").mkdir(parents=True, exist_ok=True)
        return d

    def source_file(self, video_id: str) -> Optional[Path]:
        src = self.source_dir(video_id)
        if not src.exists():
            return None
        files = [p for p in src.iterdir() if p.is_file()]
        return files[0] if files else None

    # --- nettoyage ---------------------------------------------------------
    def remove_job(self, video_id: str) -> None:
        d = self.jobs_dir / video_id
        if is_within(self.jobs_dir, d) and d.exists():
            shutil.rmtree(d, ignore_errors=True)

    def reset_segments(self, video_id: str) -> None:
        seg = self.segments_dir(video_id)
        if seg.exists():
            shutil.rmtree(seg, ignore_errors=True)
        seg.mkdir(parents=True, exist_ok=True)
        z = self.zip_path(video_id)
        if z.exists():
            z.unlink(missing_ok=True)

    def disk_free_mb(self) -> int:
        try:
            usage = shutil.disk_usage(self.root)
            return int(usage.free / (1024 * 1024))
        except OSError:
            return -1

    def has_free_space(self, needed_mb: int) -> bool:
        free = self.disk_free_mb()
        if free < 0:
            return True  # impossible à mesurer : on laisse passer
        return free - needed_mb >= self.settings.min_free_disk_mb

    def sweep_expired(self, retention_minutes: int) -> int:
        """Supprime les jobs plus vieux que la durée de conservation.

        Renvoie le nombre de jobs supprimés.
        """

        if retention_minutes <= 0:
            return 0
        cutoff = time.time() - retention_minutes * 60
        removed = 0
        if not self.jobs_dir.exists():
            return 0
        for d in self.jobs_dir.iterdir():
            if not d.is_dir():
                continue
            try:
                mtime = d.stat().st_mtime
            except OSError:
                continue
            if mtime < cutoff:
                shutil.rmtree(d, ignore_errors=True)
                removed += 1
        return removed
