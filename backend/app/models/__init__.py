"""
Modèles SQLAlchemy — importés ici pour que Base.metadata les connaisse
au moment de la création des tables (Base.metadata.create_all).
"""
from app.models.corpus import CorpusModel, ManuscriptModel, PageModel

__all__ = ["CorpusModel", "ManuscriptModel", "PageModel"]
