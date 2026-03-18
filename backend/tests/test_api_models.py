"""
Tests des endpoints /api/v1/models (Sprint 4 — Session B).

Stratégie :
  - Appels Google AI mockés via monkeypatch sur list_all_models
  - BDD SQLite en mémoire pour les endpoints qui touchent la BDD (PUT/GET model)

Vérifie :
- GET  /api/v1/models            → liste mockée
- POST /api/v1/models/refresh    → mise à jour + timestamp
- PUT  /api/v1/corpora/{id}/model → création + mise à jour
- GET  /api/v1/corpora/{id}/model → 200 ou 404
"""
# 1. stdlib
import uuid
from datetime import datetime, timezone

# 2. third-party
import pytest

# 3. local
import app.api.v1.models_api as models_api_module
from app.models.corpus import CorpusModel
from app.schemas.model_config import ModelInfo, ProviderType
from tests.conftest_api import async_client, db_session  # noqa: F401

_NOW = datetime.now(timezone.utc)

_MOCK_MODELS = [
    ModelInfo(
        model_id="gemini-2.0-flash",
        display_name="Gemini 2.0 Flash",
        provider=ProviderType.GOOGLE_AI_STUDIO,
        supports_vision=True,
        input_token_limit=1_000_000,
        output_token_limit=8192,
    ),
    ModelInfo(
        model_id="gemini-1.5-pro",
        display_name="Gemini 1.5 Pro",
        provider=ProviderType.GOOGLE_AI_STUDIO,
        supports_vision=True,
        input_token_limit=2_000_000,
        output_token_limit=8192,
    ),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _make_corpus(db, slug="models-test"):
    corpus = CorpusModel(
        id=str(uuid.uuid4()), slug=slug, title="Models Test",
        profile_id="medieval-illuminated", created_at=_NOW, updated_at=_NOW,
    )
    db.add(corpus)
    await db.commit()
    await db.refresh(corpus)
    return corpus


# ---------------------------------------------------------------------------
# POST /api/v1/settings/api-key → supprimé (clés dans secrets HF, R06)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_settings_api_key_endpoint_removed(async_client):
    """L'endpoint /api/v1/settings/api-key ne doit plus exister (404 ou 405)."""
    response = await async_client.post(
        "/api/v1/settings/api-key",
        json={"api_key": "AIza-test", "provider_type": "google_ai_studio"},
    )
    assert response.status_code in (404, 405)


# ---------------------------------------------------------------------------
# GET /api/v1/models
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_models_returns_list(async_client, monkeypatch):
    monkeypatch.setattr(
        models_api_module, "list_all_models", lambda: _MOCK_MODELS
    )
    response = await async_client.get("/api/v1/models")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_get_models_count(async_client, monkeypatch):
    monkeypatch.setattr(
        models_api_module, "list_all_models", lambda: _MOCK_MODELS
    )
    models = response = await async_client.get("/api/v1/models")
    assert len(response.json()) == 2


@pytest.mark.asyncio
async def test_get_models_fields(async_client, monkeypatch):
    monkeypatch.setattr(
        models_api_module, "list_all_models", lambda: _MOCK_MODELS
    )
    models = (await async_client.get("/api/v1/models")).json()
    m = models[0]
    assert "model_id" in m
    assert "display_name" in m
    assert "provider" in m
    assert "supports_vision" in m


@pytest.mark.asyncio
async def test_get_models_empty_when_no_provider(async_client, monkeypatch):
    monkeypatch.setattr(models_api_module, "list_all_models", lambda: [])
    response = await async_client.get("/api/v1/models")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_models_contains_gemini(async_client, monkeypatch):
    monkeypatch.setattr(
        models_api_module, "list_all_models", lambda: _MOCK_MODELS
    )
    models = (await async_client.get("/api/v1/models")).json()
    ids = [m["model_id"] for m in models]
    assert any("gemini" in mid for mid in ids)


# ---------------------------------------------------------------------------
# POST /api/v1/models/refresh
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_refresh_models_ok(async_client, monkeypatch):
    monkeypatch.setattr(
        models_api_module, "list_all_models", lambda: _MOCK_MODELS
    )
    response = await async_client.post("/api/v1/models/refresh")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_refresh_models_has_timestamp(async_client, monkeypatch):
    monkeypatch.setattr(
        models_api_module, "list_all_models", lambda: _MOCK_MODELS
    )
    data = (await async_client.post("/api/v1/models/refresh")).json()
    assert "refreshed_at" in data
    assert data["refreshed_at"]  # non-vide


@pytest.mark.asyncio
async def test_refresh_models_count(async_client, monkeypatch):
    monkeypatch.setattr(
        models_api_module, "list_all_models", lambda: _MOCK_MODELS
    )
    data = (await async_client.post("/api/v1/models/refresh")).json()
    assert data["count"] == 2
    assert len(data["models"]) == 2


@pytest.mark.asyncio
async def test_refresh_models_structure(async_client, monkeypatch):
    monkeypatch.setattr(
        models_api_module, "list_all_models", lambda: _MOCK_MODELS
    )
    data = (await async_client.post("/api/v1/models/refresh")).json()
    assert "models" in data
    assert "count" in data
    assert "refreshed_at" in data


# ---------------------------------------------------------------------------
# PUT /api/v1/corpora/{id}/model
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_set_model_corpus_not_found(async_client):
    response = await async_client.put(
        "/api/v1/corpora/nonexistent/model",
        json={"model_id": "gemini-2.0-flash", "provider_type": "google_ai_studio"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_set_model_ok(async_client, db_session):
    corpus = await _make_corpus(db_session)
    response = await async_client.put(
        f"/api/v1/corpora/{corpus.id}/model",
        json={
            "model_id": "gemini-2.0-flash",
            "provider_type": "google_ai_studio",
            "display_name": "Gemini 2.0 Flash",
        },
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_set_model_response_fields(async_client, db_session):
    corpus = await _make_corpus(db_session)
    data = (await async_client.put(
        f"/api/v1/corpora/{corpus.id}/model",
        json={"model_id": "gemini-2.0-flash", "provider_type": "google_ai_studio"},
    )).json()

    assert data["corpus_id"] == corpus.id
    assert data["selected_model_id"] == "gemini-2.0-flash"
    assert data["provider_type"] == "google_ai_studio"
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_set_model_update_existing(async_client, db_session):
    """PUT sur un corpus déjà configuré → mise à jour (pas de doublon)."""
    corpus = await _make_corpus(db_session)

    await async_client.put(
        f"/api/v1/corpora/{corpus.id}/model",
        json={"model_id": "gemini-1.5-pro", "provider_type": "google_ai_studio"},
    )
    resp2 = await async_client.put(
        f"/api/v1/corpora/{corpus.id}/model",
        json={"model_id": "gemini-2.0-flash", "provider_type": "google_ai_studio"},
    )
    data = resp2.json()
    assert data["selected_model_id"] == "gemini-2.0-flash"


@pytest.mark.asyncio
async def test_set_model_then_get(async_client, db_session):
    """Après PUT, GET retourne le même modèle."""
    corpus = await _make_corpus(db_session)
    await async_client.put(
        f"/api/v1/corpora/{corpus.id}/model",
        json={"model_id": "gemini-2.0-flash", "provider_type": "google_ai_studio"},
    )
    get_data = (await async_client.get(f"/api/v1/corpora/{corpus.id}/model")).json()
    assert get_data["selected_model_id"] == "gemini-2.0-flash"


@pytest.mark.asyncio
async def test_set_model_display_name_fallback(async_client, db_session):
    """Sans display_name, l'id est utilisé comme display_name."""
    corpus = await _make_corpus(db_session)
    data = (await async_client.put(
        f"/api/v1/corpora/{corpus.id}/model",
        json={"model_id": "gemini-2.0-flash", "provider_type": "google_ai_studio"},
    )).json()
    assert data["selected_model_display_name"] == "gemini-2.0-flash"


# ---------------------------------------------------------------------------
# GET /api/v1/corpora/{id}/model
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_model_corpus_not_found(async_client):
    response = await async_client.get("/api/v1/corpora/nonexistent/model")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_model_not_configured(async_client, db_session):
    """Corpus sans modèle configuré → 404."""
    corpus = await _make_corpus(db_session)
    response = await async_client.get(f"/api/v1/corpora/{corpus.id}/model")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_model_ok(async_client, db_session):
    corpus = await _make_corpus(db_session)
    await async_client.put(
        f"/api/v1/corpora/{corpus.id}/model",
        json={"model_id": "gemini-2.0-flash", "provider_type": "google_ai_studio"},
    )
    response = await async_client.get(f"/api/v1/corpora/{corpus.id}/model")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_model_fields(async_client, db_session):
    corpus = await _make_corpus(db_session)
    await async_client.put(
        f"/api/v1/corpora/{corpus.id}/model",
        json={"model_id": "gemini-1.5-pro", "provider_type": "google_ai_studio", "display_name": "Gemini 1.5 Pro"},
    )
    data = (await async_client.get(f"/api/v1/corpora/{corpus.id}/model")).json()
    assert data["corpus_id"] == corpus.id
    assert data["selected_model_id"] == "gemini-1.5-pro"
    assert data["selected_model_display_name"] == "Gemini 1.5 Pro"
    assert data["provider_type"] == "google_ai_studio"
    assert "updated_at" in data
