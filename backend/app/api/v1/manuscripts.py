"""
Endpoints pour les manuscrits (R10 — préfixe /api/v1/).

GET  /api/v1/manuscripts/{manuscript_id}/pages
"""
# 2. third-party
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# 3. local
from app.models.corpus import ManuscriptModel, PageModel
from app.models.database import get_db

router = APIRouter(prefix="/manuscripts", tags=["manuscripts"])


class PageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    manuscript_id: str
    folio_label: str
    sequence: int
    image_master_path: str | None
    processing_status: str
    confidence_summary: float | None


@router.get("/{manuscript_id}/pages", response_model=list[PageResponse])
async def list_pages(
    manuscript_id: str, db: AsyncSession = Depends(get_db)
) -> list[PageModel]:
    """Retourne toutes les pages d'un manuscrit, triées par séquence."""
    ms = await db.get(ManuscriptModel, manuscript_id)
    if ms is None:
        raise HTTPException(status_code=404, detail="Manuscrit introuvable")
    result = await db.execute(
        select(PageModel)
        .where(PageModel.manuscript_id == manuscript_id)
        .order_by(PageModel.sequence)
    )
    return list(result.scalars().all())
