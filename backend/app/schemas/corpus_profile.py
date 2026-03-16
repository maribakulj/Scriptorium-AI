"""
Schémas Pydantic pour le profil de corpus — entité centrale du pipeline.
"""
# 1. stdlib
from enum import Enum

# 2. third-party
from pydantic import BaseModel, ConfigDict, Field


class LayerType(str, Enum):
    IMAGE = "image"
    OCR_DIPLOMATIC = "ocr_diplomatic"
    OCR_NORMALIZED = "ocr_normalized"
    TRANSLATION_FR = "translation_fr"
    TRANSLATION_EN = "translation_en"
    SUMMARY = "summary"
    SCHOLARLY_COMMENTARY = "scholarly_commentary"
    PUBLIC_COMMENTARY = "public_commentary"
    ICONOGRAPHY_DETECTION = "iconography_detection"
    MATERIAL_NOTES = "material_notes"
    UNCERTAINTY = "uncertainty"


class ScriptType(str, Enum):
    CAROLINE = "caroline"
    GOTHIC = "gothic"
    PRINT = "print"
    CURSIVE = "cursive"
    OTHER = "other"


class ExportConfig(BaseModel):
    mets: bool = True
    alto: bool = True
    tei: bool = False


class UncertaintyConfig(BaseModel):
    flag_below: float = Field(0.4, ge=0.0, le=1.0)
    min_acceptable: float = Field(0.25, ge=0.0, le=1.0)


class CorpusProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    profile_id: str
    label: str
    language_hints: list[str]
    script_type: ScriptType
    active_layers: list[LayerType]
    prompt_templates: dict[str, str]
    uncertainty_config: UncertaintyConfig
    export_config: ExportConfig
