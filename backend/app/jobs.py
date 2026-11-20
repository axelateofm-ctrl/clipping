"""Gestionnaire de tâches : analyse et export en arrière-plan.

L'état des vidéos est conservé en mémoire. Les traitements longs ne s'exécutent
jamais dans une requête HTTP synchrone : ils tournent dans des tâches asyncio,
et le client suit l'avancement par polling ou SSE.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Set

from . import ffmpeg
from .config import Settings
from .models import (
    ExportSettings,
    SegmentOut,
    SplitParams,
    VideoMeta,
    VideoState,
    VideoStatus,
)
from .security import new_token, sanitize_basename, unique_name
from .splitter import Silence, compute_segments, validate_plan
from .storage import Storage


class JobManager:
    def __init__(self, settings: Settings, storage: Storage) -> None:
        self.settings = settings
        self.storage = storage
        self.videos: Dict[str, VideoState] = {}
        self._sem = asyncio.Semaphore(max(1, settings.max_concurrency))
        self._procs: Dict[str, Set[asyncio.subprocess.Process]] = {}
        self._tasks: Dict[str, asyncio.Task] = {}
        self._cancel: Set[str] = set()

    # --- helpers d'état ----------------------------------------------------
    def get(self, video_id: str) -> Optional[VideoState]:
        return self.videos.get(video_id)

    def _touch(self, state: VideoState) -> None:
        state.updated_at = time.time()

    def create_video(self, meta: VideoMeta) -> VideoState:
        vid = new_token(12)
        now = time.time()
        state = VideoState(
            id=vid,
            status=VideoStatus.uploaded,
            meta=meta,
            created_at=now,
            updated_at=now,
        )
        self.videos[vid] = state
        return state

    def _register_proc(self, video_id: str):
        def register(proc: asyncio.subprocess.Process) -> None:
            self._procs.setdefault(video_id, set()).add(proc)

        return register

    def _clear_procs(self, video_id: str) -> None:
        self._procs.pop(video_id, None)

    # --- annulation --------------------------------------------------------
    async def cancel(self, video_id: str) -> bool:
        state = self.videos.get(video_id)
        if state is None:
            return False
        if state.status not in (VideoStatus.analyzing, VideoStatus.exporting):
            return False

        self._cancel.add(video_id)
        for proc in list(self._procs.get(video_id, set())):
            with contextlib.suppress(ProcessLookupError):
                proc.terminate()
        task = self._tasks.get(video_id)
        if task:
            task.cancel()
        # Nettoyage des séquences partielles.
        self.storage.reset_segments(video_id)
        state.status = VideoStatus.canceled
        state.progress = 0.0
        state.progress_stage = None
        state.export_ready = False
        self._touch(state)
        return True

    def _check_canceled(self, video_id: str) -> bool:
        return video_id in self._cancel

    # --- analyse -----------------------------------------------------------
    def start_analyze(self, video_id: str, params: SplitParams) -> None:
        state = self.videos[video_id]
        self._cancel.discard(video_id)
        state.params = params
        state.status = VideoStatus.analyzing
        state.progress = 0.0
        state.progress_stage = "analyze"
        state.segments = []
        state.export_ready = False
        self._touch(state)
        task = asyncio.create_task(self._run_analyze(video_id))
        self._tasks[video_id] = task

    async def _run_analyze(self, video_id: str) -> None:
        state = self.videos[video_id]
        params = state.params
        assert params is not None
        source = self.storage.source_file(video_id)
        if source is None:
            self._fail(state, "Fichier source introuvable.")
            return

        try:
            async with self._sem:
                if self._check_canceled(video_id):
                    return
                silences: List[Silence] = []
                if params.smart and state.meta.has_audio:
                    def on_progress(frac: float) -> None:
                        state.progress = round(frac, 4)
                        self._touch(state)

                    silences = await ffmpeg.detect_silences(
                        self.settings,
                        source,
                        noise_db=params.silence_db,
                        min_silence=params.silence_min,
                        total_seconds=state.meta.duration,
                        progress_cb=on_progress,
                        register=self._register_proc(video_id),
                    )

                plan = compute_segments(
                    duration=state.meta.duration,
                    silences=silences,
                    target=params.target,
                    window=params.window,
                    smart=params.smart,
                )
                problems = validate_plan(plan)
                if problems:
                    raise RuntimeError("; ".join(problems))

                state.segments = [SegmentOut(**s.as_dict()) for s in plan.segments]
                state.total_segments = len(plan.segments)
                state.progress = 1.0
                state.progress_stage = None
                state.status = VideoStatus.ready
                self._touch(state)
        except asyncio.CancelledError:
            return
        except Exception as exc:  # noqa: BLE001
            if not self._check_canceled(video_id):
                self._fail(state, str(exc))
        finally:
            self._clear_procs(video_id)
            self._tasks.pop(video_id, None)

    # --- export ------------------------------------------------------------
    def start_export(self, video_id: str, settings: ExportSettings) -> None:
        state = self.videos[video_id]
        self._cancel.discard(video_id)
        state.status = VideoStatus.exporting
        state.progress = 0.0
        state.progress_stage = "export"
        state.current_segment = 0
        state.export_ready = False
        state.zip_name = None
        self._touch(state)
        task = asyncio.create_task(self._run_export(video_id, settings))
        self._tasks[video_id] = task

    async def _run_export(self, video_id: str, settings: ExportSettings) -> None:
        state = self.videos[video_id]
        source = self.storage.source_file(video_id)
        if source is None:
            self._fail(state, "Fichier source introuvable.")
            return
        if not state.segments:
            self._fail(state, "Aucun segment à exporter (lancez l'analyse).")
            return

        try:
            settings = settings.normalized()
        except ValueError as exc:
            self._fail(state, str(exc))
            return

        # Vérification de l'espace disque avant de commencer.
        needed_mb = int(state.meta.size_bytes / (1024 * 1024) * self.settings.export_space_factor)
        if not self.storage.has_free_space(needed_mb):
            self._fail(state, "Espace disque insuffisant pour l'export.")
            return

        from .splitter import aspect_ratio_value

        aw, ah = aspect_ratio_value(settings.aspect_ratio)
        plan = ffmpeg.plan_encode(state.meta, aw, ah, settings.precise)

        self.storage.reset_segments(video_id)
        seg_dir = self.storage.segments_dir(video_id)
        base = sanitize_basename(settings.base_name, fallback="Sequence")
        used: Set[str] = set()
        total = len(state.segments)
        pad = max(2, len(str(total)))
        produced: List[Path] = []

        try:
            async with self._sem:
                for i, seg in enumerate(state.segments):
                    if self._check_canceled(video_id):
                        return
                    state.current_segment = i + 1
                    name = unique_name(f"{base}_{str(i + 1).zfill(pad)}", "mp4", used)
                    out_path = seg_dir / name

                    def on_progress(frac: float, idx=i) -> None:
                        state.progress = round((idx + frac) / total, 4)
                        self._touch(state)

                    await ffmpeg.cut_segment(
                        self.settings,
                        source=source,
                        output=out_path,
                        start=seg.start,
                        duration=seg.duration,
                        plan=plan,
                        quality=settings.quality,
                        progress_cb=on_progress,
                        register=self._register_proc(video_id),
                    )

                    # Vérification réelle du fichier produit.
                    if not await ffmpeg.verify_output(self.settings, out_path):
                        raise RuntimeError(f"Séquence {i + 1} invalide après export.")
                    produced.append(out_path)

                if self._check_canceled(video_id):
                    return

                # Construction du ZIP.
                zip_path = self.storage.zip_path(video_id)
                with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED) as zf:
                    for p in produced:
                        zf.write(p, arcname=p.name)

                state.zip_name = f"{base}.zip"
                state.export_ready = True
                state.progress = 1.0
                state.progress_stage = None
                state.status = VideoStatus.done
                self._touch(state)
        except asyncio.CancelledError:
            return
        except Exception as exc:  # noqa: BLE001
            if not self._check_canceled(video_id):
                self._fail(state, str(exc))
        finally:
            self._clear_procs(video_id)
            self._tasks.pop(video_id, None)

    # --- divers ------------------------------------------------------------
    def _fail(self, state: VideoState, message: str) -> None:
        state.status = VideoStatus.error
        state.error = message
        state.progress_stage = None
        self._touch(state)

    def delete(self, video_id: str) -> None:
        state = self.videos.pop(video_id, None)
        if state is None:
            return
        task = self._tasks.pop(video_id, None)
        if task:
            task.cancel()
        self._clear_procs(video_id)
        self.storage.remove_job(video_id)

    def list_segment_files(self, video_id: str) -> List[Path]:
        seg_dir = self.storage.segments_dir(video_id)
        if not seg_dir.exists():
            return []
        return sorted(p for p in seg_dir.iterdir() if p.is_file() and p.suffix == ".mp4")
