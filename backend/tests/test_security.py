"""Tests de sécurité : noms de fichiers et confinement des chemins."""

from pathlib import Path

from app.security import (
    is_within,
    safe_join,
    sanitize_basename,
    unique_name,
)


def test_sanitize_basic():
    assert sanitize_basename("Podcast Omar Sy") == "Podcast_Omar_Sy"


def test_sanitize_accents():
    assert sanitize_basename("Vidéo Éàù") == "Video_Eau"


def test_sanitize_path_traversal():
    out = sanitize_basename("../../etc/passwd")
    assert "/" not in out
    assert ".." not in out


def test_sanitize_injection_chars():
    out = sanitize_basename("name; rm -rf / `whoami` $(id)")
    assert ";" not in out and "`" not in out and "$" not in out and " " not in out


def test_sanitize_empty_fallback():
    assert sanitize_basename("", fallback="video") == "video"
    assert sanitize_basename("///", fallback="x") == "x"


def test_unique_name():
    existing = set()
    a = unique_name("clip", "mp4", existing)
    b = unique_name("clip", "mp4", existing)
    c = unique_name("clip", "mp4", existing)
    assert a == "clip.mp4"
    assert b == "clip_1.mp4"
    assert c == "clip_2.mp4"


def test_is_within(tmp_path: Path):
    base = tmp_path / "jobs"
    base.mkdir()
    inside = base / "abc" / "f.mp4"
    assert is_within(base, inside)
    assert not is_within(base, tmp_path / "other")


def test_safe_join_rejects_escape(tmp_path: Path):
    base = tmp_path / "seg"
    base.mkdir()
    ok = safe_join(base, "clip.mp4")
    assert ok.name == "clip.mp4"
    try:
        safe_join(base, "../secret")
        assert False, "doit lever"
    except ValueError:
        pass
