"""
Tests des endpoints /api/v1/jobs et /api/v1/corpora/{id}/run (Sprint 4 — Session B).

Vérifie :
- POST /api/v1/corpora/{id}/run → 202 + jobs_created + job_ids
- POST /api/v1/pages/{id}/run   → 202 + job unique
- GET  /api/v1/jobs/{job_id}    → 200 ou 404
- POST /api/v1/jobs/{job_id}/retry → 200 (FAILED) ou 409 (autre statut)
- Isolation : corpus/page inexistants → 404
"""
# 1. stdlib
import uuid
from datetime import datetime, timezone

# 2. third-party
import pytest

# 3. local
from app.models.corpus import CorpusModel, ManuscriptModel, PageModel
from app.models.job import JobModel
from tests.conftest_api import async_client, db_session  # noqa: F401

_NOW = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Helpers — création de données de test
# ---------------------------------------------------------------------------

async def _make_corpus(db, slug="test-c"):
    corpus = CorpusModel(
        id=str(uuid.uuid4()), slug=slug, title="Test", profile_id="medieval-illuminated",
        created_at=_NOW, updated_at=_NOW,
    )
    db.add(corpus)
    await db.commit()
    await db.refresh(corpus)
    return corpus


async def _make_manuscript(db, corpus_id):
    ms = ManuscriptModel(
        id=str(uuid.uuid4()), corpus_id=corpus_id, title="MS", total_pages=0,
    )
    db.add(ms)
    await db.commit()
    await db.refresh(ms)
    return ms


async def _make_page(db, ms_id, folio="f001r", seq=1):
    page = PageModel(
        id=str(uuid.uuid4()), manuscript_id=ms_id, folio_label=folio,
        sequence=seq, processing_status="INGESTED",
    )
    db.add(page)
    await db.commit()
    await db.refresh(page)
    return page


async def _make_failed_job(db, corpus_id, page_id=None):
    """Crée un job en état FAILED pour tester retry."""
    job = JobModel(
        id=str(uuid.uuid4()),
        corpus_id=corpus_id,
        page_id=page_id,
        status="failed",
        error_message="Simulated failure",
        created_at=_NOW,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


# ---------------------------------------------------------------------------
# POST /api/v1/corpora/{id}/run
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_corpus_not_found(async_client):
    response = await async_client.post("/api/v1/corpora/nonexistent/run")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_run_corpus_no_pages(async_client, db_session):
    """Corpus sans pages → 202, jobs_created = 0."""
    corpus = await _make_corpus(db_session)
    response = await async_client.post(f"/api/v1/corpora/{corpus.id}/run")
    assert response.status_code == 202
    data = response.json()
    assert data["jobs_created"] == 0
    assert data["job_ids"] == []
    assert data["corpus_id"] == corpus.id


@pytest.mark.asyncio
async def test_run_corpus_creates_jobs_per_page(async_client, db_session):
    """Corpus avec 3 pages → 3 jobs créés."""
    corpus = await _make_corpus(db_session)
    ms = await _make_manuscript(db_session, corpus.id)
    for i in range(3):
        await _make_page(db_session, ms.id, folio=f"f{i+1:03d}r", seq=i + 1)

    response = await async_client.post(f"/api/v1/corpora/{corpus.id}/run")
    assert response.status_code == 202
    data = response.json()
    assert data["jobs_created"] == 3
    assert len(data["job_ids"]) == 3


@pytest.mark.asyncio
async def test_run_corpus_job_ids_are_unique(async_client, db_session):
    corpus = await _make_corpus(db_session)
    ms = await _make_manuscript(db_session, corpus.id)
    for i in range(2):
        await _make_page(db_session, ms.id, folio=f"f{i+1:03d}r", seq=i + 1)

    data = (await async_client.post(f"/api/v1/corpora/{corpus.id}/run")).json()
    assert len(set(data["job_ids"])) == 2  # all unique


@pytest.mark.asyncio
async def test_run_corpus_jobs_are_pending(async_client, db_session):
    """Les jobs créés par corpus.run ont le statut 'pending'."""
    corpus = await _make_corpus(db_session)
    ms = await _make_manuscript(db_session, corpus.id)
    await _make_page(db_session, ms.id)

    run_data = (await async_client.post(f"/api/v1/corpora/{corpus.id}/run")).json()
    job_id = run_data["job_ids"][0]

    job_data = (await async_client.get(f"/api/v1/jobs/{job_id}")).json()
    assert job_data["status"] == "pending"


# ---------------------------------------------------------------------------
# POST /api/v1/pages/{id}/run
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_page_not_found(async_client):
    response = await async_client.post("/api/v1/pages/nonexistent/run")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_run_page_creates_job(async_client, db_session):
    corpus = await _make_corpus(db_session)
    ms = await _make_manuscript(db_session, corpus.id)
    page = await _make_page(db_session, ms.id)

    response = await async_client.post(f"/api/v1/pages/{page.id}/run")
    assert response.status_code == 202


@pytest.mark.asyncio
async def test_run_page_job_fields(async_client, db_session):
    corpus = await _make_corpus(db_session)
    ms = await _make_manuscript(db_session, corpus.id)
    page = await _make_page(db_session, ms.id)

    data = (await async_client.post(f"/api/v1/pages/{page.id}/run")).json()
    assert data["page_id"] == page.id
    assert data["corpus_id"] == corpus.id
    assert data["status"] == "pending"
    assert data["started_at"] is None
    assert data["finished_at"] is None
    assert data["error_message"] is None


@pytest.mark.asyncio
async def test_run_page_job_id_is_uuid(async_client, db_session):
    corpus = await _make_corpus(db_session)
    ms = await _make_manuscript(db_session, corpus.id)
    page = await _make_page(db_session, ms.id)

    data = (await async_client.post(f"/api/v1/pages/{page.id}/run")).json()
    assert len(data["id"]) == 36


@pytest.mark.asyncio
async def test_run_page_multiple_times_creates_multiple_jobs(async_client, db_session):
    """Lancer run sur la même page deux fois crée deux jobs distincts."""
    corpus = await _make_corpus(db_session)
    ms = await _make_manuscript(db_session, corpus.id)
    page = await _make_page(db_session, ms.id)

    r1 = (await async_client.post(f"/api/v1/pages/{page.id}/run")).json()
    r2 = (await async_client.post(f"/api/v1/pages/{page.id}/run")).json()
    assert r1["id"] != r2["id"]


# ---------------------------------------------------------------------------
# GET /api/v1/jobs/{job_id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_job_not_found(async_client):
    response = await async_client.get("/api/v1/jobs/nonexistent")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_job_ok(async_client, db_session):
    corpus = await _make_corpus(db_session)
    ms = await _make_manuscript(db_session, corpus.id)
    page = await _make_page(db_session, ms.id)

    run_data = (await async_client.post(f"/api/v1/pages/{page.id}/run")).json()
    job_id = run_data["id"]

    response = await async_client.get(f"/api/v1/jobs/{job_id}")
    assert response.status_code == 200
    assert response.json()["id"] == job_id


@pytest.mark.asyncio
async def test_get_job_fields(async_client, db_session):
    corpus = await _make_corpus(db_session)
    ms = await _make_manuscript(db_session, corpus.id)
    page = await _make_page(db_session, ms.id)

    run_data = (await async_client.post(f"/api/v1/pages/{page.id}/run")).json()
    data = (await async_client.get(f"/api/v1/jobs/{run_data['id']}")).json()

    assert "status" in data
    assert "corpus_id" in data
    assert "page_id" in data
    assert "created_at" in data


# ---------------------------------------------------------------------------
# POST /api/v1/jobs/{job_id}/retry
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retry_job_not_found(async_client):
    response = await async_client.post("/api/v1/jobs/nonexistent/retry")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_retry_pending_job_409(async_client, db_session):
    """Un job en état 'pending' ne peut pas être relancé."""
    corpus = await _make_corpus(db_session)
    ms = await _make_manuscript(db_session, corpus.id)
    page = await _make_page(db_session, ms.id)

    job_data = (await async_client.post(f"/api/v1/pages/{page.id}/run")).json()
    response = await async_client.post(f"/api/v1/jobs/{job_data['id']}/retry")
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_retry_failed_job_ok(async_client, db_session):
    """Un job en état 'failed' peut être relancé → status passe à 'pending'."""
    corpus = await _make_corpus(db_session)
    job = await _make_failed_job(db_session, corpus.id)

    response = await async_client.post(f"/api/v1/jobs/{job.id}/retry")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_retry_failed_job_clears_error(async_client, db_session):
    corpus = await _make_corpus(db_session)
    job = await _make_failed_job(db_session, corpus.id)

    data = (await async_client.post(f"/api/v1/jobs/{job.id}/retry")).json()
    assert data["error_message"] is None
    assert data["started_at"] is None
    assert data["finished_at"] is None


@pytest.mark.asyncio
async def test_retry_failed_job_is_retrievable(async_client, db_session):
    """Après retry, GET /jobs/{id} reflète le nouveau statut."""
    corpus = await _make_corpus(db_session)
    job = await _make_failed_job(db_session, corpus.id)

    await async_client.post(f"/api/v1/jobs/{job.id}/retry")
    data = (await async_client.get(f"/api/v1/jobs/{job.id}")).json()
    assert data["status"] == "pending"
