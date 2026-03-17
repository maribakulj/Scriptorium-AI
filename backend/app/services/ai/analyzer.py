"""
Analyse primaire IA d'un folio : appel Google AI + écriture master.json (R02, R04, R05).

Point d'entrée : run_primary_analysis().
Chaîne : prompt_loader → client_factory → Google AI → master_writer → response_parser.
"""
# 1. stdlib
import logging
from datetime import datetime, timezone
from pathlib import Path

# 2. third-party
from google.genai import types

# 3. local
from app.schemas.corpus_profile import CorpusProfile
from app.schemas.image import ImageDerivativeInfo
from app.schemas.model_config import ModelConfig
from app.schemas.page_master import EditorialInfo, EditorialStatus, PageMaster, ProcessingInfo
from app.services.ai.client_factory import build_client
from app.services.ai.master_writer import write_gemini_raw, write_master_json
from app.services.ai.prompt_loader import load_and_render_prompt
from app.services.ai.response_parser import ParseError, parse_ai_response  # noqa: F401

logger = logging.getLogger(__name__)


def run_primary_analysis(
    derivative_image_path: Path,
    corpus_profile: CorpusProfile,
    model_config: ModelConfig,
    page_id: str,
    manuscript_id: str,
    corpus_slug: str,
    folio_label: str,
    sequence: int,
    image_info: ImageDerivativeInfo,
    base_data_dir: Path = Path("data"),
    project_root: Path = Path("."),
) -> PageMaster:
    """Analyse primaire d'un folio : charge le prompt, appelle l'IA, écrit les fichiers.

    Respecte R05 : gemini_raw.json est toujours écrit en premier, même en cas
    d'erreur de parsing. master.json n'est écrit QUE si le parsing a réussi.

    Args:
        derivative_image_path: chemin vers le JPEG dérivé (1500px max).
        corpus_profile: profil du corpus (pilote le prompt et les layers).
        model_config: configuration du modèle sélectionné (provider + model_id).
        page_id: identifiant unique de la page (ex. "beatus-lat8878-0013r").
        manuscript_id: identifiant du manuscrit.
        corpus_slug: identifiant du corpus (ex. "beatus-lat8878").
        folio_label: label du folio (ex. "0013r").
        sequence: numéro de séquence dans le manuscrit.
        image_info: métadonnées de l'image normalisée (dimensions, chemins).
        base_data_dir: racine du dossier data.
        project_root: racine du projet (pour résoudre les chemins des prompts).

    Returns:
        PageMaster validé (gemini_raw.json et master.json écrits sur disque).

    Raises:
        ParseError: si la réponse IA n'est pas un JSON valide.
        FileNotFoundError: si le template de prompt est introuvable.
        RuntimeError: si le provider n'est pas configuré (variable d'env absente).
    """
    # ── Chemins de sortie ───────────────────────────────────────────────────
    page_dir = base_data_dir / "corpora" / corpus_slug / "pages" / folio_label
    raw_path = page_dir / "gemini_raw.json"
    master_path = page_dir / "master.json"

    # ── 1. Chargement et rendu du prompt (R04) ──────────────────────────────
    prompt_rel_path: str = corpus_profile.prompt_templates["primary"]
    prompt_abs_path = project_root / prompt_rel_path

    context = {
        "profile_label": corpus_profile.label,
        "language_hints": ", ".join(corpus_profile.language_hints),
        "script_type": corpus_profile.script_type.value,
    }
    prompt_text = load_and_render_prompt(prompt_abs_path, context)
    logger.info(
        "Prompt rendu",
        extra={"template": prompt_rel_path, "corpus": corpus_slug, "folio": folio_label},
    )

    # ── 2. Chargement de l'image dérivée ────────────────────────────────────
    jpeg_bytes = derivative_image_path.read_bytes()

    # ── 3. Appel Google AI ──────────────────────────────────────────────────
    client = build_client(model_config.provider)
    image_part = types.Part.from_bytes(data=jpeg_bytes, mime_type="image/jpeg")

    logger.info(
        "Appel Google AI",
        extra={
            "model": model_config.selected_model_id,
            "corpus": corpus_slug,
            "folio": folio_label,
        },
    )
    response = client.models.generate_content(
        model=model_config.selected_model_id,
        contents=[image_part, prompt_text],
    )
    raw_text: str = response.text or ""

    # ── 4. Écriture gemini_raw.json TOUJOURS EN PREMIER (R05) ───────────────
    write_gemini_raw(raw_text, raw_path)

    # ── 5. Parsing + validation (ParseError si JSON invalide) ───────────────
    layout, ocr = parse_ai_response(raw_text)

    # ── 6. Construction du PageMaster ───────────────────────────────────────
    processed_at = datetime.now(tz=timezone.utc)
    page_master = PageMaster(
        page_id=page_id,
        corpus_profile=corpus_profile.profile_id,
        manuscript_id=manuscript_id,
        folio_label=folio_label,
        sequence=sequence,
        image={
            "original_url": image_info.original_url,
            "derivative_web": image_info.derivative_path,
            "thumbnail": image_info.thumbnail_path,
            "width": image_info.derivative_width,
            "height": image_info.derivative_height,
        },
        layout=layout,
        ocr=ocr,
        processing=ProcessingInfo(
            model_id=model_config.selected_model_id,
            model_display_name=model_config.selected_model_display_name,
            prompt_version=prompt_rel_path,
            raw_response_path=str(raw_path),
            processed_at=processed_at,
        ),
        editorial=EditorialInfo(status=EditorialStatus.MACHINE_DRAFT),
    )

    # ── 7. Écriture master.json (seulement si parsing OK) ───────────────────
    write_master_json(page_master, master_path)

    logger.info(
        "Analyse primaire terminée",
        extra={
            "page_id": page_id,
            "corpus": corpus_slug,
            "folio": folio_label,
            "regions": len(layout.get("regions", [])),
        },
    )
    return page_master
