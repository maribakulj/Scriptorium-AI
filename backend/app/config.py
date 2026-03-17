"""
Configuration globale de la plateforme, chargée depuis les variables d'environnement.

Équivalent fonctionnel de pydantic-settings sans dépendance externe :
  - les valeurs sont lues depuis os.environ au moment de l'instanciation
  - l'objet `settings` est importé partout dans l'application
  - dans les tests : monkeypatch.setattr(config, "settings", ...) pour surcharger
"""
# 1. stdlib
import os
from pathlib import Path

# 2. third-party
from pydantic import BaseModel, ConfigDict


class Settings(BaseModel):
    """Paramètres d'application lus depuis les variables d'environnement.

    Toutes les clés API sont optionnelles (None si non configurées).
    Elles ne sont jamais loguées ni exportées (R06).
    """

    model_config = ConfigDict(frozen=False)

    # ── Serveur ──────────────────────────────────────────────────────────────
    base_url: str = "http://localhost:8000"
    data_dir: Path = Path("data")

    # ── Base de données ───────────────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./scriptorium.db"

    # ── Fournisseurs IA (R06 — clés depuis l'environnement uniquement) ────────
    google_ai_studio_api_key: str | None = None
    vertex_api_key: str | None = None
    vertex_service_account_json: str | None = None


def _load_settings() -> Settings:
    """Lit les variables d'environnement et construit l'objet Settings."""
    return Settings(
        base_url=os.getenv("BASE_URL", "http://localhost:8000"),
        data_dir=Path(os.getenv("DATA_DIR", "data")),
        database_url=os.getenv(
            "DATABASE_URL", "sqlite+aiosqlite:///./scriptorium.db"
        ),
        google_ai_studio_api_key=os.getenv("GOOGLE_AI_STUDIO_API_KEY"),
        vertex_api_key=os.getenv("VERTEX_API_KEY"),
        vertex_service_account_json=os.getenv("VERTEX_SERVICE_ACCOUNT_JSON"),
    )


settings: Settings = _load_settings()
