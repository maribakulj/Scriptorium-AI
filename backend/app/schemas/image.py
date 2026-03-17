"""
Schéma Pydantic pour les métadonnées du dérivé image produit par le pipeline.
"""
# 2. third-party
from pydantic import BaseModel


class ImageDerivativeInfo(BaseModel):
    """Résultat de la normalisation d'une image : dimensions originales et chemins des dérivés."""

    original_url: str
    original_width: int
    original_height: int
    derivative_path: str
    derivative_width: int
    derivative_height: int
    thumbnail_path: str
    thumbnail_width: int
    thumbnail_height: int
