"""
Services AI — providers Google AI et registre de modèles.
"""
from app.services.ai.model_registry import build_model_config, list_all_models
from app.services.ai.provider_google_ai import GoogleAIProvider
from app.services.ai.provider_vertex_key import VertexAPIKeyProvider
from app.services.ai.provider_vertex_sa import VertexServiceAccountProvider

__all__ = [
    "GoogleAIProvider",
    "VertexAPIKeyProvider",
    "VertexServiceAccountProvider",
    "list_all_models",
    "build_model_config",
]
