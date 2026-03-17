"""
Endpoints d'export documentaire (R10 — préfixe /api/v1/).

GET  /api/v1/manuscripts/{manuscript_id}/iiif-manifest  → JSON
GET  /api/v1/manuscripts/{manuscript_id}/mets           → XML
GET  /api/v1/pages/{page_id}/alto                       → XML
GET  /api/v1/manuscripts/{manuscript_id}/export.zip     → ZIP

Règle (R02) : toutes les sorties sont générées depuis les PageMasters
(master.json), jamais depuis les réponses brutes de l'IA.
"""
# 1. stdlib
import io
import json
import logging
import zipfile
from pathlib import Path

# 2. third-party
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# 3. local
from app import config as _config_module
from app.models.corpus import CorpusModel, ManuscriptModel, PageModel
from app.models.database import get_db
from app.schemas.page_master import PageMaster
from app.services.export.alto import generate_alto
from app.services.export.iiif import generate_manifest
from app.services.export.mets import generate_mets

logger = logging.getLogger(__name__)

router = APIRouter(tags=["export"])


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _load_manuscript_with_masters(
    manuscript_id: str,
    db: AsyncSession,
) -> tuple[ManuscriptModel, CorpusModel, list[PageMaster]]:
    """Charge un manuscrit, son corpus et tous ses PageMasters.

    Raises:
        HTTPException 404: si le manuscrit ou son corpus est introuvable.
        HTTPException 404: si aucun master.json n'est disponible.
    """
    manuscript = await db.get(ManuscriptModel, manuscript_id)
    if manuscript is None:
        raise HTTPException(status_code=404, detail="Manuscrit introuvable")

    corpus = await db.get(CorpusModel, manuscript.corpus_id)
    if corpus is None:
        raise HTTPException(status_code=404, detail="Corpus introuvable")

    # Pages dans l'ordre de séquence
    result = await db.execute(
        select(PageModel)
        .where(PageModel.manuscript_id == manuscript_id)
        .order_by(PageModel.sequence)
    )
    pages = list(result.scalars().all())

    masters: list[PageMaster] = []
    for page in pages:
        master = _read_master_json(corpus.slug, page.id)
        if master is not None:
            masters.append(master)

    if not masters:
        raise HTTPException(
            status_code=404,
            detail="Aucun master.json disponible pour ce manuscrit",
        )

    return manuscript, corpus, masters


def _read_master_json(corpus_slug: str, page_id: str) -> PageMaster | None:
    """Lit le master.json d'une page depuis data/. Retourne None si absent."""
    path = (
        _config_module.settings.data_dir
        / "corpora"
        / corpus_slug
        / "pages"
        / page_id
        / "master.json"
    )
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    return PageMaster.model_validate(raw)


def _build_manuscript_meta(
    manuscript: ManuscriptModel, corpus: CorpusModel
) -> dict:
    return {
        "manuscript_id": manuscript.id,
        "label": manuscript.title,
        "corpus_slug": corpus.slug,
        "shelfmark": manuscript.shelfmark,
        "date_label": manuscript.date_label,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/manuscripts/{manuscript_id}/iiif-manifest")
async def get_iiif_manifest(
    manuscript_id: str, db: AsyncSession = Depends(get_db)
) -> dict:
    """Génère et retourne le Manifest IIIF 3.0 du manuscrit (R02)."""
    manuscript, corpus, masters = await _load_manuscript_with_masters(
        manuscript_id, db
    )
    meta = _build_manuscript_meta(manuscript, corpus)
    manifest = generate_manifest(
        masters, meta, _config_module.settings.base_url
    )
    logger.info(
        "Manifest IIIF servi",
        extra={"manuscript_id": manuscript_id, "pages": len(masters)},
    )
    return manifest


@router.get("/manuscripts/{manuscript_id}/mets")
async def get_mets(
    manuscript_id: str, db: AsyncSession = Depends(get_db)
) -> Response:
    """Génère et retourne le METS XML du manuscrit (R02)."""
    manuscript, corpus, masters = await _load_manuscript_with_masters(
        manuscript_id, db
    )
    meta = _build_manuscript_meta(manuscript, corpus)
    mets_xml = generate_mets(masters, meta)
    return Response(
        content=mets_xml,
        media_type="application/xml; charset=utf-8",
    )


@router.get("/pages/{page_id}/alto")
async def get_alto(page_id: str, db: AsyncSession = Depends(get_db)) -> Response:
    """Génère et retourne l'ALTO XML d'une page (R02)."""
    page = await db.get(PageModel, page_id)
    if page is None:
        raise HTTPException(status_code=404, detail="Page introuvable")

    manuscript = await db.get(ManuscriptModel, page.manuscript_id)
    corpus = await db.get(CorpusModel, manuscript.corpus_id)

    master = _read_master_json(corpus.slug, page_id)
    if master is None:
        raise HTTPException(
            status_code=404,
            detail="master.json introuvable — la page n'a pas encore été analysée",
        )

    alto_xml = generate_alto(master)
    return Response(
        content=alto_xml,
        media_type="application/xml; charset=utf-8",
    )


@router.get("/manuscripts/{manuscript_id}/export.zip")
async def get_export_zip(
    manuscript_id: str, db: AsyncSession = Depends(get_db)
) -> StreamingResponse:
    """Génère et retourne un ZIP contenant manifest.json + mets.xml + alto par page.

    Structure du ZIP :
      manifest.json
      mets.xml
      alto/{page_id}.xml
    """
    manuscript, corpus, masters = await _load_manuscript_with_masters(
        manuscript_id, db
    )
    meta = _build_manuscript_meta(manuscript, corpus)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        # manifest.json
        manifest = generate_manifest(
            masters, meta, _config_module.settings.base_url
        )
        zf.writestr(
            "manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2),
        )

        # mets.xml
        mets_xml = generate_mets(masters, meta)
        zf.writestr("mets.xml", mets_xml)

        # alto/{page_id}.xml
        for master in masters:
            alto_xml = generate_alto(master)
            zf.writestr(f"alto/{master.page_id}.xml", alto_xml)

    buf.seek(0)

    filename = f"{manuscript_id}.zip"
    logger.info(
        "Export ZIP généré",
        extra={"manuscript_id": manuscript_id, "pages": len(masters)},
    )
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
