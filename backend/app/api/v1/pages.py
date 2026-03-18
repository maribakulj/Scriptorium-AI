"""
Endpoints lecture et écriture des pages et de leur master.json (R10 — préfixe /api/v1/).

GET  /api/v1/pages/{page_id}
GET  /api/v1/pages/{page_id}/master-json
GET  /api/v1/pages/{page_id}/layers
POST /api/v1/pages/{page_id}/corrections
GET  /api/v1/pages/{page_id}/history

Règle (R02) : le master.json est la source canonique.
"""
# 1. stdlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# 2. third-party
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, ValidationError
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

class CorrectionsRequest(BaseModel):
    """Corrections partielles du master.json. Tous les champs sont optionnels.

    Si restore_to_version est fourni, les autres champs sont ignorés et la version
    indiquée est restaurée (avec incrémentation de editorial.version).
    """

    ocr_diplomatic_text: str | None = None
    editorial_status: str | None = None
    commentary_public: str | None = None
    commentary_scholarly: str | None = None
    region_validations: dict[str, str] | None = None
    restore_to_version: int | None = None


class VersionInfo(BaseModel):
    version: int
    saved_at: datetime
    status: str


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


# ── Helpers corrections & versioning ──────────────────────────────────────────

async def _get_page_dir(page: PageModel, db: AsyncSession) -> Path | None:
    """Retourne le répertoire data/corpora/{slug}/pages/{page.id} ou None."""
    manuscript = await db.get(ManuscriptModel, page.manuscript_id)
    if manuscript is None:
        return None
    corpus = await db.get(CorpusModel, manuscript.corpus_id)
    if corpus is None:
        return None
    return (
        _config_module.settings.data_dir
        / "corpora"
        / corpus.slug
        / "pages"
        / page.id
    )


def _archive_master(page_dir: Path, master: PageMaster) -> None:
    """Archive master.json sous master_v{version}.json avant toute modification."""
    archive_path = page_dir / f"master_v{master.editorial.version}.json"
    archive_path.write_text(
        json.dumps(master.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_master(page_dir: Path, master: PageMaster) -> None:
    """Écrit le master.json validé sur le disque."""
    master_path = page_dir / "master.json"
    master_path.write_text(
        json.dumps(master.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _apply_corrections_to_master(
    master: PageMaster, req: CorrectionsRequest
) -> PageMaster:
    """Applique les corrections partielles et incrémente editorial.version."""
    data: dict[str, Any] = master.model_dump(mode="json")

    if req.ocr_diplomatic_text is not None:
        if data.get("ocr") is None:
            data["ocr"] = {
                "diplomatic_text": "",
                "blocks": [],
                "lines": [],
                "language": "la",
                "confidence": 0.0,
                "uncertain_segments": [],
            }
        data["ocr"]["diplomatic_text"] = req.ocr_diplomatic_text

    if req.editorial_status is not None:
        data["editorial"]["status"] = req.editorial_status

    if req.commentary_public is not None:
        if data.get("commentary") is None:
            data["commentary"] = {"public": "", "scholarly": "", "claims": []}
        data["commentary"]["public"] = req.commentary_public

    if req.commentary_scholarly is not None:
        if data.get("commentary") is None:
            data["commentary"] = {"public": "", "scholarly": "", "claims": []}
        data["commentary"]["scholarly"] = req.commentary_scholarly

    if req.region_validations is not None:
        existing: dict[str, str] = (
            data.get("extensions", {}).get("region_validations") or {}
        )
        existing.update(req.region_validations)
        if "extensions" not in data:
            data["extensions"] = {}
        data["extensions"]["region_validations"] = existing

    data["editorial"]["version"] += 1
    return PageMaster.model_validate(data)


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


@router.post("/{page_id}/corrections")
async def apply_corrections(
    page_id: str,
    body: CorrectionsRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Applique des corrections partielles au master.json.

    Avant toute modification, l'état courant est archivé sous master_v{n}.json.
    editorial.version est incrémenté à chaque correction.
    Si restore_to_version est fourni, restaure la version archivée demandée.
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

    page_dir = await _get_page_dir(page, db)
    if page_dir is None:
        raise HTTPException(status_code=500, detail="Répertoire de page introuvable")

    if body.restore_to_version is not None:
        archive_path = page_dir / f"master_v{body.restore_to_version}.json"
        if not archive_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Version {body.restore_to_version} introuvable",
            )
        _archive_master(page_dir, master)
        old_data: dict[str, Any] = json.loads(archive_path.read_text(encoding="utf-8"))
        old_data["editorial"]["version"] = master.editorial.version + 1
        try:
            new_master = PageMaster.model_validate(old_data)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    else:
        _archive_master(page_dir, master)
        try:
            new_master = _apply_corrections_to_master(master, body)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    _write_master(page_dir, new_master)
    logger.info(
        "Corrections appliquées",
        extra={"page_id": page_id, "version": new_master.editorial.version},
    )
    return new_master.model_dump(mode="json")


@router.get("/{page_id}/history", response_model=list[VersionInfo])
async def get_page_history(
    page_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[VersionInfo]:
    """Liste les versions archivées du master.json (master_v*.json).

    Retourne [] si le répertoire de page n'existe pas encore.
    """
    page = await db.get(PageModel, page_id)
    if page is None:
        raise HTTPException(status_code=404, detail="Page introuvable")

    page_dir = await _get_page_dir(page, db)
    if page_dir is None:
        raise HTTPException(status_code=500, detail="Répertoire de page introuvable")

    if not page_dir.exists():
        return []

    versions: list[VersionInfo] = []
    for vpath in sorted(page_dir.glob("master_v*.json")):
        try:
            data = json.loads(vpath.read_text(encoding="utf-8"))
            version_num = data.get("editorial", {}).get("version", 0)
            status = data.get("editorial", {}).get("status", "machine_draft")
            saved_at = datetime.fromtimestamp(
                vpath.stat().st_mtime, tz=timezone.utc
            )
            versions.append(
                VersionInfo(version=version_num, saved_at=saved_at, status=status)
            )
        except (json.JSONDecodeError, KeyError, OSError):
            continue

    return sorted(versions, key=lambda v: v.version)
