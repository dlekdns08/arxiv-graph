"""Build the paper graph: nodes (papers) + edges (semantic/author similarity)."""

from __future__ import annotations

from loguru import logger
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.orm import Session

from arxiv_graph.storage.models import Paper, PaperRelation

import networkx as nx
import numpy as np

_MODEL_NAME = "all-MiniLM-L6-v2"
_SEMANTIC_THRESHOLD = 0.5  # minimum cosine similarity for an edge
_AUTHOR_WEIGHT = 1.0


def build_graph(session: Session) -> nx.DiGraph:
    """Build and return a directed NetworkX graph from the DB."""
    papers: list[Paper] = session.query(Paper).all()
    if not papers:
        logger.warning("No papers in DB — returning empty graph")
        return nx.DiGraph()

    G = nx.DiGraph()

    # --- Nodes ---
    for p in papers:
        G.add_node(
            p.arxiv_id,
            title=p.title,
            importance=p.importance_score,
            published_at=str(p.published_at),
            categories=p.categories,
        )

    # --- Semantic edges ---
    _add_semantic_edges(G, papers, session)

    # --- Author co-occurrence edges ---
    _add_author_edges(G, papers, session)

    logger.info(
        f"Graph built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges"
    )
    return G


def _add_semantic_edges(
    G: nx.DiGraph, papers: list[Paper], session: Session
) -> None:
    logger.info("Computing semantic embeddings…")
    model = SentenceTransformer(_MODEL_NAME)
    texts = [f"{p.title}. {p.abstract[:500]}" for p in papers]
    embeddings = model.encode(texts, show_progress_bar=True, batch_size=64)

    sim_matrix: np.ndarray = cosine_similarity(embeddings)

    for i, src in enumerate(papers):
        for j, tgt in enumerate(papers):
            if i >= j:
                continue
            weight = float(sim_matrix[i, j])
            if weight < _SEMANTIC_THRESHOLD:
                continue

            G.add_edge(src.arxiv_id, tgt.arxiv_id, relation="semantic", weight=weight)

            # Persist to DB (upsert)
            _upsert_relation(session, src.arxiv_id, tgt.arxiv_id, "semantic", weight)

    session.commit()


def _add_author_edges(
    G: nx.DiGraph, papers: list[Paper], session: Session
) -> None:
    logger.info("Computing author co-occurrence edges…")
    author_to_papers: dict[str, list[str]] = {}
    for p in papers:
        for a in p.authors:
            author_to_papers.setdefault(a.name, []).append(p.arxiv_id)

    for author, arxiv_ids in author_to_papers.items():
        if len(arxiv_ids) < 2:
            continue
        for i in range(len(arxiv_ids)):
            for j in range(i + 1, len(arxiv_ids)):
                src, tgt = arxiv_ids[i], arxiv_ids[j]
                if G.has_edge(src, tgt) and G[src][tgt].get("relation") == "author":
                    G[src][tgt]["weight"] += _AUTHOR_WEIGHT
                else:
                    G.add_edge(src, tgt, relation="author", weight=_AUTHOR_WEIGHT)
                _upsert_relation(session, src, tgt, "author", _AUTHOR_WEIGHT)

    session.commit()


def _upsert_relation(
    session: Session,
    source_id: str,
    target_id: str,
    relation_type: str,
    weight: float,
) -> None:
    rel = (
        session.query(PaperRelation)
        .filter_by(source_id=source_id, target_id=target_id, relation_type=relation_type)
        .first()
    )
    if rel is None:
        rel = PaperRelation(
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
            weight=weight,
        )
        session.add(rel)
    else:
        rel.weight = weight


def compute_pagerank(G: nx.DiGraph) -> dict[str, float]:
    if G.number_of_nodes() == 0:
        return {}
    pr = nx.pagerank(G, weight="weight")
    # Normalize to [0, 1]
    max_pr = max(pr.values()) or 1.0
    return {k: v / max_pr for k, v in pr.items()}
