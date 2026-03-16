"""
Schémas Pydantic pour les couches d'annotation de page.
"""
# 1. stdlib
from datetime import datetime
from enum import Enum

# 2. third-party
from pydantic import BaseModel

# 3. local
from app.schemas.corpus_profile import LayerType


class LayerStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"
    VALIDATED = "validated"


class AnnotationLayer(BaseModel):
    id: str
    page_id: str
    layer_type: LayerType
    status: LayerStatus = LayerStatus.PENDING
    version: int = 1
    source_model: str | None = None
    prompt_version: str | None = None
    created_at: datetime
