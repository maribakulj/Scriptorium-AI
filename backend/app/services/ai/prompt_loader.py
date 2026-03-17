"""
Chargement et rendu des templates de prompts depuis le système de fichiers (R04).

Les prompts vivent dans prompts/{profile_id}/{famille}_v{n}.txt.
Le code charge le fichier, substitue les variables {{nom}}, envoie à l'API.
"""
# 1. stdlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def load_and_render_prompt(template_path: str | Path, context: dict[str, str]) -> str:
    """Charge un template de prompt depuis un fichier et substitue les variables.

    Les variables du template ont la forme {{nom_variable}}.
    Toutes les clés de `context` sont substituées ; les clés absentes du template
    sont ignorées silencieusement.

    Args:
        template_path: chemin vers le fichier template (.txt), absolu ou relatif au CWD.
        context: dictionnaire {nom_variable: valeur} pour la substitution.

    Returns:
        Texte du prompt avec toutes les variables substituées.

    Raises:
        FileNotFoundError: si le fichier template n'existe pas.
    """
    path = Path(template_path)
    if not path.exists():
        raise FileNotFoundError(f"Template de prompt introuvable : {path}")

    template = path.read_text(encoding="utf-8")

    rendered = template
    for key, value in context.items():
        rendered = rendered.replace("{{" + key + "}}", value)

    logger.debug(
        "Prompt chargé et rendu",
        extra={"template": str(path), "variables": list(context.keys())},
    )
    return rendered
