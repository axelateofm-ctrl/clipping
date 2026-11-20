"""Enveloppe autour de FFmpeg / FFprobe.

Toutes les commandes sont construites avec des **listes d'arguments** (jamais
``shell=True``) : aucune valeur fournie par l'utilisateur n'est interprétée par
un shell, ce qui évite l'injection de commandes.
"""

from __future__ import annotations

import asyncio
import json
import math
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, List, Optional, Tuple

from .config import Settings
from .models import VideoMeta
from .splitter import Silence, parse_silencedetect

ProgressCb = Callable[[float], None]
RegisterCb = Callable[[asyncio.subprocess.Process], None]


class FFmpegError(RuntimeError):
    pass


def binaries_available(settings: Settings) -> Tuple[bool, bool]:
    ffmpeg = shutil.which(settings.ffmpeg_bin) is not None
    ffprobe = shutil.which(settings.ffprobe_bin) is not None
    return ffmpeg, ffprobe


def _parse_fraction(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    try:
        if "/" in value:
            num, den = value.split("/", 1)
            den_f = float(den)
            if den_f == 0:
                return None
            return float(num) / den_f
        return float(value)
    except (ValueError, ZeroDivisionError):
        return None


async def _spawn(cmd: List[str]) -> asyncio.subprocess.Process:
    """Lance un sous-processus et convertit l'absence de binaire en FFmpegError."""

    try:
        return await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        raise FFmpegError(
            f"Binaire introuvable : {cmd[0]!r}. FFmpeg/FFprobe doivent être installés."
        )


async def _run(cmd: List[str], register: Optional[RegisterCb] = None) -> Tuple[int, str, str]:
    """Exécute une commande et renvoie (code, stdout, stderr)."""

    proc = await _spawn(cmd)
    if register:
        register(proc)
    out, err = await proc.communicate()
    return proc.returncode or 0, out.decode("utf-8", "ignore"), err.decode("utf-8", "ignore")


async def probe(settings: Settings, path: Path) -> VideoMeta:
    """Lit les métadonnées réelles via ffprobe. Lève si le fichier est invalide."""

    cmd = [
        settings.ffprobe_bin,
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    code, out, err = await _run(cmd)
    if code != 0:
        raise FFmpegError(f"ffprobe a échoué : {err.strip() or 'fichier illisible'}")

    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        raise FFmpegError("Sortie ffprobe illisible.")

    streams = data.get("streams", [])
    fmt = data.get("format", {})

    v_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    a_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if v_stream is None:
        raise FFmpegError("Aucune piste vidéo détectée : fichier refusé.")

    duration = 0.0
    for candidate in (v_stream.get("duration"), fmt.get("duration")):
        try:
            if candidate is not None:
                duration = float(candidate)
                if duration > 0:
                    break
        except (TypeError, ValueError):
            continue

    width = v_stream.get("width")
    height = v_stream.get("height")
    fps = _parse_fraction(v_stream.get("avg_frame_rate")) or _parse_fraction(
        v_stream.get("r_frame_rate")
    )

    aspect = None
    if width and height:
        g = math.gcd(int(width), int(height))
        if g:
            aspect = f"{int(width) // g}:{int(height) // g}"

    try:
        size_bytes = int(fmt.get("size") or path.stat().st_size)
    except (TypeError, ValueError, OSError):
        size_bytes = 0

    return VideoMeta(
        filename=path.name,
        size_bytes=size_bytes,
        duration=round(duration, 3),
        width=int(width) if width else None,
        height=int(height) if height else None,
        aspect_ratio=aspect,
        fps=round(fps, 3) if fps else None,
        video_codec=v_stream.get("codec_name"),
        audio_codec=a_stream.get("codec_name") if a_stream else None,
        has_audio=a_stream is not None,
    )


async def _stream_progress(
    proc: asyncio.subprocess.Process,
    total_seconds: float,
    progress_cb: Optional[ProgressCb],
) -> None:
    """Lit la sortie ``-progress pipe:1`` et rapporte l'avancement (0..1)."""

    assert proc.stdout is not None
    while True:
        line = await proc.stdout.readline()
        if not line:
            break
        text = line.decode("utf-8", "ignore").strip()
        if text.startswith("out_time_ms=") and progress_cb and total_seconds > 0:
            try:
                ms = int(text.split("=", 1)[1])
                frac = max(0.0, min(1.0, (ms / 1_000_000.0) / total_seconds))
                progress_cb(frac)
            except (ValueError, IndexError):
                pass
        elif text.startswith("progress=") and text.endswith("end"):
            if progress_cb:
                progress_cb(1.0)


async def detect_silences(
    settings: Settings,
    path: Path,
    noise_db: float,
    min_silence: float,
    total_seconds: float,
    progress_cb: Optional[ProgressCb] = None,
    register: Optional[RegisterCb] = None,
) -> List[Silence]:
    """Détecte les silences via le filtre ``silencedetect``.

    On lit tout le flux audio (sortie nulle) et on analyse la sortie du filtre.
    S'il n'y a pas de piste audio, la liste renvoyée est vide.
    """

    filt = f"silencedetect=noise={noise_db}dB:d={min_silence}"
    cmd = [
        settings.ffmpeg_bin,
        "-nostdin",
        "-hide_banner",
        "-i", str(path),
        "-map", "0:a?",            # piste audio si présente, sinon rien
        "-af", filt,
        "-f", "null",
        "-progress", "pipe:1",
        "-nostats",
        "-",
    ]

    proc = await _spawn(cmd)
    if register:
        register(proc)

    stderr_chunks: List[str] = []

    async def read_stderr() -> None:
        assert proc.stderr is not None
        while True:
            line = await proc.stderr.readline()
            if not line:
                break
            stderr_chunks.append(line.decode("utf-8", "ignore"))

    await asyncio.gather(
        _stream_progress(proc, total_seconds, progress_cb),
        read_stderr(),
    )
    await proc.wait()

    stderr_text = "".join(stderr_chunks)
    if proc.returncode not in (0, None):
        # Pas d'audio => code 0 en général ; une vraie erreur est signalée.
        if "Output file #0 does not contain any stream" not in stderr_text:
            raise FFmpegError(f"silencedetect a échoué : {stderr_text[-400:]}")
    return parse_silencedetect(stderr_text)


@dataclass
class EncodePlan:
    """Décrit comment une séquence sera encodée."""

    mode: str                  # "copy" | "encode"
    canvas: Optional[Tuple[int, int]]  # dimensions cible si ré-encodage/adaptation
    reason: str


def compute_canvas(
    src_w: int,
    src_h: int,
    aspect_w: int,
    aspect_h: int,
    max_long: int = 1920,
) -> Tuple[int, int]:
    """Calcule un cadre cible au ratio demandé, sans agrandissement artificiel.

    On part d'un cadre standard (ex. 1920x1080 ou 1080x1920) puis on le réduit
    si la vidéo source est de plus faible définition, afin de ne jamais
    agrandir inutilement le contenu.
    """

    if aspect_w >= aspect_h:  # paysage
        base_w = max_long
        base_h = round(max_long * aspect_h / aspect_w)
    else:                      # vertical
        base_h = max_long
        base_w = round(max_long * aspect_w / aspect_h)

    src_long = max(src_w, src_h)
    base_long = max(base_w, base_h)
    if src_long and src_long < base_long:
        scale = src_long / base_long
        base_w = round(base_w * scale)
        base_h = round(base_h * scale)

    cw = max(2, base_w - (base_w % 2))
    ch = max(2, base_h - (base_h % 2))
    return cw, ch


def ratios_match(width: Optional[int], height: Optional[int], aspect_w: int, aspect_h: int,
                 tol: float = 0.02) -> bool:
    if not width or not height:
        return False
    return abs((width / height) - (aspect_w / aspect_h)) <= tol


def plan_encode(
    meta: VideoMeta,
    aspect_w: int,
    aspect_h: int,
    force_precise: bool,
) -> EncodePlan:
    """Décide entre copie directe (rapide) et ré-encodage (précis/adaptation)."""

    needs_reframe = not ratios_match(meta.width, meta.height, aspect_w, aspect_h)
    if needs_reframe:
        canvas = compute_canvas(meta.width or 1920, meta.height or 1080, aspect_w, aspect_h)
        return EncodePlan("encode", canvas, "Adaptation du format (recadrage sans déformation).")
    if force_precise:
        return EncodePlan("encode", None, "Découpage précis demandé (ré-encodage).")
    return EncodePlan("copy", None, "Copie directe des flux (rapide, qualité d'origine).")


def _reframe_filter(canvas: Tuple[int, int]) -> str:
    cw, ch = canvas
    # Mise à l'échelle qui tient dans le cadre sans déformer, puis marges
    # neutres centrées. Pas de flou, pas d'étirement.
    return (
        f"scale={cw}:{ch}:force_original_aspect_ratio=decrease,"
        f"pad={cw}:{ch}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1"
    )


def build_cut_command(
    settings: Settings,
    source: Path,
    output: Path,
    start: float,
    duration: float,
    plan: EncodePlan,
    quality: str,
) -> List[str]:
    """Construit la commande ffmpeg pour une séquence."""

    cmd = [settings.ffmpeg_bin, "-nostdin", "-hide_banner", "-y"]

    if plan.mode == "copy":
        # Seek rapide avant -i ; copie directe des flux.
        cmd += [
            "-ss", f"{start:.3f}",
            "-i", str(source),
            "-t", f"{duration:.3f}",
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            "-map", "0",
        ]
    else:
        # Ré-encodage précis : seek précis après -i.
        crf = settings.x264_crf if quality != "high" else max(14, settings.x264_crf - 2)
        cmd += [
            "-ss", f"{start:.3f}",
            "-i", str(source),
            "-t", f"{duration:.3f}",
            "-map", "0:v:0",
            "-map", "0:a?",
        ]
        if plan.canvas is not None:
            cmd += ["-vf", _reframe_filter(plan.canvas)]
        cmd += [
            "-c:v", "libx264",
            "-preset", settings.x264_preset,
            "-crf", str(crf),
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", settings.audio_bitrate,
        ]

    cmd += [
        "-movflags", "+faststart",
        "-progress", "pipe:1",
        "-nostats",
        str(output),
    ]
    return cmd


async def cut_segment(
    settings: Settings,
    source: Path,
    output: Path,
    start: float,
    duration: float,
    plan: EncodePlan,
    quality: str,
    progress_cb: Optional[ProgressCb] = None,
    register: Optional[RegisterCb] = None,
) -> None:
    """Génère une séquence et vérifie le fichier produit."""

    cmd = build_cut_command(settings, source, output, start, duration, plan, quality)
    proc = await _spawn(cmd)
    if register:
        register(proc)

    stderr_chunks: List[str] = []

    async def read_stderr() -> None:
        assert proc.stderr is not None
        while True:
            line = await proc.stderr.readline()
            if not line:
                break
            stderr_chunks.append(line.decode("utf-8", "ignore"))

    await asyncio.gather(
        _stream_progress(proc, duration, progress_cb),
        read_stderr(),
    )
    await proc.wait()

    if proc.returncode != 0:
        tail = "".join(stderr_chunks)[-400:]
        raise FFmpegError(f"Échec du découpage de la séquence : {tail}")
    if not output.exists() or output.stat().st_size == 0:
        raise FFmpegError("La séquence générée est vide ou absente.")


async def verify_output(settings: Settings, path: Path) -> bool:
    """Vérifie qu'un fichier exporté possède bien une piste vidéo valide."""

    try:
        meta = await probe(settings, path)
    except FFmpegError:
        return False
    return meta.duration > 0 and meta.width is not None
