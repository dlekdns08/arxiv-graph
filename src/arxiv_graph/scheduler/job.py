"""Daily crawl-and-build job."""

from __future__ import annotations

from loguru import logger

from arxiv_graph.crawler.arxiv_client import fetch_recent_papers
from arxiv_graph.crawler.ingester import ingest_results
from arxiv_graph.graph.builder import build_graph, compute_pagerank
from arxiv_graph.graph.scorer import update_scores
from arxiv_graph.storage.db import get_session


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

        logger.info("=== Daily ArXiv Graph Job DONE ===")
    except Exception:
        logger.exception("Job failed")
        raise
    finally:
        session.close()
