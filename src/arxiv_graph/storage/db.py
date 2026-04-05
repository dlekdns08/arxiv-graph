"""Database session management and CRUD helpers."""

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from arxiv_graph.storage.models import Base

# DB는 workspace 밖(~/.arxiv-graph/data/)에 저장 — GitHub Actions checkout이
# workspace를 git clean하더라도 데이터가 유실되지 않도록 한다.
# ARXIV_GRAPH_DATA_DIR 환경변수로 override 가능.
_DATA_DIR = Path(os.environ.get("ARXIV_GRAPH_DATA_DIR", str(Path.home() / ".arxiv-graph" / "data")))
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
