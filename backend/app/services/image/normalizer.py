"""
Normalisation d'images : dérivé JPEG 1500px max + thumbnail pour le pipeline IA.
"""
# 1. stdlib
import io
import logging
from pathlib import Path

# 2. third-party
from PIL import Image

# 3. local
from app.schemas.image import ImageDerivativeInfo
from app.services.ingest.iiif_fetcher import fetch_iiif_image

logger = logging.getLogger(__name__)

# Constantes de normalisation
_MAX_DERIVATIVE_PX = 1500   # grand côté max du dérivé envoyé à l'IA
_MAX_THUMBNAIL_PX = 256     # grand côté max du thumbnail
_DERIVATIVE_QUALITY = 90    # qualité JPEG dérivé
_THUMBNAIL_QUALITY = 75     # qualité JPEG thumbnail


def _resize_to_max(image: Image.Image, max_size: int) -> Image.Image:
    """Redimensionne l'image pour que son grand côté vaille max_size.

    Si l'image est déjà plus petite ou égale, retourne une copie sans upscaling.
    Le ratio d'aspect est préservé. Utilise LANCZOS pour la qualité.
    """
    w, h = image.size
    if max(w, h) <= max_size:
        return image.copy()
    if w >= h:
        new_w = max_size
        new_h = max(1, round(h * max_size / w))
    else:
        new_h = max_size
        new_w = max(1, round(w * max_size / h))
    return image.resize((new_w, new_h), Image.Resampling.LANCZOS)


def create_derivatives(
    source_bytes: bytes,
    original_url: str,
    corpus_slug: str,
    folio_label: str,
    base_data_dir: Path = Path("data"),
) -> ImageDerivativeInfo:
    """Produit un dérivé JPEG (1500px max) et un thumbnail depuis des bytes image.

    Structure de sortie (CLAUDE.md §3) :
      {base_data_dir}/corpora/{corpus_slug}/derivatives/{folio_label}.jpg
      {base_data_dir}/corpora/{corpus_slug}/derivatives/{folio_label}_thumb.jpg

    Args:
        source_bytes: contenu brut de l'image source (JPEG, PNG, TIFF, etc.).
        original_url: URL d'origine (conservée dans le schéma de sortie).
        corpus_slug: identifiant du corpus (ex. "beatus-lat8878").
        folio_label: identifiant du folio (ex. "0013r").
        base_data_dir: racine du dossier data (défaut : Path("data")).

    Returns:
        ImageDerivativeInfo avec dimensions et chemins des fichiers produits.

    Raises:
        PIL.UnidentifiedImageError: si les bytes ne sont pas une image valide.
        OSError: si l'écriture sur disque échoue.
    """
    image = Image.open(io.BytesIO(source_bytes))

    # Convertir en RGB pour garantir un JPEG valide (PNG RGBA, palette, etc.)
    if image.mode != "RGB":
        image = image.convert("RGB")

    original_width, original_height = image.size
    logger.info(
        "Image ouverte",
        extra={
            "corpus": corpus_slug,
            "folio": folio_label,
            "original_size": f"{original_width}x{original_height}",
        },
    )

    # Dossier de sortie
    derivatives_dir = base_data_dir / "corpora" / corpus_slug / "derivatives"
    derivatives_dir.mkdir(parents=True, exist_ok=True)

    # Dérivé IA : grand côté <= 1500px
    deriv_image = _resize_to_max(image, _MAX_DERIVATIVE_PX)
    derivative_width, derivative_height = deriv_image.size
    derivative_path = derivatives_dir / f"{folio_label}.jpg"
    deriv_image.save(derivative_path, format="JPEG", quality=_DERIVATIVE_QUALITY)

    # Thumbnail : grand côté <= 256px
    thumb_image = _resize_to_max(image, _MAX_THUMBNAIL_PX)
    thumbnail_width, thumbnail_height = thumb_image.size
    thumbnail_path = derivatives_dir / f"{folio_label}_thumb.jpg"
    thumb_image.save(thumbnail_path, format="JPEG", quality=_THUMBNAIL_QUALITY)

    logger.info(
        "Dérivés produits",
        extra={
            "corpus": corpus_slug,
            "folio": folio_label,
            "derivative": f"{derivative_width}x{derivative_height}",
            "thumbnail": f"{thumbnail_width}x{thumbnail_height}",
        },
    )

    return ImageDerivativeInfo(
        original_url=original_url,
        original_width=original_width,
        original_height=original_height,
        derivative_path=str(derivative_path),
        derivative_width=derivative_width,
        derivative_height=derivative_height,
        thumbnail_path=str(thumbnail_path),
        thumbnail_width=thumbnail_width,
        thumbnail_height=thumbnail_height,
    )


def fetch_and_normalize(
    url: str,
    corpus_slug: str,
    folio_label: str,
    base_data_dir: Path = Path("data"),
) -> ImageDerivativeInfo:
    """Point d'entrée principal : télécharge depuis une URL IIIF et produit les dérivés.

    Chaîne fetch_iiif_image() → create_derivatives().

    Args:
        url: URL complète de l'image IIIF.
        corpus_slug: identifiant du corpus.
        folio_label: identifiant du folio.
        base_data_dir: racine du dossier data.

    Returns:
        ImageDerivativeInfo rempli.
    """
    source_bytes = fetch_iiif_image(url)
    return create_derivatives(source_bytes, url, corpus_slug, folio_label, base_data_dir)
