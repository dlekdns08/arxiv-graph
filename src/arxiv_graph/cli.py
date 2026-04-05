"""Command-line interface for arxiv-graph."""

import typer
from loguru import logger

app = typer.Typer(name="arxiv-graph", help="ArXiv paper graph builder")


@app.command()
def crawl(
    days_back: int = typer.Option(1, "--days", help="How many days back to fetch"),
    max_results: int = typer.Option(500, "--max", help="Max papers per run"),
) -> None:
    """Run a one-shot crawl and graph update."""
    from arxiv_graph.crawler.arxiv_client import fetch_recent_papers
    from arxiv_graph.crawler.ingester import ingest_results
    from arxiv_graph.graph.builder import build_graph, compute_pagerank
    from arxiv_graph.graph.scorer import update_scores
    from arxiv_graph.storage.db import get_session

    from arxiv_graph.scheduler.job import _prune_papers

    session = get_session()
    results = list(fetch_recent_papers(days_back=days_back, max_results=max_results))
    ingest_results(results, session)
    G = build_graph(session)
    pageranks = compute_pagerank(G)
    update_scores(session, pageranks)
    _prune_papers(session)
    session.close()
    logger.info("Done.")


@app.command()
def schedule() -> None:
    """Start the daily scheduler (blocks forever)."""
    from arxiv_graph.scheduler.runner import start
    start()


@app.command()
def stats() -> None:
    """Print basic graph statistics from the DB."""
    from arxiv_graph.storage.db import get_session
    from arxiv_graph.storage.models import Paper, PaperRelation

    session = get_session()
    n_papers = session.query(Paper).count()
    n_relations = session.query(PaperRelation).count()

    top = (
        session.query(Paper)
        .order_by(Paper.importance_score.desc())
        .limit(10)
        .all()
    )

    typer.echo(f"Papers:    {n_papers}")
    typer.echo(f"Relations: {n_relations}")
    typer.echo("\nTop 10 by importance:")
    for i, p in enumerate(top, 1):
        typer.echo(f"  {i:>2}. [{p.importance_score:.4f}] {p.title[:80]}")

    session.close()


@app.command()
def enrich() -> None:
    """Backfill citation counts for all papers already in the DB via Semantic Scholar."""
    from arxiv_graph.crawler.semantic_scholar import fetch_citations
    from arxiv_graph.graph.builder import build_graph, compute_pagerank
    from arxiv_graph.graph.scorer import update_scores
    from arxiv_graph.storage.db import get_session
    from arxiv_graph.storage.models import Paper

    session = get_session()
    papers = session.query(Paper).all()
    if not papers:
        typer.echo("No papers in DB. Run 'arxiv-graph crawl' first.")
        session.close()
        return

    typer.echo(f"Fetching citations for {len(papers)} papers...")
    arxiv_ids = [p.arxiv_id.split("v")[0] for p in papers]
    citations = fetch_citations(arxiv_ids)

    updated = 0
    for paper in papers:
        base_id = paper.arxiv_id.split("v")[0]
        info = citations.get(base_id)
        if info:
            paper.citation_count = info.citation_count
            updated += 1
    session.commit()
    typer.echo(f"Updated citation counts for {updated} papers")

    # Recompute importance scores with new citation data
    G = build_graph(session)
    pageranks = compute_pagerank(G)
    update_scores(session, pageranks)
    session.close()
    typer.echo("Importance scores recalculated.")


def main() -> None:
    app()
