"""
Services AI — providers Google AI, registre de modèles, et analyse IA.
"""
from app.services.ai.analyzer import run_primary_analysis
from app.services.ai.client_factory import build_client
from app.services.ai.model_registry import build_model_config, list_all_models
from app.services.ai.prompt_loader import load_and_render_prompt
from app.services.ai.provider_google_ai import GoogleAIProvider
from app.services.ai.provider_vertex_key import VertexAPIKeyProvider
from app.services.ai.provider_vertex_sa import VertexServiceAccountProvider
from app.services.ai.response_parser import ParseError, parse_ai_response

__all__ = [
    "GoogleAIProvider",
    "VertexAPIKeyProvider",
    "VertexServiceAccountProvider",
    "list_all_models",
    "build_model_config",
    "build_client",
    "load_and_render_prompt",
    "parse_ai_response",
    "ParseError",
    "run_primary_analysis",
]
