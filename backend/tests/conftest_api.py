"""
Fixtures partagées pour les tests d'API FastAPI (Sprint 4 — Session A).

Usage dans les fichiers de test :
    from tests.conftest_api import async_client, db_session  # noqa: F401

Stratégie :
  - BDD SQLite en mémoire (":memory:") — isolation totale entre tests
  - Dependency override de `get_db` pour injecter la session de test
  - `httpx.AsyncClient` + `ASGITransport` pour simuler des requêtes HTTP
"""
# 1. stdlib
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch

# 2. third-party
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# 3. local
import app.models  # noqa: F401 — enregistrement des modèles dans Base.metadata
from app.models.database import Base, get_db

_TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_session():
    """Session AsyncSession sur une BDD SQLite en mémoire."""
    test_engine = create_async_engine(_TEST_DB_URL, echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture
async def async_client(db_session: AsyncSession):
    """AsyncClient HTTP connecté à l'app FastAPI, avec BDD de test injectée."""
    from app.main import app

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    # Les background tasks (execute_corpus_job, execute_page_job) créent leur
    # propre session via async_session_factory. On les neutralise pour éviter
    # qu'elles tentent de se connecter à la BDD réelle pendant les tests d'API.
    with patch("app.api.v1.jobs.execute_corpus_job", AsyncMock(return_value=None)), \
         patch("app.api.v1.jobs.execute_page_job", AsyncMock(return_value=None)):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client
    app.dependency_overrides.clear()
