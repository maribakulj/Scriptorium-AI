"""
Provider Mistral — authentification via MISTRAL_API_KEY.

Découverte dynamique des modèles via client.models.list() (SDK v1.x).
Fallback statique sur Pixtral Large + 12B si l'API est inaccessible.

is_configured() vérifie AUSSI que `from mistralai import Mistral` fonctionne.
Si seule la version 0.x est installée, le provider est marqué indisponible :
l'utilisateur ne peut pas sélectionner de modèle Mistral, et aucun job
ne partira avec une clé incompatible.

Bifurcation d'appel selon la capacité vision du modèle :
  - Pixtral (capabilities.vision = True, ou "pixtral" dans l'id) :
      content multimodal — image base64 + texte.
  - Modèles texte (Mistral Large, Small, Codestral…) :
      content texte seul — l'image n'est pas transmise.
"""
# 1. stdlib
import base64
import logging
import os

# 3. local
from app.schemas.model_config import ModelInfo, ProviderType
from app.services.ai.base import AIProvider

logger = logging.getLogger(__name__)

_ENV_KEY = "MISTRAL_API_KEY"

# Sous-chaînes d'IDs de modèles non génératifs à exclure de la liste
_SKIP_MODEL_KINDS = ("embed", "moderation")

# Liste statique de secours — utilisée si client.models.list() échoue
_MISTRAL_FALLBACK_MODELS: list[ModelInfo] = [
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

# Alias backward-compat (utilisé dans certains tests)
_MISTRAL_VISION_MODELS = _MISTRAL_FALLBACK_MODELS


def _model_supports_vision(model_id: str, model_obj: object = None) -> bool:
    """Détecte si un modèle Mistral supporte les entrées image.

    Utilise capabilities.vision si disponible (objet SDK v1.x),
    sinon se rabat sur la présence de 'pixtral' ou 'vision' dans l'ID.
    """
    if model_obj is not None:
        caps = getattr(model_obj, "capabilities", None)
        if caps is not None:
            return bool(getattr(caps, "vision", False))
    mid = model_id.lower()
    return "pixtral" in mid or "vision" in mid


class MistralProvider(AIProvider):
    """Provider Mistral AI (clé API MISTRAL_API_KEY).

    is_configured() valide à la fois la présence de MISTRAL_API_KEY ET
    que mistralai>=1.0 (classe Mistral) est importable. Si v0.x est installée,
    le provider est marqué indisponible pour éviter des jobs voués à l'échec.
    """

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.MISTRAL

    def is_configured(self) -> bool:
        """Retourne True si MISTRAL_API_KEY est définie ET mistralai>=1.0 est importable."""
        if not os.environ.get(_ENV_KEY):
            return False
        try:
            from mistralai import Mistral  # noqa: F401
            return True
        except ImportError:
            logger.warning(
                "MISTRAL_API_KEY est définie mais mistralai>=1.0 n'est pas disponible "
                "(version 0.x détectée ou package absent). "
                "Provider Mistral marqué indisponible. "
                "Reconstruisez le container : docker build --no-cache ..."
            )
            return False

    def list_models(self) -> list[ModelInfo]:
        """Liste les modèles Mistral disponibles via l'API (dynamique).

        Appelle client.models.list() pour récupérer la liste réelle.
        Filtre les modèles non génératifs (embeddings, modération).
        Utilise capabilities.vision pour déterminer le support image.
        Fallback sur la liste statique Pixtral si l'API est inaccessible.
        """
        if not self.is_configured():
            raise RuntimeError(
                f"Provider Mistral non configuré : vérifiez {_ENV_KEY} "
                "et que mistralai>=1.0 est installé."
            )

        from mistralai import Mistral

        client = Mistral(api_key=os.environ[_ENV_KEY])
        result: list[ModelInfo] = []

        try:
            models_resp = client.models.list()
            for m in models_resp.data or []:
                mid: str = m.id
                if any(skip in mid for skip in _SKIP_MODEL_KINDS):
                    continue
                vision = _model_supports_vision(mid, m)
                display: str = getattr(m, "display_name", None) or mid
                result.append(ModelInfo(
                    model_id=mid,
                    display_name=display,
                    provider=ProviderType.MISTRAL,
                    supports_vision=vision,
                    input_token_limit=None,
                    output_token_limit=None,
                ))
            if result:
                logger.info(
                    "Mistral models fetched from API",
                    extra={"count": len(result)},
                )
                return result
        except Exception as exc:
            logger.warning(
                "Mistral API list_models échoué : %s — fallback liste statique", exc
            )

        logger.info(
            "Mistral models : liste statique (fallback)",
            extra={"count": len(_MISTRAL_FALLBACK_MODELS)},
        )
        return list(_MISTRAL_FALLBACK_MODELS)

    def generate_content(self, image_bytes: bytes, prompt: str, model_id: str) -> str:
        """Envoie image + prompt à Mistral et retourne le texte brut.

        Bifurcation selon le support vision du modèle :
          - Vision (Pixtral) : content multimodal avec image base64 + texte.
          - Texte seul (Mistral Large, Small, Codestral…) : prompt texte uniquement,
            l'image n'est pas transmise (avertissement loggé).
        """
        if not self.is_configured():
            raise RuntimeError(
                f"Provider Mistral non disponible : vérifiez {_ENV_KEY} "
                "et que mistralai>=1.0 est installé."
            )

        from mistralai import Mistral

        client = Mistral(api_key=os.environ[_ENV_KEY])

        if _model_supports_vision(model_id):
            image_b64 = base64.b64encode(image_bytes).decode("utf-8")
            data_url = f"data:image/jpeg;base64,{image_b64}"
            content: object = [
                {"type": "image_url", "image_url": {"url": data_url}},
                {"type": "text", "text": prompt},
            ]
        else:
            logger.warning(
                "Modèle texte seul sélectionné pour une analyse image : %s. "
                "L'image ne sera pas transmise à l'API.",
                model_id,
            )
            content = prompt

        response = client.chat.complete(
            model=model_id,
            messages=[{"role": "user", "content": content}],
        )
        choices = response.choices or []
        if not choices:
            return ""
        return choices[0].message.content or ""
