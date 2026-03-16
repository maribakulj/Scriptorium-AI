"""
Tests de chargement et validation des profils JSON — un test par profil.
"""
# 1. stdlib
import json
from pathlib import Path

# 2. third-party
import pytest
from pydantic import ValidationError

# 3. local
from app.schemas.corpus_profile import CorpusProfile, LayerType, ScriptType

PROFILES_DIR = Path(__file__).parent.parent.parent / "profiles"
PROFILE_FILES = [
    "medieval-illuminated.json",
    "medieval-textual.json",
    "early-modern-print.json",
    "modern-handwritten.json",
]


def load_profile(filename: str) -> CorpusProfile:
    path = PROFILES_DIR / filename
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return CorpusProfile.model_validate(data)


# ---------------------------------------------------------------------------
# Tests de chargement
# ---------------------------------------------------------------------------

def test_medieval_illuminated_loads():
    profile = load_profile("medieval-illuminated.json")
    assert profile.profile_id == "medieval-illuminated"
    assert profile.script_type == ScriptType.CAROLINE


def test_medieval_textual_loads():
    profile = load_profile("medieval-textual.json")
    assert profile.profile_id == "medieval-textual"
    assert profile.script_type == ScriptType.GOTHIC


def test_early_modern_print_loads():
    profile = load_profile("early-modern-print.json")
    assert profile.profile_id == "early-modern-print"
    assert profile.script_type == ScriptType.PRINT


def test_modern_handwritten_loads():
    profile = load_profile("modern-handwritten.json")
    assert profile.profile_id == "modern-handwritten"
    assert profile.script_type == ScriptType.CURSIVE


# ---------------------------------------------------------------------------
# Tests de cohérence
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename", PROFILE_FILES)
def test_profile_has_required_fields(filename: str):
    profile = load_profile(filename)
    assert profile.profile_id
    assert profile.label
    assert len(profile.language_hints) >= 1
    assert len(profile.active_layers) >= 1
    assert "primary" in profile.prompt_templates


@pytest.mark.parametrize("filename", PROFILE_FILES)
def test_profile_active_layers_are_valid_layer_types(filename: str):
    profile = load_profile(filename)
    valid_values = {lt.value for lt in LayerType}
    for layer in profile.active_layers:
        assert layer.value in valid_values


@pytest.mark.parametrize("filename", PROFILE_FILES)
def test_profile_uncertainty_config_bounds(filename: str):
    profile = load_profile(filename)
    assert 0.0 <= profile.uncertainty_config.flag_below <= 1.0
    assert 0.0 <= profile.uncertainty_config.min_acceptable <= 1.0
    assert profile.uncertainty_config.min_acceptable <= profile.uncertainty_config.flag_below


@pytest.mark.parametrize("filename", PROFILE_FILES)
def test_profile_is_frozen(filename: str):
    profile = load_profile(filename)
    with pytest.raises((TypeError, ValidationError)):
        profile.label = "Hacked"  # type: ignore[misc]


@pytest.mark.parametrize("filename", PROFILE_FILES)
def test_profile_prompt_templates_point_to_txt_files(filename: str):
    profile = load_profile(filename)
    for key, path in profile.prompt_templates.items():
        assert path.endswith(".txt"), f"Template '{key}' doit pointer vers un .txt"
        assert path.startswith("prompts/"), f"Template '{key}' doit être dans prompts/"


def test_medieval_illuminated_has_iconography():
    profile = load_profile("medieval-illuminated.json")
    assert LayerType.ICONOGRAPHY_DETECTION in profile.active_layers


def test_medieval_illuminated_has_iconography_prompt():
    profile = load_profile("medieval-illuminated.json")
    assert "iconography" in profile.prompt_templates


def test_early_modern_print_no_iconography():
    profile = load_profile("early-modern-print.json")
    assert LayerType.ICONOGRAPHY_DETECTION not in profile.active_layers


def test_modern_handwritten_no_iconography():
    profile = load_profile("modern-handwritten.json")
    assert LayerType.ICONOGRAPHY_DETECTION not in profile.active_layers
