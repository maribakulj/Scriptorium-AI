"""
Téléchargement d'images depuis des URLs IIIF via httpx.
"""
# 1. stdlib
import logging

# 2. third-party
import httpx

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 60.0  # secondes — les images IIIF haute résolution peuvent être lourdes

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; ScriptoriumAI/1.0; "
        "+https://huggingface.co/spaces/Ma-Ri-Ba-Ku/scriptorium-ai)"
    ),
    "Accept": "image/jpeg,image/png,image/*,*/*",
    "Referer": "https://gallica.bnf.fr/",
}

# Content-Type prefixes qui indiquent une réponse non-image (HTML, JSON, XML manifeste…)
_NON_IMAGE_TYPES = ("text/html", "text/plain", "application/json", "application/ld+json")

# Magic bytes des formats image courants (JPEG, PNG, GIF, TIFF, JPEG2000, WebP)
_IMAGE_MAGIC: dict[bytes, str] = {
    b"\xff\xd8\xff": "JPEG",
    b"\x89PNG": "PNG",
    b"GIF8": "GIF",
    b"II*\x00": "TIFF (little-endian)",
    b"MM\x00*": "TIFF (big-endian)",
    b"\x00\x00\x00\x0cjP  ": "JPEG2000",
    b"RIFF": "WEBP",
}


def _sniff_format(data: bytes) -> str | None:
    """Détecte le format d'image depuis les magic bytes. Retourne None si inconnu."""
    for magic, fmt in _IMAGE_MAGIC.items():
        if data[:len(magic)] == magic:
            return fmt
    return None


def fetch_iiif_image(url: str, timeout: float = _DEFAULT_TIMEOUT) -> bytes:
    """Télécharge une image depuis une URL IIIF complète.

    Valide que la réponse est bien un contenu image (Content-Type + magic bytes).
    Une page HTML retournée avec 200 OK (rate-limit, redirection viewer, CAPTCHA)
    est détectée et lève ValueError avec un message explicite.

    Args:
        url: URL complète de l'image (ex. https://.../full/max/0/default.jpg).
             Pour Gallica/BnF, utiliser les URLs IIIF Image API
             (…/full/max/0/default.jpg) plutôt que les URLs du viewer
             (gallica.bnf.fr/ark:/…) qui retournent du HTML.
        timeout: délai maximal en secondes (défaut : 60 s).

    Returns:
        Contenu brut de l'image en bytes.

    Raises:
        ValueError: si la réponse n'est pas une image valide (HTML, JSON, etc.).
        httpx.HTTPStatusError: si le serveur retourne un code 4xx ou 5xx.
        httpx.TimeoutException: si la requête dépasse le délai.
        httpx.RequestError: pour toute autre erreur réseau.
    """
    logger.info("Fetching IIIF image", extra={"url": url})
    response = httpx.get(url, headers=_HEADERS, follow_redirects=True, timeout=timeout)
    response.raise_for_status()

    content = response.content
    content_type = response.headers.get("content-type", "").lower().split(";")[0].strip()

    # ── Vérification 1 : Content-Type explicitement non-image ────────────────
    if any(content_type.startswith(t) for t in _NON_IMAGE_TYPES):
        preview = content[:300].decode("utf-8", errors="replace")
        raise ValueError(
            f"L'URL {url!r} a retourné du contenu non-image "
            f"(Content-Type: {content_type!r}). "
            f"Vérifiez que l'URL pointe vers une image directe et non vers le "
            f"viewer Gallica ou un manifest IIIF. "
            f"Début de la réponse : {preview!r}"
        )

    # ── Vérification 2 : magic bytes ─────────────────────────────────────────
    detected_fmt = _sniff_format(content)
    if detected_fmt is None and not content_type.startswith("image/"):
        # Content-Type ambigu ET magic bytes non reconnus — suspect
        preview = content[:100].decode("utf-8", errors="replace")
        logger.warning(
            "Contenu de type inconnu reçu pour %s (Content-Type: %s, magic: %s). "
            "Tentative d'ouverture Pillow quand même.",
            url, content_type, content[:8].hex(),
        )
    else:
        fmt_label = detected_fmt or content_type
        logger.info(
            "IIIF image fetched",
            extra={"url": url, "size_bytes": len(content), "format": fmt_label},
        )

    return content
