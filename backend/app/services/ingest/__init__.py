"""
Services d'ingestion — téléchargement de sources (IIIF, fichiers locaux).
"""
from app.services.ingest.iiif_fetcher import fetch_iiif_image

__all__ = ["fetch_iiif_image"]
