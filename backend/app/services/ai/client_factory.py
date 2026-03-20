"""
Factory pour créer un genai.Client selon le type de provider (R06, R11).

Standalone — ne modifie pas les fichiers providers de la Session A.
La clé API n'est jamais dans le code : lue exclusivement depuis les variables
d'environnement (R06).
"""
# 1. stdlib
import json
import logging
import os

# 2. third-party
from google import genai
from google.oauth2 import service_account

# 3. local
from app.schemas.model_config import ProviderType

logger = logging.getLogger(__name__)

_VERTEX_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
_DEFAULT_VERTEX_LOCATION = "us-central1"


def build_client(provider_type: ProviderType) -> genai.Client:
    """Crée un genai.Client configuré pour le provider indiqué.

    Lit les variables d'environnement nécessaires selon le provider :
    - GOOGLE_AI_STUDIO  → GOOGLE_AI_STUDIO_API_KEY
    - VERTEX_API_KEY    → VERTEX_API_KEY
    - VERTEX_SA         → VERTEX_SERVICE_ACCOUNT_JSON

    Args:
        provider_type: type de provider (GOOGLE_AI_STUDIO, VERTEX_API_KEY,
                       VERTEX_SERVICE_ACCOUNT).

    Returns:
        Instance genai.Client prête à l'emploi.

    Raises:
        RuntimeError: si la variable d'environnement requise est absente.
        ValueError: si le JSON du compte de service est invalide ou incomplet.
    """
    if provider_type == ProviderType.GOOGLE_AI_STUDIO:
        api_key = os.environ.get("GOOGLE_AI_STUDIO_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Variable d'environnement manquante : GOOGLE_AI_STUDIO_API_KEY"
            )
        logger.debug("Client Google AI Studio créé")
        return genai.Client(api_key=api_key)

    if provider_type == ProviderType.VERTEX_API_KEY:
        api_key = os.environ.get("VERTEX_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Variable d'environnement manquante : VERTEX_API_KEY"
            )
        logger.debug("Client Vertex AI Express (clé API) créé")
        # vertexai=True route vers aiplatform.googleapis.com (Vertex AI).
        # Sans vertexai=True, le SDK route vers generativelanguage.googleapis.com
        # (Gemini Developer API) qui rejette les clés Vertex Express avec 403.
        # project/location sont omis : mutually exclusive avec api_key dans le SDK.
        return genai.Client(vertexai=True, api_key=api_key)

    if provider_type == ProviderType.VERTEX_SERVICE_ACCOUNT:
        sa_json_str = os.environ.get("VERTEX_SERVICE_ACCOUNT_JSON")
        if not sa_json_str:
            raise RuntimeError(
                "Variable d'environnement manquante : VERTEX_SERVICE_ACCOUNT_JSON"
            )
        try:
            sa_info = json.loads(sa_json_str)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"VERTEX_SERVICE_ACCOUNT_JSON : JSON invalide — {exc}"
            ) from exc

        project_id: str | None = sa_info.get("project_id")
        if not project_id:
            raise ValueError(
                "VERTEX_SERVICE_ACCOUNT_JSON : champ 'project_id' manquant dans le JSON"
            )

        credentials = service_account.Credentials.from_service_account_info(
            sa_info,
            scopes=_VERTEX_SCOPES,
        )
        logger.debug(
            "Client Vertex AI (compte de service) créé",
            extra={"project": project_id},
        )
        return genai.Client(
            vertexai=True,
            project=project_id,
            location=_DEFAULT_VERTEX_LOCATION,
            credentials=credentials,
        )

    raise ValueError(f"Type de provider inconnu : {provider_type}")
