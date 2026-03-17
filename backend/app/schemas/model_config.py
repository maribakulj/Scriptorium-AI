"""
Schémas Pydantic pour la configuration et la découverte des modèles IA.
"""
# 1. stdlib
from datetime import datetime
from enum import Enum
from typing import Any

# 2. third-party
from pydantic import BaseModel, ConfigDict, Field


class ProviderType(str, Enum):
    GOOGLE_AI_STUDIO = "google_ai_studio"
    VERTEX_API_KEY = "vertex_api_key"
    VERTEX_SERVICE_ACCOUNT = "vertex_service_account"


class ModelInfo(BaseModel):
    """Décrit un modèle IA disponible chez un provider."""

    model_config = ConfigDict(frozen=True)

    model_id: str
    display_name: str
    provider: ProviderType
    supports_vision: bool
    input_token_limit: int | None = None
    output_token_limit: int | None = None


class ModelConfig(BaseModel):
    """Configuration du modèle sélectionné pour un corpus (CLAUDE.md §9)."""

    corpus_id: str
    selected_model_id: str
    selected_model_display_name: str
    provider: ProviderType
    supports_vision: bool
    last_fetched_at: datetime
    available_models: list[dict[str, Any]]  # cache sérialisé des ModelInfo
