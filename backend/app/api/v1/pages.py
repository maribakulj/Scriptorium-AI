"""
Endpoints lecture des pages et de leur master.json (R10 — préfixe /api/v1/).

GET  /api/v1/pages/{page_id}
GET  /api/v1/pages/{page_id}/master-json
GET  /api/v1/pages/{page_id}/layers

Règle (R02) : le master.json est la source canonique. Ces endpoints le lisent
depuis data/ — ils ne reconstruisent jamais une réponse depuis d'autres sources.
"""
# 1. stdlib
import json
import logging
from pathlib import Path

# 2. third-party
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

# 3. local
from app import config as _config_module
from app.models.corpus import CorpusModel, ManuscriptModel, PageModel
from app.models.database import get_db
from app.schemas.annotation import LayerStatus
from app.schemas.corpus_profile import LayerType
from app.schemas.page_master import PageMaster

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/pages", tags=["pages"])


# ── Schémas de réponse ────────────────────────────────────────────────────────

class PageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    manuscript_id: str
    folio_label: str
    sequence: int
    image_master_path: str | None
    processing_status: str
    confidence_summary: float | None


class LayerInfo(BaseModel):
    layer_type: str
    status: str
    has_content: bool


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _load_master(
    page: PageModel,
    db: AsyncSession,
) -> PageMaster | None:
    """Lit et valide le master.json d'une page depuis data/.

    Retourne None si le fichier n'existe pas.
    """
    manuscript = await db.get(ManuscriptModel, page.manuscript_id)
    if manuscript is None:
        return None
    corpus = await db.get(CorpusModel, manuscript.corpus_id)
    if corpus is None:
        return None

    master_path = (
        _config_module.settings.data_dir
        / "corpora"
        / corpus.slug
        / "pages"
        / page.id
        / "master.json"
    )
    if not master_path.exists():
        return None

    raw = json.loads(master_path.read_text(encoding="utf-8"))
    return PageMaster.model_validate(raw)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/{page_id}", response_model=PageResponse)
async def get_page(page_id: str, db: AsyncSession = Depends(get_db)) -> PageModel:
    """Retourne les métadonnées BDD d'une page."""
    page = await db.get(PageModel, page_id)
    if page is None:
        raise HTTPException(status_code=404, detail="Page introuvable")
    return page


@router.get("/{page_id}/master-json")
async def get_master_json(
    page_id: str, db: AsyncSession = Depends(get_db)
) -> dict:
    """Retourne le PageMaster validé par Pydantic (source canonique R02)."""
    page = await db.get(PageModel, page_id)
    if page is None:
        raise HTTPException(status_code=404, detail="Page introuvable")

    master = await _load_master(page, db)
    if master is None:
        raise HTTPException(
            status_code=404,
            detail="master.json introuvable — la page n'a pas encore été analysée",
        )

    return master.model_dump(mode="json")


@router.get("/{page_id}/layers", response_model=list[LayerInfo])
async def get_page_layers(
    page_id: str, db: AsyncSession = Depends(get_db)
) -> list[LayerInfo]:
    """Liste les couches disponibles dans le master.json de la page.

    Une couche est présente si le champ correspondant est non-null dans le JSON.
    """
    page = await db.get(PageModel, page_id)
    if page is None:
        raise HTTPException(status_code=404, detail="Page introuvable")

    master = await _load_master(page, db)
    if master is None:
        raise HTTPException(
            status_code=404,
            detail="master.json introuvable — la page n'a pas encore été analysée",
        )

    layers: list[LayerInfo] = []

    # Couches toujours présentes après analyse primaire
    layers.append(
        LayerInfo(
            layer_type=LayerType.IMAGE.value,
            status=LayerStatus.DONE.value,
            has_content=bool(master.image),
        )
    )

    if master.ocr is not None:
        layers.append(
            LayerInfo(
                layer_type=LayerType.OCR_DIPLOMATIC.value,
                status=LayerStatus.DONE.value,
                has_content=bool(master.ocr.diplomatic_text),
            )
        )

    if master.translation is not None:
        if master.translation.fr:
            layers.append(
                LayerInfo(
                    layer_type=LayerType.TRANSLATION_FR.value,
                    status=LayerStatus.DONE.value,
                    has_content=True,
                )
            )
        if master.translation.en:
            layers.append(
                LayerInfo(
                    layer_type=LayerType.TRANSLATION_EN.value,
                    status=LayerStatus.DONE.value,
                    has_content=True,
                )
            )

    if master.summary is not None:
        layers.append(
            LayerInfo(
                layer_type=LayerType.SUMMARY.value,
                status=LayerStatus.DONE.value,
                has_content=bool(master.summary),
            )
        )

    if master.commentary is not None:
        if master.commentary.scholarly:
            layers.append(
                LayerInfo(
                    layer_type=LayerType.SCHOLARLY_COMMENTARY.value,
                    status=LayerStatus.DONE.value,
                    has_content=True,
                )
            )
        if master.commentary.public:
            layers.append(
                LayerInfo(
                    layer_type=LayerType.PUBLIC_COMMENTARY.value,
                    status=LayerStatus.DONE.value,
                    has_content=True,
                )
            )

    logger.info(
        "Couches listées",
        extra={"page_id": page_id, "count": len(layers)},
    )
    return layers
