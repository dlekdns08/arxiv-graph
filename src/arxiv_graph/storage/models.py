"""SQLAlchemy ORM models for paper and relation storage."""

from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


paper_author = Table(
    "paper_author",
    Base.metadata,
    Column("paper_id", String, ForeignKey("papers.arxiv_id"), primary_key=True),
    Column("author_id", Integer, ForeignKey("authors.id"), primary_key=True),
)


class Paper(Base):
    __tablename__ = "papers"

    arxiv_id: str = Column(String, primary_key=True)
    title: str = Column(String, nullable=False)
    abstract: str = Column(Text)
    published_at: datetime = Column(DateTime)
    updated_at: datetime = Column(DateTime)
    primary_category: str = Column(String)
    categories: str = Column(String)  # comma-separated
    pdf_url: str = Column(String)
    importance_score: float = Column(Float, default=0.0)
    citation_count: int = Column(Integer, default=0)
    influential_citation_count: int = Column(Integer, default=0)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)

    authors = relationship("Author", secondary=paper_author, back_populates="papers")
    outgoing_relations = relationship(
        "PaperRelation",
        foreign_keys="PaperRelation.source_id",
        back_populates="source",
    )
    incoming_relations = relationship(
        "PaperRelation",
        foreign_keys="PaperRelation.target_id",
        back_populates="target",
    )


class Author(Base):
    __tablename__ = "authors"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    name: str = Column(String, nullable=False, unique=True)

    papers = relationship("Paper", secondary=paper_author, back_populates="authors")


class PaperRelation(Base):
    """Directed weighted edge between two papers."""

    __tablename__ = "paper_relations"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    source_id: str = Column(String, ForeignKey("papers.arxiv_id"), nullable=False)
    target_id: str = Column(String, ForeignKey("papers.arxiv_id"), nullable=False)
    relation_type: str = Column(String, nullable=False)  # e.g. "semantic", "author"
    weight: float = Column(Float, default=1.0)  # similarity score

    source = relationship("Paper", foreign_keys=[source_id], back_populates="outgoing_relations")
    target = relationship("Paper", foreign_keys=[target_id], back_populates="incoming_relations")
