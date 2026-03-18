"""
Interface abstraite commune à tous les providers IA.
"""
# 1. stdlib
from abc import ABC, abstractmethod
from typing import Any

# 2. local
from app.schemas.model_config import ModelInfo, ProviderType


def is_vision_model(model: Any) -> bool:
    """Détermine si un modèle supporte les entrées image.

    Les modèles Gemini sont tous multimodaux ; les modèles texte-only (ex :
    embedding, AQA) ne contiennent pas 'gemini' dans leur identifiant.
    """
    name = (getattr(model, "name", "") or "").lower()
    display = (getattr(model, "display_name", "") or "").lower()
    return "gemini" in name or "vision" in name or "vision" in display


class AIProvider(ABC):
    """Interface commune à tous les providers IA (Google, Mistral, …)."""

    @property
    @abstractmethod
    def provider_type(self) -> ProviderType: ...

    @abstractmethod
    def is_configured(self) -> bool:
        """Retourne True si les credentials nécessaires sont présents en environnement."""
        ...

    @abstractmethod
    def list_models(self) -> list[ModelInfo]:
        """Liste les modèles disponibles pour ce provider.

        Lève RuntimeError si le provider n'est pas configuré.
        Propage les exceptions réseau/API sans les masquer.
        """
        ...

    @abstractmethod
    def generate_content(self, image_bytes: bytes, prompt: str, model_id: str) -> str:
        """Envoie une image + prompt à l'IA et retourne le texte brut de la réponse.

        Args:
            image_bytes: contenu JPEG de l'image dérivée.
            prompt: texte du prompt rendu depuis le template.
            model_id: identifiant technique du modèle à utiliser.

        Returns:
            Texte brut retourné par l'API (avant parsing).

        Raises:
            RuntimeError: si le provider n'est pas configuré.
        """
        ...
