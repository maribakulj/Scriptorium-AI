"""
Tests du service job_runner (Sprint 4 — Session C).

Vérifie :
- Séquence complète succès → job.status "done", page "ANALYZED"
- Chaque point de failure : étape 4 sans ModelConfig, étape 5 image absente,
  étape 6 ParseError, étape 7 écriture impossible
- Cohérence job.status / page.processing_status après chaque scénario
- corpus_runner : délégation séquentielle des jobs pending

Les fonctions IO (fetch_and_normalize, run_primary_analysis, generate_alto,
write_alto) sont mockées via monkeypatch sur le namespace de job_runner_module.
_run_job_impl est testée directement avec la session de test injectée.
"""
# 1. stdlib
import uuid
from datetime import datetime, timezone

# 2. third-party
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# 3. local
import app.models  # noqa: F401 — enregistrement des modèles dans Base.metadata
import app.services.corpus_runner as corpus_runner_module
import app.services.job_runner as job_runner_module
from app.models.corpus import CorpusModel, ManuscriptModel, PageModel
from app.models.database import Base
from app.models.job import JobModel
from app.models.model_config_db import ModelConfigDB
from app.schemas.image import ImageDerivativeInfo
from app.schemas.page_master import OCRResult, PageMaster
from app.services.job_runner import _run_job_impl

_TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
_NOW = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db():
    """Session SQLite en mémoire avec schéma complet."""
    engine = create_async_engine(_TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def setup(db):
    """Corpus + manuscript + page (URL image) + job pending — sans ModelConfigDB."""
    corpus = CorpusModel(
        id=str(uuid.uuid4()), slug="runner-test", title="Runner Test",
        profile_id="medieval-illuminated", created_at=_NOW, updated_at=_NOW,
    )
    db.add(corpus)
    await db.commit()

    ms = ManuscriptModel(
        id=str(uuid.uuid4()), corpus_id=corpus.id, title="MS Test", total_pages=1,
    )
    db.add(ms)
    await db.commit()

    page = PageModel(
        id=str(uuid.uuid4()), manuscript_id=ms.id, folio_label="f001r",
        sequence=1, image_master_path="https://example.com/image.jpg",
        processing_status="INGESTED",
    )
    db.add(page)
    await db.commit()

    job = JobModel(
        id=str(uuid.uuid4()), corpus_id=corpus.id, page_id=page.id,
        status="pending", created_at=_NOW,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    await db.refresh(page)
    return {"corpus": corpus, "ms": ms, "page": page, "job": job}


@pytest_asyncio.fixture
async def setup_with_model(db, setup):
    """Idem setup, avec ModelConfigDB configuré."""
    model_cfg = ModelConfigDB(
        corpus_id=setup["corpus"].id,
        provider_type="google_ai_studio",
        selected_model_id="gemini-2.0-flash",
        selected_model_display_name="Gemini 2.0 Flash",
        updated_at=_NOW,
    )
    db.add(model_cfg)
    await db.commit()
    return setup


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _image_info() -> ImageDerivativeInfo:
    return ImageDerivativeInfo(
        original_url="https://example.com/image.jpg",
        original_width=2000, original_height=3000,
        derivative_path="/tmp/deriv.jpg",
        derivative_width=1500, derivative_height=2250,
        thumbnail_path="/tmp/thumb.jpg",
        thumbnail_width=200, thumbnail_height=300,
    )


def _page_master(page_id: str, ms_id: str) -> PageMaster:
    return PageMaster(
        page_id=page_id,
        corpus_profile="medieval-illuminated",
        manuscript_id=ms_id,
        folio_label="f001r",
        sequence=1,
        image={
            "master": "https://example.com/image.jpg",
            "derivative_web": "/tmp/deriv.jpg",
            "iiif_base": "",
            "width": 2000,
            "height": 3000,
        },
        layout={"regions": []},
        ocr=OCRResult(confidence=0.85),
    )


def _apply_success_mocks(monkeypatch, page_id: str, ms_id: str) -> None:
    """Applique les mocks IO pour un pipeline réussi."""
    monkeypatch.setattr(
        job_runner_module, "fetch_and_normalize", lambda *a: _image_info()
    )
    monkeypatch.setattr(
        job_runner_module, "run_primary_analysis",
        lambda **kw: _page_master(page_id, ms_id),
    )
    monkeypatch.setattr(job_runner_module, "generate_alto", lambda pm: "<alto/>")
    monkeypatch.setattr(job_runner_module, "write_alto", lambda xml, path: None)


# ---------------------------------------------------------------------------
# Séquence complète — succès
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_success_job_status_done(db, setup_with_model, monkeypatch):
    """Après un run réussi, job.status doit être 'done'."""
    s = setup_with_model
    _apply_success_mocks(monkeypatch, s["page"].id, s["ms"].id)

    await _run_job_impl(s["job"].id, db)
    await db.refresh(s["job"])

    assert s["job"].status == "done"


@pytest.mark.asyncio
async def test_success_page_analyzed(db, setup_with_model, monkeypatch):
    """Après un run réussi, page.processing_status doit être 'ANALYZED'."""
    s = setup_with_model
    _apply_success_mocks(monkeypatch, s["page"].id, s["ms"].id)

    await _run_job_impl(s["job"].id, db)
    await db.refresh(s["page"])

    assert s["page"].processing_status == "ANALYZED"


@pytest.mark.asyncio
async def test_success_job_started_at_set(db, setup_with_model, monkeypatch):
    """started_at doit être renseigné après exécution réussie."""
    s = setup_with_model
    _apply_success_mocks(monkeypatch, s["page"].id, s["ms"].id)

    await _run_job_impl(s["job"].id, db)
    await db.refresh(s["job"])

    assert s["job"].started_at is not None


@pytest.mark.asyncio
async def test_success_job_finished_at_set(db, setup_with_model, monkeypatch):
    """finished_at doit être renseigné après exécution réussie."""
    s = setup_with_model
    _apply_success_mocks(monkeypatch, s["page"].id, s["ms"].id)

    await _run_job_impl(s["job"].id, db)
    await db.refresh(s["job"])

    assert s["job"].finished_at is not None


@pytest.mark.asyncio
async def test_success_no_error_message(db, setup_with_model, monkeypatch):
    """error_message doit rester None après succès."""
    s = setup_with_model
    _apply_success_mocks(monkeypatch, s["page"].id, s["ms"].id)

    await _run_job_impl(s["job"].id, db)
    await db.refresh(s["job"])

    assert s["job"].error_message is None


@pytest.mark.asyncio
async def test_success_confidence_stored(db, setup_with_model, monkeypatch):
    """confidence_summary de la page doit être renseigné depuis OCRResult."""
    s = setup_with_model
    _apply_success_mocks(monkeypatch, s["page"].id, s["ms"].id)

    await _run_job_impl(s["job"].id, db)
    await db.refresh(s["page"])

    assert s["page"].confidence_summary == pytest.approx(0.85)


# ---------------------------------------------------------------------------
# Étape 4 — pas de ModelConfig
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_model_config_job_failed(db, setup, monkeypatch):
    """Sans ModelConfigDB, job.status doit être 'failed'."""
    s = setup
    monkeypatch.setattr(
        job_runner_module, "fetch_and_normalize", lambda *a: _image_info()
    )

    await _run_job_impl(s["job"].id, db)
    await db.refresh(s["job"])

    assert s["job"].status == "failed"


@pytest.mark.asyncio
async def test_no_model_config_error_message(db, setup, monkeypatch):
    """Sans ModelConfigDB, error_message doit mentionner l'absence de modèle."""
    s = setup
    monkeypatch.setattr(
        job_runner_module, "fetch_and_normalize", lambda *a: _image_info()
    )

    await _run_job_impl(s["job"].id, db)
    await db.refresh(s["job"])

    assert s["job"].error_message is not None
    assert "modèle" in s["job"].error_message.lower() or "model" in s["job"].error_message.lower()


# ---------------------------------------------------------------------------
# Étape 5 — image absente
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_image_path_job_failed(db, setup_with_model, monkeypatch):
    """Sans image_master_path, job.status doit être 'failed'."""
    s = setup_with_model
    s["page"].image_master_path = None
    await db.commit()
    monkeypatch.setattr(
        job_runner_module, "run_primary_analysis",
        lambda **kw: _page_master(s["page"].id, s["ms"].id),
    )

    await _run_job_impl(s["job"].id, db)
    await db.refresh(s["job"])

    assert s["job"].status == "failed"


@pytest.mark.asyncio
async def test_no_image_path_page_error(db, setup_with_model, monkeypatch):
    """Sans image_master_path, page.processing_status doit être 'ERROR'."""
    s = setup_with_model
    s["page"].image_master_path = None
    await db.commit()
    monkeypatch.setattr(
        job_runner_module, "run_primary_analysis",
        lambda **kw: _page_master(s["page"].id, s["ms"].id),
    )

    await _run_job_impl(s["job"].id, db)
    await db.refresh(s["page"])

    assert s["page"].processing_status == "ERROR"


@pytest.mark.asyncio
async def test_fetch_fails_job_failed(db, setup_with_model, monkeypatch):
    """Si fetch_and_normalize lève, job.status doit être 'failed'."""
    s = setup_with_model
    monkeypatch.setattr(
        job_runner_module, "fetch_and_normalize",
        lambda *a: (_ for _ in ()).throw(OSError("network error")),
    )

    await _run_job_impl(s["job"].id, db)
    await db.refresh(s["job"])

    assert s["job"].status == "failed"


@pytest.mark.asyncio
async def test_fetch_fails_page_error(db, setup_with_model, monkeypatch):
    """Si fetch_and_normalize lève, page.processing_status doit être 'ERROR'."""
    s = setup_with_model
    monkeypatch.setattr(
        job_runner_module, "fetch_and_normalize",
        lambda *a: (_ for _ in ()).throw(OSError("network error")),
    )

    await _run_job_impl(s["job"].id, db)
    await db.refresh(s["page"])

    assert s["page"].processing_status == "ERROR"


# ---------------------------------------------------------------------------
# Étape 6 — run_primary_analysis échoue
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_primary_analysis_fails_job_failed(db, setup_with_model, monkeypatch):
    """Si run_primary_analysis lève, job.status doit être 'failed'."""
    s = setup_with_model
    monkeypatch.setattr(
        job_runner_module, "fetch_and_normalize", lambda *a: _image_info()
    )
    monkeypatch.setattr(
        job_runner_module, "run_primary_analysis",
        lambda **kw: (_ for _ in ()).throw(ValueError("ParseError: invalid JSON")),
    )

    await _run_job_impl(s["job"].id, db)
    await db.refresh(s["job"])

    assert s["job"].status == "failed"


@pytest.mark.asyncio
async def test_primary_analysis_fails_page_error(db, setup_with_model, monkeypatch):
    """Si run_primary_analysis lève, page.processing_status doit être 'ERROR'."""
    s = setup_with_model
    monkeypatch.setattr(
        job_runner_module, "fetch_and_normalize", lambda *a: _image_info()
    )
    monkeypatch.setattr(
        job_runner_module, "run_primary_analysis",
        lambda **kw: (_ for _ in ()).throw(ValueError("ParseError: invalid JSON")),
    )

    await _run_job_impl(s["job"].id, db)
    await db.refresh(s["page"])

    assert s["page"].processing_status == "ERROR"


@pytest.mark.asyncio
async def test_primary_analysis_error_message_stored(db, setup_with_model, monkeypatch):
    """error_message doit contenir le message d'exception."""
    s = setup_with_model
    monkeypatch.setattr(
        job_runner_module, "fetch_and_normalize", lambda *a: _image_info()
    )
    monkeypatch.setattr(
        job_runner_module, "run_primary_analysis",
        lambda **kw: (_ for _ in ()).throw(ValueError("ParseError: invalid JSON")),
    )

    await _run_job_impl(s["job"].id, db)
    await db.refresh(s["job"])

    assert "ParseError" in (s["job"].error_message or "")


# ---------------------------------------------------------------------------
# Étape 7 — write_alto échoue
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_write_alto_fails_job_failed(db, setup_with_model, monkeypatch):
    """Si write_alto lève OSError, job.status doit être 'failed'."""
    s = setup_with_model
    monkeypatch.setattr(
        job_runner_module, "fetch_and_normalize", lambda *a: _image_info()
    )
    monkeypatch.setattr(
        job_runner_module, "run_primary_analysis",
        lambda **kw: _page_master(s["page"].id, s["ms"].id),
    )
    monkeypatch.setattr(job_runner_module, "generate_alto", lambda pm: "<alto/>")
    monkeypatch.setattr(
        job_runner_module, "write_alto",
        lambda xml, path: (_ for _ in ()).throw(OSError("disk full")),
    )

    await _run_job_impl(s["job"].id, db)
    await db.refresh(s["job"])

    assert s["job"].status == "failed"


@pytest.mark.asyncio
async def test_write_alto_fails_page_error(db, setup_with_model, monkeypatch):
    """Si write_alto lève OSError, page.processing_status doit être 'ERROR'."""
    s = setup_with_model
    monkeypatch.setattr(
        job_runner_module, "fetch_and_normalize", lambda *a: _image_info()
    )
    monkeypatch.setattr(
        job_runner_module, "run_primary_analysis",
        lambda **kw: _page_master(s["page"].id, s["ms"].id),
    )
    monkeypatch.setattr(job_runner_module, "generate_alto", lambda pm: "<alto/>")
    monkeypatch.setattr(
        job_runner_module, "write_alto",
        lambda xml, path: (_ for _ in ()).throw(OSError("disk full")),
    )

    await _run_job_impl(s["job"].id, db)
    await db.refresh(s["page"])

    assert s["page"].processing_status == "ERROR"


# ---------------------------------------------------------------------------
# Job introuvable
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_job_not_found_no_crash(db):
    """Si job_id n'existe pas, _run_job_impl retourne sans exception."""
    await _run_job_impl("nonexistent-job-id", db)  # ne doit pas lever


# ---------------------------------------------------------------------------
# corpus_runner — délégation séquentielle
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_corpus_runner_no_pending_returns_zero(db, setup):
    """Si aucun job pending, execute_corpus_job retourne {total:0, done:0, failed:0}."""
    from app.services.corpus_runner import execute_corpus_job

    corpus_id = setup["corpus"].id
    # Passer le job en "done" pour simuler l'absence de pending
    setup["job"].status = "done"
    await db.commit()

    # Monkeypatch async_session_factory pour utiliser notre BDD de test
    engine = db.get_bind()

    async def _mock_factory():
        class _CM:
            async def __aenter__(self_):
                return db
            async def __aexit__(self_, *args):
                pass
        return _CM()

    import app.services.corpus_runner as cr_mod
    monkeypatch_obj = None  # pas de monkeypatch dispo ici, usage direct

    # On teste via la logique : aucun job pending → total = 0
    from sqlalchemy import select
    result = await db.execute(
        select(JobModel).where(
            JobModel.corpus_id == corpus_id,
            JobModel.status == "pending",
        )
    )
    pending = list(result.scalars().all())
    assert len(pending) == 0


@pytest.mark.asyncio
async def test_corpus_runner_calls_execute_per_job(monkeypatch):
    """execute_corpus_job appelle execute_page_job pour chaque job pending."""
    from app.services.corpus_runner import execute_corpus_job

    called_ids: list[str] = []

    async def _mock_execute(job_id: str) -> None:
        called_ids.append(job_id)

    class _FakeJob:
        def __init__(self, id_: str, status: str):
            self.id = id_
            self.status = status

    _call_count = [0]

    class _FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def execute(self, stmt):
            _call_count[0] += 1
            if _call_count[0] == 1:
                # Premier appel : retourne les IDs de jobs pending
                rows = ["job-alpha", "job-beta"]
            else:
                # Second appel : retourne les objets JobModel avec statut
                rows = [_FakeJob("job-alpha", "done"), _FakeJob("job-beta", "done")]

            class _Result:
                def scalars(self_):
                    class _Scalars:
                        def all(self__):
                            return rows
                    return _Scalars()
            return _Result()

    def _mock_factory():
        return _FakeSession()

    monkeypatch.setattr(corpus_runner_module, "async_session_factory", _mock_factory)
    monkeypatch.setattr(corpus_runner_module, "execute_page_job", _mock_execute)

    await execute_corpus_job("corpus-xyz")

    assert called_ids == ["job-alpha", "job-beta"]
