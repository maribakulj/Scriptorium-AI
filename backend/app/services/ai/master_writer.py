"""
Écriture des fichiers gemini_raw.json et master.json (R02, R05).

Règle R05 non négociable :
  1. gemini_raw.json est TOUJOURS écrit en premier.
  2. master.json n'est écrit QUE si le parsing et la validation Pydantic ont réussi.
"""
# 1. stdlib
import json
import logging
from pathlib import Path

# 3. local
from app.schemas.page_master import PageMaster

logger = logging.getLogger(__name__)


def write_gemini_raw(raw_text: str, output_path: Path) -> None:
    """Écrit la réponse brute de l'IA dans gemini_raw.json (R05).

    Toujours appelé AVANT toute tentative de parsing.
    Le contenu est enveloppé dans un objet JSON pour garantir un fichier valide,
    même si la réponse IA n'est pas du JSON.

    Args:
        raw_text: texte brut retourné par l'API Google AI.
        output_path: chemin complet du fichier de sortie (gemini_raw.json).
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"response_text": raw_text}
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("gemini_raw.json écrit", extra={"path": str(output_path)})


def write_master_json(page_master: PageMaster, output_path: Path) -> None:
    """Écrit le PageMaster validé dans master.json (R02, R05).

    N'est appelé QUE si le parsing et la validation Pydantic ont réussi.
    Crée les dossiers parents si nécessaire.

    Args:
        page_master: instance PageMaster validée par Pydantic.
        output_path: chemin complet du fichier de sortie (master.json).
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        page_master.model_dump_json(indent=2),
        encoding="utf-8",
    )
    logger.info("master.json écrit", extra={"path": str(output_path)})
