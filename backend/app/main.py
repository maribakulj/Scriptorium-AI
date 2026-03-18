"""
Application FastAPI — point d'entrée de Scriptorium AI.

Tous les endpoints sont sous /api/v1/ (R10).
CORS ouvert pour le développement local (origins=["*"]).
La BDD SQLite est créée automatiquement au démarrage (lifespan).
"""
# 1. stdlib
import logging
from contextlib import asynccontextmanager
from pathlib import Path

# 2. third-party
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse

# 3. local — on importe les modèles pour que Base.metadata les connaisse
import app.models  # noqa: F401  (enregistrement des modèles SQLAlchemy)
from app.api.v1 import corpora, export, ingest, jobs, manuscripts, models_api, pages, profiles
from app.models.database import Base, engine

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Crée les tables SQLite au démarrage, libère l'engine à l'arrêt."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Tables SQLite initialisées")
    yield
    await engine.dispose()
    logger.info("Engine SQLite fermé")


app = FastAPI(
    title="Scriptorium AI",
    description="Plateforme générique de génération d'éditions savantes augmentées",
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS (dev : tous les origines autorisés) ──────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers (préfixe /api/v1/ — R10) ─────────────────────────────────────────
_V1_PREFIX = "/api/v1"

app.include_router(corpora.router, prefix=_V1_PREFIX)
app.include_router(manuscripts.router, prefix=_V1_PREFIX)
app.include_router(pages.router, prefix=_V1_PREFIX)
app.include_router(export.router, prefix=_V1_PREFIX)
app.include_router(profiles.router, prefix=_V1_PREFIX)
app.include_router(jobs.router, prefix=_V1_PREFIX)
app.include_router(ingest.router, prefix=_V1_PREFIX)
app.include_router(models_api.router, prefix=_V1_PREFIX)

# ── Serving frontend SPA (production) ou redirect /docs (dev) ────────────────
_STATIC_DIR = Path("/app/static")


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_frontend(full_path: str) -> FileResponse | RedirectResponse:
    """En production sert le frontend React (SPA). En dev redirige vers /docs."""
    if _STATIC_DIR.is_dir():
        candidate = _STATIC_DIR / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        index = _STATIC_DIR / "index.html"
        if index.exists():
            return FileResponse(index)
    return RedirectResponse(url="/docs")
