"""
Endpoints CRUD pour les corpus (R10 — préfixe /api/v1/).

GET    /api/v1/corpora
POST   /api/v1/corpora
GET    /api/v1/corpora/{corpus_id}
DELETE /api/v1/corpora/{corpus_id}
GET    /api/v1/corpora/{corpus_id}/manuscripts

Règle : toute logique métier est dans les services, jamais dans les routers.
"""
# 1. stdlib
import uuid
from datetime import datetime, timezone

# 2. third-party
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# 3. local
from app.models.corpus import CorpusModel, ManuscriptModel
from app.models.database import get_db

router = APIRouter(prefix="/corpora", tags=["corpora"])


# ── Schémas de requête / réponse ─────────────────────────────────────────────

class CorpusCreate(BaseModel):
    slug: str
    title: str
    profile_id: str


class CorpusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str
    title: str
    profile_id: str
    created_at: datetime
    updated_at: datetime


class ManuscriptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    corpus_id: str
    title: str
    shelfmark: str | None
    date_label: str | None
    total_pages: int


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("", response_model=list[CorpusResponse])
async def list_corpora(db: AsyncSession = Depends(get_db)) -> list[CorpusModel]:
    """Retourne tous les corpus enregistrés."""
    result = await db.execute(select(CorpusModel))
    return list(result.scalars().all())


@router.post("", response_model=CorpusResponse, status_code=201)
async def create_corpus(
    body: CorpusCreate, db: AsyncSession = Depends(get_db)
) -> CorpusModel:
    """Crée un nouveau corpus. Le slug doit être unique."""
    # Vérifier unicité du slug
    existing = await db.execute(
        select(CorpusModel).where(CorpusModel.slug == body.slug)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail=f"Slug «{body.slug}» déjà utilisé")

    now = datetime.now(timezone.utc)
    corpus = CorpusModel(
        id=str(uuid.uuid4()),
        slug=body.slug,
        title=body.title,
        profile_id=body.profile_id,
        created_at=now,
        updated_at=now,
    )
    db.add(corpus)
    await db.commit()
    await db.refresh(corpus)
    return corpus


@router.get("/{corpus_id}", response_model=CorpusResponse)
async def get_corpus(corpus_id: str, db: AsyncSession = Depends(get_db)) -> CorpusModel:
    """Retourne un corpus par son id."""
    corpus = await db.get(CorpusModel, corpus_id)
    if corpus is None:
        raise HTTPException(status_code=404, detail="Corpus introuvable")
    return corpus


@router.delete("/{corpus_id}", status_code=204)
async def delete_corpus(corpus_id: str, db: AsyncSession = Depends(get_db)) -> None:
    """Supprime un corpus (cascade sur les manuscrits et pages associés)."""
    corpus = await db.get(CorpusModel, corpus_id)
    if corpus is None:
        raise HTTPException(status_code=404, detail="Corpus introuvable")
    await db.delete(corpus)
    await db.commit()


@router.get("/{corpus_id}/manuscripts", response_model=list[ManuscriptResponse])
async def list_manuscripts(
    corpus_id: str, db: AsyncSession = Depends(get_db)
) -> list[ManuscriptModel]:
    """Retourne tous les manuscrits d'un corpus."""
    corpus = await db.get(CorpusModel, corpus_id)
    if corpus is None:
        raise HTTPException(status_code=404, detail="Corpus introuvable")
    result = await db.execute(
        select(ManuscriptModel).where(ManuscriptModel.corpus_id == corpus_id)
    )
    return list(result.scalars().all())
