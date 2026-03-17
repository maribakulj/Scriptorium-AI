"""
Modèles SQLAlchemy — importés ici pour que Base.metadata les connaisse
au moment de la création des tables (Base.metadata.create_all).
"""
from app.models.corpus import CorpusModel, ManuscriptModel, PageModel
from app.models.job import JobModel
from app.models.model_config_db import ModelConfigDB

__all__ = [
    "CorpusModel",
    "ManuscriptModel",
    "PageModel",
    "JobModel",
    "ModelConfigDB",
]
