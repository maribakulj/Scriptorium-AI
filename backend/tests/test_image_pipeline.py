"""
Tests du pipeline image : fetch IIIF + normalisation (dérivé + thumbnail).
Tests unitaires : httpx mocké, images créées en mémoire (Pillow).
Tests d'intégration : requêtes réseau réelles, activés via RUN_INTEGRATION_TESTS=1.
"""
# 1. stdlib
import io
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

# 2. third-party
import httpx
import pytest
from PIL import Image
from pydantic import ValidationError

# 3. local
from app.schemas.image import ImageDerivativeInfo
from app.services.image.normalizer import (
    _MAX_DERIVATIVE_PX,
    _MAX_THUMBNAIL_PX,
    _resize_to_max,
    create_derivatives,
    fetch_and_normalize,
)
from app.services.ingest.iiif_fetcher import fetch_iiif_image

# ---------------------------------------------------------------------------
# Marqueur d'intégration — activé seulement si RUN_INTEGRATION_TESTS=1
# ---------------------------------------------------------------------------

integration = pytest.mark.skipif(
    not os.environ.get("RUN_INTEGRATION_TESTS"),
    reason="Tests réseau réels : définir RUN_INTEGRATION_TESTS=1 pour les activer",
)

# URLs IIIF des 3 manuscrits de test (BnF Gallica)
_URL_BEATUS_HI = (
    "https://gallica.bnf.fr/iiif/ark:/12148/btv1b8432836p/f13/full/max/0/default.jpg"
)
_URL_BEATUS_LO = (
    "https://gallica.bnf.fr/iiif/ark:/12148/btv1b8432836p/f13/full/600,/0/default.jpg"
)
_URL_GRANDES_CHRONIQUES = (
    "https://gallica.bnf.fr/iiif/ark:/12148/btv1b8427295k/f3/full/max/0/default.jpg"
)


# ---------------------------------------------------------------------------
# Helpers de test
# ---------------------------------------------------------------------------

def _make_jpeg_bytes(width: int, height: int, color: tuple[int, int, int] = (200, 150, 100)) -> bytes:
    """Crée un JPEG minimal en mémoire pour les tests unitaires."""
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def _make_png_rgba_bytes(width: int, height: int) -> bytes:
    """Crée un PNG RGBA en mémoire (pour tester la conversion RGB)."""
    img = Image.new("RGBA", (width, height), color=(100, 150, 200, 128))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Tests — ImageDerivativeInfo (schéma)
# ---------------------------------------------------------------------------

def test_schema_valid():
    info = ImageDerivativeInfo(
        original_url="https://example.com/image.jpg",
        original_width=3000,
        original_height=4000,
        derivative_path="/data/corpora/test/derivatives/0001r.jpg",
        derivative_width=1125,
        derivative_height=1500,
        thumbnail_path="/data/corpora/test/derivatives/0001r_thumb.jpg",
        thumbnail_width=192,
        thumbnail_height=256,
    )
    assert info.original_width == 3000
    assert info.derivative_width == 1125


def test_schema_missing_required_field():
    with pytest.raises(ValidationError):
        ImageDerivativeInfo.model_validate({"original_url": "https://x.com/img.jpg"})


def test_schema_all_fields_present():
    fields = ImageDerivativeInfo.model_fields.keys()
    expected = {
        "original_url", "original_width", "original_height",
        "derivative_path", "derivative_width", "derivative_height",
        "thumbnail_path", "thumbnail_width", "thumbnail_height",
    }
    assert set(fields) == expected


# ---------------------------------------------------------------------------
# Tests — _resize_to_max
# ---------------------------------------------------------------------------

def test_resize_small_image_not_upscaled():
    """Une image déjà petite ne doit pas être agrandie."""
    img = Image.new("RGB", (800, 600))
    result = _resize_to_max(img, _MAX_DERIVATIVE_PX)
    assert result.size == (800, 600)


def test_resize_exact_max_not_changed():
    """Une image dont le grand côté est exactement max_size n'est pas redimensionnée."""
    img = Image.new("RGB", (1500, 1000))
    result = _resize_to_max(img, _MAX_DERIVATIVE_PX)
    assert result.size == (1500, 1000)


def test_resize_landscape_large():
    """Paysage 3000x2000 → 1500x1000."""
    img = Image.new("RGB", (3000, 2000))
    result = _resize_to_max(img, 1500)
    assert result.size == (1500, 1000)


def test_resize_portrait_large():
    """Portrait 2000x3000 → 1000x1500."""
    img = Image.new("RGB", (2000, 3000))
    result = _resize_to_max(img, 1500)
    assert result.size == (1000, 1500)


def test_resize_square_large():
    """Carré 2000x2000 → 1500x1500."""
    img = Image.new("RGB", (2000, 2000))
    result = _resize_to_max(img, 1500)
    assert result.size == (1500, 1500)


def test_resize_preserves_aspect_ratio():
    """Le ratio d'aspect est préservé après resize."""
    img = Image.new("RGB", (4000, 3000))
    result = _resize_to_max(img, 1500)
    w, h = result.size
    assert w == 1500
    assert abs(w / h - 4 / 3) < 0.01


def test_resize_returns_copy_when_no_resize_needed():
    """Retourne une copie (pas la même instance) même sans resize."""
    img = Image.new("RGB", (100, 100))
    result = _resize_to_max(img, 1500)
    assert result is not img


def test_resize_thumbnail_size():
    """Vérification pour la taille thumbnail (256px)."""
    img = Image.new("RGB", (1200, 800))
    result = _resize_to_max(img, _MAX_THUMBNAIL_PX)
    assert result.size[0] == 256
    assert result.size[1] == 171  # round(800 * 256 / 1200) = round(170.67) = 171


# ---------------------------------------------------------------------------
# Tests — create_derivatives
# ---------------------------------------------------------------------------

def test_create_derivatives_large_landscape(tmp_path):
    """Image 3000x2000 → dérivé 1500x1000, thumbnail 256x171."""
    source = _make_jpeg_bytes(3000, 2000)
    info = create_derivatives(source, "https://x.com/img.jpg", "test-corpus", "0001r", tmp_path)

    assert info.original_width == 3000
    assert info.original_height == 2000
    assert info.derivative_width == 1500
    assert info.derivative_height == 1000
    assert info.thumbnail_width == 256
    assert info.thumbnail_height == 171
    assert info.original_url == "https://x.com/img.jpg"


def test_create_derivatives_small_image_not_upscaled(tmp_path):
    """Image 600x900 (< 1500px) : dérivé conserve les dimensions originales."""
    source = _make_jpeg_bytes(600, 900)
    info = create_derivatives(source, "https://x.com/img.jpg", "test-corpus", "0001r", tmp_path)

    assert info.derivative_width == 600
    assert info.derivative_height == 900
    assert info.original_width == 600
    assert info.original_height == 900


def test_create_derivatives_files_exist(tmp_path):
    """Les deux fichiers JPEG sont bien créés sur disque."""
    source = _make_jpeg_bytes(2000, 3000)
    info = create_derivatives(source, "https://x.com/img.jpg", "corpus-a", "f001r", tmp_path)

    assert Path(info.derivative_path).exists()
    assert Path(info.thumbnail_path).exists()


def test_create_derivatives_path_structure(tmp_path):
    """Les chemins respectent la convention CLAUDE.md §3."""
    source = _make_jpeg_bytes(1000, 1000)
    info = create_derivatives(source, "https://x.com/img.jpg", "beatus-lat8878", "0013r", tmp_path)

    expected_deriv = tmp_path / "corpora" / "beatus-lat8878" / "derivatives" / "0013r.jpg"
    expected_thumb = tmp_path / "corpora" / "beatus-lat8878" / "derivatives" / "0013r_thumb.jpg"
    assert info.derivative_path == str(expected_deriv)
    assert info.thumbnail_path == str(expected_thumb)


def test_create_derivatives_output_is_jpeg(tmp_path):
    """Les fichiers produits sont bien des JPEG valides."""
    source = _make_jpeg_bytes(1000, 800)
    info = create_derivatives(source, "https://x.com/img.jpg", "corpus-b", "f002r", tmp_path)

    with Image.open(info.derivative_path) as img:
        assert img.format == "JPEG"
    with Image.open(info.thumbnail_path) as img:
        assert img.format == "JPEG"


def test_create_derivatives_rgba_converted_to_rgb(tmp_path):
    """Un PNG RGBA est converti en RGB sans erreur."""
    source = _make_png_rgba_bytes(800, 1000)
    info = create_derivatives(source, "https://x.com/img.png", "corpus-c", "f003r", tmp_path)

    with Image.open(info.derivative_path) as img:
        assert img.mode == "RGB"
    assert info.original_width == 800
    assert info.original_height == 1000


def test_create_derivatives_thumbnail_dimensions(tmp_path):
    """Le thumbnail a bien son grand côté <= 256px."""
    source = _make_jpeg_bytes(3000, 4000)
    info = create_derivatives(source, "https://x.com/img.jpg", "corpus-d", "f004r", tmp_path)

    assert max(info.thumbnail_width, info.thumbnail_height) == _MAX_THUMBNAIL_PX


def test_create_derivatives_creates_parent_dirs(tmp_path):
    """Les dossiers intermédiaires sont créés automatiquement."""
    source = _make_jpeg_bytes(500, 500)
    new_slug = "nouveau-corpus-jamais-vu"
    info = create_derivatives(source, "https://x.com/img.jpg", new_slug, "f001r", tmp_path)

    assert Path(info.derivative_path).parent.exists()


# ---------------------------------------------------------------------------
# Tests — fetch_iiif_image
# ---------------------------------------------------------------------------

def test_fetch_iiif_image_success():
    """Retourne les bytes de l'image si la requête réussit."""
    fake_bytes = _make_jpeg_bytes(100, 100)

    with patch("app.services.ingest.iiif_fetcher.httpx.get") as mock_get:
        mock_response = MagicMock()
        mock_response.content = fake_bytes
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = fetch_iiif_image("https://example.com/image.jpg")

    assert result == fake_bytes
    mock_get.assert_called_once_with(
        "https://example.com/image.jpg",
        follow_redirects=True,
        timeout=60.0,
    )


def test_fetch_iiif_image_http_error():
    """Propage HTTPStatusError si le serveur répond 404."""
    with patch("app.services.ingest.iiif_fetcher.httpx.get") as mock_get:
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found",
            request=MagicMock(),
            response=MagicMock(status_code=404),
        )
        mock_get.return_value = mock_response

        with pytest.raises(httpx.HTTPStatusError):
            fetch_iiif_image("https://example.com/missing.jpg")


def test_fetch_iiif_image_timeout():
    """Propage TimeoutException si la requête dépasse le délai."""
    with patch("app.services.ingest.iiif_fetcher.httpx.get") as mock_get:
        mock_get.side_effect = httpx.TimeoutException("timed out")

        with pytest.raises(httpx.TimeoutException):
            fetch_iiif_image("https://example.com/slow.jpg", timeout=1.0)


def test_fetch_iiif_image_custom_timeout():
    """Le timeout personnalisé est bien transmis à httpx.get."""
    fake_bytes = _make_jpeg_bytes(50, 50)

    with patch("app.services.ingest.iiif_fetcher.httpx.get") as mock_get:
        mock_response = MagicMock()
        mock_response.content = fake_bytes
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        fetch_iiif_image("https://example.com/img.jpg", timeout=120.0)

    _, kwargs = mock_get.call_args
    assert kwargs["timeout"] == 120.0


# ---------------------------------------------------------------------------
# Tests — fetch_and_normalize (end-to-end mocké)
# ---------------------------------------------------------------------------

def test_fetch_and_normalize_chains_correctly(tmp_path):
    """fetch_and_normalize appelle fetch_iiif_image puis create_derivatives."""
    fake_bytes = _make_jpeg_bytes(2000, 1500)

    with patch("app.services.image.normalizer.fetch_iiif_image", return_value=fake_bytes) as mock_fetch:
        info = fetch_and_normalize(
            "https://example.com/ms/f001.jpg",
            "corpus-test",
            "0001r",
            tmp_path,
        )

    mock_fetch.assert_called_once_with("https://example.com/ms/f001.jpg")
    assert info.original_url == "https://example.com/ms/f001.jpg"
    assert info.original_width == 2000
    assert info.original_height == 1500
    assert info.derivative_width == 1500
    assert info.derivative_height == 1125
    assert Path(info.derivative_path).exists()
    assert Path(info.thumbnail_path).exists()


def test_fetch_and_normalize_propagates_http_error(tmp_path):
    """Les erreurs HTTP de fetch_iiif_image sont propagées sans être masquées."""
    with patch(
        "app.services.image.normalizer.fetch_iiif_image",
        side_effect=httpx.HTTPStatusError("403", request=MagicMock(), response=MagicMock()),
    ):
        with pytest.raises(httpx.HTTPStatusError):
            fetch_and_normalize("https://example.com/img.jpg", "corpus", "f001", tmp_path)


# ---------------------------------------------------------------------------
# Tests d'intégration — URLs IIIF BnF réelles (skippés par défaut)
# ---------------------------------------------------------------------------

@integration
def test_integration_beatus_high_res(tmp_path):
    """Beatus de Saint-Sever, BnF Latin 8878, f.13 — haute résolution."""
    info = fetch_and_normalize(_URL_BEATUS_HI, "beatus-lat8878", "0013r", tmp_path)

    assert info.original_width > 1500 or info.original_height > 1500
    assert info.derivative_width <= _MAX_DERIVATIVE_PX
    assert info.derivative_height <= _MAX_DERIVATIVE_PX
    assert max(info.derivative_width, info.derivative_height) == _MAX_DERIVATIVE_PX
    assert Path(info.derivative_path).exists()
    assert Path(info.thumbnail_path).exists()


@integration
def test_integration_beatus_low_res(tmp_path):
    """Beatus de Saint-Sever, BnF Latin 8878, f.13 — 600px (image déjà petite)."""
    info = fetch_and_normalize(_URL_BEATUS_LO, "beatus-lat8878", "0013r-600", tmp_path)

    # Image à 600px de large : pas d'upscaling, dérivé == original
    assert info.derivative_width <= _MAX_DERIVATIVE_PX
    assert info.derivative_height <= _MAX_DERIVATIVE_PX
    assert max(info.derivative_width, info.derivative_height) <= 600
    assert Path(info.derivative_path).exists()


@integration
def test_integration_grandes_chroniques(tmp_path):
    """Grandes Chroniques de France, BnF Français 2813."""
    info = fetch_and_normalize(_URL_GRANDES_CHRONIQUES, "grandes-chroniques", "f003", tmp_path)

    assert info.derivative_width <= _MAX_DERIVATIVE_PX
    assert info.derivative_height <= _MAX_DERIVATIVE_PX
    assert Path(info.derivative_path).exists()
    assert Path(info.thumbnail_path).exists()
