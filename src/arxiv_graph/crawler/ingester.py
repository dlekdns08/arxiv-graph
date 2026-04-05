"""Persist fetched arXiv results into the database."""

from __future__ import annotations

import arxiv
from loguru import logger
from sqlalchemy.orm import Session

from arxiv_graph.crawler.semantic_scholar import fetch_citations
from arxiv_graph.storage.models import Author, Paper


def ingest_results(results: list[arxiv.Result], session: Session) -> list[Paper]:
    """Upsert arXiv results into the DB and return Paper objects."""
    papers: list[Paper] = []

    for result in results:
        arxiv_id = result.entry_id.split("/")[-1]

        paper = session.get(Paper, arxiv_id)
        if paper is None:
            paper = Paper(arxiv_id=arxiv_id)
            session.add(paper)
            logger.debug(f"New paper: {arxiv_id}")
        else:
            logger.debug(f"Updating paper: {arxiv_id}")

        paper.title = result.title
        paper.abstract = result.summary
        paper.published_at = result.published
        paper.updated_at = result.updated
        paper.primary_category = result.primary_category
        paper.categories = ",".join(result.categories)
        paper.pdf_url = result.pdf_url

        # Upsert authors
        paper.authors = []
        for a in result.authors:
            name = a.name.strip()
            author = session.query(Author).filter_by(name=name).first()
            if author is None:
                author = Author(name=name)
                session.add(author)
            paper.authors.append(author)

        papers.append(paper)

    session.commit()
    logger.info(f"Ingested {len(papers)} papers")

    # Enrich with citation counts from Semantic Scholar
    arxiv_ids = [p.arxiv_id for p in papers]
    citations = fetch_citations(arxiv_ids)
    if citations:
        for paper in papers:
            # strip version suffix (e.g. "2106.00573v2" → "2106.00573")
            base_id = paper.arxiv_id.split("v")[0]
            info = citations.get(base_id)
            if info:
                paper.citation_count = info.citation_count
                paper.influential_citation_count = info.influential_count
        session.commit()
        logger.info(f"Enriched {len(citations)} papers with citation counts")

    return papers
