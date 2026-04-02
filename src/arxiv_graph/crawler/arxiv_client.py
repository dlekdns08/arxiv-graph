"""ArXiv API client for fetching cs.CL and cs.LG papers."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Iterator

import arxiv
from loguru import logger

# cs.CL = Computation and Language
# cs.LG = Machine Learning (optional companion)
DEFAULT_CATEGORIES = ["cs.CL", "cs.LG", "cs.AI"]
DEFAULT_MAX_RESULTS = 200


def fetch_recent_papers(
    categories: list[str] = DEFAULT_CATEGORIES,
    days_back: int = 1,
    max_results: int = DEFAULT_MAX_RESULTS,
) -> Iterator[arxiv.Result]:
    """Yield arXiv results published within the last `days_back` days."""
    since: date = datetime.utcnow().date() - timedelta(days=days_back)
    query = " OR ".join(f"cat:{c}" for c in categories)
    logger.info(f"Fetching papers since {since} | query: {query}")

    client = arxiv.Client(page_size=100, delay_seconds=3, num_retries=3)
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )

    count = 0
    for result in client.results(search):
        pub_date = result.published.date() if result.published else None
        if pub_date and pub_date < since:
            break
        count += 1
        yield result

    logger.info(f"Fetched {count} papers")
