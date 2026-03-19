"""
Registre agrégé des modèles disponibles tous providers confondus.
"""
# 1. stdlib
import logging
from datetime import datetime, timezone

# 2. local
from app.schemas.model_config import ModelConfig, ModelInfo, ProviderType
from app.services.ai.base import AIProvider
from app.services.ai.provider_google_ai import GoogleAIProvider
from app.services.ai.provider_mistral import MistralProvider
from app.services.ai.provider_vertex_key import VertexAPIKeyProvider
from app.services.ai.provider_vertex_sa import VertexServiceAccountProvider

logger = logging.getLogger(__name__)

# Noms lisibles par provider (pour l'interface)
_PROVIDER_DISPLAY_NAMES: dict[ProviderType, str] = {
    ProviderType.GOOGLE_AI_STUDIO: "Google AI Studio",
    ProviderType.VERTEX_API_KEY: "Vertex AI (clé API)",
    ProviderType.VERTEX_SERVICE_ACCOUNT: "Vertex AI (compte de service)",
    ProviderType.MISTRAL: "Mistral AI",
}


def _build_providers() -> list[AIProvider]:
    return [
        GoogleAIProvider(),
        VertexAPIKeyProvider(),
        VertexServiceAccountProvider(),
        MistralProvider(),
    ]


def get_available_providers() -> list[dict]:
    """Retourne la liste de tous les providers avec leur état de disponibilité.

    Pour chaque provider :
    - provider_type : identifiant technique
    - display_name  : nom lisible pour l'interface
    - available     : True si les credentials sont présents en env
    - model_count   : nombre de modèles (0 si non disponible)

    Ne lève jamais d'exception ; les erreurs réseau sont loguées en warning.
    """
    result: list[dict] = []
    for provider in _build_providers():
        available = provider.is_configured()
        model_count = 0
        if available:
            try:
                models = provider.list_models()
                model_count = len(models)
            except Exception as exc:
                logger.warning(
                    "Provider %s inaccessible : %s",
                    provider.provider_type.value,
                    exc,
                )
                available = False

        result.append({
            "provider_type": provider.provider_type.value,
            "display_name": _PROVIDER_DISPLAY_NAMES.get(provider.provider_type, provider.provider_type.value),
            "available": available,
            "model_count": model_count,
        })
    return result


def list_models_for_provider(provider_type: ProviderType) -> list[ModelInfo]:
    """Retourne les modèles disponibles pour un provider donné.

    Lève ValueError si le provider_type est inconnu.
    Lève RuntimeError si le provider n'est pas configuré.
    Propage les exceptions réseau/API.
    """
    for provider in _build_providers():
        if provider.provider_type == provider_type:
            return provider.list_models()
    raise ValueError(f"Provider inconnu : {provider_type}")


def get_provider(provider_type: ProviderType) -> AIProvider:
    """Retourne l'instance du provider pour un type donné.

    Lève ValueError si le provider_type est inconnu.
    """
    for provider in _build_providers():
        if provider.provider_type == provider_type:
            return provider
    raise ValueError(f"Provider inconnu : {provider_type}")


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
                "Provider %s inaccessible : %s",
                provider.provider_type.value,
                exc,
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
