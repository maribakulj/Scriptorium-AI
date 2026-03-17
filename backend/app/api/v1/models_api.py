"""
Endpoints de gestion des modèles IA (R10 — préfixe /api/v1/).

POST /api/v1/settings/api-key       → valide la clé sans la stocker (R06)
GET  /api/v1/models                 → liste les modèles disponibles
POST /api/v1/models/refresh         → force la mise à jour de la liste
PUT  /api/v1/corpora/{id}/model     → associe un modèle à un corpus
GET  /api/v1/corpora/{id}/model     → modèle actif d'un corpus

Règle R06 : la clé API ne transite jamais vers la BDD — elle reste
            exclusivement dans les variables d'environnement.
"""
# 1. stdlib
import logging
from datetime import datetime, timezone

# 2. third-party
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

# 3. local
from app.models.corpus import CorpusModel
from app.models.database import get_db
from app.models.model_config_db import ModelConfigDB
from app.services.ai.model_registry import list_all_models

logger = logging.getLogger(__name__)

router = APIRouter(tags=["models"])


# ── Schémas ───────────────────────────────────────────────────────────────────

class ApiKeyRequest(BaseModel):
    api_key: str
    provider_type: str = "google_ai_studio"


class ApiKeyResponse(BaseModel):
    valid: bool
    provider: str
    model_count: int
    error: str | None = None


class ModelSelectRequest(BaseModel):
    model_id: str
    provider_type: str
    display_name: str = ""


class ModelConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    corpus_id: str
    provider_type: str
    selected_model_id: str
    selected_model_display_name: str
    updated_at: datetime


class ModelsRefreshResponse(BaseModel):
    models: list[dict]
    count: int
    refreshed_at: datetime


# ── Validation de clé API (isolé pour les tests) ──────────────────────────────

def _validate_api_key(api_key: str, provider_type: str) -> tuple[bool, int, str | None]:
    """Essaie de lister les modèles avec la clé fournie.

    Retourne (valid, model_count, error_message).
    Fonction isolée au niveau module pour être patchable dans les tests.
    """
    try:
        from google import genai  # import local pour éviter l'import top-level
        client = genai.Client(api_key=api_key)
        raw_models = list(client.models.list())
        vision_count = sum(
            1 for m in raw_models if "gemini" in (getattr(m, "name", "") or "").lower()
        )
        return True, vision_count, None
    except Exception as exc:
        return False, 0, str(exc)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/settings/api-key", response_model=ApiKeyResponse)
async def validate_api_key(body: ApiKeyRequest) -> ApiKeyResponse:
    """Valide qu'une clé API fonctionne (appel list_models).

    La clé N'EST PAS stockée (R06). Elle reste dans les variables d'env.
    """
    valid, count, error = _validate_api_key(body.api_key, body.provider_type)
    return ApiKeyResponse(
        valid=valid,
        provider=body.provider_type,
        model_count=count,
        error=error,
    )


@router.get("/models", response_model=list[dict])
async def get_models() -> list[dict]:
    """Liste tous les modèles disponibles sur les providers configurés."""
    models = list_all_models()
    return [m.model_dump() for m in models]


@router.post("/models/refresh", response_model=ModelsRefreshResponse)
async def refresh_models() -> ModelsRefreshResponse:
    """Force la mise à jour de la liste des modèles (vide le cache implicite)."""
    models = list_all_models()
    return ModelsRefreshResponse(
        models=[m.model_dump() for m in models],
        count=len(models),
        refreshed_at=datetime.now(timezone.utc),
    )


@router.put("/corpora/{corpus_id}/model", response_model=ModelConfigResponse)
async def set_corpus_model(
    corpus_id: str,
    body: ModelSelectRequest,
    db: AsyncSession = Depends(get_db),
) -> ModelConfigDB:
    """Associe un modèle IA à un corpus. Crée ou met à jour la configuration."""
    corpus = await db.get(CorpusModel, corpus_id)
    if corpus is None:
        raise HTTPException(status_code=404, detail="Corpus introuvable")

    display_name = body.display_name or body.model_id

    config = await db.get(ModelConfigDB, corpus_id)
    if config is None:
        config = ModelConfigDB(
            corpus_id=corpus_id,
            provider_type=body.provider_type,
            selected_model_id=body.model_id,
            selected_model_display_name=display_name,
            updated_at=datetime.now(timezone.utc),
        )
        db.add(config)
    else:
        config.provider_type = body.provider_type
        config.selected_model_id = body.model_id
        config.selected_model_display_name = display_name
        config.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(config)
    return config


@router.get("/corpora/{corpus_id}/model", response_model=ModelConfigResponse)
async def get_corpus_model(
    corpus_id: str, db: AsyncSession = Depends(get_db)
) -> ModelConfigDB:
    """Retourne la configuration du modèle IA actif pour un corpus."""
    corpus = await db.get(CorpusModel, corpus_id)
    if corpus is None:
        raise HTTPException(status_code=404, detail="Corpus introuvable")

    config = await db.get(ModelConfigDB, corpus_id)
    if config is None:
        raise HTTPException(
            status_code=404,
            detail="Aucun modèle configuré pour ce corpus",
        )
    return config
