"""Persist fetched arXiv results into the database."""

from __future__ import annotations

import arxiv
from loguru import logger
from sqlalchemy.orm import Session

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
    return papers
