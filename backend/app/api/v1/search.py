"""
Endpoint de recherche plein texte (R10 — préfixe /api/v1/).

GET /api/v1/search?q={query}

Implémentation MVP : scan des fichiers master.json (pas d'index externe).
Insensible à la casse et aux accents (unicodedata NFD + ASCII).
"""
# 1. stdlib
import json
import logging
import unicodedata
from pathlib import Path

# 2. third-party
from fastapi import APIRouter, Query
from pydantic import BaseModel

# 3. local
from app import config as _config_module

logger = logging.getLogger(__name__)

router = APIRouter(tags=["search"])


# ── Schémas ───────────────────────────────────────────────────────────────────

class SearchResult(BaseModel):
    page_id: str
    folio_label: str
    manuscript_id: str
    excerpt: str
    score: int
    corpus_profile: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    """Minuscules + suppression des accents (NFD → ASCII)."""
    nfd = unicodedata.normalize("NFD", text.lower())
    return nfd.encode("ascii", "ignore").decode("ascii")


def _excerpt(text: str, query_normalized: str, context: int = 120) -> str:
    """Extrait un contexte autour de la première occurrence de la requête."""
    text_n = _normalize(text)
    idx = text_n.find(query_normalized)
    if idx == -1:
        return text[: context * 2]
    start = max(0, idx - context // 2)
    end = min(len(text), idx + len(query_normalized) + context // 2)
    result = text[start:end]
    if start > 0:
        result = "…" + result
    if end < len(text):
        result = result + "…"
    return result


def _score_master(data: dict, query_normalized: str) -> tuple[int, str]:
    """Retourne (nombre d'occurrences, premier extrait) pour un master.json."""
    texts: list[str] = []

    if data.get("ocr") and data["ocr"].get("diplomatic_text"):
        texts.append(data["ocr"]["diplomatic_text"])

    if data.get("translation") and data["translation"].get("fr"):
        texts.append(data["translation"]["fr"])

    # Extensions : champs iconography[].tags (profils qui les exposent)
    extensions = data.get("extensions") or {}
    icono = extensions.get("iconography") or []
    if isinstance(icono, list):
        for item in icono:
            if isinstance(item, dict):
                tags = item.get("tags") or []
                if isinstance(tags, list):
                    texts.extend(str(t) for t in tags)

    count = 0
    first_excerpt = ""
    for text in texts:
        n = _normalize(text)
        hits = n.count(query_normalized)
        count += hits
        if hits > 0 and not first_excerpt:
            first_excerpt = _excerpt(text, query_normalized)

    return count, first_excerpt


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.get("/search", response_model=list[SearchResult])
async def search_pages(
    q: str = Query(..., min_length=2, description="Requête de recherche (min. 2 caractères)"),
) -> list[SearchResult]:
    """Recherche plein texte dans les master.json de tous les corpus.

    Cherche dans : ocr.diplomatic_text, translation.fr,
    extensions.iconography[].tags (si présent).
    Insensible à la casse et aux accents.
    """
    query_normalized = _normalize(q.strip())
    data_dir = _config_module.settings.data_dir

    results: list[SearchResult] = []

    for master_path in data_dir.glob("corpora/*/pages/*/master.json"):
        try:
            raw: dict = json.loads(master_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        score, excerpt = _score_master(raw, query_normalized)
        if score == 0:
            continue

        results.append(
            SearchResult(
                page_id=raw.get("page_id", ""),
                folio_label=raw.get("folio_label", ""),
                manuscript_id=raw.get("manuscript_id", ""),
                excerpt=excerpt,
                score=score,
                corpus_profile=raw.get("corpus_profile", ""),
            )
        )

    results.sort(key=lambda r: r.score, reverse=True)
    logger.info("Recherche exécutée", extra={"q": q, "results": len(results)})
    return results
