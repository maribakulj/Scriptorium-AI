"""
Provider Google AI Studio — authentification via GOOGLE_AI_STUDIO_API_KEY.
"""
# 1. stdlib
import logging
import os

# 2. third-party
from google import genai

# 3. local
from app.schemas.model_config import ModelInfo, ProviderType
from app.services.ai.base import AIProvider, is_vision_model

logger = logging.getLogger(__name__)

_ENV_KEY = "GOOGLE_AI_STUDIO_API_KEY"


class GoogleAIProvider(AIProvider):
    """Provider Google AI Studio (clé API GOOGLE_AI_STUDIO_API_KEY)."""

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.GOOGLE_AI_STUDIO

    def is_configured(self) -> bool:
        return bool(os.environ.get(_ENV_KEY))

    def list_models(self) -> list[ModelInfo]:
        if not self.is_configured():
            raise RuntimeError(f"Variable d'environnement manquante : {_ENV_KEY}")

        client = genai.Client(api_key=os.environ[_ENV_KEY])
        result: list[ModelInfo] = []

        for model in client.models.list():
            methods = getattr(model, "supported_generation_methods", []) or []
            if "generateContent" not in methods:
                continue

            result.append(ModelInfo(
                model_id=model.name,
                display_name=getattr(model, "display_name", model.name),
                provider=self.provider_type,
                supports_vision=is_vision_model(model),
                input_token_limit=getattr(model, "input_token_limit", None),
                output_token_limit=getattr(model, "output_token_limit", None),
            ))

        logger.info(
            "Google AI Studio models fetched",
            extra={"provider": self.provider_type, "count": len(result)},
        )
        return result
