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
    # arXiv 제출일(result.published)이 발표일보다 1-3일 앞서는 경우가 있어
    # fetch 기준은 넉넉하게 잡고, 최종 필터를 원래 since로 유지한다.
    _ANNOUNCE_LAG = 3
    since: date = datetime.utcnow().date() - timedelta(days=days_back)
    fetch_since: date = since - timedelta(days=_ANNOUNCE_LAG)
    query = " OR ".join(f"cat:{c}" for c in categories)
    logger.info(f"Fetching papers since {since} (fetch_since={fetch_since}) | query: {query}")

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
    skipped = 0
    delay = _BACKOFF_BASE

    for attempt in range(_MAX_RETRIES):
        try:
            for result in client.results(search):
                pub_date = result.published.date() if result.published else None
                if pub_date and pub_date < fetch_since:
                    # arXiv의 정렬 키(발표일)와 result.published(제출일)이 다를 수 있어
                    # 첫 결과에서 즉시 break하면 실제 최신 논문을 놓칠 수 있음.
                    # 연속으로 5개 이상 오래된 논문이 나올 때만 중단.
                    skipped += 1
                    if skipped == 1:
                        logger.debug(f"Skipping old paper: {pub_date} < {since} (arxiv_id={result.entry_id})")
                    if skipped >= 5:
                        logger.debug(f"5 consecutive old papers — stopping early")
                        break
                    continue
                skipped = 0
                count += 1
                yield result
            if count == 0:
                logger.warning(
                    f"Fetched 0 papers (since={since}, skipped={skipped}). "
                    "arXiv may not have published new papers yet (weekend/holiday), "
                    "or there's a submission-announcement date gap."
                )
            else:
                logger.info(f"Fetched {count} papers (skipped {skipped} older than {since})")
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
