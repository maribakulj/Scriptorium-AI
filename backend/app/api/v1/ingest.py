"""
Endpoints d'ingestion de corpus (R10 — préfixe /api/v1/).

POST /api/v1/corpora/{id}/ingest/files
POST /api/v1/corpora/{id}/ingest/iiif-manifest
POST /api/v1/corpora/{id}/ingest/iiif-images

Règle (R01) : aucune logique spécifique à un corpus particulier.
Règle : ingestion = création des PageModel en BDD uniquement.
         L'analyse IA est déclenchée séparément via /run.
"""
# 1. stdlib
import logging
import uuid
from pathlib import Path

# 2. third-party
import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

# 3. local
from app import config as _config_module
from app.models.corpus import CorpusModel, ManuscriptModel, PageModel
from app.models.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ingestion"])


# ── Schémas ───────────────────────────────────────────────────────────────────

class IIIFManifestRequest(BaseModel):
    manifest_url: str


class IIIFImagesRequest(BaseModel):
    urls: list[str]
    folio_labels: list[str]


class IngestResponse(BaseModel):
    corpus_id: str
    manuscript_id: str
    pages_created: int
    page_ids: list[str]


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_corpus_or_404(corpus_id: str, db: AsyncSession) -> CorpusModel:
    corpus = await db.get(CorpusModel, corpus_id)
    if corpus is None:
        raise HTTPException(status_code=404, detail="Corpus introuvable")
    return corpus


async def _get_or_create_manuscript(
    db: AsyncSession, corpus_id: str, title: str | None = None
) -> ManuscriptModel:
    """Retourne le premier manuscrit du corpus, ou en crée un par défaut."""
    result = await db.execute(
        select(ManuscriptModel).where(ManuscriptModel.corpus_id == corpus_id).limit(1)
    )
    ms = result.scalar_one_or_none()
    if ms is not None:
        return ms

    corpus = await db.get(CorpusModel, corpus_id)
    ms = ManuscriptModel(
        id=str(uuid.uuid4()),
        corpus_id=corpus_id,
        title=title or (corpus.title if corpus else corpus_id),
        total_pages=0,
    )
    db.add(ms)
    await db.flush()
    return ms


async def _next_sequence(db: AsyncSession, manuscript_id: str) -> int:
    """Retourne le prochain numéro de séquence disponible (max + 1, ou 1)."""
    result = await db.execute(
        select(func.max(PageModel.sequence)).where(
            PageModel.manuscript_id == manuscript_id
        )
    )
    max_seq = result.scalar_one_or_none()
    return (max_seq or 0) + 1


async def _create_page(
    db: AsyncSession,
    manuscript_id: str,
    corpus_id: str,
    folio_label: str,
    sequence: int,
    image_master_path: str | None = None,
) -> PageModel:
    page = PageModel(
        id=f"{corpus_id}-{folio_label}",
        manuscript_id=manuscript_id,
        folio_label=folio_label,
        sequence=sequence,
        image_master_path=image_master_path,
        processing_status="INGESTED",
    )
    db.add(page)
    return page


async def _fetch_json_manifest(url: str) -> dict:
    """Télécharge un manifest IIIF. Fonction isolée pour faciliter les tests."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, follow_redirects=True, timeout=30.0)
        resp.raise_for_status()
        return resp.json()


def _extract_canvas_label(canvas: dict, index: int) -> str:
    """Extrait le folio_label d'un canvas IIIF (3.0 ou 2.x)."""
    label = canvas.get("label")
    if isinstance(label, dict):
        for lang in ("none", "en", "fr", "la"):
            values = label.get(lang)
            if values:
                return (values[0] if isinstance(values, list) else str(values)).strip()
    elif isinstance(label, str) and label.strip():
        return label.strip()
    return f"f{index + 1:03d}r"


def _extract_canvas_image_url(canvas: dict) -> str | None:
    """Extrait l'URL de l'image principale d'un canvas IIIF (3.0 ou 2.x)."""
    # IIIF 3.0
    items = canvas.get("items") or []
    if items:
        ann_items = (items[0].get("items") or []) if items else []
        if ann_items:
            body = ann_items[0].get("body") or {}
            if isinstance(body, dict):
                return body.get("id") or body.get("@id")
    # IIIF 2.x
    images = canvas.get("images") or []
    if images:
        resource = images[0].get("resource") or {}
        return resource.get("@id")
    # Fallback : ID du canvas
    return canvas.get("id") or canvas.get("@id")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/corpora/{corpus_id}/ingest/files", response_model=IngestResponse, status_code=201)
async def ingest_files(
    corpus_id: str,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
) -> IngestResponse:
    """Ingère une liste de fichiers images (multipart/form-data).

    Chaque fichier crée un PageModel. Le fichier est copié dans
    data/corpora/{slug}/masters/{folio_label}/{filename}.
    """
    corpus = await _get_corpus_or_404(corpus_id, db)
    ms = await _get_or_create_manuscript(db, corpus_id)
    seq = await _next_sequence(db, ms.id)

    created: list[PageModel] = []
    for i, upload in enumerate(files):
        filename = Path(upload.filename or f"file_{i}").name
        folio_label = Path(filename).stem  # nom sans extension

        master_dir = (
            _config_module.settings.data_dir
            / "corpora"
            / corpus.slug
            / "masters"
            / folio_label
        )
        master_dir.mkdir(parents=True, exist_ok=True)
        master_path = master_dir / filename
        content = await upload.read()
        master_path.write_bytes(content)

        page = await _create_page(
            db, ms.id, corpus.slug, folio_label, seq + i,
            image_master_path=str(master_path),
        )
        created.append(page)

    ms.total_pages = (ms.total_pages or 0) + len(created)
    await db.commit()

    logger.info(
        "Fichiers ingérés",
        extra={"corpus_id": corpus_id, "count": len(created)},
    )
    return IngestResponse(
        corpus_id=corpus_id,
        manuscript_id=ms.id,
        pages_created=len(created),
        page_ids=[p.id for p in created],
    )


@router.post("/corpora/{corpus_id}/ingest/iiif-manifest", response_model=IngestResponse, status_code=201)
async def ingest_iiif_manifest(
    corpus_id: str,
    body: IIIFManifestRequest,
    db: AsyncSession = Depends(get_db),
) -> IngestResponse:
    """Télécharge un manifest IIIF, extrait les canvases et crée les PageModel."""
    corpus = await _get_corpus_or_404(corpus_id, db)

    try:
        manifest = await _fetch_json_manifest(body.manifest_url)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Erreur HTTP lors du téléchargement du manifest : {exc.response.status_code}",
        )
    except (httpx.RequestError, httpx.TimeoutException) as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Erreur réseau lors du téléchargement du manifest : {exc}",
        )

    # Détecte le format IIIF (3.0 vs 2.x)
    canvases: list[dict] = manifest.get("items") or []
    if not canvases:
        sequences = manifest.get("sequences") or []
        canvases = sequences[0].get("canvases", []) if sequences else []

    if not canvases:
        raise HTTPException(
            status_code=422,
            detail="Le manifest IIIF ne contient aucun canvas (items vide)",
        )

    # Titre du manuscrit depuis le manifest
    ms_title_raw = manifest.get("label") or {}
    if isinstance(ms_title_raw, dict):
        for lang in ("none", "fr", "en"):
            v = ms_title_raw.get(lang)
            if v:
                ms_title = v[0] if isinstance(v, list) else str(v)
                break
        else:
            ms_title = corpus.title
    elif isinstance(ms_title_raw, str):
        ms_title = ms_title_raw
    else:
        ms_title = corpus.title

    ms = await _get_or_create_manuscript(db, corpus_id, title=ms_title)
    seq = await _next_sequence(db, ms.id)

    created: list[PageModel] = []
    for i, canvas in enumerate(canvases):
        folio_label = _extract_canvas_label(canvas, i)
        image_url = _extract_canvas_image_url(canvas)
        page = await _create_page(
            db, ms.id, corpus.slug, folio_label, seq + i,
            image_master_path=image_url,
        )
        created.append(page)

    ms.total_pages = (ms.total_pages or 0) + len(created)
    await db.commit()

    logger.info(
        "Manifest IIIF ingéré",
        extra={"corpus_id": corpus_id, "url": body.manifest_url, "pages": len(created)},
    )
    return IngestResponse(
        corpus_id=corpus_id,
        manuscript_id=ms.id,
        pages_created=len(created),
        page_ids=[p.id for p in created],
    )


@router.post("/corpora/{corpus_id}/ingest/iiif-images", response_model=IngestResponse, status_code=201)
async def ingest_iiif_images(
    corpus_id: str,
    body: IIIFImagesRequest,
    db: AsyncSession = Depends(get_db),
) -> IngestResponse:
    """Ingère une liste d'URLs d'images IIIF directes.

    urls et folio_labels doivent avoir la même longueur.
    """
    if len(body.urls) != len(body.folio_labels):
        raise HTTPException(
            status_code=422,
            detail=f"urls ({len(body.urls)}) et folio_labels ({len(body.folio_labels)}) doivent avoir la même longueur",
        )
    if not body.urls:
        raise HTTPException(status_code=422, detail="La liste d'URLs est vide")

    corpus = await _get_corpus_or_404(corpus_id, db)
    ms = await _get_or_create_manuscript(db, corpus_id)
    seq = await _next_sequence(db, ms.id)

    created: list[PageModel] = []
    for i, (url, folio_label) in enumerate(zip(body.urls, body.folio_labels)):
        page = await _create_page(
            db, ms.id, corpus.slug, folio_label, seq + i,
            image_master_path=url,
        )
        created.append(page)

    ms.total_pages = (ms.total_pages or 0) + len(created)
    await db.commit()

    logger.info(
        "Images IIIF ingérées",
        extra={"corpus_id": corpus_id, "count": len(created)},
    )
    return IngestResponse(
        corpus_id=corpus_id,
        manuscript_id=ms.id,
        pages_created=len(created),
        page_ids=[p.id for p in created],
    )
