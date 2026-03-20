"""
Provider Vertex AI — authentification via clé API Express Vertex (VERTEX_API_KEY).

ÉTAT : NON FONCTIONNEL — aiplatform.googleapis.com n'accepte pas les clés API.

Diagnostic :
  - Sans vertexai=True → generativelanguage.googleapis.com → 403 (clé Vertex rejetée)
  - Avec vertexai=True  → aiplatform.googleapis.com → 401 UNAUTHENTICATED
    "API keys are not supported by this API. Expected OAuth2 access token."

Cause : Vertex AI (aiplatform) n'accepte que OAuth2 / service account / ADC.
Les clés API (format AQ.Ab...) ne sont pas prises en charge par cette API.

Alternatives fonctionnelles :
  1. Google AI Studio : GOOGLE_AI_STUDIO_API_KEY (clé AIza...) → fonctionne
  2. Vertex AI Service Account : VERTEX_SERVICE_ACCOUNT_JSON → fonctionne

Ce provider est conservé pour la cohérence de l'interface mais is_configured()
retourne toujours False afin d'éviter des appels réseau voués à l'échec.
"""
# 1. stdlib
import logging
import os

# 2. third-party
from google.genai import types  # noqa: F401  (conservé pour import cohérence)

# 3. local
from app.schemas.model_config import ModelInfo, ProviderType
from app.services.ai.base import AIProvider

logger = logging.getLogger(__name__)

_ENV_KEY = "VERTEX_API_KEY"

_UNAVAILABLE_MSG = (
    "VERTEX_API_KEY définie mais aiplatform.googleapis.com n'accepte pas les "
    "clés API (OAuth2 requis). Utilisez GOOGLE_AI_STUDIO_API_KEY pour le "
    "Gemini Developer API, ou VERTEX_SERVICE_ACCOUNT_JSON pour Vertex AI."
)


class VertexAPIKeyProvider(AIProvider):
    """Provider Vertex AI via clé API Express — NON FONCTIONNEL.

    aiplatform.googleapis.com exige OAuth2/service account ; les clés API
    sont systématiquement rejetées avec 401 UNAUTHENTICATED.
    Ce provider reste présent mais is_configured() retourne toujours False.
    """

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.VERTEX_API_KEY

    def is_configured(self) -> bool:
        if os.environ.get(_ENV_KEY):
            logger.warning(_UNAVAILABLE_MSG)
        return False

    def list_models(self) -> list[ModelInfo]:
        raise RuntimeError(_UNAVAILABLE_MSG)

    def generate_content(self, image_bytes: bytes, prompt: str, model_id: str) -> str:
        raise RuntimeError(_UNAVAILABLE_MSG)
