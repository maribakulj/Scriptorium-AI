"""
Tests des schémas Pydantic — corpus_profile, page_master, annotation.
"""
# 1. stdlib
from datetime import datetime, timezone

# 2. third-party
import pytest
from pydantic import ValidationError

# 3. local
from app.schemas.corpus_profile import (
    CorpusProfile,
    ExportConfig,
    LayerType,
    ScriptType,
    UncertaintyConfig,
)
from app.schemas.page_master import (
    Commentary,
    CommentaryClaim,
    EditorialInfo,
    EditorialStatus,
    OCRResult,
    PageMaster,
    ProcessingInfo,
    Region,
    RegionType,
    Translation,
)
from app.schemas.annotation import AnnotationLayer, LayerStatus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def minimal_corpus_profile() -> dict:
    return {
        "profile_id": "test-profile",
        "label": "Test Profile",
        "language_hints": ["la"],
        "script_type": "caroline",
        "active_layers": ["ocr_diplomatic", "translation_fr"],
        "prompt_templates": {"primary": "prompts/test/primary_v1.txt"},
        "uncertainty_config": {"flag_below": 0.4, "min_acceptable": 0.25},
        "export_config": {"mets": True, "alto": True, "tei": False},
    }


@pytest.fixture
def minimal_page_master() -> dict:
    return {
        "page_id": "test-corpus-0001r",
        "corpus_profile": "test-profile",
        "manuscript_id": "ms-test-001",
        "folio_label": "0001r",
        "sequence": 1,
        "image": {
            "master": "data/corpora/test/masters/0001r.tif",
            "derivative_web": "data/corpora/test/derivatives/0001r.jpg",
            "iiif_base": "",
            "width": 2000,
            "height": 3000,
        },
        "layout": {"regions": []},
    }


@pytest.fixture
def valid_region() -> dict:
    return {
        "id": "r1",
        "type": "text_block",
        "bbox": [10, 20, 300, 400],
        "confidence": 0.95,
    }


# ---------------------------------------------------------------------------
# Tests — CorpusProfile
# ---------------------------------------------------------------------------

def test_corpus_profile_valid(minimal_corpus_profile):
    profile = CorpusProfile.model_validate(minimal_corpus_profile)
    assert profile.profile_id == "test-profile"
    assert profile.script_type == ScriptType.CAROLINE
    assert LayerType.OCR_DIPLOMATIC in profile.active_layers


def test_corpus_profile_is_frozen(minimal_corpus_profile):
    profile = CorpusProfile.model_validate(minimal_corpus_profile)
    with pytest.raises((TypeError, ValidationError)):
        profile.label = "Modified"  # type: ignore[misc]


def test_corpus_profile_all_script_types(minimal_corpus_profile):
    for script in ScriptType:
        data = {**minimal_corpus_profile, "script_type": script.value}
        profile = CorpusProfile.model_validate(data)
        assert profile.script_type == script


def test_corpus_profile_all_layer_types(minimal_corpus_profile):
    all_layers = [lt.value for lt in LayerType]
    data = {**minimal_corpus_profile, "active_layers": all_layers}
    profile = CorpusProfile.model_validate(data)
    assert len(profile.active_layers) == len(LayerType)


def test_uncertainty_config_defaults():
    config = UncertaintyConfig()
    assert config.flag_below == 0.4
    assert config.min_acceptable == 0.25


def test_uncertainty_config_bounds():
    with pytest.raises(ValidationError):
        UncertaintyConfig(flag_below=1.5)
    with pytest.raises(ValidationError):
        UncertaintyConfig(min_acceptable=-0.1)


def test_export_config_defaults():
    config = ExportConfig()
    assert config.mets is True
    assert config.alto is True
    assert config.tei is False


def test_corpus_profile_missing_required_field():
    with pytest.raises(ValidationError):
        CorpusProfile.model_validate({"profile_id": "x"})


# ---------------------------------------------------------------------------
# Tests — Region / bbox
# ---------------------------------------------------------------------------

def test_region_valid_bbox(valid_region):
    region = Region.model_validate(valid_region)
    assert region.bbox == [10, 20, 300, 400]
    assert region.confidence == 0.95


def test_region_bbox_negative_x():
    with pytest.raises(ValidationError):
        Region.model_validate({
            "id": "r1", "type": "text_block",
            "bbox": [-1, 20, 300, 400], "confidence": 0.5,
        })


def test_region_bbox_zero_width():
    with pytest.raises(ValidationError):
        Region.model_validate({
            "id": "r1", "type": "text_block",
            "bbox": [0, 0, 0, 400], "confidence": 0.5,
        })


def test_region_bbox_zero_height():
    with pytest.raises(ValidationError):
        Region.model_validate({
            "id": "r1", "type": "text_block",
            "bbox": [0, 0, 300, 0], "confidence": 0.5,
        })


def test_region_bbox_wrong_length():
    with pytest.raises(ValidationError):
        Region.model_validate({
            "id": "r1", "type": "text_block",
            "bbox": [0, 0, 300], "confidence": 0.5,
        })


def test_region_all_types():
    for region_type in RegionType:
        region = Region.model_validate({
            "id": "r1", "type": region_type.value,
            "bbox": [0, 0, 100, 100], "confidence": 0.8,
        })
        assert region.type == region_type


def test_region_optional_polygon():
    region = Region.model_validate({
        "id": "r1", "type": "miniature",
        "bbox": [0, 0, 200, 200], "confidence": 0.9,
        "polygon": [[0, 0], [200, 0], [200, 200], [0, 200]],
    })
    assert region.polygon is not None
    assert len(region.polygon) == 4


# ---------------------------------------------------------------------------
# Tests — PageMaster
# ---------------------------------------------------------------------------

def test_page_master_valid(minimal_page_master):
    page = PageMaster.model_validate(minimal_page_master)
    assert page.schema_version == "1.0"
    assert page.page_id == "test-corpus-0001r"
    assert page.editorial.status == EditorialStatus.MACHINE_DRAFT


def test_page_master_schema_version_default(minimal_page_master):
    page = PageMaster.model_validate(minimal_page_master)
    assert page.schema_version == "1.0"


def test_page_master_with_ocr(minimal_page_master):
    data = {**minimal_page_master, "ocr": {
        "diplomatic_text": "In nomine Domini",
        "language": "la",
        "confidence": 0.87,
    }}
    page = PageMaster.model_validate(data)
    assert page.ocr is not None
    assert page.ocr.diplomatic_text == "In nomine Domini"


def test_page_master_with_translation(minimal_page_master):
    data = {**minimal_page_master, "translation": {
        "fr": "Au nom du Seigneur",
        "en": "In the name of the Lord",
    }}
    page = PageMaster.model_validate(data)
    assert page.translation is not None
    assert page.translation.fr == "Au nom du Seigneur"


def test_page_master_with_commentary(minimal_page_master):
    data = {**minimal_page_master, "commentary": {
        "public": "Description publique.",
        "scholarly": "Analyse savante.",
        "claims": [
            {"claim": "Ce folio date du XIe siècle.", "certainty": "high"}
        ],
    }}
    page = PageMaster.model_validate(data)
    assert page.commentary is not None
    assert len(page.commentary.claims) == 1
    assert page.commentary.claims[0].certainty == "high"


def test_page_master_editorial_info_defaults(minimal_page_master):
    page = PageMaster.model_validate(minimal_page_master)
    assert page.editorial.validated is False
    assert page.editorial.version == 1
    assert page.editorial.validated_by is None


def test_commentary_claim_certainty_values():
    for certainty in ("high", "medium", "low", "speculative"):
        claim = CommentaryClaim(claim="Test.", certainty=certainty)
        assert claim.certainty == certainty


def test_commentary_claim_invalid_certainty():
    with pytest.raises(ValidationError):
        CommentaryClaim(claim="Test.", certainty="unknown")


# ---------------------------------------------------------------------------
# Tests — AnnotationLayer
# ---------------------------------------------------------------------------

def test_annotation_layer_valid():
    layer = AnnotationLayer(
        id="layer-001",
        page_id="test-corpus-0001r",
        layer_type=LayerType.OCR_DIPLOMATIC,
        created_at=datetime(2026, 3, 16, 12, 0, 0, tzinfo=timezone.utc),
    )
    assert layer.status == LayerStatus.PENDING
    assert layer.version == 1


def test_annotation_layer_all_statuses():
    for status in LayerStatus:
        layer = AnnotationLayer(
            id="layer-001",
            page_id="test-corpus-0001r",
            layer_type=LayerType.TRANSLATION_FR,
            status=status,
            created_at=datetime(2026, 3, 16, tzinfo=timezone.utc),
        )
        assert layer.status == status


def test_annotation_layer_all_layer_types():
    for layer_type in LayerType:
        layer = AnnotationLayer(
            id=f"layer-{layer_type.value}",
            page_id="test-corpus-0001r",
            layer_type=layer_type,
            created_at=datetime(2026, 3, 16, tzinfo=timezone.utc),
        )
        assert layer.layer_type == layer_type
