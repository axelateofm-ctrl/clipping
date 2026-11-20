"""Tests de la logique PURE de découpage (sans FFmpeg)."""

from app.splitter import (
    Silence,
    compute_segments,
    parse_silencedetect,
    validate_plan,
    aspect_ratio_value,
)


def _assert_covers(plan, duration, tol=1e-3):
    problems = validate_plan(plan, tolerance=tol)
    assert problems == [], f"Plan incohérent : {problems}"
    assert abs(plan.segments[0].start) < tol
    assert abs(plan.segments[-1].end - duration) < tol
    # continuité stricte
    for a, b in zip(plan.segments, plan.segments[1:]):
        assert abs(a.end - b.start) < tol
        assert b.start > a.start


def test_cinq_minutes_sans_silence():
    duration = 5 * 60
    plan = compute_segments(duration, silences=[], target=70, window=10)
    _assert_covers(plan, duration)
    # 300 / 70 ≈ 4.28 → 5 segments (le dernier plus court)
    assert len(plan.segments) == 5
    # toutes les coupes non finales sont "time" (aucun silence fourni)
    assert all(s.cut_type == "time" for s in plan.segments[:-1])
    assert plan.segments[-1].cut_type == "final"


def test_trente_minutes():
    duration = 30 * 60
    plan = compute_segments(duration, silences=[], target=70, window=10)
    _assert_covers(plan, duration)
    # Aucune séquence ne dépasse la cible.
    assert all(s.duration <= 70 + 1e-6 for s in plan.segments)


def test_sans_audio_equivaut_a_sans_silence():
    duration = 200.0
    plan = compute_segments(duration, silences=None, target=70, window=10)
    _assert_covers(plan, duration)
    assert all(s.cut_type in ("time", "final") for s in plan.segments)


def test_derniere_partie_plus_courte_que_cible():
    duration = 150.0  # 70 + 70 + 10
    plan = compute_segments(duration, silences=[], target=70, window=10)
    _assert_covers(plan, duration)
    assert len(plan.segments) == 3
    last = plan.segments[-1]
    assert last.cut_type == "final"
    assert abs(last.duration - 10.0) < 1e-3


def test_coupe_sur_silence_privilegie_pause_proche_du_max():
    duration = 200.0
    # Silences à 63s et 68s : on doit préférer 68 (plus proche de 70).
    silences = [Silence(62.8, 63.4), Silence(67.8, 68.6)]
    plan = compute_segments(duration, silences=silences, target=70, window=10)
    first = plan.segments[0]
    assert first.cut_type == "silence"
    # coupe placée peu après le début du silence à 67.8
    assert 67.8 <= first.end <= 68.6
    _assert_covers(plan, duration)


def test_nombreux_silences_restent_coherents():
    duration = 600.0
    silences = [Silence(t, t + 0.4) for t in range(5, 600, 5)]
    plan = compute_segments(duration, silences=silences, target=70, window=10)
    _assert_covers(plan, duration)
    # La plupart des coupes tombent sur un silence.
    silence_cuts = [s for s in plan.segments[:-1] if s.cut_type == "silence"]
    assert len(silence_cuts) >= len(plan.segments) - 2


def test_aucun_silence_dans_la_fenetre_repli_temporel():
    duration = 200.0
    # Silence hors fenêtre (à 30s, soit avant 60s) : ne doit pas être choisi.
    silences = [Silence(29.5, 31.0)]
    plan = compute_segments(duration, silences=silences, target=70, window=10)
    assert plan.segments[0].cut_type == "time"
    assert abs(plan.segments[0].end - 70.0) < 1e-6


def test_mode_non_intelligent_ignore_silences():
    duration = 200.0
    silences = [Silence(67.8, 68.6)]
    plan = compute_segments(duration, silences=silences, target=70, window=10, smart=False)
    assert all(s.cut_type in ("time", "final") for s in plan.segments)


def test_video_tres_courte_un_seul_segment():
    duration = 12.0
    plan = compute_segments(duration, silences=[], target=70, window=10)
    assert len(plan.segments) == 1
    assert plan.segments[0].cut_type == "final"
    _assert_covers(plan, duration)


def test_duree_nulle():
    plan = compute_segments(0.0, silences=[], target=70)
    assert plan.segments == []
    assert validate_plan(plan) == []


def test_parse_silencedetect():
    stderr = (
        "[silencedetect @ 0x1] silence_start: 12.345\n"
        "[silencedetect @ 0x1] silence_end: 13.001 | silence_duration: 0.656\n"
        "[silencedetect @ 0x1] silence_start: 40.0\n"  # sans fin -> ignoré
    )
    silences = parse_silencedetect(stderr)
    assert len(silences) == 1
    assert abs(silences[0].start - 12.345) < 1e-6
    assert abs(silences[0].end - 13.001) < 1e-6


def test_aspect_ratio_value():
    assert aspect_ratio_value("16:9") == (16, 9)
    assert aspect_ratio_value("9:16") == (9, 16)
    try:
        aspect_ratio_value("4:3")
        assert False, "doit lever"
    except ValueError:
        pass


def test_no_gap_or_overlap_property_random_like():
    # Couverture stricte sur une série de durées variées.
    for duration in (1.0, 69.9, 70.0, 70.1, 139.9, 140.0, 523.7, 1000.0):
        plan = compute_segments(duration, silences=[], target=70, window=10)
        total = sum(s.duration for s in plan.segments)
        assert abs(total - duration) < 1e-3, duration
