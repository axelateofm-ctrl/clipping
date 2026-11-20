"""Calcul des frontières de découpage.

Ce module est volontairement **pur** (aucune dépendance à FFmpeg) afin de
pouvoir être testé rapidement et de manière déterministe.

Principe
--------
On parcourt la vidéo du début à la fin en produisant une suite continue de
frontières temporelles qui couvrent toute la durée, sans trou ni
chevauchement. Chaque segment commence exactement là où le précédent se
termine.

Pour chaque segment on vise une durée cible (par défaut 70 s). On cherche un
silence « pertinent » situé dans une fenêtre juste avant la durée maximale
(par défaut entre `cible - fenetre` et `cible`). Si un silence convient, on y
place la coupe (coupe « silence »). Sinon on effectue une coupe temporelle
classique à la durée cible (coupe « time »).

Une détection de silence ne garantit jamais que la phrase est terminée : cette
fonction est une aide, pas une certitude.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


# Tolérance (secondes) pour considérer qu'un ratio/valeur est "égal".
EPS = 1e-6


@dataclass
class Silence:
    """Un intervalle de silence détecté dans la piste audio."""

    start: float
    end: float

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    @property
    def midpoint(self) -> float:
        return (self.start + self.end) / 2.0


@dataclass
class Segment:
    """Une séquence de sortie planifiée."""

    index: int
    start: float
    end: float
    cut_type: str  # "silence" | "time" | "final"

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    def as_dict(self) -> dict:
        return {
            "index": self.index,
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "duration": round(self.duration, 3),
            "cut_type": self.cut_type,
        }


@dataclass
class SplitPlan:
    duration: float
    target: float
    window: float
    segments: List[Segment] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "duration": round(self.duration, 3),
            "target": self.target,
            "window": self.window,
            "count": len(self.segments),
            "segments": [s.as_dict() for s in self.segments],
        }


def _silence_candidates(
    silences: List[Silence],
    silence_pad: float,
) -> List[float]:
    """Transforme les intervalles de silence en points de coupe candidats.

    On place le point de coupe peu après le début du silence (ou au milieu si
    le silence est très court), afin que la fin de la phrase précédente reste
    dans le segment courant et que le segment suivant démarre dans le calme.
    """

    candidates: List[float] = []
    for s in silences:
        if s.duration <= 0:
            continue
        offset = min(silence_pad, s.duration / 2.0)
        candidates.append(s.start + offset)
    candidates.sort()
    return candidates


def compute_segments(
    duration: float,
    silences: Optional[List[Silence]] = None,
    target: float = 70.0,
    window: float = 10.0,
    min_segment: float = 2.0,
    silence_pad: float = 0.15,
    smart: bool = True,
) -> SplitPlan:
    """Calcule la liste des segments.

    Parameters
    ----------
    duration:
        Durée totale de la vidéo (secondes).
    silences:
        Intervalles de silence détectés. Peut être vide ou ``None``.
    target:
        Durée cible d'un segment (secondes).
    window:
        Largeur de la fenêtre de recherche d'un silence, située *avant* la
        durée cible. Pour ``target=70`` et ``window=10`` la coupe idéale est
        recherchée entre 60 s et 70 s après le début du segment.
    min_segment:
        Durée minimale d'un segment issu d'une coupe silence (évite les
        micro-segments).
    silence_pad:
        Décalage appliqué après le début d'un silence pour placer la coupe.
    smart:
        Si ``False``, on ignore les silences (coupes temporelles pures).
    """

    if duration <= 0:
        return SplitPlan(duration=0.0, target=target, window=window, segments=[])
    if target <= 0:
        raise ValueError("La durée cible doit être strictement positive.")
    if window < 0:
        raise ValueError("La fenêtre de recherche ne peut pas être négative.")
    window = min(window, target)  # la fenêtre ne peut pas dépasser la cible

    candidates = _silence_candidates(silences or [], silence_pad) if smart else []

    segments: List[Segment] = []
    current = 0.0
    index = 1
    guard = 0

    while current < duration - EPS:
        guard += 1
        if guard > 10_000_000:  # garde-fou anti-boucle infinie
            raise RuntimeError("Boucle de découpage anormale.")

        ideal_end = current + target
        # Dernier segment : on prend tout ce qui reste.
        if ideal_end >= duration - EPS:
            segments.append(Segment(index, current, duration, "final"))
            break

        cut_lo = current + (target - window)
        cut_hi = ideal_end  # on ne dépasse jamais la durée cible

        chosen: Optional[float] = None
        if candidates:
            # Dernier silence <= cut_hi et >= cut_lo : la pause naturelle la
            # plus proche possible de la durée maximale.
            in_window = [c for c in candidates if cut_lo - EPS <= c <= cut_hi + EPS]
            # On impose aussi une durée minimale de segment.
            in_window = [c for c in in_window if c - current >= min_segment]
            if in_window:
                chosen = max(in_window)

        if chosen is not None:
            end = chosen
            cut_type = "silence"
        else:
            end = cut_hi
            cut_type = "time"

        # Sécurité : progression stricte.
        if end <= current + EPS:
            end = min(cut_hi, duration)
            cut_type = "time"
        if end >= duration - EPS:
            segments.append(Segment(index, current, duration, "final"))
            break

        segments.append(Segment(index, current, end, cut_type))
        current = end
        index += 1

    return SplitPlan(duration=duration, target=target, window=window, segments=segments)


def validate_plan(plan: SplitPlan, tolerance: float = 1e-3) -> List[str]:
    """Vérifie la cohérence d'un plan : continuité, ordre, couverture.

    Renvoie la liste des problèmes détectés (vide si tout est correct).
    """

    problems: List[str] = []
    segs = plan.segments
    if not segs:
        if plan.duration > tolerance:
            problems.append("Aucun segment pour une vidéo non vide.")
        return problems

    if abs(segs[0].start) > tolerance:
        problems.append("Le premier segment ne commence pas à 0.")
    if abs(segs[-1].end - plan.duration) > tolerance:
        problems.append("Le dernier segment ne couvre pas la fin de la vidéo.")

    for i, s in enumerate(segs):
        if s.end <= s.start + tolerance:
            problems.append(f"Segment {s.index} de durée nulle ou négative.")
        if i > 0:
            prev = segs[i - 1]
            if abs(s.start - prev.end) > tolerance:
                problems.append(
                    f"Discontinuité entre segment {prev.index} et {s.index} "
                    f"({prev.end:.3f} != {s.start:.3f})."
                )
            if s.start < prev.start:
                problems.append("Segments non ordonnés chronologiquement.")

    return problems


def parse_silencedetect(stderr: str) -> List[Silence]:
    """Analyse la sortie du filtre ``silencedetect`` de FFmpeg.

    FFmpeg écrit (sur stderr) des lignes du type::

        [silencedetect @ ...] silence_start: 12.345
        [silencedetect @ ...] silence_end: 13.001 | silence_duration: 0.656

    Un ``silence_start`` sans ``silence_end`` correspond à un silence qui dure
    jusqu'à la fin du fichier : il est ignoré (pas un point de coupe utile).
    """

    silences: List[Silence] = []
    pending_start: Optional[float] = None

    for raw in stderr.splitlines():
        line = raw.strip()
        if "silence_start:" in line:
            try:
                pending_start = float(line.split("silence_start:")[1].strip().split()[0])
            except (IndexError, ValueError):
                pending_start = None
        elif "silence_end:" in line and pending_start is not None:
            try:
                end = float(
                    line.split("silence_end:")[1].strip().split("|")[0].strip().split()[0]
                )
            except (IndexError, ValueError):
                continue
            if end > pending_start:
                silences.append(Silence(start=pending_start, end=end))
            pending_start = None

    return silences


def aspect_ratio_value(label: str) -> Tuple[int, int]:
    """Convertit un libellé de format en ratio (largeur, hauteur)."""

    mapping = {
        "16:9": (16, 9),
        "9:16": (9, 16),
    }
    if label not in mapping:
        raise ValueError(f"Format d'image non supporté : {label!r}")
    return mapping[label]
