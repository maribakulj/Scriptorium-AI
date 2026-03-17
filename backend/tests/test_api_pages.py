"""
Tests des endpoints /api/v1/pages/{id} (Sprint 4 — Session A).

Stratégie :
  - Données BDD créées directement via la session SQLAlchemy (pas via l'API)
  - master.json mockés via monkeypatch sur les méthodes de Path
  - Vérifie : 200, 404, structure du master.json, liste des couches

Tests :
- GET /api/v1/pages/{id}                → 200 ou 404
- GET /api/v1/pages/{id}/master-json    → 200 (mock), 404 (pas de fichier)
- GET /api/v1/pages/{id}/layers         → liste des couches disponibles
"""
# 1. stdlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

# 2. third-party
import pytest

# 3. local
from app.models.corpus import CorpusModel, ManuscriptModel, PageModel
from tests.conftest_api import async_client, db_session  # noqa: F401

_NOW = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Helpers — création de données de test en BDD
# ---------------------------------------------------------------------------

async def _create_corpus(db_session, slug="test-corpus"):
    corpus = CorpusModel(
        id=str(uuid.uuid4()),
        slug=slug,
        title="Test Corpus",
        profile_id="medieval-illuminated",
        created_at=_NOW,
        updated_at=_NOW,
    )
    db_session.add(corpus)
    await db_session.commit()
    await db_session.refresh(corpus)
    return corpus


async def _create_manuscript(db_session, corpus_id, ms_id=None):
    ms = ManuscriptModel(
        id=ms_id or str(uuid.uuid4()),
        corpus_id=corpus_id,
        title="Test Manuscript",
        shelfmark="Latin 8878",
        date_label="XIe siècle",
        total_pages=1,
    )
    db_session.add(ms)
    await db_session.commit()
    await db_session.refresh(ms)
    return ms


async def _create_page(db_session, manuscript_id, page_id=None):
    page = PageModel(
        id=page_id or str(uuid.uuid4()),
        manuscript_id=manuscript_id,
        folio_label="f001r",
        sequence=1,
        image_master_path="/data/master/f001r.tif",
        processing_status="ANALYZED",
        confidence_summary=0.87,
    )
    db_session.add(page)
    await db_session.commit()
    await db_session.refresh(page)
    return page


def _make_master_json(page_id: str, corpus_profile: str = "medieval-illuminated") -> str:
    data = {
        "schema_version": "1.0",
        "page_id": page_id,
        "corpus_profile": corpus_profile,
        "manuscript_id": "ms-test",
        "folio_label": "f001r",
        "sequence": 1,
        "image": {
            "original_url": "https://example.com/f001r.jpg",
            "derivative_web": "/data/deriv/f001r.jpg",
            "thumbnail": "/data/thumb/f001r.jpg",
            "width": 1500,
            "height": 2000,
        },
        "layout": {"regions": []},
        "ocr": {
            "diplomatic_text": "Incipit liber primus",
            "blocks": [],
            "lines": [],
            "language": "la",
            "confidence": 0.87,
            "uncertain_segments": [],
        },
        "translation": {"fr": "Ici commence le premier livre", "en": ""},
        "summary": {"short": "Prologue", "detailed": "Le prologue du commentaire"},
        "commentary": {
            "public": "Ce folio ouvre l'œuvre",
            "scholarly": "Analyse paléographique détaillée",
            "claims": [],
        },
        "editorial": {
            "status": "machine_draft",
            "validated": False,
            "validated_by": None,
            "version": 1,
            "notes": [],
        },
    }
    return json.dumps(data)


# ---------------------------------------------------------------------------
# GET /api/v1/pages/{id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_page_not_found(async_client):
    response = await async_client.get("/api/v1/pages/nonexistent-page")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_page_not_found_detail(async_client):
    response = await async_client.get("/api/v1/pages/unknown")
    assert "introuvable" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_page_ok(async_client, db_session):
    corpus = await _create_corpus(db_session)
    ms = await _create_manuscript(db_session, corpus.id)
    page = await _create_page(db_session, ms.id)

    response = await async_client.get(f"/api/v1/pages/{page.id}")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_page_fields(async_client, db_session):
    corpus = await _create_corpus(db_session)
    ms = await _create_manuscript(db_session, corpus.id)
    page = await _create_page(db_session, ms.id)

    data = (await async_client.get(f"/api/v1/pages/{page.id}")).json()
    assert data["id"] == page.id
    assert data["manuscript_id"] == ms.id
    assert data["folio_label"] == "f001r"
    assert data["sequence"] == 1
    assert data["processing_status"] == "ANALYZED"
    assert data["confidence_summary"] == pytest.approx(0.87)


# ---------------------------------------------------------------------------
# GET /api/v1/pages/{id}/master-json
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_master_json_page_not_found(async_client):
    response = await async_client.get("/api/v1/pages/unknown/master-json")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_master_json_file_not_found(async_client, db_session, monkeypatch):
    corpus = await _create_corpus(db_session)
    ms = await _create_manuscript(db_session, corpus.id)
    page = await _create_page(db_session, ms.id)

    # Simule l'absence du fichier
    monkeypatch.setattr(Path, "exists", lambda self: False)

    response = await async_client.get(f"/api/v1/pages/{page.id}/master-json")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_master_json_ok(async_client, db_session, monkeypatch):
    corpus = await _create_corpus(db_session)
    ms = await _create_manuscript(db_session, corpus.id)
    page = await _create_page(db_session, ms.id)

    master_data = _make_master_json(page.id)

    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(Path, "read_text", lambda self, **kw: master_data)

    response = await async_client.get(f"/api/v1/pages/{page.id}/master-json")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_master_json_contains_page_id(async_client, db_session, monkeypatch):
    corpus = await _create_corpus(db_session)
    ms = await _create_manuscript(db_session, corpus.id)
    page = await _create_page(db_session, ms.id)

    master_data = _make_master_json(page.id)
    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(Path, "read_text", lambda self, **kw: master_data)

    data = (await async_client.get(f"/api/v1/pages/{page.id}/master-json")).json()
    assert data["page_id"] == page.id


@pytest.mark.asyncio
async def test_master_json_schema_version(async_client, db_session, monkeypatch):
    corpus = await _create_corpus(db_session)
    ms = await _create_manuscript(db_session, corpus.id)
    page = await _create_page(db_session, ms.id)

    master_data = _make_master_json(page.id)
    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(Path, "read_text", lambda self, **kw: master_data)

    data = (await async_client.get(f"/api/v1/pages/{page.id}/master-json")).json()
    assert data["schema_version"] == "1.0"


@pytest.mark.asyncio
async def test_master_json_ocr_present(async_client, db_session, monkeypatch):
    corpus = await _create_corpus(db_session)
    ms = await _create_manuscript(db_session, corpus.id)
    page = await _create_page(db_session, ms.id)

    master_data = _make_master_json(page.id)
    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(Path, "read_text", lambda self, **kw: master_data)

    data = (await async_client.get(f"/api/v1/pages/{page.id}/master-json")).json()
    assert data["ocr"]["diplomatic_text"] == "Incipit liber primus"


# ---------------------------------------------------------------------------
# GET /api/v1/pages/{id}/layers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_layers_page_not_found(async_client):
    response = await async_client.get("/api/v1/pages/unknown/layers")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_layers_file_not_found(async_client, db_session, monkeypatch):
    corpus = await _create_corpus(db_session)
    ms = await _create_manuscript(db_session, corpus.id)
    page = await _create_page(db_session, ms.id)

    monkeypatch.setattr(Path, "exists", lambda self: False)

    response = await async_client.get(f"/api/v1/pages/{page.id}/layers")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_layers_ok_is_list(async_client, db_session, monkeypatch):
    corpus = await _create_corpus(db_session)
    ms = await _create_manuscript(db_session, corpus.id)
    page = await _create_page(db_session, ms.id)

    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(Path, "read_text", lambda self, **kw: _make_master_json(page.id))

    response = await async_client.get(f"/api/v1/pages/{page.id}/layers")
    assert response.status_code == 200
    layers = response.json()
    assert isinstance(layers, list)
    assert len(layers) > 0


@pytest.mark.asyncio
async def test_layers_contains_image(async_client, db_session, monkeypatch):
    corpus = await _create_corpus(db_session)
    ms = await _create_manuscript(db_session, corpus.id)
    page = await _create_page(db_session, ms.id)

    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(Path, "read_text", lambda self, **kw: _make_master_json(page.id))

    layers = (await async_client.get(f"/api/v1/pages/{page.id}/layers")).json()
    types = [l["layer_type"] for l in layers]
    assert "image" in types


@pytest.mark.asyncio
async def test_layers_contains_ocr(async_client, db_session, monkeypatch):
    corpus = await _create_corpus(db_session)
    ms = await _create_manuscript(db_session, corpus.id)
    page = await _create_page(db_session, ms.id)

    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(Path, "read_text", lambda self, **kw: _make_master_json(page.id))

    layers = (await async_client.get(f"/api/v1/pages/{page.id}/layers")).json()
    types = [l["layer_type"] for l in layers]
    assert "ocr_diplomatic" in types


@pytest.mark.asyncio
async def test_layers_contains_translation(async_client, db_session, monkeypatch):
    corpus = await _create_corpus(db_session)
    ms = await _create_manuscript(db_session, corpus.id)
    page = await _create_page(db_session, ms.id)

    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(Path, "read_text", lambda self, **kw: _make_master_json(page.id))

    layers = (await async_client.get(f"/api/v1/pages/{page.id}/layers")).json()
    types = [l["layer_type"] for l in layers]
    assert "translation_fr" in types


@pytest.mark.asyncio
async def test_layers_have_status(async_client, db_session, monkeypatch):
    corpus = await _create_corpus(db_session)
    ms = await _create_manuscript(db_session, corpus.id)
    page = await _create_page(db_session, ms.id)

    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(Path, "read_text", lambda self, **kw: _make_master_json(page.id))

    layers = (await async_client.get(f"/api/v1/pages/{page.id}/layers")).json()
    for layer in layers:
        assert "layer_type" in layer
        assert "status" in layer
        assert "has_content" in layer
