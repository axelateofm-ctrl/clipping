"""Singletons partagés et dépendances d'authentification."""

from __future__ import annotations

from typing import Optional, Set

from fastapi import Cookie, Header, HTTPException, status

from .config import Settings, get_settings
from .jobs import JobManager
from .storage import Storage

# Conteneur simple initialisé au démarrage de l'application.
settings: Settings = get_settings()
storage: Storage = Storage(settings)
manager: JobManager = JobManager(settings, storage)

# Jetons de session valides (protection d'accès facultative).
_valid_tokens: Set[str] = set()


def register_token(token: str) -> None:
    _valid_tokens.add(token)


def revoke_token(token: str) -> None:
    _valid_tokens.discard(token)


def is_protected() -> bool:
    return bool(settings.app_password)


def check_auth(
    axie_session: Optional[str] = Cookie(default=None),
    x_app_password: Optional[str] = Header(default=None),
) -> None:
    """Dépendance FastAPI : vérifie l'accès si une protection est activée."""

    if not is_protected():
        return
    if x_app_password and x_app_password == settings.app_password:
        return
    if axie_session and axie_session in _valid_tokens:
        return
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentification requise.",
    )
