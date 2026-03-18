"""
Endpoints de lecture des profils de corpus (R10 — préfixe /api/v1/).

GET  /api/v1/profiles
GET  /api/v1/profiles/{profile_id}

Les profils sont des fichiers JSON dans profiles/ (racine du dépôt).
Ils sont validés par CorpusProfile avant d'être retournés.
"""
# 1. stdlib
import json
import logging
from pathlib import Path

# 2. third-party
from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

# 3. local
from app.config import settings
from app.schemas.corpus_profile import CorpusProfile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profiles", tags=["profiles"])


def _load_profile(path: Path) -> CorpusProfile | None:
    """Charge et valide un fichier de profil JSON. Retourne None si invalide."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return CorpusProfile.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as exc:
        logger.warning("Profil invalide ignoré", extra={"path": str(path), "error": str(exc)})
        return None


@router.get("", response_model=list[dict])
async def list_profiles() -> list[dict]:
    """Retourne tous les profils valides du dossier profiles/."""
    if not settings.profiles_dir.is_dir():
        return []
    profiles = []
    for path in sorted(settings.profiles_dir.glob("*.json")):
        profile = _load_profile(path)
        if profile is not None:
            profiles.append(profile.model_dump())
    return profiles


@router.get("/{profile_id}", response_model=dict)
async def get_profile(profile_id: str) -> dict:
    """Retourne un profil par son id (nom du fichier sans extension)."""
    path = settings.profiles_dir / f"{profile_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Profil introuvable")
    profile = _load_profile(path)
    if profile is None:
        raise HTTPException(status_code=422, detail="Profil invalide")
    return profile.model_dump()
