"""
Provider Vertex AI — authentification via clé API Express Vertex (VERTEX_API_KEY).

La clé Vertex Express (format AQ.Ab...) encode le projet GCP ; elle est utilisée
avec vertexai=True pour router vers aiplatform.googleapis.com (et non vers
generativelanguage.googleapis.com qui est l'endpoint Google AI Studio).

Référence SDK google-genai :
  api_key seul               → Gemini Developer API (generativelanguage)
  vertexai=True + api_key    → Vertex AI Express mode (aiplatform)
  project/location + api_key → ValueError (mutually exclusive dans le constructeur)
"""
# 1. stdlib
import logging
import os

# 2. third-party
from google import genai
from google.genai import types

# 3. local
from app.schemas.model_config import ModelInfo, ProviderType
from app.services.ai.base import AIProvider, is_vision_model

logger = logging.getLogger(__name__)

_ENV_KEY = "VERTEX_API_KEY"


class VertexAPIKeyProvider(AIProvider):
    """Provider Vertex AI via clé API Express (VERTEX_API_KEY).

    Utilise genai.Client(vertexai=True, api_key=...) pour router vers
    l'endpoint Vertex AI (aiplatform.googleapis.com). La clé Express encode
    le projet GCP ; project/location explicites sont omis car ils sont
    mutually exclusive avec api_key dans le constructeur SDK.
    """

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.VERTEX_API_KEY

    def is_configured(self) -> bool:
        return bool(os.environ.get(_ENV_KEY))

    def _build_client(self) -> genai.Client:
        """Construit un client Vertex AI en mode Express API key.

        vertexai=True route vers aiplatform.googleapis.com.
        project/location sont omis : mutually exclusive avec api_key
        dans le SDK (la clé Express encode le projet).
        """
        return genai.Client(
            vertexai=True,
            api_key=os.environ[_ENV_KEY],
        )

    def list_models(self) -> list[ModelInfo]:
        if not self.is_configured():
            raise RuntimeError(f"Variable d'environnement manquante : {_ENV_KEY}")

        client = self._build_client()
        result: list[ModelInfo] = []

        for model in client.models.list():
            methods = getattr(model, "supported_generation_methods", []) or []
            # Pour Vertex, certains modèles peuvent ne pas avoir
            # supported_generation_methods renseigné ; on les inclut
            # s'ils contiennent "gemini" dans le nom (modèles génératifs Vertex).
            name_lower = (getattr(model, "name", "") or "").lower()
            is_generative = (
                "generateContent" in methods
                or (not methods and "gemini" in name_lower)
            )
            if not is_generative:
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
            "Vertex API key (Express) models fetched",
            extra={"provider": self.provider_type.value, "count": len(result)},
        )
        return result

    def generate_content(self, image_bytes: bytes, prompt: str, model_id: str) -> str:
        if not self.is_configured():
            raise RuntimeError(f"Variable d'environnement manquante : {_ENV_KEY}")
        client = self._build_client()
        image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
        response = client.models.generate_content(
            model=model_id,
            contents=[image_part, prompt],
        )
        return response.text or ""
