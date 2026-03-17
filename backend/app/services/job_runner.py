"""
Exécution réelle du pipeline sur un job page (Sprint 4 — Session C).

Point d'entrée principal : execute_page_job(job_id)
Séquence stricte (CLAUDE.md §8 pipeline) :
  1. job → RUNNING
  2. Charger page / manuscrit / corpus depuis BDD
  3. Charger CorpusProfile depuis profiles/{profile_id}.json
  4. Charger ModelConfig depuis BDD  (erreur explicite si absent)
  5. fetch_and_normalize()  → ImageDerivativeInfo
  6. run_primary_analysis() → PageMaster  (+ double stockage R05)
  7. generate_alto() + write_alto()
  8. page.processing_status → ANALYZED
  9. job → DONE

Sur toute exception : job → FAILED + error_message, page → ERROR.
Aucun échec silencieux (CLAUDE.md §7).
"""
# 1. stdlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

# 2. third-party
from sqlalchemy.ext.asyncio import AsyncSession

# 3. local
from app import config as _config_module
from app.models.corpus import CorpusModel, ManuscriptModel, PageModel
from app.models.database import async_session_factory
from app.models.job import JobModel
from app.models.model_config_db import ModelConfigDB
from app.schemas.corpus_profile import CorpusProfile
from app.schemas.model_config import ModelConfig, ProviderType
from app.services.ai.analyzer import run_primary_analysis
from app.services.export.alto import generate_alto, write_alto
from app.services.image.normalizer import create_derivatives, fetch_and_normalize

logger = logging.getLogger(__name__)

# Racine du projet : backend/app/services/job_runner.py → 3 parents → project root
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


# ── Point d'entrée public ──────────────────────────────────────────────────

async def execute_page_job(job_id: str, db: AsyncSession | None = None) -> None:
    """BackgroundTask : exécute le pipeline complet sur une page.

    Args:
        job_id: identifiant du JobModel en BDD.
        db: session optionnelle (fournie dans les tests ; None = nouvelle session).
    """
    if db is None:
        async with async_session_factory() as session:
            await _run_job_impl(job_id, session)
    else:
        await _run_job_impl(job_id, db)


# ── Implémentation interne (testable directement) ──────────────────────────

async def _run_job_impl(job_id: str, db: AsyncSession) -> None:
    """Exécution du pipeline sur un job, avec la session fournie.

    Exposé (préfixe _ conservé) pour les tests unitaires.
    """
    # ── 1. Charger le job, passer status → RUNNING ──────────────────────────
    job = await db.get(JobModel, job_id)
    if job is None:
        logger.error("Job introuvable — exécution abandonnée", extra={"job_id": job_id})
        return

    job.status = "running"
    job.started_at = datetime.now(timezone.utc)
    await db.commit()

    page: PageModel | None = None

    try:
        # ── 2. Charger page / manuscrit / corpus ─────────────────────────────
        if job.page_id is None:
            raise ValueError("Ce job n'a pas de page_id — impossible d'exécuter le pipeline")

        page = await db.get(PageModel, job.page_id)
        if page is None:
            raise ValueError(f"Page introuvable en BDD : {job.page_id}")

        manuscript = await db.get(ManuscriptModel, page.manuscript_id)
        if manuscript is None:
            raise ValueError(f"Manuscrit introuvable en BDD : {page.manuscript_id}")

        corpus = await db.get(CorpusModel, manuscript.corpus_id)
        if corpus is None:
            raise ValueError(f"Corpus introuvable en BDD : {manuscript.corpus_id}")

        # ── 3. Charger le CorpusProfile ──────────────────────────────────────
        profile_path = _PROJECT_ROOT / "profiles" / f"{corpus.profile_id}.json"
        if not profile_path.exists():
            raise FileNotFoundError(
                f"Fichier de profil introuvable : {profile_path}. "
                f"Profil attendu : «{corpus.profile_id}»"
            )
        profile_data = json.loads(profile_path.read_text(encoding="utf-8"))
        corpus_profile = CorpusProfile.model_validate(profile_data)

        # ── 4. Charger le ModelConfig (erreur explicite si absent) ───────────
        model_db = await db.get(ModelConfigDB, corpus.id)
        if model_db is None:
            raise ValueError(
                f"Aucun modèle IA configuré pour le corpus «{corpus.id}». "
                "Sélectionnez un modèle via PUT /api/v1/corpora/{id}/model avant "
                "de lancer le pipeline."
            )
        model_config = ModelConfig(
            corpus_id=corpus.id,
            selected_model_id=model_db.selected_model_id,
            selected_model_display_name=model_db.selected_model_display_name,
            provider=ProviderType(model_db.provider_type),
            supports_vision=True,
            last_fetched_at=model_db.updated_at,
            available_models=[],
        )

        # ── 5. Normaliser l'image ────────────────────────────────────────────
        data_dir = _config_module.settings.data_dir
        image_source = page.image_master_path or ""

        if image_source.startswith(("http://", "https://")):
            image_info = fetch_and_normalize(
                image_source, corpus.slug, page.folio_label, data_dir
            )
        elif image_source:
            source_bytes = Path(image_source).read_bytes()
            image_info = create_derivatives(
                source_bytes, image_source, corpus.slug, page.folio_label, data_dir
            )
        else:
            raise ValueError(
                f"La page {page.id} n'a pas d'image source "
                "(image_master_path vide ou None)"
            )

        # ── 6. Analyse primaire IA (R05 : double stockage) ───────────────────
        page_master = run_primary_analysis(
            derivative_image_path=Path(image_info.derivative_path),
            corpus_profile=corpus_profile,
            model_config=model_config,
            page_id=page.id,
            manuscript_id=manuscript.id,
            corpus_slug=corpus.slug,
            folio_label=page.folio_label,
            sequence=page.sequence,
            image_info=image_info,
            base_data_dir=data_dir,
            project_root=_PROJECT_ROOT,
        )

        # ── 7. Générer et écrire l'ALTO XML ──────────────────────────────────
        alto_xml = generate_alto(page_master)
        alto_path = (
            data_dir
            / "corpora"
            / corpus.slug
            / "pages"
            / page.folio_label
            / "alto.xml"
        )
        write_alto(alto_xml, alto_path)

        # ── 8. Page → ANALYZED ───────────────────────────────────────────────
        page.processing_status = "ANALYZED"
        if page_master.ocr is not None:
            page.confidence_summary = page_master.ocr.confidence

        # ── 9. Job → DONE ────────────────────────────────────────────────────
        job.status = "done"
        job.finished_at = datetime.now(timezone.utc)
        await db.commit()

        logger.info(
            "Job terminé avec succès",
            extra={
                "job_id": job_id,
                "page_id": page.id,
                "folio": page.folio_label,
                "corpus": corpus.slug,
            },
        )

    except Exception as exc:
        logger.error(
            "Échec du job",
            extra={"job_id": job_id, "error": str(exc)},
            exc_info=True,
        )
        job.status = "failed"
        job.error_message = str(exc)
        job.finished_at = datetime.now(timezone.utc)
        if page is not None:
            page.processing_status = "ERROR"
        try:
            await db.commit()
        except Exception as commit_exc:
            logger.error(
                "Impossible de persister l'état d'échec du job",
                extra={"job_id": job_id, "commit_error": str(commit_exc)},
            )
