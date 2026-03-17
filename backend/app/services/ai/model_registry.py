"""
Registre agrégé des modèles disponibles tous providers confondus.
"""
# 1. stdlib
import logging
from datetime import datetime, timezone

# 2. local
from app.schemas.model_config import ModelConfig, ModelInfo
from app.services.ai.base import AIProvider
from app.services.ai.provider_google_ai import GoogleAIProvider
from app.services.ai.provider_vertex_key import VertexAPIKeyProvider
from app.services.ai.provider_vertex_sa import VertexServiceAccountProvider

logger = logging.getLogger(__name__)


def _build_providers() -> list[AIProvider]:
    return [
        GoogleAIProvider(),
        VertexAPIKeyProvider(),
        VertexServiceAccountProvider(),
    ]


def list_all_models() -> list[ModelInfo]:
    """Interroge tous les providers configurés et retourne la liste agrégée.

    - Un provider non configuré (credentials absentes) est silencieusement ignoré.
    - Un provider défaillant (clé invalide, erreur réseau) logue un warning et est ignoré.
    """
    result: list[ModelInfo] = []

    for provider in _build_providers():
        if not provider.is_configured():
            logger.debug(
                "Provider non configuré, ignoré",
                extra={"provider": provider.provider_type},
            )
            continue

        try:
            models = provider.list_models()
            result.extend(models)
            logger.info(
                "Provider interrogé avec succès",
                extra={"provider": provider.provider_type, "count": len(models)},
            )
        except Exception as exc:
            logger.warning(
                "Provider inaccessible",
                extra={"provider": provider.provider_type, "error": str(exc)},
            )

    return result


def build_model_config(corpus_id: str, selected_model_id: str) -> ModelConfig:
    """Construit un ModelConfig à partir d'un model_id sélectionné.

    Lève ValueError si le modèle n'est pas dans la liste des disponibles.
    """
    models = list_all_models()
    model_map = {m.model_id: m for m in models}

    if selected_model_id not in model_map:
        available = sorted(model_map.keys())
        raise ValueError(
            f"Modèle '{selected_model_id}' non disponible. "
            f"Modèles disponibles : {available}"
        )

    selected = model_map[selected_model_id]
    return ModelConfig(
        corpus_id=corpus_id,
        selected_model_id=selected.model_id,
        selected_model_display_name=selected.display_name,
        provider=selected.provider,
        supports_vision=selected.supports_vision,
        last_fetched_at=datetime.now(tz=timezone.utc),
        available_models=[m.model_dump() for m in models],
    )
