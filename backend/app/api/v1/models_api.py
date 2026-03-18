"""
Endpoints de gestion des modèles IA (R10 — préfixe /api/v1/).

GET  /api/v1/models                 → liste les modèles disponibles via les credentials env
POST /api/v1/models/refresh         → force la mise à jour de la liste
PUT  /api/v1/corpora/{id}/model     → associe un modèle à un corpus
GET  /api/v1/corpora/{id}/model     → modèle actif d'un corpus

Les clés API vivent exclusivement dans les secrets HuggingFace (variables d'environnement).
L'interface ne demande jamais de clé à l'utilisateur (R06).
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

@router.get("/models", response_model=list[dict])
async def get_models() -> list[dict]:
    """Liste tous les modèles disponibles sur les providers configurés en environnement."""
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
