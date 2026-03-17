"""
Interface abstraite commune à tous les providers Google AI.
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
    """Interface commune à tous les providers Google AI."""

    @property
    @abstractmethod
    def provider_type(self) -> ProviderType: ...

    @abstractmethod
    def is_configured(self) -> bool:
        """Retourne True si les credentials nécessaires sont présents en environnement."""
        ...

    @abstractmethod
    def list_models(self) -> list[ModelInfo]:
        """Liste les modèles filtrés (generateContent présent dans les méthodes supportées).

        Lève RuntimeError si le provider n'est pas configuré.
        Propage les exceptions réseau/API sans les masquer.
        """
        ...
