"""
Modèles SQLAlchemy 2.0 — tables Corpus, Manuscript, Page.

Ces modèles représentent la couche de persistance (BDD).
Ils NE se substituent PAS aux schémas Pydantic (source canonique des types).
"""
# 1. stdlib
from datetime import datetime, timezone

# 2. third-party
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

# 3. local
from app.models.database import Base


class CorpusModel(Base):
    """Un corpus regroupe un ou plusieurs manuscrits sous un même profil."""

    __tablename__ = "corpora"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    profile_id: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    manuscripts: Mapped[list["ManuscriptModel"]] = relationship(
        back_populates="corpus", cascade="all, delete-orphan"
    )


class ManuscriptModel(Base):
    """Un manuscrit appartient à un corpus et contient des pages."""

    __tablename__ = "manuscripts"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    corpus_id: Mapped[str] = mapped_column(
        String, ForeignKey("corpora.id"), nullable=False, index=True
    )
    shelfmark: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    date_label: Mapped[str | None] = mapped_column(String, nullable=True)
    total_pages: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    corpus: Mapped["CorpusModel"] = relationship(back_populates="manuscripts")
    pages: Mapped[list["PageModel"]] = relationship(
        back_populates="manuscript", cascade="all, delete-orphan"
    )


class PageModel(Base):
    """Une page appartient à un manuscrit.

    processing_status suit le cycle de vie défini en CLAUDE.md §10 :
      CREATED → INGESTING → INGESTED → PREPARED → ANALYZED → LAYERED
      → EXPORTED → VALIDATED → ERROR
    """

    __tablename__ = "pages"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    manuscript_id: Mapped[str] = mapped_column(
        String, ForeignKey("manuscripts.id"), nullable=False, index=True
    )
    folio_label: Mapped[str] = mapped_column(String, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    image_master_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    processing_status: Mapped[str] = mapped_column(
        String, nullable=False, default="CREATED"
    )
    confidence_summary: Mapped[float | None] = mapped_column(Float, nullable=True)

    manuscript: Mapped["ManuscriptModel"] = relationship(back_populates="pages")
