"""
Modèle SQLAlchemy 2.0 — table des jobs de traitement.

Un job suit l'exécution du pipeline sur une page.
  corpus.run  → crée un JobModel par page du corpus (page_id renseigné)
  pages.run   → crée un JobModel pour la page cible

Cycle de vie :
  pending → running → done
                   ↘ failed
"""
# 1. stdlib
from datetime import datetime

# 2. third-party
from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

# 3. local
from app.models.database import Base


class JobModel(Base):
    """Suivi d'un job de pipeline (1 job = 1 page)."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    corpus_id: Mapped[str] = mapped_column(
        String, ForeignKey("corpora.id"), nullable=False, index=True
    )
    page_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("pages.id"), nullable=True, index=True
    )
    # pending / running / done / failed
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
