"""
Tests des endpoints d'export /api/v1/ (Sprint 4 — Session A).

Stratégie :
  - BDD en mémoire avec corpus / manuscrit / pages créés directement
  - master.json mockés via monkeypatch sur Path.exists + Path.read_text
  - Vérifie : 200, 404, type de contenu, structure JSON/XML/ZIP

Tests :
- GET /api/v1/manuscripts/{id}/iiif-manifest → JSON IIIF 3.0 ou 404
- GET /api/v1/manuscripts/{id}/mets          → XML ou 404
- GET /api/v1/pages/{id}/alto               → XML ou 404
- GET /api/v1/manuscripts/{id}/export.zip   → ZIP ou 404
"""
# 1. stdlib
import io
import json
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

# 2. third-party
import pytest

# 3. local
from app.models.corpus import CorpusModel, ManuscriptModel, PageModel
from tests.conftest_api import async_client, db_session  # noqa: F401

_NOW = datetime.now(timezone.utc)
_IIIF_CONTEXT = "http://iiif.io/api/presentation/3/context.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _populate_db(db_session, n_pages: int = 2):
    """Crée corpus + manuscrit + n pages dans la BDD de test."""
    corpus = CorpusModel(
        id=str(uuid.uuid4()),
        slug="test-ms",
        title="Test Corpus",
        profile_id="medieval-illuminated",
        created_at=_NOW,
        updated_at=_NOW,
    )
    db_session.add(corpus)

    ms = ManuscriptModel(
        id=str(uuid.uuid4()),
        corpus_id=corpus.id,
        title="Test Manuscript",
        shelfmark="Latin 0001",
        date_label="XIIe siècle",
        total_pages=n_pages,
    )
    db_session.add(ms)

    pages = []
    for i in range(1, n_pages + 1):
        p = PageModel(
            id=f"test-ms-f{i:03d}r",
            manuscript_id=ms.id,
            folio_label=f"f{i:03d}r",
            sequence=i,
            image_master_path=f"/data/master/f{i:03d}r.tif",
            processing_status="ANALYZED",
        )
        db_session.add(p)
        pages.append(p)

    await db_session.commit()
    return corpus, ms, pages


def _make_master_json(page_id: str, folio_label: str, sequence: int) -> str:
    return json.dumps({
        "schema_version": "1.0",
        "page_id": page_id,
        "corpus_profile": "medieval-illuminated",
        "manuscript_id": "test-ms",
        "folio_label": folio_label,
        "sequence": sequence,
        "image": {
            "original_url": f"https://example.com/{page_id}.jpg",
            "derivative_web": f"/data/deriv/{page_id}.jpg",
            "thumbnail": f"/data/thumb/{page_id}.jpg",
            "width": 1500,
            "height": 2000,
        },
        "layout": {"regions": []},
        "ocr": {
            "diplomatic_text": "Text content",
            "blocks": [],
            "lines": [],
            "language": "la",
            "confidence": 0.9,
            "uncertain_segments": [],
        },
        "editorial": {
            "status": "machine_draft",
            "validated": False,
            "validated_by": None,
            "version": 1,
            "notes": [],
        },
    })


def _mock_master_files(monkeypatch, pages):
    """Patche Path.exists / Path.read_text pour simuler les master.json."""
    master_data = {
        p.id: _make_master_json(p.id, p.folio_label, p.sequence)
        for p in pages
    }

    def fake_exists(self: Path) -> bool:
        return any(p_id in str(self) for p_id in master_data)

    def fake_read_text(self: Path, **kwargs) -> str:
        for p_id, data in master_data.items():
            if p_id in str(self):
                return data
        raise FileNotFoundError(str(self))

    monkeypatch.setattr(Path, "exists", fake_exists)
    monkeypatch.setattr(Path, "read_text", fake_read_text)


# ---------------------------------------------------------------------------
# GET /api/v1/manuscripts/{id}/iiif-manifest
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_iiif_manifest_not_found(async_client):
    response = await async_client.get("/api/v1/manuscripts/unknown/iiif-manifest")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_iiif_manifest_no_master_files(async_client, db_session, monkeypatch):
    _, ms, _ = await _populate_db(db_session, n_pages=1)
    monkeypatch.setattr(Path, "exists", lambda self: False)

    response = await async_client.get(f"/api/v1/manuscripts/{ms.id}/iiif-manifest")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_iiif_manifest_ok(async_client, db_session, monkeypatch):
    _, ms, pages = await _populate_db(db_session, n_pages=2)
    _mock_master_files(monkeypatch, pages)

    response = await async_client.get(f"/api/v1/manuscripts/{ms.id}/iiif-manifest")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_iiif_manifest_context(async_client, db_session, monkeypatch):
    _, ms, pages = await _populate_db(db_session, n_pages=2)
    _mock_master_files(monkeypatch, pages)

    data = (await async_client.get(f"/api/v1/manuscripts/{ms.id}/iiif-manifest")).json()
    assert data["@context"] == _IIIF_CONTEXT


@pytest.mark.asyncio
async def test_iiif_manifest_type(async_client, db_session, monkeypatch):
    _, ms, pages = await _populate_db(db_session, n_pages=2)
    _mock_master_files(monkeypatch, pages)

    data = (await async_client.get(f"/api/v1/manuscripts/{ms.id}/iiif-manifest")).json()
    assert data["type"] == "Manifest"


@pytest.mark.asyncio
async def test_iiif_manifest_canvas_count(async_client, db_session, monkeypatch):
    _, ms, pages = await _populate_db(db_session, n_pages=2)
    _mock_master_files(monkeypatch, pages)

    data = (await async_client.get(f"/api/v1/manuscripts/{ms.id}/iiif-manifest")).json()
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_iiif_manifest_id_contains_base_url(async_client, db_session, monkeypatch):
    _, ms, pages = await _populate_db(db_session, n_pages=1)
    _mock_master_files(monkeypatch, pages)

    data = (await async_client.get(f"/api/v1/manuscripts/{ms.id}/iiif-manifest")).json()
    assert data["id"].startswith("http")


# ---------------------------------------------------------------------------
# GET /api/v1/manuscripts/{id}/mets
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mets_not_found(async_client):
    response = await async_client.get("/api/v1/manuscripts/unknown/mets")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_mets_ok(async_client, db_session, monkeypatch):
    _, ms, pages = await _populate_db(db_session, n_pages=2)
    _mock_master_files(monkeypatch, pages)

    response = await async_client.get(f"/api/v1/manuscripts/{ms.id}/mets")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_mets_content_type_xml(async_client, db_session, monkeypatch):
    _, ms, pages = await _populate_db(db_session, n_pages=1)
    _mock_master_files(monkeypatch, pages)

    response = await async_client.get(f"/api/v1/manuscripts/{ms.id}/mets")
    assert "xml" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_mets_body_starts_with_xml(async_client, db_session, monkeypatch):
    _, ms, pages = await _populate_db(db_session, n_pages=1)
    _mock_master_files(monkeypatch, pages)

    response = await async_client.get(f"/api/v1/manuscripts/{ms.id}/mets")
    assert response.text.lstrip().startswith("<?xml")


@pytest.mark.asyncio
async def test_mets_contains_mets_root(async_client, db_session, monkeypatch):
    _, ms, pages = await _populate_db(db_session, n_pages=1)
    _mock_master_files(monkeypatch, pages)

    text = (await async_client.get(f"/api/v1/manuscripts/{ms.id}/mets")).text
    assert "mets" in text.lower()


# ---------------------------------------------------------------------------
# GET /api/v1/pages/{id}/alto
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_alto_not_found(async_client):
    response = await async_client.get("/api/v1/pages/unknown-page/alto")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_alto_no_master_file(async_client, db_session, monkeypatch):
    _, ms, pages = await _populate_db(db_session, n_pages=1)
    monkeypatch.setattr(Path, "exists", lambda self: False)

    response = await async_client.get(f"/api/v1/pages/{pages[0].id}/alto")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_alto_ok(async_client, db_session, monkeypatch):
    _, ms, pages = await _populate_db(db_session, n_pages=1)
    _mock_master_files(monkeypatch, pages)

    response = await async_client.get(f"/api/v1/pages/{pages[0].id}/alto")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_alto_content_type_xml(async_client, db_session, monkeypatch):
    _, ms, pages = await _populate_db(db_session, n_pages=1)
    _mock_master_files(monkeypatch, pages)

    response = await async_client.get(f"/api/v1/pages/{pages[0].id}/alto")
    assert "xml" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_alto_body_is_xml(async_client, db_session, monkeypatch):
    _, ms, pages = await _populate_db(db_session, n_pages=1)
    _mock_master_files(monkeypatch, pages)

    response = await async_client.get(f"/api/v1/pages/{pages[0].id}/alto")
    assert response.text.lstrip().startswith("<?xml")


@pytest.mark.asyncio
async def test_alto_contains_alto_element(async_client, db_session, monkeypatch):
    _, ms, pages = await _populate_db(db_session, n_pages=1)
    _mock_master_files(monkeypatch, pages)

    text = (await async_client.get(f"/api/v1/pages/{pages[0].id}/alto")).text
    assert "alto" in text.lower() or "ALTO" in text


# ---------------------------------------------------------------------------
# GET /api/v1/manuscripts/{id}/export.zip
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_export_zip_not_found(async_client):
    response = await async_client.get("/api/v1/manuscripts/unknown/export.zip")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_export_zip_no_master_files(async_client, db_session, monkeypatch):
    _, ms, _ = await _populate_db(db_session, n_pages=1)
    monkeypatch.setattr(Path, "exists", lambda self: False)

    response = await async_client.get(f"/api/v1/manuscripts/{ms.id}/export.zip")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_export_zip_ok(async_client, db_session, monkeypatch):
    _, ms, pages = await _populate_db(db_session, n_pages=2)
    _mock_master_files(monkeypatch, pages)

    response = await async_client.get(f"/api/v1/manuscripts/{ms.id}/export.zip")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_export_zip_content_type(async_client, db_session, monkeypatch):
    _, ms, pages = await _populate_db(db_session, n_pages=1)
    _mock_master_files(monkeypatch, pages)

    response = await async_client.get(f"/api/v1/manuscripts/{ms.id}/export.zip")
    assert "zip" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_export_zip_contains_manifest(async_client, db_session, monkeypatch):
    _, ms, pages = await _populate_db(db_session, n_pages=2)
    _mock_master_files(monkeypatch, pages)

    response = await async_client.get(f"/api/v1/manuscripts/{ms.id}/export.zip")
    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        assert "manifest.json" in zf.namelist()


@pytest.mark.asyncio
async def test_export_zip_contains_mets(async_client, db_session, monkeypatch):
    _, ms, pages = await _populate_db(db_session, n_pages=2)
    _mock_master_files(monkeypatch, pages)

    response = await async_client.get(f"/api/v1/manuscripts/{ms.id}/export.zip")
    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        assert "mets.xml" in zf.namelist()


@pytest.mark.asyncio
async def test_export_zip_contains_alto_per_page(async_client, db_session, monkeypatch):
    _, ms, pages = await _populate_db(db_session, n_pages=2)
    _mock_master_files(monkeypatch, pages)

    response = await async_client.get(f"/api/v1/manuscripts/{ms.id}/export.zip")
    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        names = zf.namelist()
        alto_files = [n for n in names if n.startswith("alto/")]
        assert len(alto_files) == 2


@pytest.mark.asyncio
async def test_export_zip_manifest_is_valid_json(async_client, db_session, monkeypatch):
    _, ms, pages = await _populate_db(db_session, n_pages=1)
    _mock_master_files(monkeypatch, pages)

    response = await async_client.get(f"/api/v1/manuscripts/{ms.id}/export.zip")
    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        manifest_data = json.loads(zf.read("manifest.json").decode("utf-8"))
        assert manifest_data["@context"] == _IIIF_CONTEXT
        assert manifest_data["type"] == "Manifest"


@pytest.mark.asyncio
async def test_export_zip_content_disposition(async_client, db_session, monkeypatch):
    _, ms, pages = await _populate_db(db_session, n_pages=1)
    _mock_master_files(monkeypatch, pages)

    response = await async_client.get(f"/api/v1/manuscripts/{ms.id}/export.zip")
    cd = response.headers.get("content-disposition", "")
    assert "attachment" in cd
    assert ".zip" in cd
