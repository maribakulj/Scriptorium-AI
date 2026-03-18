"""
Tests de l'endpoint GET /api/v1/search (Sprint 6 — Session B).

Stratégie :
  - Fichiers master.json réels dans tmp_path
  - Override de settings.data_dir pour pointer sur tmp_path
  - Vérifie : 422 (paramètre manquant / trop court), résultats vides,
    correspondance OCR, insensibilité casse et accents, tri par score,
    extrait (excerpt) présent.
"""
# 1. stdlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

# 2. third-party
import pytest

# 3. local
from tests.conftest_api import async_client, db_session  # noqa: F401

_NOW = datetime.now(timezone.utc)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_master(page_id: str, diplomatic_text: str = "", translation_fr: str = "") -> dict:
    return {
        "schema_version": "1.0",
        "page_id": page_id,
        "corpus_profile": "medieval-illuminated",
        "manuscript_id": "ms-test",
        "folio_label": "f001r",
        "sequence": 1,
        "image": {"original_url": "https://example.com/f.jpg", "width": 1500, "height": 2000},
        "layout": {"regions": []},
        "ocr": {
            "diplomatic_text": diplomatic_text,
            "blocks": [], "lines": [], "language": "la",
            "confidence": 0.87, "uncertain_segments": [],
        },
        "translation": {"fr": translation_fr, "en": ""},
        "summary": None,
        "commentary": {"public": "", "scholarly": "", "claims": []},
        "editorial": {
            "status": "machine_draft",
            "validated": False, "validated_by": None,
            "version": 1, "notes": [],
        },
    }


def _write_master(tmp_path: Path, corpus_slug: str, page_id: str, data: dict) -> None:
    page_dir = tmp_path / "corpora" / corpus_slug / "pages" / page_id
    page_dir.mkdir(parents=True)
    (page_dir / "master.json").write_text(json.dumps(data), encoding="utf-8")


# ── Tests ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_missing_q(async_client):
    """q est obligatoire — 422 si absent."""
    resp = await async_client.get("/api/v1/search")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_search_q_too_short(async_client):
    """q doit faire au moins 2 caractères — 422 si trop court."""
    resp = await async_client.get("/api/v1/search?q=a")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_search_empty_results(async_client, tmp_path):
    """Retourne [] quand aucun master.json ne correspond."""
    import app.config as config_mod
    original = config_mod.settings.data_dir
    config_mod.settings.__dict__["data_dir"] = tmp_path
    try:
        resp = await async_client.get("/api/v1/search?q=rien")
    finally:
        config_mod.settings.__dict__["data_dir"] = original

    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_search_returns_list(async_client, tmp_path):
    """Le type de retour est toujours une liste."""
    import app.config as config_mod
    original = config_mod.settings.data_dir
    config_mod.settings.__dict__["data_dir"] = tmp_path
    try:
        resp = await async_client.get("/api/v1/search?q=texte")
    finally:
        config_mod.settings.__dict__["data_dir"] = original

    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_search_finds_ocr_text(async_client, tmp_path):
    """Trouve un master.json dont ocr.diplomatic_text contient la requête."""
    import app.config as config_mod

    page_id = str(uuid.uuid4())
    _write_master(tmp_path, "corpus-a", page_id, _make_master(page_id, diplomatic_text="Incipit liber primus"))

    original = config_mod.settings.data_dir
    config_mod.settings.__dict__["data_dir"] = tmp_path
    try:
        resp = await async_client.get("/api/v1/search?q=Incipit")
    finally:
        config_mod.settings.__dict__["data_dir"] = original

    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 1
    assert results[0]["page_id"] == page_id


@pytest.mark.asyncio
async def test_search_case_insensitive(async_client, tmp_path):
    """La recherche est insensible à la casse."""
    import app.config as config_mod

    page_id = str(uuid.uuid4())
    _write_master(tmp_path, "corpus-b", page_id, _make_master(page_id, diplomatic_text="INCIPIT LIBER"))

    original = config_mod.settings.data_dir
    config_mod.settings.__dict__["data_dir"] = tmp_path
    try:
        resp = await async_client.get("/api/v1/search?q=incipit")
    finally:
        config_mod.settings.__dict__["data_dir"] = original

    assert resp.status_code == 200
    results = resp.json()
    assert len(results) >= 1
    assert any(r["page_id"] == page_id for r in results)


@pytest.mark.asyncio
async def test_search_accent_insensitive(async_client, tmp_path):
    """La recherche est insensible aux accents."""
    import app.config as config_mod

    page_id = str(uuid.uuid4())
    _write_master(tmp_path, "corpus-c", page_id, _make_master(page_id, diplomatic_text="Édition française médiévale"))

    original = config_mod.settings.data_dir
    config_mod.settings.__dict__["data_dir"] = tmp_path
    try:
        resp = await async_client.get("/api/v1/search?q=edition")
    finally:
        config_mod.settings.__dict__["data_dir"] = original

    assert resp.status_code == 200
    results = resp.json()
    assert len(results) >= 1
    assert any(r["page_id"] == page_id for r in results)


@pytest.mark.asyncio
async def test_search_finds_translation_fr(async_client, tmp_path):
    """Trouve également dans translation.fr."""
    import app.config as config_mod

    page_id = str(uuid.uuid4())
    _write_master(tmp_path, "corpus-d", page_id, _make_master(page_id, translation_fr="Ici commence le premier livre"))

    original = config_mod.settings.data_dir
    config_mod.settings.__dict__["data_dir"] = tmp_path
    try:
        resp = await async_client.get("/api/v1/search?q=premier")
    finally:
        config_mod.settings.__dict__["data_dir"] = original

    assert resp.status_code == 200
    results = resp.json()
    assert any(r["page_id"] == page_id for r in results)


@pytest.mark.asyncio
async def test_search_no_match_returns_empty(async_client, tmp_path):
    """Ne retourne rien quand la requête ne correspond à aucun texte."""
    import app.config as config_mod

    page_id = str(uuid.uuid4())
    _write_master(tmp_path, "corpus-e", page_id, _make_master(page_id, diplomatic_text="Incipit liber"))

    original = config_mod.settings.data_dir
    config_mod.settings.__dict__["data_dir"] = tmp_path
    try:
        resp = await async_client.get("/api/v1/search?q=xyznomatch")
    finally:
        config_mod.settings.__dict__["data_dir"] = original

    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_search_result_has_excerpt(async_client, tmp_path):
    """Chaque résultat contient un champ excerpt non vide."""
    import app.config as config_mod

    page_id = str(uuid.uuid4())
    _write_master(tmp_path, "corpus-f", page_id, _make_master(page_id, diplomatic_text="Incipit liber primus"))

    original = config_mod.settings.data_dir
    config_mod.settings.__dict__["data_dir"] = tmp_path
    try:
        resp = await async_client.get("/api/v1/search?q=liber")
    finally:
        config_mod.settings.__dict__["data_dir"] = original

    assert resp.status_code == 200
    results = resp.json()
    assert len(results) >= 1
    assert results[0]["excerpt"] != ""


@pytest.mark.asyncio
async def test_search_sorted_by_score_desc(async_client, tmp_path):
    """Les résultats sont triés par score décroissant."""
    import app.config as config_mod

    page_id_1 = str(uuid.uuid4())
    page_id_2 = str(uuid.uuid4())
    # page_id_1 contient 3 occurrences, page_id_2 en contient 1
    _write_master(tmp_path, "corpus-g", page_id_1, _make_master(
        page_id_1, diplomatic_text="liber liber liber"
    ))
    _write_master(tmp_path, "corpus-g", page_id_2, _make_master(
        page_id_2, diplomatic_text="liber unus"
    ))

    original = config_mod.settings.data_dir
    config_mod.settings.__dict__["data_dir"] = tmp_path
    try:
        resp = await async_client.get("/api/v1/search?q=liber")
    finally:
        config_mod.settings.__dict__["data_dir"] = original

    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 2
    assert results[0]["score"] >= results[1]["score"]
    assert results[0]["page_id"] == page_id_1


@pytest.mark.asyncio
async def test_search_result_fields(async_client, tmp_path):
    """Chaque résultat expose les champs attendus."""
    import app.config as config_mod

    page_id = str(uuid.uuid4())
    _write_master(tmp_path, "corpus-h", page_id, _make_master(page_id, diplomatic_text="Incipit liber"))

    original = config_mod.settings.data_dir
    config_mod.settings.__dict__["data_dir"] = tmp_path
    try:
        resp = await async_client.get("/api/v1/search?q=Incipit")
    finally:
        config_mod.settings.__dict__["data_dir"] = original

    assert resp.status_code == 200
    result = resp.json()[0]
    assert "page_id" in result
    assert "folio_label" in result
    assert "manuscript_id" in result
    assert "excerpt" in result
    assert "score" in result
    assert "corpus_profile" in result
