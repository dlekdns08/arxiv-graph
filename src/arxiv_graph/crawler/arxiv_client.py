"""ArXiv API client for fetching cs.CL and cs.LG papers."""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from typing import Iterator

import arxiv
from loguru import logger

DEFAULT_CATEGORIES = ["cs.CL", "cs.LG", "cs.AI"]
DEFAULT_MAX_RESULTS = 500

_INITIAL_DELAY = 5      # 첫 요청 전 대기 (초)
_MAX_RETRIES = 5
_BACKOFF_BASE = 30      # 429 발생 시 첫 대기 시간 (초)
_BACKOFF_MULT = 2       # 재시도마다 2배씩 증가


def fetch_recent_papers(
    categories: list[str] = DEFAULT_CATEGORIES,
    days_back: int = 1,
    max_results: int = DEFAULT_MAX_RESULTS,
) -> Iterator[arxiv.Result]:
    """Yield arXiv results published within the last `days_back` days."""
    since: date = datetime.utcnow().date() - timedelta(days=days_back)
    query = " OR ".join(f"cat:{c}" for c in categories)
    logger.info(f"Fetching papers since {since} | query: {query}")

    # arXiv API는 첫 요청에서도 rate limit에 걸릴 수 있음 — 선제적 대기
    logger.info(f"Waiting {_INITIAL_DELAY}s before first request...")
    time.sleep(_INITIAL_DELAY)

    client = arxiv.Client(page_size=100, delay_seconds=5, num_retries=1)
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )

    count = 0
    delay = _BACKOFF_BASE

    for attempt in range(_MAX_RETRIES):
        try:
            for result in client.results(search):
                pub_date = result.published.date() if result.published else None
                if pub_date and pub_date < since:
                    break
                count += 1
                yield result
            logger.info(f"Fetched {count} papers")
            return
        except arxiv.HTTPError as e:
            if e.status == 429:
                if attempt < _MAX_RETRIES - 1:
                    logger.warning(
                        f"arXiv 429 rate limit (attempt {attempt + 1}/{_MAX_RETRIES}). "
                        f"Waiting {delay}s..."
                    )
                    time.sleep(delay)
                    delay *= _BACKOFF_MULT
                else:
                    logger.error("arXiv 429: max retries exceeded. Giving up.")
                    raise
            else:
                raise
