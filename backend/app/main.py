"""Point d'entrée de l'application FastAPI."""

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import __version__, ffmpeg
from .config import get_settings
from .deps import (
    is_protected,
    register_token,
    settings,
    storage,
)
from .models import HealthResponse
from .routes import router as api_router
from .security import new_token

app = FastAPI(title="AXIE Video Splitter", version=__version__)

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# --- Authentification (protection d'accès facultative) --------------------
class LoginBody(BaseModel):
    password: str


@app.get("/api/auth/status")
async def auth_status() -> dict:
    return {"protected": is_protected()}


@app.post("/api/auth/login")
async def auth_login(body: LoginBody) -> JSONResponse:
    if not is_protected():
        return JSONResponse({"ok": True, "protected": False})
    if body.password != settings.app_password:
        return JSONResponse({"ok": False, "detail": "Mot de passe incorrect."}, status_code=401)
    token = new_token()
    register_token(token)
    resp = JSONResponse({"ok": True})
    resp.set_cookie(
        "axie_session",
        token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
    )
    return resp


@app.post("/api/auth/logout")
async def auth_logout() -> JSONResponse:
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("axie_session")
    return resp


# --- Santé ----------------------------------------------------------------
@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    ffmpeg_ok, ffprobe_ok = ffmpeg.binaries_available(settings)
    return HealthResponse(
        status="ok" if (ffmpeg_ok and ffprobe_ok) else "degraded",
        ffmpeg=ffmpeg_ok,
        ffprobe=ffprobe_ok,
        version=__version__,
        disk_free_mb=storage.disk_free_mb(),
    )


# Alias de santé à la racine /healthz (pratique pour Railway).
@app.get("/healthz")
async def healthz() -> dict:
    ffmpeg_ok, ffprobe_ok = ffmpeg.binaries_available(settings)
    return {"status": "ok" if (ffmpeg_ok and ffprobe_ok) else "degraded"}


# --- API ------------------------------------------------------------------
app.include_router(api_router)


# --- Nettoyage automatique en arrière-plan --------------------------------
_cleanup_task: asyncio.Task | None = None


async def _cleanup_loop() -> None:
    interval = max(1, settings.cleanup_interval_minutes) * 60
    while True:
        try:
            await asyncio.sleep(interval)
            removed = storage.sweep_expired(settings.retention_minutes)
            if removed:
                # Retirer de la mémoire les états dont le dossier a disparu.
                from .deps import manager

                for vid in list(manager.videos.keys()):
                    if storage.job_dir(vid).exists() is False:
                        manager.videos.pop(vid, None)
        except asyncio.CancelledError:
            break
        except Exception:  # noqa: BLE001
            # Le nettoyage ne doit jamais faire tomber le service.
            continue


@app.on_event("startup")
async def _on_startup() -> None:
    global _cleanup_task
    storage.jobs_dir.mkdir(parents=True, exist_ok=True)
    _cleanup_task = asyncio.create_task(_cleanup_loop())


@app.on_event("shutdown")
async def _on_shutdown() -> None:
    if _cleanup_task:
        _cleanup_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _cleanup_task


# --- Frontend statique (SPA) ----------------------------------------------
# En production, le frontend compilé (Vite) est copié dans STATIC_DIR par le
# Dockerfile. On le sert à la racine, avec repli SPA sur index.html.
static_dir: Path = settings.static_dir
if static_dir.exists() and (static_dir / "index.html").exists():
    assets = static_dir / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/")
    async def spa_root() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str) -> Response:
        # Ne jamais intercepter l'API.
        if full_path.startswith("api/") or full_path == "healthz":
            return JSONResponse({"detail": "Not found"}, status_code=404)
        candidate = static_dir / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(static_dir / "index.html")
else:
    @app.get("/")
    async def no_frontend() -> dict:
        return {
            "app": "AXIE Video Splitter",
            "version": __version__,
            "note": "Frontend non compilé. Lancez le build Vite ou utilisez le Dockerfile.",
        }
