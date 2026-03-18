"""
Endpoints de gestion des providers et modèles IA (R10 — préfixe /api/v1/).

GET  /api/v1/providers                      → providers détectés (disponibles ou non)
GET  /api/v1/providers/{provider_type}/models → modèles d'un provider
POST /api/v1/models/refresh                 → liste agrégée de tous les modèles
PUT  /api/v1/corpora/{id}/model             → associe un modèle à un corpus
GET  /api/v1/corpora/{id}/model             → modèle actif d'un corpus

Les clés API vivent exclusivement dans les secrets HuggingFace (variables
d'environnement). Le backend détecte automatiquement quels providers sont
disponibles au démarrage. L'interface ne demande jamais de clé (R06).
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
from app.schemas.model_config import ProviderType
from app.services.ai.model_registry import (
    get_available_providers,
    list_all_models,
    list_models_for_provider,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["models"])


# ── Schémas ───────────────────────────────────────────────────────────────────

class ProviderInfo(BaseModel):
    """Informations sur un provider IA détecté au démarrage."""
    provider_type: str
    display_name: str
    available: bool
    model_count: int


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


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/providers", response_model=list[ProviderInfo])
async def list_providers() -> list[dict]:
    """Liste tous les providers IA avec leur disponibilité.

    Un provider est disponible si la variable d'environnement correspondante
    est présente dans les secrets HuggingFace. Aucune clé n'est exposée.
    """
    return get_available_providers()


@router.get("/providers/{provider_type}/models", response_model=list[dict])
async def get_provider_models(provider_type: str) -> list[dict]:
    """Liste les modèles disponibles pour un provider spécifique."""
    try:
        ptype = ProviderType(provider_type)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail=f"Provider inconnu : {provider_type}. "
                   f"Valeurs acceptées : {[p.value for p in ProviderType]}",
        )
    try:
        models = list_models_for_provider(ptype)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.warning("Erreur listing models", extra={"provider": provider_type, "error": str(exc)})
        raise HTTPException(status_code=502, detail=f"Erreur provider : {exc}")
    return [m.model_dump() for m in models]


@router.post("/models/refresh", response_model=ModelsRefreshResponse)
async def refresh_models() -> ModelsRefreshResponse:
    """Force la mise à jour de la liste agrégée de tous les modèles disponibles."""
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
