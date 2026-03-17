"""
Tests du pipeline d'analyse IA :
  - prompt_loader  : chargement + rendu des templates
  - client_factory : construction du genai.Client selon le provider
  - response_parser: parsing JSON brut → layout + OCRResult
  - master_writer  : écriture gemini_raw.json et master.json
  - analyzer       : run_primary_analysis (end-to-end mocké)
"""
# 1. stdlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, call, patch

# 2. third-party
import pytest
from PIL import Image
from pydantic import ValidationError

# 3. local
from app.schemas.corpus_profile import (
    CorpusProfile,
    ExportConfig,
    LayerType,
    ScriptType,
    UncertaintyConfig,
)
from app.schemas.image import ImageDerivativeInfo
from app.schemas.model_config import ModelConfig, ProviderType
from app.schemas.page_master import OCRResult, PageMaster
from app.services.ai.analyzer import run_primary_analysis
from app.services.ai.client_factory import build_client
from app.services.ai.master_writer import write_gemini_raw, write_master_json
from app.services.ai.prompt_loader import load_and_render_prompt
from app.services.ai.response_parser import ParseError, parse_ai_response


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_jpeg_bytes(width: int = 100, height: int = 100) -> bytes:
    img = Image.new("RGB", (width, height), color=(128, 64, 32))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def _make_corpus_profile(
    profile_id: str = "medieval-illuminated",
    prompt_rel_path: str = "prompts/medieval-illuminated/primary_v1.txt",
) -> CorpusProfile:
    return CorpusProfile(
        profile_id=profile_id,
        label="Manuscrit médiéval enluminé",
        language_hints=["la"],
        script_type=ScriptType.CAROLINE,
        active_layers=[LayerType.IMAGE, LayerType.OCR_DIPLOMATIC],
        prompt_templates={"primary": prompt_rel_path},
        uncertainty_config=UncertaintyConfig(),
        export_config=ExportConfig(),
    )


def _make_model_config(provider: ProviderType = ProviderType.GOOGLE_AI_STUDIO) -> ModelConfig:
    return ModelConfig(
        corpus_id="test-corpus",
        selected_model_id="gemini-2.0-flash",
        selected_model_display_name="Gemini 2.0 Flash",
        provider=provider,
        supports_vision=True,
        last_fetched_at=datetime.now(tz=timezone.utc),
        available_models=[],
    )


def _make_image_info() -> ImageDerivativeInfo:
    return ImageDerivativeInfo(
        original_url="https://example.com/iiif/f001.jpg",
        original_width=3000,
        original_height=4000,
        derivative_path="/data/corpora/test-corpus/derivatives/0001r.jpg",
        derivative_width=1125,
        derivative_height=1500,
        thumbnail_path="/data/corpora/test-corpus/derivatives/0001r_thumb.jpg",
        thumbnail_width=192,
        thumbnail_height=256,
    )


def _valid_ai_json(regions: list | None = None) -> str:
    if regions is None:
        regions = [
            {"id": "r1", "type": "text_block", "bbox": [10, 20, 300, 400], "confidence": 0.95},
            {"id": "r2", "type": "miniature", "bbox": [0, 0, 500, 600], "confidence": 0.88},
        ]
    return json.dumps({
        "layout": {"regions": regions},
        "ocr": {
            "diplomatic_text": "Incipit liber beati Ieronimi",
            "blocks": [],
            "lines": [],
            "language": "la",
            "confidence": 0.87,
            "uncertain_segments": [],
        },
    })


# ---------------------------------------------------------------------------
# Tests — load_and_render_prompt
# ---------------------------------------------------------------------------

def test_prompt_loader_renders_variables(tmp_path):
    tpl = tmp_path / "prompt.txt"
    tpl.write_text("Corpus : {{profile_label}}\nLangue : {{language_hints}}")

    result = load_and_render_prompt(tpl, {
        "profile_label": "Manuscrit test",
        "language_hints": "la, fr",
    })

    assert "Manuscrit test" in result
    assert "la, fr" in result
    assert "{{profile_label}}" not in result
    assert "{{language_hints}}" not in result


def test_prompt_loader_unknown_variable_kept(tmp_path):
    """Une variable absente du contexte reste telle quelle dans le texte."""
    tpl = tmp_path / "prompt.txt"
    tpl.write_text("Hello {{name}} — {{unknown}}")

    result = load_and_render_prompt(tpl, {"name": "World"})

    assert "World" in result
    assert "{{unknown}}" in result


def test_prompt_loader_empty_context(tmp_path):
    tpl = tmp_path / "prompt.txt"
    tpl.write_text("Texte sans variables.")

    result = load_and_render_prompt(tpl, {})
    assert result == "Texte sans variables."


def test_prompt_loader_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_and_render_prompt("/nonexistent/path/prompt.txt", {})


def test_prompt_loader_accepts_path_object(tmp_path):
    tpl = tmp_path / "sub" / "tpl.txt"
    tpl.parent.mkdir()
    tpl.write_text("OK {{var}}")

    result = load_and_render_prompt(tpl, {"var": "value"})
    assert result == "OK value"


def test_prompt_loader_multiple_occurrences(tmp_path):
    """Une même variable peut apparaître plusieurs fois."""
    tpl = tmp_path / "prompt.txt"
    tpl.write_text("{{x}} et {{x}} encore")

    result = load_and_render_prompt(tpl, {"x": "Z"})
    assert result == "Z et Z encore"


# ---------------------------------------------------------------------------
# Tests — build_client
# ---------------------------------------------------------------------------

def test_build_client_google_ai_studio(monkeypatch):
    monkeypatch.setenv("GOOGLE_AI_STUDIO_API_KEY", "fake-key-studio")

    with patch("app.services.ai.client_factory.genai.Client") as mock_cls:
        mock_cls.return_value = MagicMock()
        client = build_client(ProviderType.GOOGLE_AI_STUDIO)

    mock_cls.assert_called_once_with(api_key="fake-key-studio")
    assert client is mock_cls.return_value


def test_build_client_google_ai_studio_missing_env(monkeypatch):
    monkeypatch.delenv("GOOGLE_AI_STUDIO_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="GOOGLE_AI_STUDIO_API_KEY"):
        build_client(ProviderType.GOOGLE_AI_STUDIO)


def test_build_client_vertex_api_key(monkeypatch):
    monkeypatch.setenv("VERTEX_API_KEY", "fake-vertex-key")

    with patch("app.services.ai.client_factory.genai.Client") as mock_cls:
        mock_cls.return_value = MagicMock()
        client = build_client(ProviderType.VERTEX_API_KEY)

    mock_cls.assert_called_once_with(api_key="fake-vertex-key")
    assert client is mock_cls.return_value


def test_build_client_vertex_api_key_missing_env(monkeypatch):
    monkeypatch.delenv("VERTEX_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="VERTEX_API_KEY"):
        build_client(ProviderType.VERTEX_API_KEY)


def test_build_client_vertex_service_account(monkeypatch):
    sa_json = json.dumps({
        "type": "service_account",
        "project_id": "my-project",
        "private_key_id": "key-id",
        "private_key": "-----BEGIN RSA PRIVATE KEY-----\nfake\n-----END RSA PRIVATE KEY-----\n",
        "client_email": "sa@my-project.iam.gserviceaccount.com",
        "client_id": "123",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    })
    monkeypatch.setenv("VERTEX_SERVICE_ACCOUNT_JSON", sa_json)

    mock_creds = MagicMock()
    with (
        patch("app.services.ai.client_factory.service_account.Credentials.from_service_account_info",
              return_value=mock_creds) as mock_sa,
        patch("app.services.ai.client_factory.genai.Client") as mock_cls,
    ):
        mock_cls.return_value = MagicMock()
        client = build_client(ProviderType.VERTEX_SERVICE_ACCOUNT)

    mock_sa.assert_called_once()
    mock_cls.assert_called_once_with(
        vertexai=True,
        project="my-project",
        location="us-central1",
        credentials=mock_creds,
    )
    assert client is mock_cls.return_value


def test_build_client_vertex_sa_missing_env(monkeypatch):
    monkeypatch.delenv("VERTEX_SERVICE_ACCOUNT_JSON", raising=False)

    with pytest.raises(RuntimeError, match="VERTEX_SERVICE_ACCOUNT_JSON"):
        build_client(ProviderType.VERTEX_SERVICE_ACCOUNT)


def test_build_client_vertex_sa_invalid_json(monkeypatch):
    monkeypatch.setenv("VERTEX_SERVICE_ACCOUNT_JSON", "not-valid-json{{{")

    with pytest.raises(ValueError, match="JSON invalide"):
        build_client(ProviderType.VERTEX_SERVICE_ACCOUNT)


def test_build_client_vertex_sa_missing_project_id(monkeypatch):
    sa_json = json.dumps({"type": "service_account"})  # no project_id
    monkeypatch.setenv("VERTEX_SERVICE_ACCOUNT_JSON", sa_json)

    with pytest.raises(ValueError, match="project_id"):
        build_client(ProviderType.VERTEX_SERVICE_ACCOUNT)


# ---------------------------------------------------------------------------
# Tests — parse_ai_response
# ---------------------------------------------------------------------------

def test_parse_valid_response():
    layout, ocr = parse_ai_response(_valid_ai_json())

    assert len(layout["regions"]) == 2
    assert layout["regions"][0]["id"] == "r1"
    assert layout["regions"][0]["type"] == "text_block"
    assert layout["regions"][0]["bbox"] == [10, 20, 300, 400]
    assert isinstance(ocr, OCRResult)
    assert ocr.diplomatic_text == "Incipit liber beati Ieronimi"
    assert ocr.confidence == pytest.approx(0.87)


def test_parse_invalid_json_raises_parse_error():
    with pytest.raises(ParseError, match="non parseable"):
        parse_ai_response("this is not json at all {{}")


def test_parse_non_object_raises_parse_error():
    with pytest.raises(ParseError, match="objet JSON attendu"):
        parse_ai_response("[1, 2, 3]")


def test_parse_invalid_bbox_region_is_skipped():
    """Une région avec bbox invalide est ignorée ; les autres sont conservées."""
    raw = json.dumps({
        "layout": {
            "regions": [
                {"id": "r1", "type": "text_block", "bbox": [0, 0, 100, 100], "confidence": 0.9},
                {"id": "r_bad", "type": "text_block", "bbox": [0, 0, -10, 50], "confidence": 0.7},
                {"id": "r3", "type": "miniature", "bbox": [5, 5, 200, 300], "confidence": 0.8},
            ]
        },
        "ocr": {},
    })

    layout, ocr = parse_ai_response(raw)

    assert len(layout["regions"]) == 2
    ids = [r["id"] for r in layout["regions"]]
    assert "r1" in ids
    assert "r3" in ids
    assert "r_bad" not in ids


def test_parse_zero_width_bbox_is_skipped():
    """Une bbox avec width=0 est rejetée par le validator Pydantic."""
    raw = json.dumps({
        "layout": {
            "regions": [
                {"id": "r1", "type": "text_block", "bbox": [0, 0, 0, 100], "confidence": 0.9},
            ]
        },
        "ocr": {},
    })

    layout, _ = parse_ai_response(raw)
    assert len(layout["regions"]) == 0


def test_parse_all_bad_regions_returns_empty_layout():
    raw = json.dumps({
        "layout": {"regions": [
            {"id": "r1", "type": "text_block", "bbox": [-5, 0, 100, 100], "confidence": 0.9},
        ]},
        "ocr": {},
    })

    layout, _ = parse_ai_response(raw)
    assert layout == {"regions": []}


def test_parse_missing_layout_returns_empty():
    raw = json.dumps({"ocr": {"diplomatic_text": "hello", "confidence": 0.5}})

    layout, ocr = parse_ai_response(raw)
    assert layout == {"regions": []}
    assert ocr.diplomatic_text == "hello"


def test_parse_missing_ocr_returns_default():
    raw = json.dumps({"layout": {"regions": []}})

    layout, ocr = parse_ai_response(raw)
    assert isinstance(ocr, OCRResult)
    assert ocr.diplomatic_text == ""
    assert ocr.confidence == 0.0


def test_parse_markdown_code_fence_stripped():
    """Les balises ```json ... ``` sont supprimées avant parsing."""
    inner = json.dumps({"layout": {"regions": []}, "ocr": {}})
    fenced = f"```json\n{inner}\n```"

    layout, ocr = parse_ai_response(fenced)
    assert layout == {"regions": []}


def test_parse_markdown_code_fence_no_lang_stripped():
    inner = json.dumps({"layout": {"regions": []}, "ocr": {}})
    fenced = f"```\n{inner}\n```"

    layout, ocr = parse_ai_response(fenced)
    assert layout == {"regions": []}


def test_parse_invalid_ocr_uses_defaults():
    """Un champ OCR hors bornes (confidence > 1) → valeurs par défaut."""
    raw = json.dumps({
        "layout": {"regions": []},
        "ocr": {"confidence": 9.9},  # confidence > 1.0 : Pydantic rejette
    })

    layout, ocr = parse_ai_response(raw)
    assert ocr.confidence == 0.0  # valeur par défaut


def test_parse_empty_regions_list():
    raw = json.dumps({"layout": {"regions": []}, "ocr": {}})
    layout, _ = parse_ai_response(raw)
    assert layout == {"regions": []}


# ---------------------------------------------------------------------------
# Tests — write_gemini_raw / write_master_json
# ---------------------------------------------------------------------------

def test_write_gemini_raw_creates_file(tmp_path):
    out = tmp_path / "page" / "gemini_raw.json"
    write_gemini_raw("raw AI text here", out)

    assert out.exists()


def test_write_gemini_raw_valid_json(tmp_path):
    out = tmp_path / "gemini_raw.json"
    write_gemini_raw('{"not": "valid json from AI"}', out)

    content = json.loads(out.read_text(encoding="utf-8"))
    assert "response_text" in content
    assert content["response_text"] == '{"not": "valid json from AI"}'


def test_write_gemini_raw_creates_parent_dirs(tmp_path):
    out = tmp_path / "deep" / "nested" / "dir" / "gemini_raw.json"
    write_gemini_raw("text", out)
    assert out.exists()


def test_write_gemini_raw_with_non_json_text(tmp_path):
    """Même si le texte brut est invalide, gemini_raw.json est créé."""
    out = tmp_path / "gemini_raw.json"
    write_gemini_raw("this is not json at all", out)

    content = json.loads(out.read_text(encoding="utf-8"))
    assert content["response_text"] == "this is not json at all"


def _make_page_master() -> PageMaster:
    return PageMaster(
        page_id="test-ms-0001r",
        corpus_profile="medieval-illuminated",
        manuscript_id="ms-test",
        folio_label="0001r",
        sequence=1,
        image={
            "original_url": "https://example.com/img.jpg",
            "derivative_web": "/data/deriv.jpg",
            "thumbnail": "/data/thumb.jpg",
            "width": 1500,
            "height": 2000,
        },
        layout={"regions": []},
        processing={
            "model_id": "gemini-2.0-flash",
            "model_display_name": "Gemini 2.0 Flash",
            "prompt_version": "prompts/medieval-illuminated/primary_v1.txt",
            "raw_response_path": "/data/gemini_raw.json",
            "processed_at": datetime.now(tz=timezone.utc),
        },
    )


def test_write_master_json_creates_file(tmp_path):
    out = tmp_path / "master.json"
    pm = _make_page_master()
    write_master_json(pm, out)
    assert out.exists()


def test_write_master_json_valid_json(tmp_path):
    out = tmp_path / "master.json"
    pm = _make_page_master()
    write_master_json(pm, out)

    content = json.loads(out.read_text(encoding="utf-8"))
    assert content["page_id"] == "test-ms-0001r"
    assert content["schema_version"] == "1.0"


def test_write_master_json_creates_parent_dirs(tmp_path):
    out = tmp_path / "a" / "b" / "c" / "master.json"
    write_master_json(_make_page_master(), out)
    assert out.exists()


def test_write_master_json_contains_processing_info(tmp_path):
    out = tmp_path / "master.json"
    write_master_json(_make_page_master(), out)

    content = json.loads(out.read_text(encoding="utf-8"))
    assert content["processing"]["model_id"] == "gemini-2.0-flash"
    assert content["processing"]["prompt_version"] == "prompts/medieval-illuminated/primary_v1.txt"


# ---------------------------------------------------------------------------
# Tests — run_primary_analysis (end-to-end mocké)
# ---------------------------------------------------------------------------

def _setup_prompt_file(tmp_path: Path, rel_path: str) -> Path:
    """Crée le fichier template dans tmp_path/rel_path."""
    full = tmp_path / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(
        "Analyse {{profile_label}} en {{language_hints}} ({{script_type}}).",
        encoding="utf-8",
    )
    return full


def _setup_derivative(tmp_path: Path) -> Path:
    """Crée un JPEG dérivé factice dans tmp_path."""
    deriv = tmp_path / "derivative.jpg"
    deriv.write_bytes(_make_jpeg_bytes(200, 300))
    return deriv


def _make_mock_client(ai_response_text: str) -> MagicMock:
    mock_response = MagicMock()
    mock_response.text = ai_response_text
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    return mock_client


def test_run_primary_analysis_success(tmp_path):
    """Cas nominal : retourne un PageMaster, crée les deux fichiers."""
    prompt_rel = "prompts/medieval-illuminated/primary_v1.txt"
    _setup_prompt_file(tmp_path, prompt_rel)
    deriv_path = _setup_derivative(tmp_path)

    profile = _make_corpus_profile(prompt_rel_path=prompt_rel)
    model_cfg = _make_model_config()
    image_info = _make_image_info()

    mock_client = _make_mock_client(_valid_ai_json())

    with patch("app.services.ai.analyzer.build_client", return_value=mock_client):
        result = run_primary_analysis(
            derivative_image_path=deriv_path,
            corpus_profile=profile,
            model_config=model_cfg,
            page_id="test-corpus-0001r",
            manuscript_id="ms-test",
            corpus_slug="test-corpus",
            folio_label="0001r",
            sequence=1,
            image_info=image_info,
            base_data_dir=tmp_path / "data",
            project_root=tmp_path,
        )

    assert isinstance(result, PageMaster)
    assert result.page_id == "test-corpus-0001r"
    assert result.corpus_profile == "medieval-illuminated"
    assert result.folio_label == "0001r"
    assert result.sequence == 1


def test_run_primary_analysis_files_created(tmp_path):
    """Les deux fichiers obligatoires (R05) sont créés sur disque."""
    prompt_rel = "prompts/medieval-illuminated/primary_v1.txt"
    _setup_prompt_file(tmp_path, prompt_rel)
    deriv_path = _setup_derivative(tmp_path)

    mock_client = _make_mock_client(_valid_ai_json())

    with patch("app.services.ai.analyzer.build_client", return_value=mock_client):
        run_primary_analysis(
            derivative_image_path=deriv_path,
            corpus_profile=_make_corpus_profile(prompt_rel_path=prompt_rel),
            model_config=_make_model_config(),
            page_id="test-corpus-0001r",
            manuscript_id="ms-test",
            corpus_slug="test-corpus",
            folio_label="0001r",
            sequence=1,
            image_info=_make_image_info(),
            base_data_dir=tmp_path / "data",
            project_root=tmp_path,
        )

    page_dir = tmp_path / "data" / "corpora" / "test-corpus" / "pages" / "0001r"
    assert (page_dir / "gemini_raw.json").exists()
    assert (page_dir / "master.json").exists()


def test_run_primary_analysis_raw_written_before_parse(tmp_path):
    """gemini_raw.json est écrit AVANT que le parsing échoue (R05)."""
    prompt_rel = "prompts/medieval-illuminated/primary_v1.txt"
    _setup_prompt_file(tmp_path, prompt_rel)
    deriv_path = _setup_derivative(tmp_path)

    mock_client = _make_mock_client("this is definitely not json {{{{")

    with patch("app.services.ai.analyzer.build_client", return_value=mock_client):
        with pytest.raises(ParseError):
            run_primary_analysis(
                derivative_image_path=deriv_path,
                corpus_profile=_make_corpus_profile(prompt_rel_path=prompt_rel),
                model_config=_make_model_config(),
                page_id="test-corpus-0001r",
                manuscript_id="ms-test",
                corpus_slug="test-corpus",
                folio_label="0001r",
                sequence=1,
                image_info=_make_image_info(),
                base_data_dir=tmp_path / "data",
                project_root=tmp_path,
            )

    # gemini_raw.json existe malgré l'échec de parsing
    raw_path = tmp_path / "data" / "corpora" / "test-corpus" / "pages" / "0001r" / "gemini_raw.json"
    assert raw_path.exists()

    # master.json N'existe PAS (parsing a échoué)
    master_path = tmp_path / "data" / "corpora" / "test-corpus" / "pages" / "0001r" / "master.json"
    assert not master_path.exists()


def test_run_primary_analysis_processing_info(tmp_path):
    """ProcessingInfo contient le bon model_id et prompt_version."""
    prompt_rel = "prompts/test-profile/primary_v1.txt"
    _setup_prompt_file(tmp_path, prompt_rel)
    deriv_path = _setup_derivative(tmp_path)

    profile = _make_corpus_profile(
        profile_id="test-profile",
        prompt_rel_path=prompt_rel,
    )
    model_cfg = _make_model_config()
    mock_client = _make_mock_client(_valid_ai_json())

    with patch("app.services.ai.analyzer.build_client", return_value=mock_client):
        result = run_primary_analysis(
            derivative_image_path=deriv_path,
            corpus_profile=profile,
            model_config=model_cfg,
            page_id="test-corpus-0001r",
            manuscript_id="ms-test",
            corpus_slug="test-corpus",
            folio_label="0001r",
            sequence=1,
            image_info=_make_image_info(),
            base_data_dir=tmp_path / "data",
            project_root=tmp_path,
        )

    assert result.processing is not None
    assert result.processing.model_id == "gemini-2.0-flash"
    assert result.processing.model_display_name == "Gemini 2.0 Flash"
    assert result.processing.prompt_version == prompt_rel


def test_run_primary_analysis_image_dict(tmp_path):
    """Le dict image du PageMaster reprend les données de ImageDerivativeInfo."""
    prompt_rel = "prompts/medieval-illuminated/primary_v1.txt"
    _setup_prompt_file(tmp_path, prompt_rel)
    deriv_path = _setup_derivative(tmp_path)

    image_info = _make_image_info()
    mock_client = _make_mock_client(_valid_ai_json())

    with patch("app.services.ai.analyzer.build_client", return_value=mock_client):
        result = run_primary_analysis(
            derivative_image_path=deriv_path,
            corpus_profile=_make_corpus_profile(prompt_rel_path=prompt_rel),
            model_config=_make_model_config(),
            page_id="test-corpus-0001r",
            manuscript_id="ms-test",
            corpus_slug="test-corpus",
            folio_label="0001r",
            sequence=1,
            image_info=image_info,
            base_data_dir=tmp_path / "data",
            project_root=tmp_path,
        )

    assert result.image["original_url"] == image_info.original_url
    assert result.image["width"] == image_info.derivative_width
    assert result.image["height"] == image_info.derivative_height


def test_run_primary_analysis_regions_in_layout(tmp_path):
    """Les régions valides de la réponse IA sont dans layout du PageMaster."""
    prompt_rel = "prompts/medieval-illuminated/primary_v1.txt"
    _setup_prompt_file(tmp_path, prompt_rel)
    deriv_path = _setup_derivative(tmp_path)

    mock_client = _make_mock_client(_valid_ai_json())

    with patch("app.services.ai.analyzer.build_client", return_value=mock_client):
        result = run_primary_analysis(
            derivative_image_path=deriv_path,
            corpus_profile=_make_corpus_profile(prompt_rel_path=prompt_rel),
            model_config=_make_model_config(),
            page_id="test-corpus-0001r",
            manuscript_id="ms-test",
            corpus_slug="test-corpus",
            folio_label="0001r",
            sequence=1,
            image_info=_make_image_info(),
            base_data_dir=tmp_path / "data",
            project_root=tmp_path,
        )

    assert len(result.layout["regions"]) == 2


def test_run_primary_analysis_prompt_rendered_with_profile(tmp_path):
    """Le prompt envoyé à l'IA contient les valeurs du profil substituées."""
    prompt_rel = "prompts/medieval-illuminated/primary_v1.txt"
    tpl = tmp_path / prompt_rel
    tpl.parent.mkdir(parents=True, exist_ok=True)
    tpl.write_text("Profil: {{profile_label}} | Script: {{script_type}}")
    deriv_path = _setup_derivative(tmp_path)

    mock_client = _make_mock_client(_valid_ai_json())
    profile = _make_corpus_profile(prompt_rel_path=prompt_rel)

    with patch("app.services.ai.analyzer.build_client", return_value=mock_client):
        run_primary_analysis(
            derivative_image_path=deriv_path,
            corpus_profile=profile,
            model_config=_make_model_config(),
            page_id="test-corpus-0001r",
            manuscript_id="ms-test",
            corpus_slug="test-corpus",
            folio_label="0001r",
            sequence=1,
            image_info=_make_image_info(),
            base_data_dir=tmp_path / "data",
            project_root=tmp_path,
        )

    # Vérifier que generate_content a été appelé avec le prompt rendu
    call_args = mock_client.models.generate_content.call_args
    contents = call_args.kwargs.get("contents") or call_args.args[0] if call_args.args else call_args.kwargs["contents"]
    prompt_sent = contents[-1]  # le prompt est le dernier élément
    assert "Manuscrit médiéval enluminé" in prompt_sent
    assert "caroline" in prompt_sent
    assert "{{profile_label}}" not in prompt_sent


def test_run_primary_analysis_prompt_not_found_raises(tmp_path):
    """FileNotFoundError si le template de prompt n'existe pas."""
    deriv_path = _setup_derivative(tmp_path)
    profile = _make_corpus_profile(prompt_rel_path="prompts/nonexistent/prompt.txt")

    mock_client = _make_mock_client(_valid_ai_json())

    with patch("app.services.ai.analyzer.build_client", return_value=mock_client):
        with pytest.raises(FileNotFoundError):
            run_primary_analysis(
                derivative_image_path=deriv_path,
                corpus_profile=profile,
                model_config=_make_model_config(),
                page_id="test-corpus-0001r",
                manuscript_id="ms-test",
                corpus_slug="test-corpus",
                folio_label="0001r",
                sequence=1,
                image_info=_make_image_info(),
                base_data_dir=tmp_path / "data",
                project_root=tmp_path,
            )


def test_run_primary_analysis_ocr_in_result(tmp_path):
    """Le résultat OCR est bien présent dans le PageMaster."""
    prompt_rel = "prompts/medieval-illuminated/primary_v1.txt"
    _setup_prompt_file(tmp_path, prompt_rel)
    deriv_path = _setup_derivative(tmp_path)

    mock_client = _make_mock_client(_valid_ai_json())

    with patch("app.services.ai.analyzer.build_client", return_value=mock_client):
        result = run_primary_analysis(
            derivative_image_path=deriv_path,
            corpus_profile=_make_corpus_profile(prompt_rel_path=prompt_rel),
            model_config=_make_model_config(),
            page_id="test-corpus-0001r",
            manuscript_id="ms-test",
            corpus_slug="test-corpus",
            folio_label="0001r",
            sequence=1,
            image_info=_make_image_info(),
            base_data_dir=tmp_path / "data",
            project_root=tmp_path,
        )

    assert result.ocr is not None
    assert result.ocr.diplomatic_text == "Incipit liber beati Ieronimi"
    assert result.ocr.language == "la"


def test_run_primary_analysis_editorial_status_machine_draft(tmp_path):
    """Le statut éditorial initial est machine_draft."""
    prompt_rel = "prompts/medieval-illuminated/primary_v1.txt"
    _setup_prompt_file(tmp_path, prompt_rel)
    deriv_path = _setup_derivative(tmp_path)

    mock_client = _make_mock_client(_valid_ai_json())

    with patch("app.services.ai.analyzer.build_client", return_value=mock_client):
        result = run_primary_analysis(
            derivative_image_path=deriv_path,
            corpus_profile=_make_corpus_profile(prompt_rel_path=prompt_rel),
            model_config=_make_model_config(),
            page_id="test-corpus-0001r",
            manuscript_id="ms-test",
            corpus_slug="test-corpus",
            folio_label="0001r",
            sequence=1,
            image_info=_make_image_info(),
            base_data_dir=tmp_path / "data",
            project_root=tmp_path,
        )

    assert result.editorial.status.value == "machine_draft"


def test_run_primary_analysis_master_json_content(tmp_path):
    """Le master.json écrit sur disque est un JSON valide avec schema_version."""
    prompt_rel = "prompts/medieval-illuminated/primary_v1.txt"
    _setup_prompt_file(tmp_path, prompt_rel)
    deriv_path = _setup_derivative(tmp_path)

    mock_client = _make_mock_client(_valid_ai_json())

    with patch("app.services.ai.analyzer.build_client", return_value=mock_client):
        run_primary_analysis(
            derivative_image_path=deriv_path,
            corpus_profile=_make_corpus_profile(prompt_rel_path=prompt_rel),
            model_config=_make_model_config(),
            page_id="test-corpus-0001r",
            manuscript_id="ms-test",
            corpus_slug="test-corpus",
            folio_label="0001r",
            sequence=1,
            image_info=_make_image_info(),
            base_data_dir=tmp_path / "data",
            project_root=tmp_path,
        )

    master_path = tmp_path / "data" / "corpora" / "test-corpus" / "pages" / "0001r" / "master.json"
    content = json.loads(master_path.read_text(encoding="utf-8"))
    assert content["schema_version"] == "1.0"
    assert content["page_id"] == "test-corpus-0001r"


def test_run_primary_analysis_invalid_region_skipped(tmp_path):
    """Une région invalide dans la réponse IA est ignorée sans lever d'exception."""
    prompt_rel = "prompts/medieval-illuminated/primary_v1.txt"
    _setup_prompt_file(tmp_path, prompt_rel)
    deriv_path = _setup_derivative(tmp_path)

    response_with_bad_region = json.dumps({
        "layout": {"regions": [
            {"id": "r_good", "type": "text_block", "bbox": [0, 0, 100, 100], "confidence": 0.9},
            {"id": "r_bad", "type": "text_block", "bbox": [-1, 0, 100, 100], "confidence": 0.9},
        ]},
        "ocr": {},
    })
    mock_client = _make_mock_client(response_with_bad_region)

    with patch("app.services.ai.analyzer.build_client", return_value=mock_client):
        result = run_primary_analysis(
            derivative_image_path=deriv_path,
            corpus_profile=_make_corpus_profile(prompt_rel_path=prompt_rel),
            model_config=_make_model_config(),
            page_id="test-corpus-0001r",
            manuscript_id="ms-test",
            corpus_slug="test-corpus",
            folio_label="0001r",
            sequence=1,
            image_info=_make_image_info(),
            base_data_dir=tmp_path / "data",
            project_root=tmp_path,
        )

    assert len(result.layout["regions"]) == 1
    assert result.layout["regions"][0]["id"] == "r_good"
