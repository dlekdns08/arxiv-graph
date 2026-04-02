"""Semantic Scholar API client for enriching papers with citation counts.

Batch endpoint: POST https://api.semanticscholar.org/graph/v1/paper/batch
- Up to 500 papers per request
- Rate limit: 1 req/s (no key) | 10 req/s (free API key)
- Set env var SEMANTIC_SCHOLAR_API_KEY to use an API key
"""

from __future__ import annotations

import os
import time
from typing import NamedTuple

import httpx
from loguru import logger

_BATCH_URL = "https://api.semanticscholar.org/graph/v1/paper/batch"
_BATCH_SIZE = 500
_FIELDS = "citationCount,influentialCitationCount,externalIds"
_RATE_DELAY = 1.1  # seconds between requests without API key


class CitationInfo(NamedTuple):
    arxiv_id: str
    citation_count: int
    influential_count: int


def fetch_citations(arxiv_ids: list[str]) -> dict[str, CitationInfo]:
    """Fetch citation counts for a list of arXiv IDs.

    Returns a dict mapping arxiv_id → CitationInfo.
    Missing / errored papers are simply absent from the result.
    """
    if not arxiv_ids:
        return {}

    api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")
    headers: dict[str, str] = {}
    if api_key:
        headers["x-api-key"] = api_key

    results: dict[str, CitationInfo] = {}

    for i in range(0, len(arxiv_ids), _BATCH_SIZE):
        batch = arxiv_ids[i : i + _BATCH_SIZE]
        ids = [f"arXiv:{aid}" for aid in batch]

        try:
            resp = httpx.post(
                _BATCH_URL,
                json={"ids": ids},
                params={"fields": _FIELDS},
                headers=headers,
                timeout=30.0,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.warning(f"Semantic Scholar batch {i // _BATCH_SIZE + 1} failed: {e}")
            continue
        except httpx.RequestError as e:
            logger.warning(f"Semantic Scholar request error: {e}")
            continue

        for item in resp.json():
            if item is None:
                continue
            # external_id 역추적: Semantic Scholar는 externalIds 를 반환
            ext_ids = item.get("externalIds") or {}
            raw_aid = ext_ids.get("ArXiv") or ""
            if not raw_aid:
                continue
            # Semantic Scholar는 버전 없이 반환 (예: "2106.00573")
            results[raw_aid] = CitationInfo(
                arxiv_id=raw_aid,
                citation_count=item.get("citationCount") or 0,
                influential_count=item.get("influentialCitationCount") or 0,
            )

        logger.info(
            f"Semantic Scholar batch {i // _BATCH_SIZE + 1}: "
            f"{len(batch)} requested, {len(results)} total enriched so far"
        )

        if i + _BATCH_SIZE < len(arxiv_ids):
            delay = _RATE_DELAY if not api_key else 0.12
            time.sleep(delay)

    return results
