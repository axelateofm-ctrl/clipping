"""Routes de l'API REST."""

from __future__ import annotations

import asyncio
import json
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse, Response, StreamingResponse

from . import ffmpeg
from .config import get_settings
from .deps import check_auth, manager, storage
from .ffmpeg import FFmpegError
from .models import (
    AnalyzeRequest,
    ExportRequest,
    SplitParams,
    VideoState,
    VideoStatus,
)
from .security import sanitize_basename, safe_join

router = APIRouter(prefix="/api", dependencies=[Depends(check_auth)])

settings = get_settings()

# Taille des blocs de lecture en flux (upload). On n'alloue jamais tout le
# fichier en RAM.
CHUNK = 1024 * 1024  # 1 Mo


@router.post("/videos", response_model=VideoState)
async def upload_video(file: UploadFile = File(...)) -> VideoState:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Nom de fichier manquant.")

    base = sanitize_basename(file.filename.rsplit(".", 1)[0], fallback="video")
    # On impose l'extension .mp4 ; le contenu est validé ensuite par ffprobe.
    safe_name = f"{base}.mp4"

    # Création d'un job provisoire pour écrire la source en flux.
    from .security import new_token

    tmp_id = new_token(12)
    storage.ensure_job(tmp_id)
    dest = safe_join(storage.source_dir(tmp_id), safe_name)

    size = 0
    try:
        with open(dest, "wb") as out:
            while True:
                chunk = await file.read(CHUNK)
                if not chunk:
                    break
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    out.close()
                    storage.remove_job(tmp_id)
                    raise HTTPException(
                        status_code=413,
                        detail=f"Fichier trop volumineux (max {settings.max_upload_mb} Mo).",
                    )
                out.write(chunk)
    except HTTPException:
        raise
    except OSError as exc:
        storage.remove_job(tmp_id)
        raise HTTPException(status_code=500, detail=f"Écriture impossible : {exc}")
    finally:
        await file.close()

    if size == 0:
        storage.remove_job(tmp_id)
        raise HTTPException(status_code=400, detail="Fichier vide.")

    # Validation réelle du format avec ffprobe.
    try:
        meta = await ffmpeg.probe(settings, dest)
    except FFmpegError as exc:
        storage.remove_job(tmp_id)
        raise HTTPException(status_code=400, detail=str(exc))

    meta.filename = file.filename
    meta.size_bytes = size

    # On crée l'état définitif, puis on déplace le dossier source sous ce nouvel id.
    state = manager.create_video(meta)
    # Réutiliser le dossier déjà écrit : on le renomme vers l'id définitif.
    tmp_dir = storage.job_dir(tmp_id)
    final_dir = storage.job_dir(state.id)
    import shutil

    if final_dir.exists():
        shutil.rmtree(final_dir, ignore_errors=True)
    tmp_dir.rename(final_dir)
    storage.ensure_job(state.id)
    return state


@router.get("/videos", response_model=List[VideoState])
async def list_videos() -> List[VideoState]:
    return list(manager.videos.values())


@router.get("/videos/{video_id}", response_model=VideoState)
async def get_video(video_id: str) -> VideoState:
    state = manager.get(video_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Vidéo introuvable.")
    return state


@router.delete("/videos/{video_id}")
async def delete_video(video_id: str) -> dict:
    if manager.get(video_id) is None:
        raise HTTPException(status_code=404, detail="Vidéo introuvable.")
    await manager.cancel(video_id)
    manager.delete(video_id)
    return {"ok": True}


@router.post("/videos/{video_id}/analyze", response_model=VideoState)
async def analyze_video(video_id: str, body: AnalyzeRequest) -> VideoState:
    state = manager.get(video_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Vidéo introuvable.")
    if state.status in (VideoStatus.analyzing, VideoStatus.exporting):
        raise HTTPException(status_code=409, detail="Traitement déjà en cours.")
    manager.start_analyze(video_id, body.params)
    return manager.get(video_id)  # type: ignore[return-value]


@router.post("/videos/{video_id}/export", response_model=VideoState)
async def export_video(video_id: str, body: ExportRequest) -> VideoState:
    state = manager.get(video_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Vidéo introuvable.")
    if not state.segments:
        raise HTTPException(status_code=409, detail="Analysez la vidéo avant d'exporter.")
    if state.status in (VideoStatus.analyzing, VideoStatus.exporting):
        raise HTTPException(status_code=409, detail="Traitement déjà en cours.")
    try:
        body.settings.normalized()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    manager.start_export(video_id, body.settings)
    return manager.get(video_id)  # type: ignore[return-value]


@router.post("/videos/{video_id}/cancel", response_model=VideoState)
async def cancel_video(video_id: str) -> VideoState:
    state = manager.get(video_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Vidéo introuvable.")
    await manager.cancel(video_id)
    return manager.get(video_id)  # type: ignore[return-value]


@router.get("/videos/{video_id}/events")
async def video_events(video_id: str, request: Request) -> StreamingResponse:
    """Flux Server-Sent Events rapportant la progression en temps réel."""

    if manager.get(video_id) is None:
        raise HTTPException(status_code=404, detail="Vidéo introuvable.")

    async def event_stream():
        terminal = {VideoStatus.done, VideoStatus.error, VideoStatus.canceled}
        last = None
        while True:
            if await request.is_disconnected():
                break
            state = manager.get(video_id)
            if state is None:
                break
            payload = state.model_dump(mode="json")
            snapshot = json.dumps(payload, sort_keys=True)
            if snapshot != last:
                yield f"data: {snapshot}\n\n"
                last = snapshot
            if state.status in terminal:
                yield "event: end\ndata: {}\n\n"
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/videos/{video_id}/source")
async def get_source(video_id: str) -> FileResponse:
    """Sert la vidéo d'origine (lecteur HTML5, avec support Range)."""

    state = manager.get(video_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Vidéo introuvable.")
    src = storage.source_file(video_id)
    if src is None or not src.exists():
        raise HTTPException(status_code=404, detail="Source introuvable.")
    return FileResponse(src, media_type="video/mp4", filename=state.meta.filename)


@router.get("/videos/{video_id}/thumb")
async def get_thumbnail(video_id: str, t: float = 0.0, w: int = 240) -> Response:
    """Extrait une miniature JPEG à l'instant ``t`` (secondes)."""

    if manager.get(video_id) is None:
        raise HTTPException(status_code=404, detail="Vidéo introuvable.")
    src = storage.source_file(video_id)
    if src is None or not src.exists():
        raise HTTPException(status_code=404, detail="Source introuvable.")
    w = max(32, min(640, int(w)))
    t = max(0.0, float(t))
    cmd = [
        settings.ffmpeg_bin,
        "-nostdin", "-hide_banner", "-loglevel", "error",
        "-ss", f"{t:.3f}",
        "-i", str(src),
        "-frames:v", "1",
        "-vf", f"scale={w}:-2",
        "-f", "image2pipe",
        "-vcodec", "mjpeg",
        "pipe:1",
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="FFmpeg indisponible sur le serveur.")
    out, _ = await proc.communicate()
    if proc.returncode != 0 or not out:
        # Image transparente 1x1 de secours (évite une erreur dans l'UI).
        raise HTTPException(status_code=404, detail="Miniature indisponible.")
    return Response(content=out, media_type="image/jpeg",
                    headers={"Cache-Control": "max-age=3600"})


@router.get("/videos/{video_id}/segments/{name}")
async def get_segment(video_id: str, name: str) -> FileResponse:
    """Sert une séquence générée (prévisualisation après export)."""

    if manager.get(video_id) is None:
        raise HTTPException(status_code=404, detail="Vidéo introuvable.")
    try:
        path = safe_join(storage.segments_dir(video_id), name)
    except ValueError:
        raise HTTPException(status_code=400, detail="Nom invalide.")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Séquence introuvable.")
    return FileResponse(path, media_type="video/mp4", filename=path.name)


@router.get("/videos/{video_id}/download/{name}")
async def download_segment(video_id: str, name: str) -> FileResponse:
    if manager.get(video_id) is None:
        raise HTTPException(status_code=404, detail="Vidéo introuvable.")
    try:
        path = safe_join(storage.segments_dir(video_id), name)
    except ValueError:
        raise HTTPException(status_code=400, detail="Nom invalide.")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Séquence introuvable.")
    return FileResponse(
        path,
        media_type="application/octet-stream",
        filename=path.name,
        headers={"Content-Disposition": f'attachment; filename="{path.name}"'},
    )


@router.get("/videos/{video_id}/download")
async def download_zip(video_id: str) -> FileResponse:
    state = manager.get(video_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Vidéo introuvable.")
    zip_path = storage.zip_path(video_id)
    if not state.export_ready or not zip_path.exists():
        raise HTTPException(status_code=409, detail="Aucune archive disponible.")
    download_name = state.zip_name or "sequences.zip"
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=download_name,
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
    )
