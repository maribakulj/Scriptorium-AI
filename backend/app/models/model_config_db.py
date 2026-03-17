"""
Modèle SQLAlchemy 2.0 — configuration du modèle IA par corpus.

Une seule ligne par corpus (corpus_id = PK).
La clé API n'est JAMAIS stockée ici (R06) — elle reste dans l'environnement.
"""
# 1. stdlib
from datetime import datetime

# 2. third-party
from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

# 3. local
from app.models.database import Base


class ModelConfigDB(Base):
    """Modèle IA sélectionné pour un corpus (1 entrée par corpus)."""

    __tablename__ = "model_configs"

    corpus_id: Mapped[str] = mapped_column(
        String, ForeignKey("corpora.id"), primary_key=True
    )
    provider_type: Mapped[str] = mapped_column(String, nullable=False)
    selected_model_id: Mapped[str] = mapped_column(String, nullable=False)
    selected_model_display_name: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
