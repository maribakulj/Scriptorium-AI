"""
Engine SQLAlchemy async (aiosqlite) et session factory.

Utilisation dans les endpoints FastAPI :
    async def my_endpoint(db: AsyncSession = Depends(get_db)):
        ...

Les tables sont créées au démarrage de l'application (voir main.py lifespan).
"""
# 1. stdlib
import logging

# 2. third-party
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

# 3. local
from app.config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.database_url,
    echo=False,
    connect_args={"check_same_thread": False},
)

async_session_factory = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    """Dépendance FastAPI — injecte une AsyncSession par requête."""
    async with async_session_factory() as session:
        yield session
