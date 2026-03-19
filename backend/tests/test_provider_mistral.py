"""
Tests du provider Mistral AI (MistralProvider).

Stratégie :
  - Pas d'appel réseau réel : les appels SDK sont mockés via monkeypatch.
  - is_configured() vérifié via variables d'env simulées.
  - list_models() : vérification de la liste statique.
  - generate_content() : mock du client Mistral.
"""
# 1. stdlib
import os

# 2. third-party
import pytest

# 3. local
from app.schemas.model_config import ProviderType
from app.services.ai.provider_mistral import MistralProvider, _MISTRAL_VISION_MODELS


# ---------------------------------------------------------------------------
# is_configured()
# ---------------------------------------------------------------------------

def test_is_configured_true(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key-abc")
    assert MistralProvider().is_configured() is True


def test_is_configured_false(monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    assert MistralProvider().is_configured() is False


def test_is_configured_empty_key(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "")
    assert MistralProvider().is_configured() is False


# ---------------------------------------------------------------------------
# provider_type
# ---------------------------------------------------------------------------

def test_provider_type():
    assert MistralProvider().provider_type == ProviderType.MISTRAL


# ---------------------------------------------------------------------------
# list_models()
# ---------------------------------------------------------------------------

def test_list_models_returns_two(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    models = MistralProvider().list_models()
    assert len(models) == 2


def test_list_models_ids(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    models = MistralProvider().list_models()
    ids = {m.model_id for m in models}
    assert "pixtral-large-latest" in ids
    assert "pixtral-12b-2409" in ids


def test_list_models_all_vision(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    models = MistralProvider().list_models()
    assert all(m.supports_vision for m in models)


def test_list_models_all_mistral_provider(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    models = MistralProvider().list_models()
    assert all(m.provider == ProviderType.MISTRAL for m in models)


def test_list_models_raises_if_not_configured(monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="MISTRAL_API_KEY"):
        MistralProvider().list_models()


def test_list_models_display_names(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    models = MistralProvider().list_models()
    display_names = {m.display_name for m in models}
    assert "Pixtral Large" in display_names
    assert "Pixtral 12B" in display_names


# ---------------------------------------------------------------------------
# generate_content() — SDK mocké
# ---------------------------------------------------------------------------

class _MockMessage:
    content = "Voici le JSON de la page."


class _MockChoice:
    message = _MockMessage()


class _MockResponse:
    choices = [_MockChoice()]


class _MockChat:
    def complete(self, *, model, messages):
        return _MockResponse()


class _MockMistralClient:
    chat = _MockChat()


def test_generate_content_returns_text(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")

    def _mock_mistral_cls(api_key):  # noqa: ARG001
        return _MockMistralClient()

    import app.services.ai.provider_mistral as mod
    monkeypatch.setattr(mod, "MistralProvider", MistralProvider)
    # On patch l'import interne dans generate_content()
    import sys
    import types as _types

    fake_mistralai = _types.ModuleType("mistralai")
    fake_mistralai.Mistral = _mock_mistral_cls
    monkeypatch.setitem(sys.modules, "mistralai", fake_mistralai)

    provider = MistralProvider()
    result = provider.generate_content(b"fake-jpeg", "Analyse ce folio.", "pixtral-large-latest")
    assert result == "Voici le JSON de la page."


def test_generate_content_raises_if_not_configured(monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="MISTRAL_API_KEY"):
        MistralProvider().generate_content(b"img", "prompt", "pixtral-large-latest")


def test_generate_content_empty_response(monkeypatch):
    """Si choices est vide, retourne une chaîne vide sans lever d'exception."""
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")

    class _EmptyResp:
        choices = []

    class _EmptyChat:
        def complete(self, *, model, messages):
            return _EmptyResp()

    class _EmptyClient:
        chat = _EmptyChat()

    import sys
    import types as _types

    fake_mistralai = _types.ModuleType("mistralai")
    fake_mistralai.Mistral = lambda api_key: _EmptyClient()
    monkeypatch.setitem(sys.modules, "mistralai", fake_mistralai)

    result = MistralProvider().generate_content(b"img", "prompt", "pixtral-large-latest")
    assert result == ""


def test_generate_content_v0_package_raises_runtime_error(monkeypatch):
    """Si mistralai est installé en v0.x (pas de classe Mistral), lève RuntimeError avec un message clair."""
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")

    import sys
    import types as _types

    # Simuler mistralai v0.x : le module existe mais n'a pas la classe Mistral
    fake_mistralai_v0 = _types.ModuleType("mistralai")
    # Pas d'attribut Mistral → from mistralai import Mistral lèvera ImportError
    monkeypatch.setitem(sys.modules, "mistralai", fake_mistralai_v0)

    with pytest.raises(RuntimeError, match="version 0.x"):
        MistralProvider().generate_content(b"img", "prompt", "pixtral-large-latest")
