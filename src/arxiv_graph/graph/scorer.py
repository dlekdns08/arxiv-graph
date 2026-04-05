"""Paper importance scoring.

Scoring strategy (extensible):
  - recency:   newer papers get a higher base score
  - citations: citation_count from external sources (stub for now)
  - pagerank:  computed from the semantic graph
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from arxiv_graph.storage.models import Paper


_RECENCY_FLAT_DAYS = 30  # papers within this window all score 1.0


def score_recency(paper: Paper) -> float:
    if paper.published_at is None:
        return 0.0
    now = datetime.now(timezone.utc)
    pub = paper.published_at
    if pub.tzinfo is None:
        pub = pub.replace(tzinfo=timezone.utc)
    age_days = max((now - pub).days, 0)
    if age_days <= _RECENCY_FLAT_DAYS:
        return 1.0
    # 30일 초과부터 지수 감쇠 (반감기 30일)
    return 2 ** (-( age_days - _RECENCY_FLAT_DAYS) / _RECENCY_FLAT_DAYS)


def score_citations(paper: Paper) -> float:
    # 일반 인용수 + influential 인용수(3배 가중) 합산, 100 기준으로 정규화
    weighted = paper.citation_count + 3 * paper.influential_citation_count
    return min(weighted / 100, 1.0)


def compute_importance(paper: Paper, pagerank: float = 0.0) -> float:
    """Weighted composite importance score in [0, 1]."""
    recency = score_recency(paper)
    citations = score_citations(paper)
    # weights: recency 30%, citations 40%, pagerank 30%
    return round(0.3 * recency + 0.4 * citations + 0.3 * pagerank, 4)


def update_scores(session: Session, pageranks: dict[str, float]) -> None:
    papers: list[Paper] = session.query(Paper).all()
    for paper in papers:
        pr = pageranks.get(paper.arxiv_id, 0.0)
        paper.importance_score = compute_importance(paper, pr)
    session.commit()
