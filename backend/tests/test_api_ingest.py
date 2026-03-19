"""
Tests des endpoints d'ingestion /api/v1/corpora/{id}/ingest/* (Sprint 4 — Session B).

Stratégie :
  - BDD SQLite en mémoire
  - Appels réseau mockés via monkeypatch (_fetch_json_manifest)
  - Écriture disque mockée via monkeypatch (Path.mkdir, Path.write_bytes)

Vérifie :
- POST /ingest/files → pages créées, IDs retournés
- POST /ingest/iiif-manifest → manifest parsé, pages créées
- POST /ingest/iiif-images → pages créées depuis liste d'URLs
- 404 si corpus inexistant
- 422 si données invalides
"""
# 1. stdlib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

# 2. third-party
import pytest

# 3. local
import app.api.v1.ingest as ingest_module
from app.models.corpus import CorpusModel
from tests.conftest_api import async_client, db_session  # noqa: F401

_NOW = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _make_corpus(db, slug="test-ingest"):
    corpus = CorpusModel(
        id=str(uuid.uuid4()), slug=slug, title="Corpus Test",
        profile_id="medieval-illuminated", created_at=_NOW, updated_at=_NOW,
    )
    db.add(corpus)
    await db.commit()
    await db.refresh(corpus)
    return corpus


def _iiif3_manifest(n_canvases: int = 3) -> dict:
    """Génère un manifest IIIF 3.0 minimal avec n canvases."""
    return {
        "@context": "http://iiif.io/api/presentation/3/context.json",
        "id": "https://example.com/manifest",
        "type": "Manifest",
        "label": {"fr": ["Beatus de Saint-Sever"]},
        "items": [
            {
                "id": f"https://example.com/canvas/{i}",
                "type": "Canvas",
                "label": {"none": [f"f{i:03d}r"]},
                "width": 1500, "height": 2000,
                "items": [
                    {
                        "id": f"https://example.com/canvas/{i}/page",
                        "type": "AnnotationPage",
                        "items": [
                            {
                                "id": f"https://example.com/canvas/{i}/annotation",
                                "type": "Annotation",
                                "motivation": "painting",
                                "body": {
                                    "id": f"https://example.com/images/{i}.jpg",
                                    "type": "Image",
                                    "format": "image/jpeg",
                                },
                                "target": f"https://example.com/canvas/{i}",
                            }
                        ],
                    }
                ],
            }
            for i in range(1, n_canvases + 1)
        ],
    }


def _iiif2_manifest(n_canvases: int = 2) -> dict:
    """Génère un manifest IIIF 2.x minimal."""
    return {
        "@context": "http://iiif.io/api/presentation/2/context.json",
        "@type": "sc:Manifest",
        "label": "Test Manuscript 2.x",
        "sequences": [
            {
                "canvases": [
                    {
                        "@id": f"https://example.com/canvas/{i}",
                        "@type": "sc:Canvas",
                        "label": f"f{i:03d}r",
                        "images": [
                            {
                                "resource": {
                                    "@id": f"https://example.com/images/{i}.jpg"
                                }
                            }
                        ],
                    }
                    for i in range(1, n_canvases + 1)
                ]
            }
        ],
    }


# ---------------------------------------------------------------------------
# POST /api/v1/corpora/{id}/ingest/files
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ingest_files_corpus_not_found(async_client):
    response = await async_client.post(
        "/api/v1/corpora/nonexistent/ingest/files",
        files=[("files", ("img.jpg", b"data", "image/jpeg"))],
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_ingest_files_ok(async_client, db_session, tmp_path, monkeypatch):
    corpus = await _make_corpus(db_session)
    monkeypatch.setattr(_config_module := __import__("app.config", fromlist=["config"]), "settings",
                        type("S", (), {"data_dir": tmp_path})())

    import app.config as _cfg
    import app.api.v1.ingest as _ingest
    original_data_dir = _cfg.settings.data_dir
    _cfg.settings.data_dir = tmp_path

    try:
        response = await async_client.post(
            f"/api/v1/corpora/{corpus.id}/ingest/files",
            files=[
                ("files", ("f001r.jpg", b"fake_jpeg_data_1", "image/jpeg")),
                ("files", ("f002r.jpg", b"fake_jpeg_data_2", "image/jpeg")),
            ],
        )
        assert response.status_code == 201
        data = response.json()
        assert data["pages_created"] == 2
        assert len(data["page_ids"]) == 2
        assert data["corpus_id"] == corpus.id
    finally:
        _cfg.settings.data_dir = original_data_dir


@pytest.mark.asyncio
async def test_ingest_files_creates_manuscript(async_client, db_session, tmp_path):
    corpus = await _make_corpus(db_session)

    import app.config as _cfg
    original = _cfg.settings.data_dir
    _cfg.settings.data_dir = tmp_path
    try:
        response = await async_client.post(
            f"/api/v1/corpora/{corpus.id}/ingest/files",
            files=[("files", ("f001r.jpg", b"data", "image/jpeg"))],
        )
        data = response.json()
        assert "manuscript_id" in data
        assert data["manuscript_id"]  # non-vide
    finally:
        _cfg.settings.data_dir = original


@pytest.mark.asyncio
async def test_ingest_files_folio_from_filename(async_client, db_session, tmp_path):
    """Le folio_label est dérivé du nom de fichier (sans extension)."""
    corpus = await _make_corpus(db_session)

    import app.config as _cfg
    original = _cfg.settings.data_dir
    _cfg.settings.data_dir = tmp_path
    try:
        response = await async_client.post(
            f"/api/v1/corpora/{corpus.id}/ingest/files",
            files=[("files", ("f013v.jpg", b"data", "image/jpeg"))],
        )
        data = response.json()
        # L'ID de page contient le folio_label
        assert any("f013v" in pid for pid in data["page_ids"])
    finally:
        _cfg.settings.data_dir = original


@pytest.mark.asyncio
async def test_ingest_files_writes_to_disk(async_client, db_session, tmp_path):
    """Les fichiers sont bien écrits dans data/corpora/{slug}/masters/."""
    corpus = await _make_corpus(db_session, slug="test-write")

    import app.config as _cfg
    original = _cfg.settings.data_dir
    _cfg.settings.data_dir = tmp_path
    try:
        await async_client.post(
            f"/api/v1/corpora/{corpus.id}/ingest/files",
            files=[("files", ("f001r.jpg", b"JPEG_CONTENT", "image/jpeg"))],
        )
        expected = tmp_path / "corpora" / "test-write" / "masters" / "f001r" / "f001r.jpg"
        assert expected.exists()
        assert expected.read_bytes() == b"JPEG_CONTENT"
    finally:
        _cfg.settings.data_dir = original


# ---------------------------------------------------------------------------
# POST /api/v1/corpora/{id}/ingest/iiif-manifest
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ingest_manifest_corpus_not_found(async_client):
    response = await async_client.post(
        "/api/v1/corpora/nonexistent/ingest/iiif-manifest",
        json={"manifest_url": "https://example.com/manifest"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_ingest_manifest_iiif3_ok(async_client, db_session, monkeypatch):
    corpus = await _make_corpus(db_session)
    manifest = _iiif3_manifest(n_canvases=3)

    async def fake_fetch(url: str) -> dict:
        return manifest

    monkeypatch.setattr(ingest_module, "_fetch_json_manifest", fake_fetch)

    response = await async_client.post(
        f"/api/v1/corpora/{corpus.id}/ingest/iiif-manifest",
        json={"manifest_url": "https://example.com/manifest"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["pages_created"] == 3
    assert len(data["page_ids"]) == 3


@pytest.mark.asyncio
async def test_ingest_manifest_iiif2_ok(async_client, db_session, monkeypatch):
    corpus = await _make_corpus(db_session)
    manifest = _iiif2_manifest(n_canvases=2)

    async def fake_fetch(url: str) -> dict:
        return manifest

    monkeypatch.setattr(ingest_module, "_fetch_json_manifest", fake_fetch)

    response = await async_client.post(
        f"/api/v1/corpora/{corpus.id}/ingest/iiif-manifest",
        json={"manifest_url": "https://example.com/manifest"},
    )
    assert response.status_code == 201
    assert response.json()["pages_created"] == 2


@pytest.mark.asyncio
async def test_ingest_manifest_extracts_folio_labels(async_client, db_session, monkeypatch):
    """Les folio_labels sont extraits des labels des canvases."""
    corpus = await _make_corpus(db_session)
    manifest = _iiif3_manifest(n_canvases=2)

    async def fake_fetch(url: str) -> dict:
        return manifest

    monkeypatch.setattr(ingest_module, "_fetch_json_manifest", fake_fetch)

    data = (await async_client.post(
        f"/api/v1/corpora/{corpus.id}/ingest/iiif-manifest",
        json={"manifest_url": "https://example.com/manifest"},
    )).json()

    # Canvas labels: "f001r", "f002r"
    assert any("f001r" in pid for pid in data["page_ids"])
    assert any("f002r" in pid for pid in data["page_ids"])


@pytest.mark.asyncio
async def test_ingest_manifest_empty_canvases_422(async_client, db_session, monkeypatch):
    """Manifest sans canvases → 422."""
    corpus = await _make_corpus(db_session)

    async def fake_fetch(url: str) -> dict:
        return {"type": "Manifest", "items": []}

    monkeypatch.setattr(ingest_module, "_fetch_json_manifest", fake_fetch)

    response = await async_client.post(
        f"/api/v1/corpora/{corpus.id}/ingest/iiif-manifest",
        json={"manifest_url": "https://example.com/manifest"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_ingest_manifest_network_error_502(async_client, db_session, monkeypatch):
    """Erreur réseau → 502."""
    corpus = await _make_corpus(db_session)
    import httpx

    async def fake_fetch(url: str) -> dict:
        raise httpx.RequestError("Connection refused")

    monkeypatch.setattr(ingest_module, "_fetch_json_manifest", fake_fetch)

    response = await async_client.post(
        f"/api/v1/corpora/{corpus.id}/ingest/iiif-manifest",
        json={"manifest_url": "https://example.com/manifest"},
    )
    assert response.status_code == 502


@pytest.mark.asyncio
async def test_ingest_manifest_returns_corpus_id(async_client, db_session, monkeypatch):
    corpus = await _make_corpus(db_session)
    monkeypatch.setattr(ingest_module, "_fetch_json_manifest", AsyncMock(return_value=_iiif3_manifest(1)))

    data = (await async_client.post(
        f"/api/v1/corpora/{corpus.id}/ingest/iiif-manifest",
        json={"manifest_url": "https://example.com/manifest"},
    )).json()
    assert data["corpus_id"] == corpus.id


# ---------------------------------------------------------------------------
# POST /api/v1/corpora/{id}/ingest/iiif-images
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ingest_images_corpus_not_found(async_client):
    response = await async_client.post(
        "/api/v1/corpora/nonexistent/ingest/iiif-images",
        json={"urls": ["https://x.com/1.jpg"], "folio_labels": ["f001r"]},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_ingest_images_ok(async_client, db_session):
    corpus = await _make_corpus(db_session)
    urls = ["https://example.com/img1.jpg", "https://example.com/img2.jpg"]
    labels = ["f001r", "f002r"]

    response = await async_client.post(
        f"/api/v1/corpora/{corpus.id}/ingest/iiif-images",
        json={"urls": urls, "folio_labels": labels},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["pages_created"] == 2
    assert len(data["page_ids"]) == 2


@pytest.mark.asyncio
async def test_ingest_images_folio_labels_in_ids(async_client, db_session):
    corpus = await _make_corpus(db_session)
    response = await async_client.post(
        f"/api/v1/corpora/{corpus.id}/ingest/iiif-images",
        json={
            "urls": ["https://example.com/a.jpg"],
            "folio_labels": ["f013v"],
        },
    )
    data = response.json()
    assert any("f013v" in pid for pid in data["page_ids"])


@pytest.mark.asyncio
async def test_ingest_images_mismatched_lengths_422(async_client, db_session):
    """urls et folio_labels de longueurs différentes → 422."""
    corpus = await _make_corpus(db_session)
    response = await async_client.post(
        f"/api/v1/corpora/{corpus.id}/ingest/iiif-images",
        json={"urls": ["https://a.com/1.jpg", "https://a.com/2.jpg"], "folio_labels": ["f001r"]},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_ingest_images_empty_urls_422(async_client, db_session):
    corpus = await _make_corpus(db_session)
    response = await async_client.post(
        f"/api/v1/corpora/{corpus.id}/ingest/iiif-images",
        json={"urls": [], "folio_labels": []},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_ingest_images_pages_in_sequence_order(async_client, db_session):
    """Les pages ont des séquences consécutives."""
    corpus = await _make_corpus(db_session)
    n = 4
    urls = [f"https://example.com/{i}.jpg" for i in range(1, n + 1)]
    labels = [f"f{i:03d}r" for i in range(1, n + 1)]

    data = (await async_client.post(
        f"/api/v1/corpora/{corpus.id}/ingest/iiif-images",
        json={"urls": urls, "folio_labels": labels},
    )).json()
    assert data["pages_created"] == n


@pytest.mark.asyncio
async def test_ingest_images_corpus_id_in_response(async_client, db_session):
    corpus = await _make_corpus(db_session)
    data = (await async_client.post(
        f"/api/v1/corpora/{corpus.id}/ingest/iiif-images",
        json={"urls": ["https://x.com/1.jpg"], "folio_labels": ["f001r"]},
    )).json()
    assert data["corpus_id"] == corpus.id


# ---------------------------------------------------------------------------
# Réingestion — pas de 500
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reingest_manifest_skips_existing_pages(async_client, db_session, monkeypatch):
    """Réingérer le même manifest ne provoque pas de 500 (UNIQUE constraint).

    La deuxième ingestion doit retourner 201 avec pages_created=0 et pages_skipped=N.
    """
    corpus = await _make_corpus(db_session, slug="reingest")
    manifest = _iiif3_manifest(n_canvases=2)

    async def fake_fetch(url: str) -> dict:
        return manifest

    monkeypatch.setattr(ingest_module, "_fetch_json_manifest", fake_fetch)

    # Première ingestion
    resp1 = await async_client.post(
        f"/api/v1/corpora/{corpus.id}/ingest/iiif-manifest",
        json={"manifest_url": "https://example.com/manifest"},
    )
    assert resp1.status_code == 201
    data1 = resp1.json()
    assert data1["pages_created"] == 2
    assert data1["pages_skipped"] == 0

    # Deuxième ingestion — même manifest
    resp2 = await async_client.post(
        f"/api/v1/corpora/{corpus.id}/ingest/iiif-manifest",
        json={"manifest_url": "https://example.com/manifest"},
    )
    assert resp2.status_code == 201
    data2 = resp2.json()
    assert data2["pages_created"] == 0
    assert data2["pages_skipped"] == 2


@pytest.mark.asyncio
async def test_reingest_images_skips_existing_pages(async_client, db_session):
    """Réingérer les mêmes images ne provoque pas de 500."""
    corpus = await _make_corpus(db_session, slug="reingest2")

    payload = {"urls": ["https://x.com/a.jpg"], "folio_labels": ["f001r"]}

    resp1 = await async_client.post(
        f"/api/v1/corpora/{corpus.id}/ingest/iiif-images", json=payload,
    )
    assert resp1.status_code == 201
    assert resp1.json()["pages_created"] == 1

    resp2 = await async_client.post(
        f"/api/v1/corpora/{corpus.id}/ingest/iiif-images", json=payload,
    )
    assert resp2.status_code == 201
    assert resp2.json()["pages_created"] == 0
    assert resp2.json()["pages_skipped"] == 1


@pytest.mark.asyncio
async def test_ingest_manifest_duplicate_labels_no_collision(async_client, db_session, monkeypatch):
    """Deux canvases avec le même label ne provoquent pas de collision d'ID."""
    corpus = await _make_corpus(db_session, slug="dupe-labels")
    manifest = {
        "@context": "http://iiif.io/api/presentation/3/context.json",
        "type": "Manifest",
        "label": {"fr": ["Test"]},
        "items": [
            {
                "id": f"https://example.com/canvas/{i}",
                "type": "Canvas",
                "label": {"none": ["NP"]},
                "items": [{
                    "type": "AnnotationPage",
                    "items": [{
                        "type": "Annotation",
                        "motivation": "painting",
                        "body": {"id": f"https://example.com/img/{i}.jpg", "type": "Image"},
                        "target": f"https://example.com/canvas/{i}",
                    }],
                }],
            }
            for i in range(1, 4)
        ],
    }

    monkeypatch.setattr(ingest_module, "_fetch_json_manifest", AsyncMock(return_value=manifest))

    resp = await async_client.post(
        f"/api/v1/corpora/{corpus.id}/ingest/iiif-manifest",
        json={"manifest_url": "https://example.com/manifest"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["pages_created"] == 3
    # All IDs must be distinct
    assert len(set(data["page_ids"])) == 3
