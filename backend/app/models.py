"""Schémas Pydantic (API) et énumérations d'état."""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class VideoStatus(str, Enum):
    uploaded = "uploaded"          # importée, métadonnées lues
    analyzing = "analyzing"        # analyse des silences en cours
    ready = "ready"                # analyse terminée, prête à exporter
    exporting = "exporting"        # export en cours
    done = "done"                  # export terminé et vérifié
    error = "error"                # erreur
    canceled = "canceled"          # annulée


class VideoMeta(BaseModel):
    """Métadonnées réelles issues de ffprobe."""

    filename: str
    size_bytes: int
    duration: float = 0.0
    width: Optional[int] = None
    height: Optional[int] = None
    aspect_ratio: Optional[str] = None
    fps: Optional[float] = None
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    has_audio: bool = False


class SegmentOut(BaseModel):
    index: int
    start: float
    end: float
    duration: float
    cut_type: str  # silence | time | final


class SplitParams(BaseModel):
    target: float = Field(70.0, gt=0, description="Durée cible (secondes).")
    window: float = Field(10.0, ge=0, description="Fenêtre de recherche de silence (s).")
    smart: bool = Field(True, description="Activer le découpage intelligent.")
    silence_db: float = Field(-35.0, description="Seuil de silence (dB).")
    silence_min: float = Field(0.25, gt=0, description="Durée mini de silence (s).")


class VideoState(BaseModel):
    id: str
    status: VideoStatus
    meta: VideoMeta
    params: Optional[SplitParams] = None
    segments: List[SegmentOut] = Field(default_factory=list)
    error: Optional[str] = None
    # Progression (0..1) de l'opération courante.
    progress: float = 0.0
    progress_stage: Optional[str] = None  # "analyze" | "export"
    current_segment: int = 0
    total_segments: int = 0
    export_ready: bool = False
    zip_name: Optional[str] = None
    created_at: float = 0.0
    updated_at: float = 0.0


class ExportSettings(BaseModel):
    aspect_ratio: str = Field("16:9", description="16:9 ou 9:16")
    quality: str = Field("original", description="original | high")
    precise: bool = Field(False, description="Forcer le ré-encodage précis.")
    base_name: str = Field("Sequence", description="Préfixe de nommage.")

    def normalized(self) -> "ExportSettings":
        if self.aspect_ratio not in ("16:9", "9:16"):
            raise ValueError("Format d'image invalide (16:9 ou 9:16).")
        if self.quality not in ("original", "high"):
            self.quality = "original"
        return self


class AnalyzeRequest(BaseModel):
    params: SplitParams = Field(default_factory=SplitParams)


class ExportRequest(BaseModel):
    settings: ExportSettings = Field(default_factory=ExportSettings)


class HealthResponse(BaseModel):
    status: str
    ffmpeg: bool
    ffprobe: bool
    version: str
    disk_free_mb: Optional[int] = None
