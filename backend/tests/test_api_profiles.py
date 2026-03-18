"""
Tests HTTP de l'endpoint GET /api/v1/profiles (Sprint 1 — régression Docker).

Pourquoi ces tests existent :
  GET /api/v1/profiles retournait [] en production (HuggingFace) alors qu'il
  fonctionnait en local. Cause : chemin relatif vers profiles/ non résolu dans
  le container Docker. Ces tests vérifient l'endpoint HTTP complet (pas seulement
  le schéma Pydantic) pour détecter toute régression de chemin en CI.

Stratégie :
  - Utilise le dossier profiles/ réel du dépôt via settings.profiles_dir
    (déjà résolu correctement en local par config.py via Path(__file__).resolve())
  - Teste le cas de régression : retourne [] si profiles_dir est manquant
"""
# 1. stdlib
from pathlib import Path

# 2. third-party
import pytest

# 3. local
import app.config as config_mod
from tests.conftest_api import async_client, db_session  # noqa: F401


# ── Tests "happy path" — utilise le vrai dossier profiles/ ────────────────────

@pytest.mark.asyncio
async def test_list_profiles_returns_nonempty_list(async_client):
    """L'endpoint retourne une liste non vide — régression Docker principale."""
    resp = await async_client.get("/api/v1/profiles")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0, (
        f"profiles_dir={config_mod.settings.profiles_dir} "
        f"(exists={config_mod.settings.profiles_dir.is_dir()}) — "
        "l'endpoint retourne [] alors qu'il devrait retourner les 4 profils"
    )


@pytest.mark.asyncio
async def test_list_profiles_returns_all_four_profiles(async_client):
    """Les 4 profils du dépôt sont tous retournés."""
    resp = await async_client.get("/api/v1/profiles")
    assert resp.status_code == 200
    ids = {p["profile_id"] for p in resp.json()}
    expected = {
        "medieval-illuminated",
        "medieval-textual",
        "early-modern-print",
        "modern-handwritten",
    }
    assert ids == expected


@pytest.mark.asyncio
async def test_list_profiles_each_has_required_fields(async_client):
    """Chaque profil expose les champs obligatoires de CorpusProfile."""
    resp = await async_client.get("/api/v1/profiles")
    assert resp.status_code == 200
    for profile in resp.json():
        assert "profile_id" in profile
        assert "label" in profile
        assert "active_layers" in profile
        assert "prompt_templates" in profile
        assert "script_type" in profile
        assert "language_hints" in profile


@pytest.mark.asyncio
async def test_get_profile_by_id(async_client):
    """GET /api/v1/profiles/{id} retourne le profil correspondant."""
    resp = await async_client.get("/api/v1/profiles/medieval-illuminated")
    assert resp.status_code == 200
    data = resp.json()
    assert data["profile_id"] == "medieval-illuminated"
    assert data["script_type"] == "caroline"


@pytest.mark.asyncio
async def test_get_profile_by_id_not_found(async_client):
    """GET /api/v1/profiles/{id} retourne 404 pour un identifiant inconnu."""
    resp = await async_client.get("/api/v1/profiles/nonexistent-xyz")
    assert resp.status_code == 404


# ── Test de régression Docker — simule un profiles_dir manquant ───────────────

@pytest.mark.asyncio
async def test_list_profiles_empty_when_dir_missing(async_client):
    """Retourne [] si profiles_dir n'existe pas (régression Docker).

    Ce test reproduit exactement la condition du bug de production :
    settings.profiles_dir pointe vers un répertoire qui n'existe pas dans
    le container (mauvais chemin résolu). L'endpoint doit retourner [] sans
    erreur 500, mais le test vérifie aussi que le cas ne se produit pas en
    conditions normales (voir test_list_profiles_returns_nonempty_list).
    """
    original = config_mod.settings.profiles_dir
    config_mod.settings.profiles_dir = Path("/nonexistent/path/profiles")
    try:
        resp = await async_client.get("/api/v1/profiles")
    finally:
        config_mod.settings.profiles_dir = original

    assert resp.status_code == 200
    assert resp.json() == []
