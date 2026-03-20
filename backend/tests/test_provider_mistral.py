"""
Tests du provider Mistral AI (MistralProvider).

Stratégie :
  - Pas d'appel réseau réel : SDK mocké via sys.modules.
  - is_configured() : vérifié via variables d'env ET import mock.
  - list_models() : mock de client.models.list() → comportement dynamique
    et fallback statique quand l'API échoue.
  - generate_content() : bifurcation vision / texte seul.
"""
# 1. stdlib
import sys
import types as _types

# 2. third-party
import pytest

# 3. local
from app.schemas.model_config import ProviderType
from app.services.ai.provider_mistral import (
    MistralProvider,
    _MISTRAL_FALLBACK_MODELS,
    _MISTRAL_VISION_MODELS,  # alias backward-compat
    _model_supports_vision,
)


# ---------------------------------------------------------------------------
# Helpers — faux SDK Mistral
# ---------------------------------------------------------------------------

class _FakeCaps:
    """Capabilities d'un modèle Mistral (SDK v1.x)."""
    def __init__(self, vision: bool = False):
        self.vision = vision


class _FakeModel:
    def __init__(self, id_: str, vision: bool = False, display_name: str | None = None):
        self.id = id_
        self.display_name = display_name or id_
        self.capabilities = _FakeCaps(vision=vision)


class _FakeModelsListResponse:
    def __init__(self, models: list[_FakeModel]):
        self.data = models


class _FakeModelsAPI:
    def __init__(self, models: list[_FakeModel]):
        self._models = models

    def list(self) -> _FakeModelsListResponse:
        return _FakeModelsListResponse(self._models)


class _FakeMessage:
    content = "Voici le JSON de la page."


class _FakeChoice:
    message = _FakeMessage()


class _FakeChatResponse:
    choices = [_FakeChoice()]


class _FakeChat:
    def complete(self, *, model, messages):
        return _FakeChatResponse()


def _make_fake_mistralai(models: list[_FakeModel] | None = None) -> _types.ModuleType:
    """Crée un faux module mistralai avec Mistral class et modèles mockés."""
    fake = _types.ModuleType("mistralai")
    chat = _FakeChat()
    models_api = _FakeModelsAPI(models or [])

    class _FakeMistral:
        def __init__(self, api_key):
            self.chat = chat
            self.models = models_api

    fake.Mistral = _FakeMistral
    return fake


# ---------------------------------------------------------------------------
# _model_supports_vision() — helper pur
# ---------------------------------------------------------------------------

def test_vision_detection_pixtral_by_name():
    assert _model_supports_vision("pixtral-large-latest") is True
    assert _model_supports_vision("pixtral-12b-2409") is True


def test_vision_detection_text_models_by_name():
    assert _model_supports_vision("mistral-large-latest") is False
    assert _model_supports_vision("mistral-small-latest") is False
    assert _model_supports_vision("codestral-latest") is False


def test_vision_detection_uses_capabilities_when_available():
    m_vision = _FakeModel("some-model", vision=True)
    m_text = _FakeModel("some-model", vision=False)
    assert _model_supports_vision("some-model", m_vision) is True
    assert _model_supports_vision("some-model", m_text) is False


def test_vision_detection_capabilities_override_name():
    """capabilities.vision=False surpasse un nom contenant 'pixtral'."""
    m = _FakeModel("pixtral-test", vision=False)
    assert _model_supports_vision("pixtral-test", m) is False


# ---------------------------------------------------------------------------
# is_configured()
# ---------------------------------------------------------------------------

def test_is_configured_true(monkeypatch):
    """Clé présente + mistralai v1.x importable → True."""
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key-abc")
    fake = _make_fake_mistralai()
    monkeypatch.setitem(sys.modules, "mistralai", fake)
    assert MistralProvider().is_configured() is True


def test_is_configured_false_no_key(monkeypatch):
    """Pas de clé → False, même si mistralai est installé."""
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    fake = _make_fake_mistralai()
    monkeypatch.setitem(sys.modules, "mistralai", fake)
    assert MistralProvider().is_configured() is False


def test_is_configured_false_empty_key(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "")
    fake = _make_fake_mistralai()
    monkeypatch.setitem(sys.modules, "mistralai", fake)
    assert MistralProvider().is_configured() is False


def test_is_configured_false_v0x_installed(monkeypatch):
    """Clé présente mais mistralai v0.x (pas de classe Mistral) → False."""
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    fake_v0 = _types.ModuleType("mistralai")
    # Pas d'attribut Mistral → from mistralai import Mistral lèvera ImportError
    monkeypatch.setitem(sys.modules, "mistralai", fake_v0)
    assert MistralProvider().is_configured() is False


def test_is_configured_false_mistralai_not_installed(monkeypatch):
    """Clé présente mais mistralai pas du tout installé → False."""
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    # Supprimer mistralai du chemin d'import
    monkeypatch.setitem(sys.modules, "mistralai", None)  # type: ignore[arg-type]
    assert MistralProvider().is_configured() is False


# ---------------------------------------------------------------------------
# provider_type
# ---------------------------------------------------------------------------

def test_provider_type(monkeypatch):
    fake = _make_fake_mistralai()
    monkeypatch.setitem(sys.modules, "mistralai", fake)
    assert MistralProvider().provider_type == ProviderType.MISTRAL


# ---------------------------------------------------------------------------
# list_models() — comportement dynamique
# ---------------------------------------------------------------------------

def _setup_list_models(monkeypatch, models: list[_FakeModel]) -> None:
    """Configure le monkeypatch pour list_models()."""
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    fake = _make_fake_mistralai(models)
    monkeypatch.setitem(sys.modules, "mistralai", fake)


def test_list_models_dynamic_returns_all_non_embed(monkeypatch):
    """list_models() retourne tous les modèles sauf embeddings/modération.
    mistral-ocr-latest est toujours ajouté s'il n'est pas dans la liste dynamique."""
    _setup_list_models(monkeypatch, [
        _FakeModel("pixtral-large-latest", vision=True),
        _FakeModel("pixtral-12b-2409", vision=True),
        _FakeModel("mistral-large-latest", vision=False),
        _FakeModel("mistral-embed", vision=False),       # exclut
        _FakeModel("mistral-moderation", vision=False),  # exclut
    ])
    models = MistralProvider().list_models()
    ids = {m.model_id for m in models}
    assert "pixtral-large-latest" in ids
    assert "pixtral-12b-2409" in ids
    assert "mistral-large-latest" in ids
    assert "mistral-ocr-latest" in ids   # ajouté automatiquement
    assert "mistral-embed" not in ids
    assert "mistral-moderation" not in ids
    assert len(models) == 4  # 3 filtres + OCR ajouté


def test_list_models_vision_flag_from_capabilities(monkeypatch):
    """supports_vision reflète capabilities.vision du SDK."""
    _setup_list_models(monkeypatch, [
        _FakeModel("pixtral-large-latest", vision=True),
        _FakeModel("mistral-large-latest", vision=False),
    ])
    models = MistralProvider().list_models()
    by_id = {m.model_id: m for m in models}
    assert by_id["pixtral-large-latest"].supports_vision is True
    assert by_id["mistral-large-latest"].supports_vision is False


def test_list_models_all_mistral_provider(monkeypatch):
    _setup_list_models(monkeypatch, [
        _FakeModel("pixtral-large-latest", vision=True),
        _FakeModel("mistral-large-latest", vision=False),
    ])
    models = MistralProvider().list_models()
    assert all(m.provider == ProviderType.MISTRAL for m in models)


def test_list_models_fallback_when_api_fails(monkeypatch):
    """Si client.models.list() lève une exception, retourne la liste statique."""
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    fake = _types.ModuleType("mistralai")

    class _FailingModels:
        def list(self):
            raise RuntimeError("API timeout")

    class _FakeMistral:
        def __init__(self, api_key):
            self.models = _FailingModels()

    fake.Mistral = _FakeMistral
    monkeypatch.setitem(sys.modules, "mistralai", fake)

    models = MistralProvider().list_models()
    # Fallback = _MISTRAL_FALLBACK_MODELS = Pixtral Large + 12B + mistral-ocr-latest
    assert len(models) == 3
    ids = {m.model_id for m in models}
    assert "pixtral-large-latest" in ids
    assert "pixtral-12b-2409" in ids
    assert "mistral-ocr-latest" in ids


def test_list_models_raises_if_not_configured(monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="MISTRAL_API_KEY"):
        MistralProvider().list_models()


def test_list_models_fallback_backward_compat():
    """_MISTRAL_VISION_MODELS est un alias de _MISTRAL_FALLBACK_MODELS."""
    assert _MISTRAL_VISION_MODELS is _MISTRAL_FALLBACK_MODELS


# ---------------------------------------------------------------------------
# generate_content() — bifurcation vision / texte
# ---------------------------------------------------------------------------

def test_generate_content_vision_model_returns_text(monkeypatch):
    """Modèle vision (Pixtral) : envoie l'image et retourne la réponse."""
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    fake = _make_fake_mistralai()
    monkeypatch.setitem(sys.modules, "mistralai", fake)

    result = MistralProvider().generate_content(
        b"fake-jpeg", "Analyse ce folio.", "pixtral-large-latest"
    )
    assert result == "Voici le JSON de la page."


def test_generate_content_text_model_returns_text(monkeypatch):
    """Modèle texte (Mistral Large) : envoie seulement le prompt, retourne la réponse."""
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    fake = _make_fake_mistralai()
    monkeypatch.setitem(sys.modules, "mistralai", fake)

    result = MistralProvider().generate_content(
        b"fake-jpeg", "Analyse ce folio.", "mistral-large-latest"
    )
    assert result == "Voici le JSON de la page."


def test_generate_content_vision_sends_image_url(monkeypatch):
    """Modèle vision : le message content contient image_url + text."""
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    captured: list[dict] = []

    class _CapturingChat:
        def complete(self, *, model, messages):
            captured.extend(messages)
            return _FakeChatResponse()

    class _FakeMistral:
        def __init__(self, api_key):
            self.chat = _CapturingChat()
            self.models = _FakeModelsAPI([])

    fake = _types.ModuleType("mistralai")
    fake.Mistral = _FakeMistral
    monkeypatch.setitem(sys.modules, "mistralai", fake)

    MistralProvider().generate_content(b"jpeg", "prompt", "pixtral-large-latest")

    assert len(captured) == 1
    content = captured[0]["content"]
    assert isinstance(content, list)
    types_sent = {item["type"] for item in content}
    assert "image_url" in types_sent
    assert "text" in types_sent


def test_generate_content_text_sends_string_content(monkeypatch):
    """Modèle texte : le message content est une chaîne (pas d'image)."""
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    captured: list[dict] = []

    class _CapturingChat:
        def complete(self, *, model, messages):
            captured.extend(messages)
            return _FakeChatResponse()

    class _FakeMistral:
        def __init__(self, api_key):
            self.chat = _CapturingChat()
            self.models = _FakeModelsAPI([])

    fake = _types.ModuleType("mistralai")
    fake.Mistral = _FakeMistral
    monkeypatch.setitem(sys.modules, "mistralai", fake)

    MistralProvider().generate_content(b"jpeg", "mon prompt", "mistral-large-latest")

    assert len(captured) == 1
    assert captured[0]["content"] == "mon prompt"


def test_generate_content_raises_if_not_configured(monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="MISTRAL_API_KEY"):
        MistralProvider().generate_content(b"img", "prompt", "pixtral-large-latest")


def test_generate_content_raises_if_v0x_installed(monkeypatch):
    """Si mistralai v0.x est installé (is_configured() → False), RuntimeError clair."""
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    fake_v0 = _types.ModuleType("mistralai")
    monkeypatch.setitem(sys.modules, "mistralai", fake_v0)

    with pytest.raises(RuntimeError, match="mistralai>=1.0"):
        MistralProvider().generate_content(b"img", "prompt", "pixtral-large-latest")


def test_generate_content_empty_response(monkeypatch):
    """Si choices est vide, retourne une chaîne vide sans exception."""
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")

    class _EmptyChat:
        def complete(self, *, model, messages):
            class _EmptyResp:
                choices = []
            return _EmptyResp()

    class _FakeMistral:
        def __init__(self, api_key):
            self.chat = _EmptyChat()
            self.models = _FakeModelsAPI([])

    fake = _types.ModuleType("mistralai")
    fake.Mistral = _FakeMistral
    monkeypatch.setitem(sys.modules, "mistralai", fake)

    result = MistralProvider().generate_content(b"img", "prompt", "pixtral-large-latest")
    assert result == ""


# ---------------------------------------------------------------------------
# generate_content() — chemin OCR dédié (mistral-ocr-latest)
# ---------------------------------------------------------------------------

def test_generate_content_ocr_uses_ocr_endpoint(monkeypatch):
    """mistral-ocr-latest utilise client.ocr.process(), pas client.chat.complete()."""
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")

    ocr_calls: list[dict] = []
    chat_calls: list = []

    class _FakeOCRPage:
        markdown = "Explicit liber primus..."

    class _FakeOCRResponse:
        pages = [_FakeOCRPage(), _FakeOCRPage()]

    class _FakeOCR:
        def process(self, *, model, document):
            ocr_calls.append({"model": model, "document": document})
            return _FakeOCRResponse()

    class _FakeChat:
        def complete(self, *, model, messages):
            chat_calls.append(messages)

    class _FakeMistral:
        def __init__(self, api_key):
            self.ocr = _FakeOCR()
            self.chat = _FakeChat()
            self.models = _FakeModelsAPI([])

    fake = _types.ModuleType("mistralai")
    fake.Mistral = _FakeMistral
    monkeypatch.setitem(sys.modules, "mistralai", fake)

    result = MistralProvider().generate_content(b"jpeg", "prompt", "mistral-ocr-latest")

    # OCR endpoint appelé, pas chat
    assert len(ocr_calls) == 1
    assert len(chat_calls) == 0
    assert ocr_calls[0]["model"] == "mistral-ocr-latest"
    # Document doit être image_url avec data URI
    doc = ocr_calls[0]["document"]
    assert doc["type"] == "image_url"
    assert doc["image_url"]["url"].startswith("data:image/jpeg;base64,")
    # Résultat = pages concaténées
    assert "Explicit liber primus..." in result


def test_generate_content_ocr_concatenates_pages(monkeypatch):
    """OCR multi-pages : les markdowns sont concaténés par double saut de ligne."""
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")

    class _Page:
        def __init__(self, md):
            self.markdown = md

    class _FakeOCRResponse:
        pages = [_Page("Page 1 texte"), _Page("Page 2 texte")]

    class _FakeOCR:
        def process(self, **kwargs):
            return _FakeOCRResponse()

    class _FakeMistral:
        def __init__(self, api_key):
            self.ocr = _FakeOCR()
            self.models = _FakeModelsAPI([])

    fake = _types.ModuleType("mistralai")
    fake.Mistral = _FakeMistral
    monkeypatch.setitem(sys.modules, "mistralai", fake)

    result = MistralProvider().generate_content(b"jpeg", "prompt", "mistral-ocr-latest")

    assert "Page 1 texte" in result
    assert "Page 2 texte" in result
    assert "\n\n" in result


def test_generate_content_ocr_model_not_called_for_vision(monkeypatch):
    """Un modèle Pixtral NE passe PAS par l'endpoint OCR."""
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    ocr_called = []

    class _FakeOCR:
        def process(self, **kwargs):
            ocr_called.append(True)

    class _FakeMistral:
        def __init__(self, api_key):
            self.ocr = _FakeOCR()
            self.chat = type("C", (), {"complete": lambda self, **k: _FakeChatResponse()})()
            self.models = _FakeModelsAPI([])

    fake = _types.ModuleType("mistralai")
    fake.Mistral = _FakeMistral
    monkeypatch.setitem(sys.modules, "mistralai", fake)

    MistralProvider().generate_content(b"jpeg", "prompt", "pixtral-large-latest")
    assert len(ocr_called) == 0


def test_generate_content_ocr_model_detected_by_id(monkeypatch):
    """Tout modèle contenant 'ocr' dans l'ID utilise l'endpoint OCR."""
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    ocr_called = []

    class _FakeOCR:
        def process(self, **kwargs):
            ocr_called.append(True)
            class R:
                pages = []
            return R()

    class _FakeMistral:
        def __init__(self, api_key):
            self.ocr = _FakeOCR()
            self.models = _FakeModelsAPI([])

    fake = _types.ModuleType("mistralai")
    fake.Mistral = _FakeMistral
    monkeypatch.setitem(sys.modules, "mistralai", fake)

    MistralProvider().generate_content(b"jpeg", "prompt", "mistral-ocr-latest")
    assert len(ocr_called) == 1
