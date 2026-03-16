"""
Schémas Pydantic pour le JSON maître de page — source canonique de toutes les sorties.
"""
# 1. stdlib
from datetime import datetime
from enum import Enum
from typing import Any, Literal

# 2. third-party
from pydantic import BaseModel, ConfigDict, Field, field_validator


class RegionType(str, Enum):
    TEXT_BLOCK = "text_block"
    MINIATURE = "miniature"
    DECORATED_INITIAL = "decorated_initial"
    MARGIN = "margin"
    RUBRIC = "rubric"
    OTHER = "other"


class Region(BaseModel):
    id: str
    type: RegionType
    bbox: list[int] = Field(..., min_length=4, max_length=4)
    confidence: float = Field(..., ge=0.0, le=1.0)
    polygon: list[list[int]] | None = None
    parent_region_id: str | None = None

    @field_validator("bbox")
    @classmethod
    def bbox_must_be_positive(cls, v: list[int]) -> list[int]:
        if any(x < 0 for x in v):
            raise ValueError("bbox values must be >= 0")
        if v[2] <= 0 or v[3] <= 0:
            raise ValueError("bbox width and height must be > 0")
        return v


class OCRResult(BaseModel):
    diplomatic_text: str = ""
    blocks: list[dict] = []
    lines: list[dict] = []
    language: str = "la"
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    uncertain_segments: list[str] = []


class Translation(BaseModel):
    fr: str = ""
    en: str = ""


class CommentaryClaim(BaseModel):
    claim: str
    evidence_region_ids: list[str] = []
    certainty: Literal["high", "medium", "low", "speculative"] = "medium"


class Commentary(BaseModel):
    public: str = ""
    scholarly: str = ""
    claims: list[CommentaryClaim] = []


class ProcessingInfo(BaseModel):
    model_id: str
    model_display_name: str
    prompt_version: str
    raw_response_path: str
    processed_at: datetime
    cost_estimate_usd: float | None = None


class EditorialStatus(str, Enum):
    MACHINE_DRAFT = "machine_draft"
    NEEDS_REVIEW = "needs_review"
    REVIEWED = "reviewed"
    VALIDATED = "validated"
    PUBLISHED = "published"


class EditorialInfo(BaseModel):
    status: EditorialStatus = EditorialStatus.MACHINE_DRAFT
    validated: bool = False
    validated_by: str | None = None
    version: int = 1
    notes: list[str] = []


class PageMaster(BaseModel):
    schema_version: str = "1.0"
    page_id: str
    corpus_profile: str
    manuscript_id: str
    folio_label: str
    sequence: int

    image: dict
    layout: dict
    ocr: OCRResult | None = None
    translation: Translation | None = None
    summary: dict | None = None
    commentary: Commentary | None = None
    extensions: dict[str, Any] = {}

    processing: ProcessingInfo | None = None
    editorial: EditorialInfo = Field(default_factory=EditorialInfo)
