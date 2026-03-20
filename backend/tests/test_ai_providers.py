"""
Tests des providers Google AI et du registre de modèles.
Aucun appel réseau réel — tous les clients SDK sont mockés.
"""
# 1. stdlib
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

# 2. third-party
import pytest
from pydantic import ValidationError

# 3. local
from app.schemas.model_config import ModelConfig, ModelInfo, ProviderType
from app.services.ai.base import is_vision_model
from app.services.ai.model_registry import build_model_config, list_all_models
from app.services.ai.provider_google_ai import GoogleAIProvider
from app.services.ai.provider_vertex_key import VertexAPIKeyProvider
from app.services.ai.provider_vertex_sa import VertexServiceAccountProvider

# ---------------------------------------------------------------------------
# Données de test partagées
# ---------------------------------------------------------------------------

FAKE_SA_JSON = {
    "type": "service_account",
    "project_id": "test-project-123",
    "private_key_id": "key-abc",
    "private_key": "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA\n-----END RSA PRIVATE KEY-----\n",
    "client_email": "test-sa@test-project-123.iam.gserviceaccount.com",
    "client_id": "123456789",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
}


def _make_mock_model(
    name: str = "models/gemini-1.5-pro",
    display_name: str = "Gemini 1.5 Pro",
    methods: list[str] | None = None,
    input_token_limit: int = 1_000_000,
    output_token_limit: int = 8192,
) -> MagicMock:
    """Construit un objet modèle factice imitant google.genai.types.Model."""
    m = MagicMock()
    m.name = name
    m.display_name = display_name
    m.supported_generation_methods = methods if methods is not None else ["generateContent"]
    m.input_token_limit = input_token_limit
    m.output_token_limit = output_token_limit
    return m


# ---------------------------------------------------------------------------
# Tests — ModelInfo (schéma)
# ---------------------------------------------------------------------------

def test_model_info_valid():
    info = ModelInfo(
        model_id="models/gemini-1.5-pro",
        display_name="Gemini 1.5 Pro",
        provider=ProviderType.GOOGLE_AI_STUDIO,
        supports_vision=True,
        input_token_limit=1_000_000,
        output_token_limit=8192,
    )
    assert info.model_id == "models/gemini-1.5-pro"
    assert info.supports_vision is True


def test_model_info_is_frozen():
    info = ModelInfo(
        model_id="models/gemini-1.5-pro",
        display_name="Gemini 1.5 Pro",
        provider=ProviderType.GOOGLE_AI_STUDIO,
        supports_vision=True,
    )
    with pytest.raises((TypeError, ValidationError)):
        info.model_id = "changed"  # type: ignore[misc]


def test_model_info_optional_token_limits():
    info = ModelInfo(
        model_id="models/gemini-2.0-flash",
        display_name="Gemini 2.0 Flash",
        provider=ProviderType.VERTEX_SERVICE_ACCOUNT,
        supports_vision=True,
    )
    assert info.input_token_limit is None
    assert info.output_token_limit is None


def test_model_info_all_provider_types():
    for ptype in ProviderType:
        info = ModelInfo(
            model_id=f"models/test-{ptype.value}",
            display_name="Test",
            provider=ptype,
            supports_vision=False,
        )
        assert info.provider == ptype


# ---------------------------------------------------------------------------
# Tests — ModelConfig (schéma)
# ---------------------------------------------------------------------------

def test_model_config_valid():
    cfg = ModelConfig(
        corpus_id="corpus-001",
        selected_model_id="models/gemini-1.5-pro",
        selected_model_display_name="Gemini 1.5 Pro",
        provider=ProviderType.GOOGLE_AI_STUDIO,
        supports_vision=True,
        last_fetched_at=datetime(2026, 3, 17, tzinfo=timezone.utc),
        available_models=[],
    )
    assert cfg.corpus_id == "corpus-001"
    assert cfg.supports_vision is True


def test_model_config_missing_required_field():
    with pytest.raises(ValidationError):
        ModelConfig.model_validate({"corpus_id": "x"})


# ---------------------------------------------------------------------------
# Tests — is_vision_model helper
# ---------------------------------------------------------------------------

def test_is_vision_model_gemini():
    m = MagicMock()
    m.name = "models/gemini-1.5-pro"
    m.display_name = "Gemini 1.5 Pro"
    assert is_vision_model(m) is True


def test_is_vision_model_vision_in_name():
    m = MagicMock()
    m.name = "models/some-vision-model"
    m.display_name = "Some Model"
    assert is_vision_model(m) is True


def test_is_vision_model_vision_in_display():
    m = MagicMock()
    m.name = "models/some-model"
    m.display_name = "Some Vision Model"
    assert is_vision_model(m) is True


def test_is_vision_model_text_only():
    m = MagicMock()
    m.name = "models/text-embedding-004"
    m.display_name = "Text Embedding"
    assert is_vision_model(m) is False


# ---------------------------------------------------------------------------
# Tests — GoogleAIProvider
# ---------------------------------------------------------------------------

def test_google_ai_provider_not_configured(monkeypatch):
    monkeypatch.delenv("GOOGLE_AI_STUDIO_API_KEY", raising=False)
    provider = GoogleAIProvider()
    assert provider.is_configured() is False


def test_google_ai_provider_configured(monkeypatch):
    monkeypatch.setenv("GOOGLE_AI_STUDIO_API_KEY", "fake-key")
    provider = GoogleAIProvider()
    assert provider.is_configured() is True


def test_google_ai_provider_type():
    assert GoogleAIProvider().provider_type == ProviderType.GOOGLE_AI_STUDIO


def test_google_ai_provider_list_models_not_configured(monkeypatch):
    monkeypatch.delenv("GOOGLE_AI_STUDIO_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GOOGLE_AI_STUDIO_API_KEY"):
        GoogleAIProvider().list_models()


def test_google_ai_provider_list_models_success(monkeypatch):
    monkeypatch.setenv("GOOGLE_AI_STUDIO_API_KEY", "fake-key")
    mock_model = _make_mock_model()

    with patch("app.services.ai.provider_google_ai.genai.Client") as MockClient:
        MockClient.return_value.models.list.return_value = [mock_model]
        models = GoogleAIProvider().list_models()

    assert len(models) == 1
    assert models[0].model_id == "models/gemini-1.5-pro"
    assert models[0].provider == ProviderType.GOOGLE_AI_STUDIO
    assert models[0].supports_vision is True
    MockClient.assert_called_once_with(api_key="fake-key")


def test_google_ai_provider_filters_non_generate_content(monkeypatch):
    monkeypatch.setenv("GOOGLE_AI_STUDIO_API_KEY", "fake-key")
    embedding = _make_mock_model(
        name="models/text-embedding-004",
        display_name="Text Embedding",
        methods=["embedContent"],
    )
    gemini = _make_mock_model()

    with patch("app.services.ai.provider_google_ai.genai.Client") as MockClient:
        MockClient.return_value.models.list.return_value = [embedding, gemini]
        models = GoogleAIProvider().list_models()

    assert len(models) == 1
    assert models[0].model_id == "models/gemini-1.5-pro"


def test_google_ai_provider_empty_list(monkeypatch):
    monkeypatch.setenv("GOOGLE_AI_STUDIO_API_KEY", "fake-key")
    with patch("app.services.ai.provider_google_ai.genai.Client") as MockClient:
        MockClient.return_value.models.list.return_value = []
        models = GoogleAIProvider().list_models()
    assert models == []


# ---------------------------------------------------------------------------
# Tests — VertexAPIKeyProvider
# ---------------------------------------------------------------------------

def test_vertex_key_provider_not_configured(monkeypatch):
    monkeypatch.delenv("VERTEX_API_KEY", raising=False)
    assert VertexAPIKeyProvider().is_configured() is False


def test_vertex_key_provider_configured(monkeypatch):
    monkeypatch.setenv("VERTEX_API_KEY", "fake-vertex-key")
    assert VertexAPIKeyProvider().is_configured() is True


def test_vertex_key_provider_type():
    assert VertexAPIKeyProvider().provider_type == ProviderType.VERTEX_API_KEY


def test_vertex_key_provider_list_models_not_configured(monkeypatch):
    monkeypatch.delenv("VERTEX_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="VERTEX_API_KEY"):
        VertexAPIKeyProvider().list_models()


def test_vertex_key_provider_list_models_success(monkeypatch):
    monkeypatch.setenv("VERTEX_API_KEY", "fake-vertex-key")
    mock_model = _make_mock_model(
        name="models/gemini-2.0-flash",
        display_name="Gemini 2.0 Flash",
    )

    with patch("app.services.ai.provider_vertex_key.genai.Client") as MockClient:
        MockClient.return_value.models.list.return_value = [mock_model]
        models = VertexAPIKeyProvider().list_models()

    assert len(models) == 1
    assert models[0].model_id == "models/gemini-2.0-flash"
    assert models[0].provider == ProviderType.VERTEX_API_KEY
    # vertexai=True est obligatoire pour router vers aiplatform.googleapis.com
    # (sans ça, le SDK route vers generativelanguage.googleapis.com → 403)
    MockClient.assert_called_once_with(vertexai=True, api_key="fake-vertex-key")


def test_vertex_key_provider_list_models_includes_gemini_without_methods(monkeypatch):
    """Vertex peut retourner des modèles sans supported_generation_methods.
    Si le nom contient 'gemini', on les inclut quand même."""
    monkeypatch.setenv("VERTEX_API_KEY", "fake-vertex-key")
    model_no_methods = _make_mock_model(
        name="publishers/google/models/gemini-1.5-pro-002",
        display_name="Gemini 1.5 Pro 002",
        methods=[],
    )
    model_non_gemini = _make_mock_model(
        name="publishers/google/models/text-bison",
        display_name="Text Bison",
        methods=[],
    )

    with patch("app.services.ai.provider_vertex_key.genai.Client") as MockClient:
        MockClient.return_value.models.list.return_value = [model_no_methods, model_non_gemini]
        models = VertexAPIKeyProvider().list_models()

    assert len(models) == 1
    assert "gemini" in models[0].model_id.lower()


def test_vertex_key_provider_generate_content_uses_vertexai(monkeypatch):
    """generate_content doit aussi utiliser vertexai=True."""
    monkeypatch.setenv("VERTEX_API_KEY", "fake-vertex-key")

    with patch("app.services.ai.provider_vertex_key.genai.Client") as MockClient:
        with patch("app.services.ai.provider_vertex_key.types.Part.from_bytes") as mock_part:
            mock_part.return_value = "fake-part"
            MockClient.return_value.models.generate_content.return_value.text = "result"
            result = VertexAPIKeyProvider().generate_content(b"img", "prompt", "gemini-2.0-flash")

    MockClient.assert_called_once_with(vertexai=True, api_key="fake-vertex-key")
    assert result == "result"


# ---------------------------------------------------------------------------
# Tests — VertexServiceAccountProvider
# ---------------------------------------------------------------------------

def test_vertex_sa_provider_not_configured(monkeypatch):
    monkeypatch.delenv("VERTEX_SERVICE_ACCOUNT_JSON", raising=False)
    assert VertexServiceAccountProvider().is_configured() is False


def test_vertex_sa_provider_configured(monkeypatch):
    monkeypatch.setenv("VERTEX_SERVICE_ACCOUNT_JSON", json.dumps(FAKE_SA_JSON))
    assert VertexServiceAccountProvider().is_configured() is True


def test_vertex_sa_provider_type():
    assert VertexServiceAccountProvider().provider_type == ProviderType.VERTEX_SERVICE_ACCOUNT


def test_vertex_sa_provider_list_models_not_configured(monkeypatch):
    monkeypatch.delenv("VERTEX_SERVICE_ACCOUNT_JSON", raising=False)
    with pytest.raises(RuntimeError, match="VERTEX_SERVICE_ACCOUNT_JSON"):
        VertexServiceAccountProvider().list_models()


def test_vertex_sa_provider_invalid_json(monkeypatch):
    monkeypatch.setenv("VERTEX_SERVICE_ACCOUNT_JSON", "not-valid-json{{{")
    with pytest.raises(ValueError, match="JSON invalide"):
        VertexServiceAccountProvider().list_models()


def test_vertex_sa_provider_missing_project_id(monkeypatch):
    sa_no_project = {k: v for k, v in FAKE_SA_JSON.items() if k != "project_id"}
    monkeypatch.setenv("VERTEX_SERVICE_ACCOUNT_JSON", json.dumps(sa_no_project))
    with pytest.raises(ValueError, match="project_id"):
        VertexServiceAccountProvider().list_models()


def test_vertex_sa_provider_list_models_success(monkeypatch):
    monkeypatch.setenv("VERTEX_SERVICE_ACCOUNT_JSON", json.dumps(FAKE_SA_JSON))
    mock_model = _make_mock_model(
        name="models/gemini-1.5-pro-002",
        display_name="Gemini 1.5 Pro 002",
    )
    mock_credentials = MagicMock()

    with patch(
        "app.services.ai.provider_vertex_sa.service_account.Credentials.from_service_account_info",
        return_value=mock_credentials,
    ) as mock_creds_factory:
        with patch("app.services.ai.provider_vertex_sa.genai.Client") as MockClient:
            MockClient.return_value.models.list.return_value = [mock_model]
            models = VertexServiceAccountProvider().list_models()

    assert len(models) == 1
    assert models[0].model_id == "models/gemini-1.5-pro-002"
    assert models[0].provider == ProviderType.VERTEX_SERVICE_ACCOUNT
    mock_creds_factory.assert_called_once_with(
        FAKE_SA_JSON,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    MockClient.assert_called_once_with(
        vertexai=True,
        project="test-project-123",
        location="us-central1",
        credentials=mock_credentials,
    )


def test_vertex_sa_provider_filters_non_generate_content(monkeypatch):
    monkeypatch.setenv("VERTEX_SERVICE_ACCOUNT_JSON", json.dumps(FAKE_SA_JSON))
    embedding = _make_mock_model(
        name="models/textembedding-gecko",
        display_name="Text Embedding Gecko",
        methods=["embedContent"],
    )

    with patch(
        "app.services.ai.provider_vertex_sa.service_account.Credentials.from_service_account_info",
        return_value=MagicMock(),
    ):
        with patch("app.services.ai.provider_vertex_sa.genai.Client") as MockClient:
            MockClient.return_value.models.list.return_value = [embedding]
            models = VertexServiceAccountProvider().list_models()

    assert models == []


# ---------------------------------------------------------------------------
# Tests — model_registry.list_all_models
# ---------------------------------------------------------------------------

def test_list_all_models_no_providers_configured(monkeypatch):
    monkeypatch.delenv("GOOGLE_AI_STUDIO_API_KEY", raising=False)
    monkeypatch.delenv("VERTEX_API_KEY", raising=False)
    monkeypatch.delenv("VERTEX_SERVICE_ACCOUNT_JSON", raising=False)
    result = list_all_models()
    assert result == []


def test_list_all_models_one_provider(monkeypatch):
    monkeypatch.setenv("GOOGLE_AI_STUDIO_API_KEY", "fake-key")
    monkeypatch.delenv("VERTEX_API_KEY", raising=False)
    monkeypatch.delenv("VERTEX_SERVICE_ACCOUNT_JSON", raising=False)
    mock_model = _make_mock_model()

    with patch("app.services.ai.provider_google_ai.genai.Client") as MockClient:
        MockClient.return_value.models.list.return_value = [mock_model]
        result = list_all_models()

    assert len(result) == 1
    assert result[0].provider == ProviderType.GOOGLE_AI_STUDIO


def test_list_all_models_aggregates_multiple_providers(monkeypatch):
    # Note : provider_google_ai et provider_vertex_key partagent le même objet
    # google.genai (import module). On patch au niveau des méthodes pour éviter
    # que le second patch.object("...genai.Client") écrase le premier.
    monkeypatch.setenv("GOOGLE_AI_STUDIO_API_KEY", "fake-key-ai")
    monkeypatch.setenv("VERTEX_API_KEY", "fake-key-vertex")
    monkeypatch.delenv("VERTEX_SERVICE_ACCOUNT_JSON", raising=False)

    models_ai = [ModelInfo(
        model_id="models/gemini-1.5-pro",
        display_name="Gemini 1.5 Pro",
        provider=ProviderType.GOOGLE_AI_STUDIO,
        supports_vision=True,
    )]
    models_vertex = [ModelInfo(
        model_id="models/gemini-2.0-flash",
        display_name="Gemini 2.0 Flash",
        provider=ProviderType.VERTEX_API_KEY,
        supports_vision=True,
    )]

    with patch.object(GoogleAIProvider, "list_models", return_value=models_ai):
        with patch.object(VertexAPIKeyProvider, "list_models", return_value=models_vertex):
            result = list_all_models()

    assert len(result) == 2
    providers = {m.provider for m in result}
    assert ProviderType.GOOGLE_AI_STUDIO in providers
    assert ProviderType.VERTEX_API_KEY in providers


def test_list_all_models_failing_provider_is_skipped(monkeypatch):
    monkeypatch.setenv("GOOGLE_AI_STUDIO_API_KEY", "bad-key")
    monkeypatch.setenv("VERTEX_API_KEY", "good-key")
    monkeypatch.delenv("VERTEX_SERVICE_ACCOUNT_JSON", raising=False)

    models_vertex = [ModelInfo(
        model_id="models/gemini-2.0-flash",
        display_name="Gemini 2.0 Flash",
        provider=ProviderType.VERTEX_API_KEY,
        supports_vision=True,
    )]

    with patch.object(GoogleAIProvider, "list_models", side_effect=Exception("API key invalid")):
        with patch.object(VertexAPIKeyProvider, "list_models", return_value=models_vertex):
            result = list_all_models()

    assert len(result) == 1
    assert result[0].provider == ProviderType.VERTEX_API_KEY


# ---------------------------------------------------------------------------
# Tests — model_registry.build_model_config
# ---------------------------------------------------------------------------

def test_build_model_config_valid(monkeypatch):
    monkeypatch.setenv("GOOGLE_AI_STUDIO_API_KEY", "fake-key")
    monkeypatch.delenv("VERTEX_API_KEY", raising=False)
    monkeypatch.delenv("VERTEX_SERVICE_ACCOUNT_JSON", raising=False)
    mock_model = _make_mock_model()

    with patch("app.services.ai.provider_google_ai.genai.Client") as MockClient:
        MockClient.return_value.models.list.return_value = [mock_model]
        cfg = build_model_config("corpus-001", "models/gemini-1.5-pro")

    assert cfg.corpus_id == "corpus-001"
    assert cfg.selected_model_id == "models/gemini-1.5-pro"
    assert cfg.selected_model_display_name == "Gemini 1.5 Pro"
    assert cfg.provider == ProviderType.GOOGLE_AI_STUDIO
    assert cfg.supports_vision is True
    assert len(cfg.available_models) == 1
    assert isinstance(cfg.available_models[0], dict)


def test_build_model_config_unknown_model(monkeypatch):
    monkeypatch.setenv("GOOGLE_AI_STUDIO_API_KEY", "fake-key")
    monkeypatch.delenv("VERTEX_API_KEY", raising=False)
    monkeypatch.delenv("VERTEX_SERVICE_ACCOUNT_JSON", raising=False)
    mock_model = _make_mock_model()

    with patch("app.services.ai.provider_google_ai.genai.Client") as MockClient:
        MockClient.return_value.models.list.return_value = [mock_model]
        with pytest.raises(ValueError, match="non disponible"):
            build_model_config("corpus-001", "models/nonexistent-model")


def test_build_model_config_no_providers(monkeypatch):
    monkeypatch.delenv("GOOGLE_AI_STUDIO_API_KEY", raising=False)
    monkeypatch.delenv("VERTEX_API_KEY", raising=False)
    monkeypatch.delenv("VERTEX_SERVICE_ACCOUNT_JSON", raising=False)
    with pytest.raises(ValueError, match="non disponible"):
        build_model_config("corpus-001", "models/gemini-1.5-pro")
