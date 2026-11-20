"""Fonctions de sécurité : noms de fichiers, chemins, accès."""

from __future__ import annotations

import os
import re
import secrets
import unicodedata
from pathlib import Path
from typing import Set

# Caractères autorisés dans un nom de base (sans extension).
_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")
_MULTI_DASH = re.compile(r"-{2,}")


def sanitize_basename(name: str, fallback: str = "video", max_len: int = 80) -> str:
    """Nettoie un nom de fichier fourni par l'utilisateur.

    - translittère les accents,
    - ne garde que ``[A-Za-z0-9._-]``,
    - supprime les séquences ``..`` et les séparateurs de chemin,
    - borne la longueur.
    """

    if not name:
        return fallback

    # Retirer tout chemin éventuel.
    name = os.path.basename(name)
    # Translittération ASCII.
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    # Remplacer les espaces par des underscores.
    name = name.replace(" ", "_")
    # Remplacer tout caractère non autorisé.
    name = _SAFE_RE.sub("_", name)
    # Neutraliser les points successifs (évite ".." et extensions trompeuses).
    name = name.replace("..", "_")
    name = name.strip("._-")
    name = _MULTI_DASH.sub("-", name)

    if not name:
        return fallback
    return name[:max_len]


def unique_name(base: str, ext: str, existing: Set[str]) -> str:
    """Garantit l'unicité d'un nom de fichier dans un ensemble donné."""

    ext = ext.lstrip(".")
    candidate = f"{base}.{ext}"
    i = 1
    while candidate.lower() in {e.lower() for e in existing}:
        candidate = f"{base}_{i}.{ext}"
        i += 1
    existing.add(candidate)
    return candidate


def new_token(nbytes: int = 24) -> str:
    """Génère un identifiant/token aléatoire sûr, utilisable dans une URL."""

    return secrets.token_urlsafe(nbytes)


def is_within(base: Path, target: Path) -> bool:
    """Vérifie que ``target`` est bien situé à l'intérieur de ``base``.

    Protège contre les traversées de répertoire (``..``) entre sessions.
    """

    try:
        base_r = base.resolve()
        target_r = target.resolve()
    except (OSError, RuntimeError):
        return False
    return base_r == target_r or base_r in target_r.parents


def safe_join(base: Path, *parts: str) -> Path:
    """Joint des segments de chemin et vérifie le confinement dans ``base``.

    Lève ``ValueError`` si le résultat sort de ``base``.
    """

    target = base.joinpath(*parts)
    if not is_within(base, target):
        raise ValueError("Chemin non autorisé (hors du répertoire de session).")
    return target
