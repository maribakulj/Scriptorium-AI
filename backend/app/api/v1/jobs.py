"""
Endpoints de gestion des jobs de traitement (R10 — préfixe /api/v1/).

POST /api/v1/corpora/{id}/run         → crée un job par page + lance le pipeline en fond
POST /api/v1/pages/{id}/run           → crée un job + lance le pipeline en fond
GET  /api/v1/jobs/{job_id}            → état du job
POST /api/v1/jobs/{job_id}/retry      → relance un job FAILED

Le pipeline est exécuté via FastAPI BackgroundTasks (pas de Celery, pas de threading manuel).
"""
# 1. stdlib
import uuid
from datetime import datetime, timezone

# 2. third-party
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# 3. local
from app.models.corpus import CorpusModel, ManuscriptModel, PageModel
from app.models.database import get_db
from app.models.job import JobModel
from app.services.corpus_runner import execute_corpus_job
from app.services.job_runner import execute_page_job

router = APIRouter(tags=["jobs"])

_JOB_STATUS_PENDING = "pending"
_JOB_STATUS_FAILED = "failed"


# ── Schémas de réponse ────────────────────────────────────────────────────────

class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    corpus_id: str
    page_id: str | None
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    error_message: str | None
    created_at: datetime


class CorpusRunResponse(BaseModel):
    corpus_id: str
    jobs_created: int
    job_ids: list[str]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _new_job(corpus_id: str, page_id: str | None) -> JobModel:
    now = datetime.now(timezone.utc)
    return JobModel(
        id=str(uuid.uuid4()),
        corpus_id=corpus_id,
        page_id=page_id,
        status=_JOB_STATUS_PENDING,
        started_at=None,
        finished_at=None,
        error_message=None,
        created_at=now,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/corpora/{corpus_id}/run", response_model=CorpusRunResponse, status_code=202)
async def run_corpus(
    corpus_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> CorpusRunResponse:
    """Lance le pipeline sur toutes les pages du corpus.

    Crée un JobModel par page (status=pending), puis délègue l'exécution
    réelle à execute_corpus_job via BackgroundTasks (retour immédiat).
    """
    corpus = await db.get(CorpusModel, corpus_id)
    if corpus is None:
        raise HTTPException(status_code=404, detail="Corpus introuvable")

    ms_result = await db.execute(
        select(ManuscriptModel).where(ManuscriptModel.corpus_id == corpus_id)
    )
    ms_ids = [ms.id for ms in ms_result.scalars().all()]

    pages_result = await db.execute(
        select(PageModel).where(PageModel.manuscript_id.in_(ms_ids))
    )
    pages = list(pages_result.scalars().all())

    jobs = [_new_job(corpus_id, page.id) for page in pages]
    for job in jobs:
        db.add(job)
    await db.commit()

    # Lancer le pipeline en arrière-plan (après envoi de la réponse)
    background_tasks.add_task(execute_corpus_job, corpus_id)

    return CorpusRunResponse(
        corpus_id=corpus_id,
        jobs_created=len(jobs),
        job_ids=[j.id for j in jobs],
    )


@router.post("/pages/{page_id}/run", response_model=JobResponse, status_code=202)
async def run_page(
    page_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> JobModel:
    """Lance le pipeline sur une seule page.

    Crée un JobModel (status=pending) et délègue l'exécution à
    execute_page_job via BackgroundTasks (retour immédiat).
    """
    page = await db.get(PageModel, page_id)
    if page is None:
        raise HTTPException(status_code=404, detail="Page introuvable")

    manuscript = await db.get(ManuscriptModel, page.manuscript_id)
    if manuscript is None:
        raise HTTPException(status_code=404, detail="Manuscrit introuvable")

    job = _new_job(manuscript.corpus_id, page_id)
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Lancer le pipeline en arrière-plan (après envoi de la réponse)
    background_tasks.add_task(execute_page_job, job.id)

    return job


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)) -> JobModel:
    """Retourne l'état d'un job."""
    job = await db.get(JobModel, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job introuvable")
    return job


@router.post("/jobs/{job_id}/retry", response_model=JobResponse)
async def retry_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> JobModel:
    """Relance un job en état FAILED (remet le status à pending).

    Retourne 409 si le job n'est pas dans l'état FAILED.
    """
    job = await db.get(JobModel, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job introuvable")
    if job.status != _JOB_STATUS_FAILED:
        raise HTTPException(
            status_code=409,
            detail=f"Le job ne peut être relancé que depuis l'état 'failed' (statut actuel : '{job.status}')",
        )
    job.status = _JOB_STATUS_PENDING
    job.error_message = None
    job.started_at = None
    job.finished_at = None
    await db.commit()
    await db.refresh(job)

    # Relancer le pipeline
    background_tasks.add_task(execute_page_job, job.id)

    return job
