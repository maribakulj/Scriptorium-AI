"""
Provider Vertex AI — authentification via compte de service JSON (VERTEX_SERVICE_ACCOUNT_JSON).
"""
# 1. stdlib
import json
import logging
import os

# 2. third-party
from google import genai
from google.oauth2 import service_account

# 3. local
from app.schemas.model_config import ModelInfo, ProviderType
from app.services.ai.base import AIProvider, is_vision_model

logger = logging.getLogger(__name__)

_ENV_KEY = "VERTEX_SERVICE_ACCOUNT_JSON"
_VERTEX_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
_DEFAULT_LOCATION = "us-central1"


class VertexServiceAccountProvider(AIProvider):
    """Provider Vertex AI via compte de service JSON (VERTEX_SERVICE_ACCOUNT_JSON).

    Le JSON complet du compte de service est lu depuis la variable d'environnement.
    Le project_id est extrait du JSON ; la localisation par défaut est us-central1.
    """

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.VERTEX_SERVICE_ACCOUNT

    def is_configured(self) -> bool:
        return bool(os.environ.get(_ENV_KEY))

    def list_models(self) -> list[ModelInfo]:
        if not self.is_configured():
            raise RuntimeError(f"Variable d'environnement manquante : {_ENV_KEY}")

        sa_json_str = os.environ[_ENV_KEY]
        try:
            sa_info = json.loads(sa_json_str)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"{_ENV_KEY} : JSON invalide — {exc}"
            ) from exc

        project_id: str | None = sa_info.get("project_id")
        if not project_id:
            raise ValueError(
                f"{_ENV_KEY} : champ 'project_id' manquant dans le JSON"
            )

        credentials = service_account.Credentials.from_service_account_info(
            sa_info,
            scopes=_VERTEX_SCOPES,
        )
        client = genai.Client(
            vertexai=True,
            project=project_id,
            location=_DEFAULT_LOCATION,
            credentials=credentials,
        )
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
            "Vertex service account models fetched",
            extra={
                "provider": self.provider_type,
                "project": project_id,
                "count": len(result),
            },
        )
        return result
