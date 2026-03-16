# Scriptorium AI — Instructions permanentes pour Claude Code

## 1. Contexte du projet

Scriptorium AI est une **plateforme générique** de génération d'éditions savantes augmentées
pour documents patrimoniaux numérisés : manuscrits médiévaux, incunables, cartulaires,
archives, chartes, papyri — tout type de document, toute époque, toute langue.

Pipeline général :
  images sources → ingestion → normalisation → analyse Google AI → JSON maître
  → passes dérivées → ALTO / METS / Manifest IIIF → interface web → validation humaine

Le premier démonstrateur est le **Beatus de Saint-Sever** (manuscrit enluminé médiéval,
latin, BnF Latin 8878). Mais la plateforme n'est PAS un outil Beatus.
Le Beatus est un profil parmi d'autres.

---

## 2. Stack technique

| Composant       | Technologie                                      |
|-----------------|--------------------------------------------------|
| Backend         | Python 3.11+, FastAPI, Uvicorn                   |
| Validation      | Pydantic v2 (jamais v1)                          |
| Base de données | SQLite via SQLAlchemy 2.0 async                  |
| IA              | Google AI API, modèle sélectionnable dynamiquement|
| SDK Google      | google-generativeai >= 0.3                       |
| XML             | lxml                                             |
| Images          | Pillow                                           |
| Tests           | pytest, pytest-cov, pytest-asyncio               |
| Frontend        | React + Vite, TypeScript, Tailwind CSS (sprint 4+)|
| Hébergement     | HuggingFace Spaces (Docker) + HF Datasets        |

---

## 3. Arborescence du repo — structure canonique

```
scriptorium-ai/
│
├── CLAUDE.md               ← CE FICHIER
├── CONTEXT.md              ← état courant du projet (tu ne le modifies pas)
├── DECISIONS.md            ← décisions figées (tu ne les remets pas en question)
├── TODO.md                 ← tâches de la session courante
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── v1/                  ← tous les endpoints FastAPI
│   │   ├── models/                  ← modèles SQLAlchemy (tables BDD)
│   │   ├── schemas/                 ← modèles Pydantic (source canonique des types)
│   │   │   ├── __init__.py
│   │   │   ├── corpus_profile.py
│   │   │   ├── page_master.py
│   │   │   └── annotation.py
│   │   └── services/
│   │       ├── ingest/              ← ingestion corpus
│   │       ├── image/               ← normalisation + dérivés
│   │       ├── ai/                  ← appels Google AI + parsing + validation
│   │       ├── export/              ← générateurs ALTO, METS, IIIF
│   │       └── search/              ← index recherche
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_schemas.py
│   │   └── test_profiles.py
│   └── pyproject.toml
│
├── prompts/
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
├── profiles/
│   ├── medieval-illuminated.json
│   ├── medieval-textual.json
│   ├── early-modern-print.json
│   └── modern-handwritten.json
│
├── data/                   ← JAMAIS versionné (.gitignore)
│   └── corpora/
│       └── {corpus_slug}/
│           ├── masters/
│           ├── derivatives/
│           ├── iiif/
│           └── pages/
│               └── {folio}/
│                   ├── master.json
│                   ├── gemini_raw.json
│                   ├── alto.xml
│                   └── annotations.json
│
└── infra/
    └── Dockerfile
```

Ne jamais créer de fichiers en dehors de cette arborescence sans demande explicite.

---

## 4. Modèle de données — schémas canoniques

### 4.1 CorpusProfile

Entité centrale. Tout le pipeline en est piloté.
Fichier : `backend/app/schemas/corpus_profile.py`

```python
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
    prompt_templates: dict[str, str]      # {"primary": "path/v1.txt", ...}
    uncertainty_config: UncertaintyConfig
    export_config: ExportConfig
```

### 4.2 PageMaster

Source canonique de toute page. Toutes les sorties en dérivent.
Fichier : `backend/app/schemas/page_master.py`

```python
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
    def bbox_must_be_positive(cls, v):
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
    corpus_profile: str            # profile_id du CorpusProfile
    manuscript_id: str
    folio_label: str
    sequence: int

    image: dict                    # master, derivative_web, iiif_base, width, height
    layout: dict                   # {"regions": [Region, ...]}
    ocr: OCRResult | None = None
    translation: Translation | None = None
    summary: dict | None = None    # {"short": str, "detailed": str}
    commentary: Commentary | None = None
    extensions: dict[str, Any] = {}   # données spécifiques au profil

    processing: ProcessingInfo | None = None
    editorial: EditorialInfo = EditorialInfo()
```

### 4.3 AnnotationLayer

Fichier : `backend/app/schemas/annotation.py`

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
```

---

## 5. Règles absolues — NE JAMAIS ENFREINDRE

### R01 — Aucune logique hardcodée par corpus
Jamais de condition du type `if corpus == "beatus"` ou `if profile == "medieval-illuminated"`.
Toute logique spécifique passe par le CorpusProfile. Le code est générique.

### R02 — Le JSON maître est la source canonique
Toutes les sorties (IIIF, ALTO, METS, annotations) sont générées depuis le PageMaster JSON.
On ne génère jamais une sortie directement depuis la réponse brute de l'IA.

### R03 — Convention bbox [x, y, width, height] UNIQUEMENT
Format : [x, y, largeur, hauteur] en pixels entiers dans l'image source.
- x, y = coin supérieur gauche
- width, height = dimensions
JAMAIS [x1, y1, x2, y2] (coins opposés).
JAMAIS de coordonnées relatives ou normalisées (0.0–1.0).
Le validator Pydantic doit rejeter toute bbox avec width ou height <= 0.

### R04 — Prompts dans des fichiers, jamais dans le code
Les prompts vivent dans prompts/{profile_id}/{famille}_v{n}.txt
Le code charge le fichier, injecte les variables, envoie à l'API.
Jamais de f-string de prompt hardcodée dans un fichier .py.

### R05 — Double stockage des réponses IA
Toujours écrire DEUX fichiers distincts :
- `gemini_raw.json` : réponse brute telle que retournée par l'API
- `master.json` : JSON parsé, validé par Pydantic, canonique
Un seul fichier = bug. Les deux sont obligatoires.

### R06 — Clé API jamais dans le code
La clé API Google AI vit uniquement dans les variables d'environnement.
Jamais dans : le code, les logs, les fichiers versionnés, les exports, les JSON maîtres.
Variable d'environnement : GOOGLE_AI_API_KEY

### R07 — Pydantic v2 exclusivement
Syntaxe v2 : `model_config = ConfigDict(...)` et non `class Config:`
`@field_validator` et non `@validator`
`model_validate()` et non `parse_obj()`
Imports : `from pydantic import BaseModel, ConfigDict, Field, field_validator`

### R08 — Tests pour tout modèle de données
Aucun nouveau schéma Pydantic sans test correspondant.
Aucun profil JSON sans test de chargement et validation.
Les tests ne sont pas optionnels.

### R09 — schema_version dans tout JSON maître
Le champ `schema_version: str = "1.0"` est obligatoire dans PageMaster.
Si le schéma change, la version change.

### R10 — Endpoints préfixés /api/v1/
Tous les endpoints FastAPI sont sous /api/v1/.
Exemple : /api/v1/corpora, /api/v1/pages/{id}/master-json

---

## 6. Anti-patterns — ce qui est interdit

```python
# ❌ INTERDIT — logique hardcodée par corpus
if profile_id == "medieval-illuminated":
    process_iconography()

# ✅ CORRECT — piloté par le profil
if "iconography_detection" in corpus_profile.active_layers:
    process_iconography()

# ❌ INTERDIT — prompt hardcodé dans le code
prompt = f"Tu analyses un manuscrit {profile.label}. Retourne ce JSON..."

# ✅ CORRECT — prompt chargé depuis fichier versionné
prompt_path = corpus_profile.prompt_templates["primary"]
prompt = load_and_render_prompt(prompt_path, context)

# ❌ INTERDIT — bbox en coordonnées de coins opposés
bbox = [x1, y1, x2, y2]

# ✅ CORRECT — bbox en [x, y, width, height]
bbox = [x, y, x2 - x1, y2 - y1]

# ❌ INTERDIT — pydantic v1
class MyModel(BaseModel):
    class Config:
        frozen = True

# ✅ CORRECT — pydantic v2
class MyModel(BaseModel):
    model_config = ConfigDict(frozen=True)

# ❌ INTERDIT — réponse brute non conservée
master_json = parse_ai_response(response)
save(master_json)

# ✅ CORRECT — double stockage obligatoire
save_raw(response, path="gemini_raw.json")
master_json = parse_and_validate(response)
save_canonical(master_json, path="master.json")

# ❌ INTERDIT — clé API dans le code
client = genai.Client(api_key="AIza...")

# ✅ CORRECT — depuis l'environnement
client = genai.Client(api_key=os.environ["GOOGLE_AI_API_KEY"])
```

---

## 7. Conventions de code

### Nommage
- Python : snake_case pour variables et fonctions, PascalCase pour classes
- TypeScript (sprint 4+) : camelCase pour variables, PascalCase pour composants
- Fichiers Python : snake_case.py
- Fichiers de prompts : {famille}_v{n}.txt (ex: primary_v1.txt, commentary_v2.txt)
- Profils JSON : {profile_id}.json (ex: medieval-illuminated.json)
- IDs de pages : {corpus_slug}-{folio_label} (ex: beatus-lat8878-0013r)

### Structure d'un fichier Python
```python
"""
Module docstring courte (1–2 lignes max).
"""
# 1. stdlib
import os
from datetime import datetime
from typing import Any

# 2. third-party
from pydantic import BaseModel, Field

# 3. local
from app.schemas.corpus_profile import CorpusProfile
```

### Gestion d'erreurs
```python
# ✅ Exceptions explicites avec message utile
if not image_path.exists():
    raise FileNotFoundError(f"Image not found: {image_path}")

# ✅ Logging structuré
import logging
logger = logging.getLogger(__name__)
logger.info("Processing page", extra={"page_id": page_id, "profile": profile_id})

# ❌ Jamais
try:
    ...
except:
    pass  # silence total = bug silencieux
```

### Type hints
- Obligatoires sur toutes les signatures de fonctions
- `Any` accepté uniquement pour les extensions de profil
- Préférer `str | None` à `Optional[str]` (Python 3.10+ syntax)

---

## 8. Pipeline — étapes et responsabilités

```
Étape 1 — Ingestion
  Input  : dossier local / ZIP / URLs IIIF / manifest IIIF
  Output : enregistrements Corpus + Manuscript + Page en SQLite
  Status : INGESTED
  Règle  : aucun appel IA, aucune image modifiée

Étape 2 — Préparation image
  Input  : image master (TIFF / JP2 / JPEG / PNG)
  Output : dérivé JPEG 1500px max pour l'IA + thumbnail
  Status : PREPARED
  Règle  : jamais envoyer le master brut à l'IA

Étape 3 — Analyse primaire IA (1 seul appel par page)
  Input  : dérivé JPEG + prompt primary_v1.txt rendu avec le profil
  Output : gemini_raw.json (brut) + master.json partiel (layout + OCR)
  Status : ANALYZED
  Règle  : 1 seule passe visuelle. Pas d'appels concurrents sur la même image.

Étape 4 — Passes dérivées (selon active_layers du profil)
  Input  : master.json de l'étape 3
  Output : master.json enrichi (traduction, commentaire, iconographie)
  Status : LAYERED
  Règle  : les passes dérivées sont textuelles. Pas de nouvelle passe visuelle
           sauf pour l'iconographie (crops des régions uniquement).

Étape 5 — Génération documentaire
  Input  : master.json complet
  Output : alto.xml + mets.xml + manifest.json + annotations IIIF
  Status : EXPORTED
  Règle  : toujours régénérable depuis master.json. Ne jamais éditer les XML
           manuellement — ils sont des sorties dérivées.

Étape 6 — Validation humaine
  Input  : master.json + interface
  Output : master.json corrigé avec version incrémentée
  Status : VALIDATED → PUBLISHED
```

---

## 9. Modèle Google AI — sélection dynamique

Le modèle n'est jamais hardcodé. Flux :
1. Utilisateur fournit sa clé API → `POST /api/v1/settings/api-key`
2. Plateforme appelle Google AI List Models → filtre sur `generateContent` + vision
3. Utilisateur sélectionne un modèle → `PUT /api/v1/corpora/{id}/model`
4. Modèle stocké dans `ModelConfig` par corpus (pas dans CorpusProfile)
5. Chaque appel IA journalise `model_id` + `model_display_name`

Entité `ModelConfig` (par corpus) :
```python
class ModelConfig(BaseModel):
    corpus_id: str
    selected_model_id: str          # ID technique Google AI
    selected_model_display_name: str
    supports_vision: bool
    last_fetched_at: datetime
    available_models: list[dict]    # cache de la liste
```

---

## 10. Statuts métier

### Corpus / Page
```
CREATED → INGESTING → INGESTED → PROCESSING → READY → ERROR
INGESTED → PREPARED → ANALYZED → LAYERED → EXPORTED → VALIDATED → ERROR
```

### Couche (AnnotationLayer)
```
PENDING → RUNNING → DONE → FAILED → NEEDS_REVIEW → VALIDATED
```

### Éditorial (PageMaster.editorial.status)
```
machine_draft → needs_review → reviewed → validated → published
```

---

## 11. Endpoints API — liste complète

```
# Configuration & modèles
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

## 12. État du projet par sprint

```
Sprint 1 — Fondations du modèle de données        [ EN COURS ]
  → Schémas Pydantic + tests pytest + profils JSON + templates prompts

Sprint 2 — Pipeline page unique                    [ À FAIRE ]
  → Ingestion + appel Google AI + master.json

Sprint 3 — Exports documentaires                   [ À FAIRE ]
  → ALTO + METS + Manifest IIIF

Sprint 4 — API FastAPI + interface de lecture       [ À FAIRE ]
  → Endpoints + visionneuse + 4 couches

Sprint 5 — Traitement en lot + HuggingFace         [ À FAIRE ]
  → Pipeline batch + déploiement public

Sprint 6 — Validation humaine + V1 complète        [ À FAIRE ]
  → Éditeur + versionnement + recherche
```

**Règle :** ne jamais implémenter du code appartenant à un sprint ultérieur
au sprint en cours. Si une idée émerge pour un sprint futur, la noter
dans TODO.md section "Backlog" et ne pas la coder.

---

## 13. Ce que tu NE dois PAS faire sans demande explicite

- Modifier le schéma PageMaster (champs, types, noms, structure)
- Modifier la convention bbox
- Ajouter des dépendances non listées dans pyproject.toml
- Refactoriser du code existant si la session n'a pas ce but explicite
- Créer des fichiers hors de l'arborescence définie section 3
- Implémenter du code de sprint futur (voir section 12)
- Simplifier un schéma pour "faire plus propre" — les schémas sont figés
- Changer une règle listée en section 5 pour une raison de commodité
- Utiliser une librairie alternative à celles listées section 2
- Créer une logique spécifique à un corpus particulier
