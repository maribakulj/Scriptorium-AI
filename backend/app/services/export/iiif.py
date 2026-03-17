"""
Générateur de Manifest IIIF Presentation API 3.0 par manuscrit (R02).

Source canonique : list[PageMaster] uniquement.
1 Canvas par page — règle absolue.
Les couches éditoriales (transcription, commentaire, iconographie) sont
hors périmètre MVP : elles seront ajoutées en Sprint 4 via des annotations.

Structure du manifest :
  @context  → http://iiif.io/api/presentation/3/context.json
  id        → {base_url}/api/v1/manuscripts/{manuscript_id}/iiif-manifest
  items     → Canvas par page (triés par sequence)
               └─ AnnotationPage
                   └─ Annotation painting (image originale)
"""
# 1. stdlib
import json
import logging
from pathlib import Path

# 3. local
from app.schemas.page_master import PageMaster

logger = logging.getLogger(__name__)

_IIIF_CONTEXT = "http://iiif.io/api/presentation/3/context.json"


def _meta_entry(label_en: str, value: str) -> dict:
    """Formate une entrée de métadonnée IIIF (label/value pair)."""
    return {
        "label": {"en": [label_en]},
        "value": {"none": [value]},
    }


def generate_manifest(
    masters: list[PageMaster],
    manuscript_meta: dict,
    base_url: str,
) -> dict:
    """Génère un Manifest IIIF Presentation API 3.0 pour un manuscrit.

    Le manifest est sérialisable en JSON sans perte (pas d'objets non-sérialisables).
    Le base_url est paramétrable pour permettre le déploiement sur différents domaines.

    Args:
        masters: liste des PageMaster du manuscrit (au moins 1, triés par sequence).
        manuscript_meta: dict avec les clés :
            Obligatoires : manuscript_id (str), label (str), corpus_slug (str)
            Optionnelles : language (str), repository (str), shelfmark (str),
                           date_label (str), institution (str)
        base_url: URL de base de la plateforme, sans slash final
                  (ex. "https://scriptorium-ai.hf.space").

    Returns:
        dict sérialisable en JSON contenant le Manifest IIIF 3.0.

    Raises:
        ValueError: si masters est vide ou si un champ obligatoire est absent.
    """
    # ── Validation ───────────────────────────────────────────────────────────
    if not masters:
        raise ValueError(
            "generate_manifest : la liste de PageMaster est vide — "
            "un manuscrit doit avoir au moins une page."
        )
    for key in ("manuscript_id", "label", "corpus_slug"):
        if not manuscript_meta.get(key):
            raise ValueError(
                f"generate_manifest : champ obligatoire manquant dans "
                f"manuscript_meta : «{key}»"
            )

    manuscript_id = manuscript_meta["manuscript_id"]
    label         = manuscript_meta["label"]
    language      = manuscript_meta.get("language") or "none"

    # Pages dans l'ordre de séquence (règle absolue — structMap PHYSICAL)
    pages = sorted(masters, key=lambda m: m.sequence)

    # ── IDs de base ─────────────────────────────────────────────────────────
    base_url = base_url.rstrip("/")
    manifest_id = f"{base_url}/api/v1/manuscripts/{manuscript_id}/iiif-manifest"

    # ── Métadonnées descriptives ─────────────────────────────────────────────
    metadata: list[dict] = []
    for field, meta_label in (
        ("repository", "Repository"),
        ("shelfmark",  "Shelfmark"),
        ("date_label", "Date"),
        ("institution","Institution"),
        ("language",   "Language"),
    ):
        value = manuscript_meta.get(field)
        if value:
            metadata.append(_meta_entry(meta_label, value))

    # ── Canvases (1 par page) ────────────────────────────────────────────────
    items: list[dict] = []
    for page in pages:
        canvas_id = (
            f"{base_url}/api/v1/manuscripts/{manuscript_id}/canvas/{page.page_id}"
        )
        width  = int(page.image.get("width",  0))
        height = int(page.image.get("height", 0))

        annotation_page_id = f"{canvas_id}/annotation-page/1"
        annotation_id      = f"{canvas_id}/annotation/painting"
        image_url          = page.image.get("original_url", "")

        canvas: dict = {
            "id":     canvas_id,
            "type":   "Canvas",
            "label":  {"none": [f"Folio {page.folio_label}"]},
            "width":  width,
            "height": height,
            "items": [
                {
                    "id":   annotation_page_id,
                    "type": "AnnotationPage",
                    "items": [
                        {
                            "id":         annotation_id,
                            "type":       "Annotation",
                            "motivation": "painting",
                            "body": {
                                "id":     image_url,
                                "type":   "Image",
                                "format": "image/jpeg",
                                "width":  width,
                                "height": height,
                            },
                            "target": canvas_id,
                        }
                    ],
                }
            ],
        }
        items.append(canvas)

    manifest: dict = {
        "@context": _IIIF_CONTEXT,
        "id":       manifest_id,
        "type":     "Manifest",
        "label":    {language: [label]},
        "metadata": metadata,
        "items":    items,
    }

    logger.info(
        "Manifest IIIF généré",
        extra={"manuscript_id": manuscript_id, "canvases": len(items)},
    )
    return manifest


def write_manifest(
    manifest: dict,
    corpus_slug: str,
    base_data_dir: Path = Path("data"),
) -> None:
    """Écrit le Manifest IIIF dans data/corpora/{corpus_slug}/iiif/manifest.json.

    Crée les dossiers parents si nécessaire.

    Args:
        manifest: dict retourné par generate_manifest().
        corpus_slug: identifiant du corpus (détermine le répertoire de sortie).
        base_data_dir: racine du dossier data.
    """
    output_path = base_data_dir / "corpora" / corpus_slug / "iiif" / "manifest.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("manifest.json écrit", extra={"path": str(output_path)})
