"""
Tests des endpoints corrections et historique (Sprint 6 — Session B).

POST /api/v1/pages/{id}/corrections   → corrections partielles, versionnement
GET  /api/v1/pages/{id}/history       → liste des versions archivées
"""
# 1. stdlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

# 2. third-party
import pytest

# 3. local
from app.models.corpus import CorpusModel, ManuscriptModel, PageModel
from tests.conftest_api import async_client, db_session  # noqa: F401

_NOW = datetime.now(timezone.utc)


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _create_corpus(db_session, slug: str = "test-corpus") -> CorpusModel:
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


async def _create_manuscript(db_session, corpus_id: str) -> ManuscriptModel:
    ms = ManuscriptModel(
        id=str(uuid.uuid4()),
        corpus_id=corpus_id,
        title="Test MS",
        total_pages=1,
    )
    db_session.add(ms)
    await db_session.commit()
    await db_session.refresh(ms)
    return ms


async def _create_page(db_session, manuscript_id: str) -> PageModel:
    page = PageModel(
        id=str(uuid.uuid4()),
        manuscript_id=manuscript_id,
        folio_label="f001r",
        sequence=1,
        image_master_path="/data/f001r.jpg",
        processing_status="ANALYZED",
    )
    db_session.add(page)
    await db_session.commit()
    await db_session.refresh(page)
    return page


def _make_master(
    page_id: str, version: int = 1, status: str = "machine_draft"
) -> str:
    return json.dumps({
        "schema_version": "1.0",
        "page_id": page_id,
        "corpus_profile": "medieval-illuminated",
        "manuscript_id": "ms-test",
        "folio_label": "f001r",
        "sequence": 1,
        "image": {"original_url": "https://example.com/f.jpg", "width": 1500, "height": 2000},
        "layout": {"regions": []},
        "ocr": {
            "diplomatic_text": "Incipit liber primus",
            "blocks": [], "lines": [], "language": "la",
            "confidence": 0.87, "uncertain_segments": [],
        },
        "translation": {"fr": "", "en": ""},
        "summary": None,
        "commentary": {
            "public": "Texte public", "scholarly": "Analyse savante", "claims": [],
        },
        "editorial": {
            "status": status,
            "validated": False, "validated_by": None,
            "version": version, "notes": [],
        },
    })


# ── POST /api/v1/pages/{id}/corrections ───────────────────────────────────────

@pytest.mark.asyncio
async def test_corrections_page_not_found(async_client):
    resp = await async_client.post(
        "/api/v1/pages/nonexistent/corrections",
        json={"ocr_diplomatic_text": "texte"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_corrections_no_master_json(async_client, db_session, monkeypatch):
    corpus = await _create_corpus(db_session)
    ms = await _create_manuscript(db_session, corpus.id)
    page = await _create_page(db_session, ms.id)

    monkeypatch.setattr(Path, "exists", lambda self: False)

    resp = await async_client.post(
        f"/api/v1/pages/{page.id}/corrections",
        json={"ocr_diplomatic_text": "texte"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_corrections_updates_ocr_text(async_client, db_session, monkeypatch):
    corpus = await _create_corpus(db_session)
    ms = await _create_manuscript(db_session, corpus.id)
    page = await _create_page(db_session, ms.id)

    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(Path, "read_text", lambda self, **kw: _make_master(page.id))
    monkeypatch.setattr(Path, "write_text", lambda self, content, **kw: None)

    resp = await async_client.post(
        f"/api/v1/pages/{page.id}/corrections",
        json={"ocr_diplomatic_text": "Texte corrigé manuellement"},
    )
    assert resp.status_code == 200
    assert resp.json()["ocr"]["diplomatic_text"] == "Texte corrigé manuellement"


@pytest.mark.asyncio
async def test_corrections_increments_version(async_client, db_session, monkeypatch):
    corpus = await _create_corpus(db_session)
    ms = await _create_manuscript(db_session, corpus.id)
    page = await _create_page(db_session, ms.id)

    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(Path, "read_text", lambda self, **kw: _make_master(page.id, version=1))
    monkeypatch.setattr(Path, "write_text", lambda self, content, **kw: None)

    resp = await async_client.post(
        f"/api/v1/pages/{page.id}/corrections",
        json={"editorial_status": "needs_review"},
    )
    assert resp.status_code == 200
    assert resp.json()["editorial"]["version"] == 2


@pytest.mark.asyncio
async def test_corrections_updates_editorial_status(async_client, db_session, monkeypatch):
    corpus = await _create_corpus(db_session)
    ms = await _create_manuscript(db_session, corpus.id)
    page = await _create_page(db_session, ms.id)

    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(Path, "read_text", lambda self, **kw: _make_master(page.id))
    monkeypatch.setattr(Path, "write_text", lambda self, content, **kw: None)

    resp = await async_client.post(
        f"/api/v1/pages/{page.id}/corrections",
        json={"editorial_status": "reviewed"},
    )
    assert resp.status_code == 200
    assert resp.json()["editorial"]["status"] == "reviewed"


@pytest.mark.asyncio
async def test_corrections_updates_commentary_public(async_client, db_session, monkeypatch):
    corpus = await _create_corpus(db_session)
    ms = await _create_manuscript(db_session, corpus.id)
    page = await _create_page(db_session, ms.id)

    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(Path, "read_text", lambda self, **kw: _make_master(page.id))
    monkeypatch.setattr(Path, "write_text", lambda self, content, **kw: None)

    resp = await async_client.post(
        f"/api/v1/pages/{page.id}/corrections",
        json={"commentary_public": "Commentaire public révisé"},
    )
    assert resp.status_code == 200
    assert resp.json()["commentary"]["public"] == "Commentaire public révisé"


@pytest.mark.asyncio
async def test_corrections_updates_commentary_scholarly(async_client, db_session, monkeypatch):
    corpus = await _create_corpus(db_session)
    ms = await _create_manuscript(db_session, corpus.id)
    page = await _create_page(db_session, ms.id)

    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(Path, "read_text", lambda self, **kw: _make_master(page.id))
    monkeypatch.setattr(Path, "write_text", lambda self, content, **kw: None)

    resp = await async_client.post(
        f"/api/v1/pages/{page.id}/corrections",
        json={"commentary_scholarly": "Analyse savante révisée"},
    )
    assert resp.status_code == 200
    assert resp.json()["commentary"]["scholarly"] == "Analyse savante révisée"


@pytest.mark.asyncio
async def test_corrections_region_validations(async_client, db_session, monkeypatch):
    corpus = await _create_corpus(db_session)
    ms = await _create_manuscript(db_session, corpus.id)
    page = await _create_page(db_session, ms.id)

    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(Path, "read_text", lambda self, **kw: _make_master(page.id))
    monkeypatch.setattr(Path, "write_text", lambda self, content, **kw: None)

    resp = await async_client.post(
        f"/api/v1/pages/{page.id}/corrections",
        json={"region_validations": {"r001": "validated", "r002": "rejected"}},
    )
    assert resp.status_code == 200
    validations = resp.json().get("extensions", {}).get("region_validations", {})
    assert validations.get("r001") == "validated"
    assert validations.get("r002") == "rejected"


@pytest.mark.asyncio
async def test_corrections_archives_old_version(async_client, db_session, monkeypatch):
    """Vérifie qu'une copie master_v1.json est écrite avant la correction."""
    corpus = await _create_corpus(db_session)
    ms = await _create_manuscript(db_session, corpus.id)
    page = await _create_page(db_session, ms.id)

    written_paths: list[str] = []

    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(Path, "read_text", lambda self, **kw: _make_master(page.id, version=1))

    def _capture_write(self: Path, content: str, **kw: object) -> None:
        written_paths.append(str(self))

    monkeypatch.setattr(Path, "write_text", _capture_write)

    await async_client.post(
        f"/api/v1/pages/{page.id}/corrections",
        json={"editorial_status": "needs_review"},
    )

    # Deux écritures attendues : master_v1.json (archive) + master.json (nouveau)
    assert len(written_paths) >= 2
    assert any("master_v1.json" in p for p in written_paths)
    assert any("master.json" in p and "master_v" not in p for p in written_paths)


@pytest.mark.asyncio
async def test_corrections_multiple_fields(async_client, db_session, monkeypatch):
    """Plusieurs corrections peuvent être envoyées en un seul appel."""
    corpus = await _create_corpus(db_session)
    ms = await _create_manuscript(db_session, corpus.id)
    page = await _create_page(db_session, ms.id)

    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(Path, "read_text", lambda self, **kw: _make_master(page.id))
    monkeypatch.setattr(Path, "write_text", lambda self, content, **kw: None)

    resp = await async_client.post(
        f"/api/v1/pages/{page.id}/corrections",
        json={
            "ocr_diplomatic_text": "Nouveau texte diplomatique",
            "editorial_status": "reviewed",
            "commentary_public": "Nouveau commentaire",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ocr"]["diplomatic_text"] == "Nouveau texte diplomatique"
    assert data["editorial"]["status"] == "reviewed"
    assert data["commentary"]["public"] == "Nouveau commentaire"
    assert data["editorial"]["version"] == 2


# ── GET /api/v1/pages/{id}/history ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_history_page_not_found(async_client):
    resp = await async_client.get("/api/v1/pages/nonexistent/history")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_history_returns_empty_list_when_no_dir(async_client, db_session, monkeypatch):
    """Retourne [] si le répertoire de page n'existe pas."""
    corpus = await _create_corpus(db_session)
    ms = await _create_manuscript(db_session, corpus.id)
    page = await _create_page(db_session, ms.id)

    monkeypatch.setattr(Path, "exists", lambda self: False)

    resp = await async_client.get(f"/api/v1/pages/{page.id}/history")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_history_returns_list(async_client, db_session, monkeypatch):
    """Le type de retour est une liste (même vide)."""
    corpus = await _create_corpus(db_session)
    ms = await _create_manuscript(db_session, corpus.id)
    page = await _create_page(db_session, ms.id)

    monkeypatch.setattr(Path, "exists", lambda self: False)

    resp = await async_client.get(f"/api/v1/pages/{page.id}/history")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_history_with_archived_files(async_client, db_session, tmp_path, monkeypatch):
    """Retourne les versions trouvées dans les fichiers master_v*.json."""
    corpus = await _create_corpus(db_session, slug="hist-corpus")
    ms = await _create_manuscript(db_session, corpus.id)
    page = await _create_page(db_session, ms.id)

    # Crée le répertoire avec des fichiers de version
    page_dir = tmp_path / "corpora" / corpus.slug / "pages" / page.id
    page_dir.mkdir(parents=True)
    (page_dir / "master_v1.json").write_text(_make_master(page.id, version=1, status="machine_draft"))
    (page_dir / "master_v2.json").write_text(_make_master(page.id, version=2, status="reviewed"))

    import app.api.v1.pages as pages_module
    import app.config as config_mod

    original_data_dir = config_mod.settings.data_dir
    config_mod.settings.__dict__["data_dir"] = tmp_path
    try:
        resp = await async_client.get(f"/api/v1/pages/{page.id}/history")
    finally:
        config_mod.settings.__dict__["data_dir"] = original_data_dir

    assert resp.status_code == 200
    versions = resp.json()
    assert len(versions) == 2
    statuses = [v["status"] for v in versions]
    assert "machine_draft" in statuses
    assert "reviewed" in statuses
