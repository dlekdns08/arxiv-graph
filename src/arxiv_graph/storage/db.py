"""Database session management and CRUD helpers."""

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from arxiv_graph.storage.models import Base

_DATA_DIR = Path(__file__).resolve().parents[3] / "data"
_DEFAULT_DB_URL = f"sqlite:///{_DATA_DIR / 'arxiv_graph.db'}"


def get_engine(db_url: str = _DEFAULT_DB_URL):
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    engine = create_engine(db_url, echo=False)
    Base.metadata.create_all(engine)
    return engine


def get_session(db_url: str = _DEFAULT_DB_URL) -> Session:
    engine = get_engine(db_url)
    factory = sessionmaker(bind=engine)
    return factory()
