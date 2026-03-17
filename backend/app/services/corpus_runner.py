"""
Exécution séquentielle du pipeline sur tous les jobs d'un corpus (Sprint 4 — Session C).

Point d'entrée : execute_corpus_job(corpus_id)
  → récupère tous les jobs PENDING du corpus
  → les exécute séquentiellement (pas de parallélisme au MVP)
  → retourne un résumé {total, done, failed}

Chaque page reçoit sa propre session pour isoler les échecs.
"""
# 1. stdlib
import logging

# 2. third-party
from sqlalchemy import select

# 3. local
from app.models.database import async_session_factory
from app.models.job import JobModel
from app.services.job_runner import execute_page_job

logger = logging.getLogger(__name__)


async def execute_corpus_job(corpus_id: str) -> dict:
    """Lance tous les jobs PENDING du corpus séquentiellement.

    Chaque job est exécuté dans sa propre session (isolement des échecs).
    Un job FAILED n'interrompt pas les suivants.

    Returns:
        {"total": int, "done": int, "failed": int}
    """
    # Collecte des IDs de jobs PENDING (snapshot en début de run)
    async with async_session_factory() as db:
        result = await db.execute(
            select(JobModel.id).where(
                JobModel.corpus_id == corpus_id,
                JobModel.status == "pending",
            )
        )
        job_ids: list[str] = list(result.scalars().all())

    if not job_ids:
        logger.info(
            "Corpus run : aucun job pending",
            extra={"corpus_id": corpus_id},
        )
        return {"total": 0, "done": 0, "failed": 0}

    logger.info(
        "Corpus run démarré",
        extra={"corpus_id": corpus_id, "jobs": len(job_ids)},
    )

    # Exécution séquentielle — chaque job gère sa propre session
    for job_id in job_ids:
        await execute_page_job(job_id)

    # Bilan final
    async with async_session_factory() as db:
        result = await db.execute(
            select(JobModel).where(JobModel.id.in_(job_ids))
        )
        jobs = list(result.scalars().all())

    done = sum(1 for j in jobs if j.status == "done")
    failed = sum(1 for j in jobs if j.status == "failed")
    total = len(job_ids)

    logger.info(
        "Corpus run terminé",
        extra={
            "corpus_id": corpus_id,
            "total": total,
            "done": done,
            "failed": failed,
        },
    )
    return {"total": total, "done": done, "failed": failed}
