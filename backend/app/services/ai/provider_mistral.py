"""
Provider Mistral — authentification via MISTRAL_API_KEY.

Modèles multimodaux supportés : pixtral-large-latest, pixtral-12b-2409.
L'API Mistral n'expose pas d'endpoint list_models public stable ;
la liste des modèles est donc statique et maintenue ici.

Les appels image utilisent le format image_url (base64) dans le message user.
"""
# 1. stdlib
import base64
import logging
import os

# 3. local  (mistralai importé localement pour éviter l'import top-level à froid)
from app.schemas.model_config import ModelInfo, ProviderType
from app.services.ai.base import AIProvider

logger = logging.getLogger(__name__)

_ENV_KEY = "MISTRAL_API_KEY"

_MISTRAL_VISION_MODELS: list[ModelInfo] = [
    ModelInfo(
        model_id="pixtral-large-latest",
        display_name="Pixtral Large",
        provider=ProviderType.MISTRAL,
        supports_vision=True,
        input_token_limit=128_000,
        output_token_limit=None,
    ),
    ModelInfo(
        model_id="pixtral-12b-2409",
        display_name="Pixtral 12B",
        provider=ProviderType.MISTRAL,
        supports_vision=True,
        input_token_limit=128_000,
        output_token_limit=None,
    ),
]


class MistralProvider(AIProvider):
    """Provider Mistral AI (clé API MISTRAL_API_KEY).

    Liste de modèles statique (Pixtral Large + Pixtral 12B).
    Les appels image encodent le JPEG en base64 et l'envoient comme image_url.
    """

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.MISTRAL

    def is_configured(self) -> bool:
        return bool(os.environ.get(_ENV_KEY))

    def list_models(self) -> list[ModelInfo]:
        if not self.is_configured():
            raise RuntimeError(f"Variable d'environnement manquante : {_ENV_KEY}")
        logger.info(
            "Mistral models listed (static)",
            extra={"provider": self.provider_type, "count": len(_MISTRAL_VISION_MODELS)},
        )
        return list(_MISTRAL_VISION_MODELS)

    def generate_content(self, image_bytes: bytes, prompt: str, model_id: str) -> str:
        if not self.is_configured():
            raise RuntimeError(f"Variable d'environnement manquante : {_ENV_KEY}")

        try:
            from mistralai import Mistral  # v1.x — import local
        except ImportError as exc:
            raise ImportError(
                "Impossible d'importer 'Mistral' depuis mistralai. "
                "Vérifiez que le package est installé : pip install 'mistralai>=1.0'"
            ) from exc

        api_key = os.environ[_ENV_KEY]
        client = Mistral(api_key=api_key)

        image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        data_url = f"data:image/jpeg;base64,{image_b64}"

        response = client.chat.complete(
            model=model_id,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_url}},
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
        choices = response.choices or []
        if not choices:
            return ""
        return choices[0].message.content or ""
