"""Daily crawl-and-build job."""

from __future__ import annotations

from loguru import logger
from sqlalchemy.orm import Session

from arxiv_graph.crawler.arxiv_client import fetch_recent_papers
from arxiv_graph.crawler.ingester import ingest_results
from arxiv_graph.graph.builder import build_graph, compute_pagerank
from arxiv_graph.graph.scorer import update_scores
from arxiv_graph.storage.db import get_session
from arxiv_graph.storage.models import Paper, PaperRelation

_MAX_PAPERS = 10_000


def _prune_papers(session: Session) -> None:
    """중요도 낮은 논문을 삭제해 DB를 _MAX_PAPERS 이하로 유지한다."""
    total = session.query(Paper).count()
    if total <= _MAX_PAPERS:
        logger.info(f"Paper count {total} ≤ {_MAX_PAPERS} — no pruning needed")
        return

    excess = total - _MAX_PAPERS
    to_delete = (
        session.query(Paper)
        .order_by(Paper.importance_score.asc())
        .limit(excess)
        .all()
    )
    ids_to_delete = [p.arxiv_id for p in to_delete]

    # PaperRelation 먼저 제거 (FK 제약)
    session.query(PaperRelation).filter(
        PaperRelation.source_id.in_(ids_to_delete)
        | PaperRelation.target_id.in_(ids_to_delete)
    ).delete(synchronize_session=False)

    for paper in to_delete:
        session.delete(paper)

    session.commit()
    logger.info(f"Pruned {len(ids_to_delete)} papers — DB now at {total - len(ids_to_delete)}")


def run_daily_job() -> None:
    logger.info("=== Daily ArXiv Graph Job START ===")
    session = get_session()

    try:
        # 1. Crawl
        results = list(fetch_recent_papers())
        if not results:
            logger.warning("No new papers fetched — skipping graph update")
            return

        # 2. Ingest into DB
        ingest_results(results, session)

        # 3. Build graph + compute PageRank
        G = build_graph(session)
        pageranks = compute_pagerank(G)

        # 4. Update importance scores
        update_scores(session, pageranks)

        # 5. 만개 초과 시 중요도 낮은 순으로 pruning
        _prune_papers(session)

        logger.info("=== Daily ArXiv Graph Job DONE ===")
    except Exception:
        logger.exception("Job failed")
        raise
    finally:
        session.close()
