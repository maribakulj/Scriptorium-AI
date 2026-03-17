"""
Parsing et validation de la réponse brute de l'IA → layout dict + OCRResult.

Comportement :
- JSON non parseable       → ParseError (toute la page échoue)
- Région avec bbox invalide → région ignorée + log (la page continue)
- OCR invalide             → OCRResult() par défaut + log (la page continue)
"""
# 1. stdlib
import json
import logging

# 2. third-party
from pydantic import ValidationError

# 3. local
from app.schemas.page_master import OCRResult, Region

logger = logging.getLogger(__name__)


class ParseError(Exception):
    """Levée si la réponse de l'IA est un JSON invalide ou structurellement incorrecte."""


def parse_ai_response(raw_text: str) -> tuple[dict, OCRResult]:
    """Parse la réponse textuelle de l'IA en layout dict + OCRResult validés.

    Les régions avec bbox invalide sont ignorées individuellement (loguées) sans
    faire échouer toute la page. Un JSON non parseable lève ParseError.

    Gère les balises Markdown (```json ... ```) que certains modèles ajoutent
    malgré les instructions.

    Args:
        raw_text: texte brut retourné par l'IA (censé être du JSON strict).

    Returns:
        Tuple (layout_dict, ocr_result) où layout_dict = {"regions": [...]}.

    Raises:
        ParseError: si le texte n'est pas du JSON valide ou pas un objet JSON.
    """
    # Suppression des balises Markdown éventuelles
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[1:end])

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ParseError(
            f"Réponse IA non parseable en JSON : {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise ParseError(
            f"Réponse IA invalide — objet JSON attendu, reçu : {type(data).__name__}"
        )

    # ── Layout / régions ────────────────────────────────────────────────────
    raw_layout = data.get("layout")
    raw_regions: list = []
    if isinstance(raw_layout, dict):
        raw_regions = raw_layout.get("regions") or []

    valid_regions: list[dict] = []
    for i, raw_region in enumerate(raw_regions):
        try:
            region = Region.model_validate(raw_region)
            valid_regions.append(region.model_dump())
        except (ValidationError, Exception) as exc:
            logger.warning(
                "Région ignorée — bbox ou champ invalide",
                extra={"index": i, "region": raw_region, "error": str(exc)},
            )

    layout: dict = {"regions": valid_regions}

    # ── OCR ─────────────────────────────────────────────────────────────────
    raw_ocr = data.get("ocr")
    ocr: OCRResult
    if raw_ocr and isinstance(raw_ocr, dict):
        try:
            ocr = OCRResult.model_validate(raw_ocr)
        except ValidationError as exc:
            logger.warning(
                "OCR invalide — utilisation des valeurs par défaut",
                extra={"error": str(exc)},
            )
            ocr = OCRResult()
    else:
        ocr = OCRResult()

    logger.info(
        "Réponse IA parsée",
        extra={
            "regions_total": len(raw_regions),
            "regions_valides": len(valid_regions),
            "regions_ignorees": len(raw_regions) - len(valid_regions),
            "ocr_confidence": ocr.confidence,
        },
    )
    return layout, ocr
