"""
Tests des endpoints CRUD /api/v1/corpora (Sprint 4 — Session A).

Vérifie :
- GET  /api/v1/corpora → liste vide puis liste peuplée
- POST /api/v1/corpora → 201 + corps de réponse complet
- POST /api/v1/corpora (slug dupliqué) → 409
- GET  /api/v1/corpora/{id} → 200 ou 404
- DELETE /api/v1/corpora/{id} → 204 ou 404
- Champs manquants dans le POST body → 422 automatique Pydantic
"""
# 1. stdlib
import pytest

# 3. local
from tests.conftest_api import async_client, db_session  # noqa: F401

_CORPUS_PAYLOAD = {
    "slug": "beatus-lat8878",
    "title": "Beatus de Saint-Sever",
    "profile_id": "medieval-illuminated",
}


# ---------------------------------------------------------------------------
# GET /api/v1/corpora
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_corpora_empty(async_client):
    response = await async_client.get("/api/v1/corpora")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_corpora_after_create(async_client):
    await async_client.post("/api/v1/corpora", json=_CORPUS_PAYLOAD)
    response = await async_client.get("/api/v1/corpora")
    assert response.status_code == 200
    corpora = response.json()
    assert len(corpora) == 1
    assert corpora[0]["slug"] == "beatus-lat8878"


@pytest.mark.asyncio
async def test_list_corpora_multiple(async_client):
    await async_client.post("/api/v1/corpora", json=_CORPUS_PAYLOAD)
    await async_client.post(
        "/api/v1/corpora",
        json={"slug": "grandes-chroniques", "title": "Grandes Chroniques", "profile_id": "medieval-textual"},
    )
    response = await async_client.get("/api/v1/corpora")
    assert len(response.json()) == 2


# ---------------------------------------------------------------------------
# POST /api/v1/corpora
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_corpus_status_201(async_client):
    response = await async_client.post("/api/v1/corpora", json=_CORPUS_PAYLOAD)
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_create_corpus_response_fields(async_client):
    response = await async_client.post("/api/v1/corpora", json=_CORPUS_PAYLOAD)
    data = response.json()
    assert "id" in data
    assert data["slug"] == "beatus-lat8878"
    assert data["title"] == "Beatus de Saint-Sever"
    assert data["profile_id"] == "medieval-illuminated"
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_create_corpus_id_is_uuid(async_client):
    response = await async_client.post("/api/v1/corpora", json=_CORPUS_PAYLOAD)
    corpus_id = response.json()["id"]
    # UUID v4 — 36 caractères avec tirets
    assert len(corpus_id) == 36
    assert corpus_id.count("-") == 4


@pytest.mark.asyncio
async def test_create_corpus_duplicate_slug_409(async_client):
    await async_client.post("/api/v1/corpora", json=_CORPUS_PAYLOAD)
    response = await async_client.post("/api/v1/corpora", json=_CORPUS_PAYLOAD)
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_create_corpus_missing_slug_422(async_client):
    response = await async_client.post(
        "/api/v1/corpora", json={"title": "X", "profile_id": "medieval-illuminated"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_corpus_missing_title_422(async_client):
    response = await async_client.post(
        "/api/v1/corpora", json={"slug": "x", "profile_id": "medieval-illuminated"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_corpus_missing_profile_id_422(async_client):
    response = await async_client.post(
        "/api/v1/corpora", json={"slug": "x", "title": "X"}
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/corpora/{id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_corpus_ok(async_client):
    create_resp = await async_client.post("/api/v1/corpora", json=_CORPUS_PAYLOAD)
    corpus_id = create_resp.json()["id"]

    response = await async_client.get(f"/api/v1/corpora/{corpus_id}")
    assert response.status_code == 200
    assert response.json()["id"] == corpus_id


@pytest.mark.asyncio
async def test_get_corpus_fields(async_client):
    create_resp = await async_client.post("/api/v1/corpora", json=_CORPUS_PAYLOAD)
    corpus_id = create_resp.json()["id"]
    data = (await async_client.get(f"/api/v1/corpora/{corpus_id}")).json()

    assert data["slug"] == "beatus-lat8878"
    assert data["title"] == "Beatus de Saint-Sever"
    assert data["profile_id"] == "medieval-illuminated"


@pytest.mark.asyncio
async def test_get_corpus_not_found(async_client):
    response = await async_client.get("/api/v1/corpora/nonexistent-id")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_corpus_not_found_detail(async_client):
    response = await async_client.get("/api/v1/corpora/unknown")
    assert "introuvable" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# DELETE /api/v1/corpora/{id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_corpus_204(async_client):
    create_resp = await async_client.post("/api/v1/corpora", json=_CORPUS_PAYLOAD)
    corpus_id = create_resp.json()["id"]

    response = await async_client.delete(f"/api/v1/corpora/{corpus_id}")
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_delete_corpus_disappears_from_list(async_client):
    create_resp = await async_client.post("/api/v1/corpora", json=_CORPUS_PAYLOAD)
    corpus_id = create_resp.json()["id"]

    await async_client.delete(f"/api/v1/corpora/{corpus_id}")
    list_resp = await async_client.get("/api/v1/corpora")
    assert list_resp.json() == []


@pytest.mark.asyncio
async def test_delete_corpus_makes_get_404(async_client):
    create_resp = await async_client.post("/api/v1/corpora", json=_CORPUS_PAYLOAD)
    corpus_id = create_resp.json()["id"]

    await async_client.delete(f"/api/v1/corpora/{corpus_id}")
    get_resp = await async_client.get(f"/api/v1/corpora/{corpus_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_corpus_not_found(async_client):
    response = await async_client.delete("/api/v1/corpora/nonexistent")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_only_target_corpus(async_client):
    """Supprimer un corpus ne supprime pas les autres."""
    r1 = await async_client.post("/api/v1/corpora", json=_CORPUS_PAYLOAD)
    r2 = await async_client.post(
        "/api/v1/corpora",
        json={"slug": "other", "title": "Other", "profile_id": "medieval-textual"},
    )
    await async_client.delete(f"/api/v1/corpora/{r1.json()['id']}")

    list_resp = await async_client.get("/api/v1/corpora")
    remaining = list_resp.json()
    assert len(remaining) == 1
    assert remaining[0]["id"] == r2.json()["id"]
