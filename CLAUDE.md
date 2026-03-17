# Scriptorium AI — Instructions permanentes pour Claude Code
## Version 2.0 — mise à jour Sprint 2

---

## 1. Contexte du projet

Scriptorium AI est une **plateforme générique** de génération d'éditions savantes augmentées
pour documents patrimoniaux numérisés : manuscrits médiévaux, incunables, cartulaires,
archives, chartes, papyri — tout type de document, toute époque, toute langue.

Pipeline général :
  images sources → ingestion → normalisation → analyse Google AI → JSON maître
  → passes dérivées → ALTO / METS / Manifest IIIF → interface web → validation humaine

Premier démonstrateur : **Beatus de Saint-Sever** (BnF Latin 8878, manuscrit enluminé,
latin carolingien, XIe siècle). Le Beatus est un profil parmi d'autres — pas un cas spécial.

---

## 2. Stack technique

| Composant       | Technologie                                            |
|-----------------|--------------------------------------------------------|
| Backend         | Python 3.11+, FastAPI, Uvicorn                         |
| Validation      | Pydantic v2 (JAMAIS v1)                                |
| Base de données | SQLite via SQLAlchemy 2.0 async + aiosqlite            |
| IA              | Google AI — provider sélectionnable (section 9)        |
| SDK Google      | google-genai (PAS google-generativeai — paquet différent)|
| XML             | lxml                                                   |
| Images          | Pillow (PIL)                                           |
| HTTP client     | httpx (téléchargement images IIIF)                     |
| Tests           | pytest, pytest-cov, pytest-asyncio                     |
| Frontend        | React + Vite, TypeScript, Tailwind CSS (sprint 4+)     |
| Hébergement     | HuggingFace Spaces (Docker) + HF Datasets              |

### pyproject.toml — dépendances exactes

```toml
[project]
name = "scriptorium-ai"
version = "0.1.0"
requires-python = ">=3.11"

dependencies = [
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "fastapi>=0.104",
    "uvicorn>=0.24",
    "python-multipart>=0.0.6",
    "google-genai>=0.3",
    "lxml>=4.9",
    "Pillow>=10.0",
    "httpx>=0.25",
    "sqlalchemy>=2.0",
    "aiosqlite>=0.19",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
    "pytest-asyncio>=0.21",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

---

## 3. Arborescence du repo — structure canonique

```
scriptorium-ai/
│
├── CLAUDE.md               ← CE FICHIER — ne pas modifier sans instruction
├── STATUS.md               ← état courant (mis à jour avant chaque session)
│
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  ← point d'entrée FastAPI (sprint 4+)
│   │   ├── config.py                ← settings Pydantic depuis env vars
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── __init__.py
│   │   │       ├── corpora.py
│   │   │       ├── pages.py
│   │   │       ├── jobs.py
│   │   │       ├── models.py        ← endpoints sélection modèle IA
│   │   │       └── export.py
│   │   ├── models/                  ← modèles SQLAlchemy (tables BDD)
│   │   │   ├── __init__.py
│   │   │   ├── corpus.py
│   │   │   ├── page.py
│   │   │   └── job.py
│   │   ├── schemas/                 ← modèles Pydantic (SOURCE CANONIQUE)
│   │   │   ├── __init__.py
│   │   │   ├── corpus_profile.py    ← ✓ Sprint 1
│   │   │   ├── page_master.py       ← ✓ Sprint 1
│   │   │   └── annotation.py        ← ✓ Sprint 1
│   │   └── services/
│   │       ├── __init__.py
│   │       ├── ingest/
│   │       │   ├── __init__.py
│   │       │   └── image_loader.py  ← chargement images (URL/fichier)
│   │       ├── image/
│   │       │   ├── __init__.py
│   │       │   └── processor.py     ← dérivés + thumbnails
│   │       ├── ai/
│   │       │   ├── __init__.py
│   │       │   ├── client.py        ← factory provider A/B/C
│   │       │   ├── models.py        ← listage modèles disponibles
│   │       │   ├── prompt_loader.py ← chargement + rendu templates
│   │       │   └── pipeline.py      ← orchestration appels IA
│   │       ├── export/
│   │       │   ├── __init__.py
│   │       │   ├── alto.py          ← générateur ALTO (sprint 3+)
│   │       │   ├── mets.py          ← générateur METS (sprint 3+)
│   │       │   └── iiif.py          ← générateur manifest IIIF (sprint 3+)
│   │       └── search/
│   │           ├── __init__.py
│   │           └── index.py         ← index recherche (sprint 6+)
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_schemas.py          ← ✓ 26 tests Sprint 1
│   │   ├── test_profiles.py         ← ✓ 28 tests Sprint 1
│   │   ├── test_ai_connection.py    ← Sprint 2 Session A
│   │   ├── test_image_processing.py ← Sprint 2 Session B
│   │   └── test_pipeline.py         ← Sprint 2 Session C
│   └── pyproject.toml
│
├── prompts/                         ← ✓ Sprint 1
│   ├── medieval-illuminated/
│   │   ├── primary_v1.txt
│   │   ├── transcription_v1.txt
│   │   ├── translation_v1.txt
│   │   ├── commentary_v1.txt
│   │   └── iconography_v1.txt
│   ├── medieval-textual/
│   │   ├── primary_v1.txt
│   │   ├── translation_v1.txt
│   │   └── commentary_v1.txt
│   ├── early-modern-print/
│   │   └── primary_v1.txt
│   └── modern-handwritten/
│       └── primary_v1.txt
│
├── profiles/                        ← ✓ Sprint 1
│   ├── medieval-illuminated.json
│   ├── medieval-textual.json
│   ├── early-modern-print.json
│   └── modern-handwritten.json
│
├── data/                            ← JAMAIS versionné (.gitignore)
│   └── corpora/
│       └── {corpus_slug}/
│           ├── masters/             ← images sources originales
│           ├── derivatives/         ← JPEG 1500px pour l'IA
│           ├── thumbnails/          ← aperçus 300px
│           ├── iiif/
│           │   ├── manifest.json
│           │   └── annotations/
│           └── pages/
│               └── {folio_label}/
│                   ├── master.json      ← PageMaster canonique
│                   ├── ai_raw.json      ← réponse brute IA (JAMAIS effacée)
│                   ├── alto.xml
│                   └── annotations.json
│
└── infra/
    └── Dockerfile
```

---

## 4. Modèles de données — schémas Pydantic canoniques

### 4.1 CorpusProfile (corpus_profile.py)

```python
from enum import Enum
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
    prompt_templates: dict[str, str]      # {"primary": "prompts/.../v1.txt"}
    uncertainty_config: UncertaintyConfig
    export_config: ExportConfig
```

### 4.2 PageMaster (page_master.py)

```python
from datetime import datetime
from typing import Any, Literal
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
    def bbox_must_be_valid(cls, v: list[int]) -> list[int]:
        if any(x < 0 for x in v):
            raise ValueError("bbox: toutes les valeurs doivent être >= 0")
        if v[2] <= 0 or v[3] <= 0:
            raise ValueError("bbox: width et height doivent être > 0")
        return v

class ImageInfo(BaseModel):
    master: str                        # path ou URL source
    derivative_web: str | None = None  # JPEG 1500px
    thumbnail: str | None = None       # JPEG 300px
    iiif_base: str | None = None
    width: int
    height: int

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

class Summary(BaseModel):
    short: str = ""
    detailed: str = ""

class CommentaryClaim(BaseModel):
    claim: str
    evidence_region_ids: list[str] = []
    certainty: Literal["high", "medium", "low", "speculative"] = "medium"

class Commentary(BaseModel):
    public: str = ""
    scholarly: str = ""
    claims: list[CommentaryClaim] = []

class ProcessingInfo(BaseModel):
    provider: str                       # "google_ai_studio"|"vertex_api_key"|"vertex_service_account"
    model_id: str                       # ID technique retourné par l'API
    model_display_name: str
    prompt_version: str                 # ex: "primary_v1"
    raw_response_path: str              # chemin vers ai_raw.json
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
    schema_version: str = "1.0"        # OBLIGATOIRE — ne jamais omettre
    page_id: str                        # format: {corpus_slug}-{folio_label}
    corpus_profile: str                 # profile_id du CorpusProfile utilisé
    manuscript_id: str
    folio_label: str                    # ex: "13r", "f29"
    sequence: int                       # ordre dans le manuscrit (1-based)
    image: ImageInfo
    layout: dict                        # {"regions": [Region, ...]}
    ocr: OCRResult | None = None
    translation: Translation | None = None
    summary: Summary | None = None
    commentary: Commentary | None = None
    extensions: dict[str, Any] = {}    # données spécifiques au profil
    processing: ProcessingInfo | None = None
    editorial: EditorialInfo = EditorialInfo()
```

### 4.3 AnnotationLayer (annotation.py)

```python
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

class ModelConfig(BaseModel):
    corpus_id: str
    provider: str
    selected_model_id: str
    selected_model_display_name: str
    supports_vision: bool
    last_fetched_at: datetime
    available_models: list[dict] = []
```

---

## 5. Exemple complet d'un master.json valide

Cet exemple est la référence. Tout master.json produit doit avoir cette forme.

```json
{
  "schema_version": "1.0",
  "page_id": "beatus-lat8878-0013r",
  "corpus_profile": "medieval-illuminated",
  "manuscript_id": "beatus-lat8878",
  "folio_label": "13r",
  "sequence": 25,
  "image": {
    "master": "https://gallica.bnf.fr/ark:/12148/btv1b8432314s/f29.highres",
    "derivative_web": "data/corpora/beatus-lat8878/derivatives/0013r.jpg",
    "thumbnail": "data/corpora/beatus-lat8878/thumbnails/0013r.jpg",
    "iiif_base": null,
    "width": 3543,
    "height": 4724
  },
  "layout": {
    "regions": [
      {
        "id": "r1",
        "type": "text_block",
        "bbox": [320, 510, 2900, 3200],
        "confidence": 0.91,
        "polygon": null,
        "parent_region_id": null
      },
      {
        "id": "r2",
        "type": "miniature",
        "bbox": [320, 3750, 2900, 800],
        "confidence": 0.95,
        "polygon": null,
        "parent_region_id": null
      }
    ]
  },
  "ocr": {
    "diplomatic_text": "Explicit liber primus incipit secundus...",
    "blocks": [],
    "lines": [],
    "language": "la",
    "confidence": 0.74,
    "uncertain_segments": ["primus incipit"]
  },
  "translation": {
    "fr": "Fin du premier livre, début du second...",
    "en": "End of the first book, beginning of the second..."
  },
  "summary": {
    "short": "Page de transition entre deux livres avec scène apocalyptique.",
    "detailed": "Ce folio marque la fin du livre I et l'ouverture du livre II..."
  },
  "commentary": {
    "public": "Cette page illustre la transition narrative entre deux grandes parties...",
    "scholarly": "Le programme iconographique de ce folio suit la tradition des Beatus...",
    "claims": [
      {
        "claim": "La scène de la région r2 représente l'ouverture du cinquième sceau",
        "evidence_region_ids": ["r2"],
        "certainty": "medium"
      }
    ]
  },
  "extensions": {
    "iconography": [
      {
        "region_id": "r2",
        "label": "ouverture_cinquieme_sceau",
        "description": "Personnages en prière, autel central, âmes des martyrs",
        "confidence": 0.78,
        "tags": ["apocalypse", "sceau", "martyrs", "autel"]
      }
    ],
    "materiality": {
      "notes": ["Légère décoloration dans la marge inférieure droite"],
      "pigment_hints": ["ocre", "lapis-lazuli probable", "blanc de plomb"]
    }
  },
  "processing": {
    "provider": "vertex_api_key",
    "model_id": "gemini-2.0-flash-exp",
    "model_display_name": "Gemini 2.0 Flash Experimental",
    "prompt_version": "primary_v1",
    "raw_response_path": "data/corpora/beatus-lat8878/pages/0013r/ai_raw.json",
    "processed_at": "2025-01-01T10:00:00Z",
    "cost_estimate_usd": 0.004
  },
  "editorial": {
    "status": "machine_draft",
    "validated": false,
    "validated_by": null,
    "version": 1,
    "notes": []
  }
}
```

---

## 6. Règles absolues — NE JAMAIS ENFREINDRE

### R01 — Zéro logique hardcodée par corpus
```python
# ❌ INTERDIT
if profile_id == "medieval-illuminated":
    process_iconography()

# ✅ CORRECT
if "iconography_detection" in corpus_profile.active_layers:
    process_iconography()
```

### R02 — Le JSON maître est la source canonique
Toutes les sorties (IIIF, ALTO, METS) sont générées depuis PageMaster.
Jamais depuis ai_raw.json directement.

### R03 — Convention bbox [x, y, width, height] UNIQUEMENT
```python
# ❌ INTERDIT — coordonnées de coins opposés
bbox = [x1, y1, x2, y2]

# ✅ CORRECT — origine + dimensions
bbox = [x, y, x2 - x1, y2 - y1]
```
Pixels entiers absolus dans l'image. Width et height > 0. Toujours validé par Pydantic.

### R04 — Prompts dans des fichiers versionnés, jamais dans le code
```python
# ❌ INTERDIT
prompt = f"Tu analyses un {profile.label}. Retourne ce JSON..."

# ✅ CORRECT
prompt = load_and_render_prompt(
    corpus_profile.prompt_templates["primary"],
    {"profile_label": profile.label, ...}
)
```

### R05 — Double stockage obligatoire des réponses IA
```python
# ❌ INTERDIT — un seul fichier
master = parse(response)
save(master, "master.json")

# ✅ CORRECT — toujours deux fichiers distincts
save_raw(response.text, page_dir / "ai_raw.json")      # brut, jamais effacé
master = parse_and_validate(response.text)
save_json(master.model_dump(), page_dir / "master.json")
```

### R06 — Secrets uniquement dans les variables d'environnement
Jamais dans le code, les logs, les fichiers versionnés, les exports JSON.

### R07 — Pydantic v2 exclusivement
```python
# ❌ INTERDIT — syntaxe v1
class Config:
    frozen = True

# ✅ CORRECT — syntaxe v2
model_config = ConfigDict(frozen=True)
```

### R08 — Tests pour tout nouveau modèle
Aucun schéma Pydantic sans test de validation et de rejet.

### R09 — schema_version dans tout PageMaster
`schema_version: str = "1.0"` — obligatoire, valeur par défaut suffit.

### R10 — Endpoints préfixés /api/v1/

### R11 — SDK google-genai, pas google-generativeai
```python
# ❌ INTERDIT
import google.generativeai as genai

# ✅ CORRECT
from google import genai
```

### R12 — Jamais le master TIFF/JP2 brut envoyé à l'IA
Toujours passer par le dérivé JPEG 1500px max.

---

## 7. Patterns de code attendus

### Config depuis variables d'environnement (config.py)

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    ai_provider: str = "vertex_api_key"
    google_ai_studio_api_key: str | None = None
    vertex_api_key: str | None = None
    vertex_project_id: str | None = None
    vertex_location: str = "europe-west1"
    vertex_service_account_json: str | None = None
    data_dir: str = "data"

    model_config = ConfigDict(env_file=".env", extra="ignore")

settings = Settings()
```

### Pattern SQLAlchemy (models/)

```python
from sqlalchemy import String, Integer, Float, DateTime, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from datetime import datetime

class Base(DeclarativeBase):
    pass

class PageModel(Base):
    __tablename__ = "pages"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    manuscript_id: Mapped[str] = mapped_column(String, index=True)
    folio_label: Mapped[str] = mapped_column(String)
    sequence: Mapped[int] = mapped_column(Integer)
    processing_status: Mapped[str] = mapped_column(String, default="ingested")
    confidence_summary: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

### Pattern FastAPI endpoint (api/v1/)

```python
from fastapi import APIRouter, HTTPException, Depends
from app.schemas.page_master import PageMaster

router = APIRouter(prefix="/api/v1")

@router.get("/pages/{page_id}/master-json", response_model=PageMaster)
async def get_master_json(page_id: str) -> PageMaster:
    master_path = get_page_dir(page_id) / "master.json"
    if not master_path.exists():
        raise HTTPException(status_code=404, detail=f"Page {page_id} not found")
    return PageMaster.model_validate_json(master_path.read_text())

@router.put("/pages/{page_id}/master-json", response_model=PageMaster)
async def update_master_json(page_id: str, master: PageMaster) -> PageMaster:
    # incrémenter la version
    master = master.model_copy(update={"editorial": {
        **master.editorial.model_dump(),
        "version": master.editorial.version + 1
    }})
    save_json(master.model_dump(), get_page_dir(page_id) / "master.json")
    return master
```

### Pattern gestion d'erreur IA

```python
import json
import logging
from pydantic import ValidationError

logger = logging.getLogger(__name__)

def parse_ai_response(raw_text: str, page_id: str) -> PageMaster:
    # 1. Nettoyer les éventuels blocs markdown (triple backtick json)
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:-1])

    # 2. Parser le JSON
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error("JSON invalide", extra={"page_id": page_id, "error": str(e)})
        raise ValueError(f"Réponse IA non parseable pour {page_id}: {e}")

    # 3. Valider avec Pydantic
    try:
        return PageMaster.model_validate(data)
    except ValidationError as e:
        logger.error("Validation Pydantic échouée", extra={"page_id": page_id, "errors": e.errors()})
        raise ValueError(f"JSON IA invalide pour {page_id}: {e}")
```

---

## 8. Rendu des prompts — conventions

### Variables disponibles dans tous les templates

```
{{profile_label}}      → CorpusProfile.label
{{language_hints}}     → ", ".join(CorpusProfile.language_hints)
{{script_type}}        → CorpusProfile.script_type.value
{{folio_label}}        → Page.folio_label
{{manuscript_title}}   → Manuscript.title (si disponible)
```

### Implémentation attendue (prompt_loader.py)

```python
from pathlib import Path

def load_and_render_prompt(template_path: str, context: dict[str, str]) -> str:
    """Charge un template de prompt et injecte les variables."""
    path = Path(template_path)
    if not path.exists():
        raise FileNotFoundError(f"Template introuvable : {template_path}")

    content = path.read_text(encoding="utf-8")

    for key, value in context.items():
        content = content.replace("{{" + key + "}}", str(value))

    # Vérifier qu'il ne reste pas de variables non résolues
    if "{{" in content:
        import re
        unresolved = re.findall(r"\{\{\w+\}\}", content)
        raise ValueError(f"Variables non résolues dans le prompt : {unresolved}")

    return content
```

---

## 9. Providers Google AI — architecture à 3 options

### Variables d'environnement (GitHub Secrets)

```
# Option A — Google AI Studio (développement, gratuit)
GOOGLE_AI_STUDIO_API_KEY  = AIza...

# Option B — Vertex AI avec clé API Express (production)
VERTEX_API_KEY             = AQ.Ab...
VERTEX_PROJECT_ID          = beatus-490422
VERTEX_LOCATION            = europe-west1

# Option C — Vertex AI avec compte de service (institutions)
VERTEX_SERVICE_ACCOUNT_JSON = { ...json complet... }
VERTEX_PROJECT_ID           = (même)
VERTEX_LOCATION             = (même)

# Sélecteur actif — changer pour switcher de provider
AI_PROVIDER = vertex_api_key
```

### Factory client (client.py)

```python
from google import genai
import os, json, logging

logger = logging.getLogger(__name__)

def get_ai_client() -> genai.Client:
    provider = os.environ.get("AI_PROVIDER", "google_ai_studio")
    logger.info(f"Initialisation client IA", extra={"provider": provider})

    if provider == "google_ai_studio":
        # Option A — Google AI Studio, clé AIza
        return genai.Client(
            api_key=os.environ["GOOGLE_AI_STUDIO_API_KEY"]
        )

    elif provider == "vertex_api_key":
        # Option B — Vertex Express, clé AQ.Ab
        # SYNTAXE EXACTE À VALIDER EN SPRINT 2 SESSION A
        # Tester approche 1 en premier :
        return genai.Client(
            api_key=os.environ["VERTEX_API_KEY"]
        )
        # Si approche 1 échoue, tester approche 2 :
        # return genai.Client(
        #     api_key=os.environ["VERTEX_API_KEY"],
        #     http_options={"api_version": "v1beta"}
        # )

    elif provider == "vertex_service_account":
        # Option C — Vertex avec compte de service JSON
        creds_json = os.environ["VERTEX_SERVICE_ACCOUNT_JSON"]
        creds_dict = json.loads(creds_json)
        return genai.Client(
            vertexai=True,
            project=os.environ["VERTEX_PROJECT_ID"],
            location=os.environ.get("VERTEX_LOCATION", "europe-west1"),
            credentials=creds_dict,
        )

    raise ValueError(f"AI_PROVIDER inconnu : {provider!r}. "
                     "Valeurs acceptées : google_ai_studio, vertex_api_key, vertex_service_account")
```

### Listage des modèles disponibles (models.py)

```python
def list_available_models(client: genai.Client) -> list[dict]:
    """
    Retourne les modèles disponibles supportant vision + generateContent.
    Format : [{"id": str, "display_name": str, "supports_vision": bool}]
    """
    models = []
    for model in client.models.list():
        # Garder uniquement les modèles multimodaux
        supported = getattr(model, "supported_generation_methods", [])
        if "generateContent" not in supported:
            continue
        # Vérifier le support vision (input_token_limit et modalities)
        modalities = getattr(model, "supported_actions", None) or []
        supports_vision = "image" in str(model).lower() or "vision" in str(model.name).lower()
        models.append({
            "id": model.name,
            "display_name": getattr(model, "display_name", model.name),
            "supports_vision": supports_vision,
        })
    return models
```

---

## 10. Structure des exports documentaires

### ALTO (par page)

ALTO contient la géométrie textuelle uniquement.
```xml
<alto>
  <Layout>
    <Page WIDTH="{width}" HEIGHT="{height}" ID="{page_id}">
      <PrintSpace>
        <!-- Pour chaque région de type text_block -->
        <TextBlock ID="{region.id}"
                   HPOS="{bbox[0]}" VPOS="{bbox[1]}"
                   WIDTH="{bbox[2]}" HEIGHT="{bbox[3]}">
          <TextLine>
            <String CONTENT="{text}" WC="{confidence}"/>
          </TextLine>
        </TextBlock>
        <!-- Pour chaque région de type miniature -->
        <Illustration ID="{region.id}"
                      HPOS="{bbox[0]}" VPOS="{bbox[1]}"
                      WIDTH="{bbox[2]}" HEIGHT="{bbox[3]}"/>
      </PrintSpace>
    </Page>
  </Layout>
</alto>
```

ALTO ne porte PAS : commentaires savants, iconographie, couches éditoriales.

### IIIF Manifest (par manuscrit)

Structure minimale V1 :
```json
{
  "@context": "http://iiif.io/api/presentation/3/context.json",
  "id": "https://{base_url}/api/v1/manuscripts/{id}/iiif-manifest",
  "type": "Manifest",
  "label": {"fr": ["{manuscript.title}"]},
  "metadata": [],
  "items": [
    {
      "id": "https://{base_url}/canvas/{page_id}",
      "type": "Canvas",
      "width": "{image.width}",
      "height": "{image.height}",
      "items": [{"type": "AnnotationPage", "items": [
        {"type": "Annotation", "motivation": "painting",
         "body": {"type": "Image", "id": "{image.derivative_web}",
                  "format": "image/jpeg",
                  "width": "{image.width}", "height": "{image.height}"},
         "target": "https://{base_url}/canvas/{page_id}"}
      ]}]
    }
  ]
}
```

---

## 11. Statuts métier

```
Corpus  : CREATED → INGESTING → INGESTED → PROCESSING → READY → ERROR
Page    : INGESTED → PREPARED → ANALYZED → LAYERED → EXPORTED → VALIDATED → ERROR
Layer   : PENDING → RUNNING → DONE → FAILED → NEEDS_REVIEW → VALIDATED
Éditorial: machine_draft → needs_review → reviewed → validated → published
```

---

## 12. Endpoints API — liste complète

```
# Configuration & modèles IA
POST   /api/v1/settings/api-key
GET    /api/v1/models
POST   /api/v1/models/refresh
PUT    /api/v1/corpora/{id}/model
GET    /api/v1/corpora/{id}/model

# Profils
GET    /api/v1/profiles
GET    /api/v1/profiles/{id}

# Corpus
POST   /api/v1/corpora
GET    /api/v1/corpora
GET    /api/v1/corpora/{id}
DELETE /api/v1/corpora/{id}

# Ingestion
POST   /api/v1/corpora/{id}/ingest/files
POST   /api/v1/corpora/{id}/ingest/iiif-manifest
POST   /api/v1/corpora/{id}/ingest/iiif-images

# Jobs
POST   /api/v1/corpora/{id}/run
POST   /api/v1/pages/{id}/run
GET    /api/v1/jobs/{job_id}
POST   /api/v1/jobs/{job_id}/retry

# Pages
GET    /api/v1/pages/{id}
GET    /api/v1/pages/{id}/master-json
PUT    /api/v1/pages/{id}/master-json
GET    /api/v1/pages/{id}/layers
POST   /api/v1/pages/{id}/layers/{layer_type}/regenerate

# Export
GET    /api/v1/manuscripts/{id}/iiif-manifest
GET    /api/v1/manuscripts/{id}/mets
GET    /api/v1/pages/{id}/alto
GET    /api/v1/manuscripts/{id}/export.zip

# Validation
POST   /api/v1/pages/{id}/validate
POST   /api/v1/pages/{id}/corrections
GET    /api/v1/pages/{id}/history

# Recherche
GET    /api/v1/search?q=
GET    /api/v1/manuscripts/{id}/search?q=
```

---

## 13. État du projet par sprint

```
Sprint 1 — Fondations du modèle de données        
  54 tests passants. Schémas Pydantic. 4 profils. 9 templates prompts.

Sprint 2 — Pipeline page unique                    
  Connexion Google AI validée → ingestion image → master.json

Sprint 3 — Exports documentaires                   
  ALTO par page + METS + Manifest IIIF

Sprint 4 — API FastAPI + interface de lecture       
  Endpoints + visionneuse OpenSeadragon + 4 couches

Sprint 5 — Traitement en lot + HuggingFace         
  Pipeline batch + déploiement public

Sprint 6 — Validation humaine + V1 complète       
  Éditeur + versionnement + recherche
```

**Règle stricte** : ne jamais implémenter du code d'un sprint futur.
Si une idée émerge, la noter dans STATUS.md section "Backlog" et ne pas la coder.

---

## 14. Ce que tu NE dois PAS faire sans demande explicite

- Modifier le schéma PageMaster (champs, types, noms, structure)
- Modifier la convention bbox
- Ajouter des dépendances non listées dans pyproject.toml section 2
- Refactoriser du code existant si la session n'a pas ce but
- Créer des fichiers hors de l'arborescence section 3
- Implémenter du code d'un sprint futur (section 13)
- "Simplifier" un schéma pour "faire plus propre" — les schémas sont figés
- Créer une logique spécifique à un corpus (règle R01)
- Utiliser google-generativeai au lieu de google-genai (règle R11)
- Laisser une variable d'environnement dans le code (règle R06)
