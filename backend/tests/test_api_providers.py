"""
Tests des endpoints GET /api/v1/providers et GET /api/v1/providers/{type}/models.

Stratégie :
  - get_available_providers() et list_models_for_provider() mockés via monkeypatch
    sur models_api_module (nom local après import from … import …)
  - BDD SQLite en mémoire (fixture async_client)

Vérifie :
- GET /api/v1/providers → liste de providers avec available + model_count
- GET /api/v1/providers/{provider_type}/models → 200 ou 404/503
- Comportement avec 0, 1 ou plusieurs providers disponibles
"""
# 1. stdlib
from datetime import datetime, timezone

# 2. third-party
import pytest

# 3. local
import app.api.v1.models_api as models_api_module
from app.schemas.model_config import ModelInfo, ProviderType
from tests.conftest_api import async_client, db_session  # noqa: F401

_NOW = datetime.now(timezone.utc)

_PROVIDERS_ALL_UNAVAILABLE = [
    {"provider_type": "google_ai_studio", "display_name": "Google AI Studio", "available": False, "model_count": 0},
    {"provider_type": "vertex_api_key", "display_name": "Vertex AI (clé API)", "available": False, "model_count": 0},
    {"provider_type": "vertex_service_account", "display_name": "Vertex AI (compte de service)", "available": False, "model_count": 0},
    {"provider_type": "mistral", "display_name": "Mistral AI", "available": False, "model_count": 0},
]

_PROVIDERS_GOOGLE_ONLY = [
    {"provider_type": "google_ai_studio", "display_name": "Google AI Studio", "available": True, "model_count": 2},
    {"provider_type": "vertex_api_key", "display_name": "Vertex AI (clé API)", "available": False, "model_count": 0},
    {"provider_type": "vertex_service_account", "display_name": "Vertex AI (compte de service)", "available": False, "model_count": 0},
    {"provider_type": "mistral", "display_name": "Mistral AI", "available": False, "model_count": 0},
]

_PROVIDERS_GOOGLE_AND_MISTRAL = [
    {"provider_type": "google_ai_studio", "display_name": "Google AI Studio", "available": True, "model_count": 3},
    {"provider_type": "vertex_api_key", "display_name": "Vertex AI (clé API)", "available": False, "model_count": 0},
    {"provider_type": "vertex_service_account", "display_name": "Vertex AI (compte de service)", "available": False, "model_count": 0},
    {"provider_type": "mistral", "display_name": "Mistral AI", "available": True, "model_count": 2},
]

_MOCK_GOOGLE_MODELS = [
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

_MOCK_MISTRAL_MODELS = [
    ModelInfo(
        model_id="pixtral-large-latest",
        display_name="Pixtral Large",
        provider=ProviderType.MISTRAL,
        supports_vision=True,
        input_token_limit=128_000,
        output_token_limit=None,
    ),
    ModelInfo(
        model_id="pixtral-12b-2409",
        display_name="Pixtral 12B",
        provider=ProviderType.MISTRAL,
        supports_vision=True,
        input_token_limit=128_000,
        output_token_limit=None,
    ),
]


# ---------------------------------------------------------------------------
# GET /api/v1/providers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_providers_returns_list(async_client, monkeypatch):
    monkeypatch.setattr(models_api_module, "get_available_providers", lambda: _PROVIDERS_ALL_UNAVAILABLE)
    resp = await async_client.get("/api/v1/providers")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_list_providers_count(async_client, monkeypatch):
    monkeypatch.setattr(models_api_module, "get_available_providers", lambda: _PROVIDERS_ALL_UNAVAILABLE)
    data = (await async_client.get("/api/v1/providers")).json()
    assert len(data) == 4  # 4 providers connus


@pytest.mark.asyncio
async def test_list_providers_fields(async_client, monkeypatch):
    monkeypatch.setattr(models_api_module, "get_available_providers", lambda: _PROVIDERS_ALL_UNAVAILABLE)
    data = (await async_client.get("/api/v1/providers")).json()
    p = data[0]
    assert "provider_type" in p
    assert "display_name" in p
    assert "available" in p
    assert "model_count" in p


@pytest.mark.asyncio
async def test_list_providers_all_unavailable(async_client, monkeypatch):
    monkeypatch.setattr(models_api_module, "get_available_providers", lambda: _PROVIDERS_ALL_UNAVAILABLE)
    data = (await async_client.get("/api/v1/providers")).json()
    assert all(not p["available"] for p in data)
    assert all(p["model_count"] == 0 for p in data)


@pytest.mark.asyncio
async def test_list_providers_google_available(async_client, monkeypatch):
    monkeypatch.setattr(models_api_module, "get_available_providers", lambda: _PROVIDERS_GOOGLE_ONLY)
    data = (await async_client.get("/api/v1/providers")).json()
    google = next(p for p in data if p["provider_type"] == "google_ai_studio")
    assert google["available"] is True
    assert google["model_count"] == 2


@pytest.mark.asyncio
async def test_list_providers_mistral_available(async_client, monkeypatch):
    monkeypatch.setattr(models_api_module, "get_available_providers", lambda: _PROVIDERS_GOOGLE_AND_MISTRAL)
    data = (await async_client.get("/api/v1/providers")).json()
    mistral = next(p for p in data if p["provider_type"] == "mistral")
    assert mistral["available"] is True
    assert mistral["model_count"] == 2


@pytest.mark.asyncio
async def test_list_providers_includes_mistral_type(async_client, monkeypatch):
    """Mistral est toujours dans la liste même si indisponible."""
    monkeypatch.setattr(models_api_module, "get_available_providers", lambda: _PROVIDERS_ALL_UNAVAILABLE)
    data = (await async_client.get("/api/v1/providers")).json()
    types_ = [p["provider_type"] for p in data]
    assert "mistral" in types_


# ---------------------------------------------------------------------------
# GET /api/v1/providers/{provider_type}/models
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_provider_models_google(async_client, monkeypatch):
    monkeypatch.setattr(
        models_api_module, "list_models_for_provider", lambda ptype: _MOCK_GOOGLE_MODELS
    )
    resp = await async_client.get("/api/v1/providers/google_ai_studio/models")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_get_provider_models_mistral(async_client, monkeypatch):
    monkeypatch.setattr(
        models_api_module, "list_models_for_provider", lambda ptype: _MOCK_MISTRAL_MODELS
    )
    resp = await async_client.get("/api/v1/providers/mistral/models")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    ids = [m["model_id"] for m in data]
    assert "pixtral-large-latest" in ids
    assert "pixtral-12b-2409" in ids


@pytest.mark.asyncio
async def test_get_provider_models_unknown_provider(async_client):
    resp = await async_client.get("/api/v1/providers/openai/models")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_provider_models_not_configured(async_client, monkeypatch):
    """Provider connu mais clé absente → 503."""
    def _raise(ptype):
        raise RuntimeError("Variable d'environnement manquante : MISTRAL_API_KEY")

    monkeypatch.setattr(models_api_module, "list_models_for_provider", _raise)
    resp = await async_client.get("/api/v1/providers/mistral/models")
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_get_provider_models_fields(async_client, monkeypatch):
    monkeypatch.setattr(
        models_api_module, "list_models_for_provider", lambda ptype: _MOCK_MISTRAL_MODELS
    )
    data = (await async_client.get("/api/v1/providers/mistral/models")).json()
    m = data[0]
    assert "model_id" in m
    assert "display_name" in m
    assert "provider" in m
    assert "supports_vision" in m
