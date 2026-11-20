"""Tests d'intégration FFmpeg.

Ces tests ne s'exécutent que si FFmpeg/FFprobe sont installés *et* si pydantic
est disponible. Sinon ils sont ignorés proprement (``skip``).

Ils génèrent une petite vidéo de test (source synthétique FFmpeg), puis
vérifient : lecture des métadonnées, détection de silence, découpage (copie et
ré-encodage), conversion de format 4:3 → 9:16, et validité des sorties via
ffprobe.
"""

import asyncio
import shutil

import pytest

pytest.importorskip("pydantic")

from app.config import Settings  # noqa: E402
from app import ffmpeg  # noqa: E402
from app.splitter import compute_segments  # noqa: E402

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="FFmpeg/FFprobe non installés",
)


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def settings():
    return Settings()


@pytest.fixture()
def sample_video(tmp_path, settings):
    """Crée une vidéo 6 s, 320x240 (4:3), avec une tonalité audio."""

    out = tmp_path / "sample.mp4"
    cmd = [
        settings.ffmpeg_bin, "-nostdin", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc=duration=6:size=320x240:rate=25",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=6",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest",
        str(out),
    ]
    code = asyncio.run(_exec(cmd))
    assert code == 0 and out.exists(), "Impossible de générer la vidéo de test."
    return out


async def _exec(cmd):
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, err = await proc.communicate()
    if proc.returncode != 0:
        print(err.decode("utf-8", "ignore"))
    return proc.returncode


def test_probe_reads_real_metadata(settings, sample_video):
    meta = _run(ffmpeg.probe(settings, sample_video))
    assert meta.width == 320 and meta.height == 240
    assert meta.has_audio is True
    assert 5.5 <= meta.duration <= 6.5
    assert meta.video_codec == "h264"


def test_silence_detection_runs(settings, sample_video):
    # Une tonalité continue n'a pas de silence : la liste peut être vide,
    # mais l'appel doit réussir sans erreur.
    silences = _run(
        ffmpeg.detect_silences(settings, sample_video, -35.0, 0.25, 6.0)
    )
    assert isinstance(silences, list)


def test_fast_copy_cut_produces_valid_file(settings, sample_video, tmp_path):
    out = tmp_path / "seg1.mp4"
    plan = ffmpeg.plan_encode(
        _run(ffmpeg.probe(settings, sample_video)), 4, 3, force_precise=False
    )
    assert plan.mode == "copy"  # même ratio, pas de précision forcée
    _run(ffmpeg.cut_segment(settings, sample_video, out, 0.0, 3.0, plan, "original"))
    assert out.exists() and out.stat().st_size > 0
    assert _run(ffmpeg.verify_output(settings, out)) is True


def test_reframe_to_vertical_9_16(settings, sample_video, tmp_path):
    meta = _run(ffmpeg.probe(settings, sample_video))
    plan = ffmpeg.plan_encode(meta, 9, 16, force_precise=False)
    assert plan.mode == "encode" and plan.canvas is not None
    cw, ch = plan.canvas
    # Ratio cible 9:16 respecté (à l'arrondi pair près).
    assert abs((cw / ch) - (9 / 16)) < 0.03
    out = tmp_path / "vertical.mp4"
    _run(ffmpeg.cut_segment(settings, sample_video, out, 0.0, 2.0, plan, "original"))
    res = _run(ffmpeg.probe(settings, out))
    assert res.width == cw and res.height == ch
    assert _run(ffmpeg.verify_output(settings, out)) is True


def test_full_plan_segments_cover_duration(settings, sample_video, tmp_path):
    meta = _run(ffmpeg.probe(settings, sample_video))
    plan = compute_segments(meta.duration, silences=[], target=2.0, window=0.5)
    # 6 s / 2 s -> 3 segments.
    assert len(plan.segments) == 3
    enc = ffmpeg.plan_encode(meta, 4, 3, force_precise=True)
    total = 0.0
    for i, seg in enumerate(plan.segments):
        out = tmp_path / f"part_{i}.mp4"
        _run(ffmpeg.cut_segment(settings, sample_video, out, seg.start, seg.duration, enc, "original"))
        res = _run(ffmpeg.probe(settings, out))
        assert res.duration > 0
        total += res.duration
    # La somme des durées produites approche la durée source.
    assert abs(total - meta.duration) < 1.0
