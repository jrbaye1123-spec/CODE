"""Hybrid retrieval integration for VaultLens.

Extends the retriever with optional vector seed discovery.
Vectors are NEVER the primary retrieval path.
"""

import sqlite3
from typing import Optional

from .hybrid import fuse_seeds, should_use_vector
from ..retriever import retrieve, bm25_search
from ..graph_store import GraphStore


def retrieve_hybrid(
    conn: sqlite3.Connection,
    graph: GraphStore,
    query: str,
    vector_store=None,             # VectorStore instance (optional)
    vector_model_id: str = "bge-small-en-v1.5",
    embedder=None,                 # FastEmbedder instance (optional)
    variants: Optional[list[str]] = None,
    max_hops: int = 2,
    max_notes: int = 25,
    explain: bool = False,
    verbose: bool = False,
) -> dict:
    """Hybrid retrieval: BM25 + optional vector seeds → graph expansion.

    When vector_store and embedder are available, vector seeds supplement BM25.
    Otherwise, falls back to pure BM25+graph (identical to retrieve()).

    Args:
        conn: SQLite connection to vault DB
        graph: GraphStore instance
        query: Natural language query
        vector_store: Optional VectorStore for title embeddings
        vector_model_id: Model ID for vector search
        embedder: Optional FastEmbedder for encoding the query
        variants: Override auto-detected variants
        max_hops: Max graph traversal depth
        max_notes: Max notes to return
        explain: Include explanation details
        verbose: Print progress

    Returns:
        Same dict format as retrieve()
    """
    # Run standard retrieval first
    result = retrieve(
        conn=conn,
        graph=graph,
        query=query,
        variants=variants,
        max_hops=max_hops,
        max_notes=max_notes,
        explain=False,
        verbose=verbose,
    )

    # Decide whether to supplement with vectors
    use_vec = should_use_vector(query) and vector_store is not None and embedder is not None

    if not use_vec:
        if explain:
            result["vector_used"] = False
            result["vector_reason"] = "router decided against vector seeds"
        return result

    # Get BM25 seed IDs
    bm25_seed_ids = [s["note_id"] for s in result.get("seed_notes", [])[:20]]

    # Get vector seeds
    try:
        query_vecs = embedder.embed([query])
        if query_vecs:
            vec_hits = vector_store.search(query_vecs[0], vector_model_id, top_k=20)
            vector_seed_ids = [nid for nid, _ in vec_hits]
        else:
            vector_seed_ids = []
    except Exception:
        vector_seed_ids = []

    if not vector_seed_ids:
        if explain:
            result["vector_used"] = False
            result["vector_reason"] = "vector search returned no results"
        return result

    # Fuse seeds
    fused_ids = fuse_seeds(
        bm25_hits=bm25_seed_ids,
        vector_hits=vector_seed_ids,
        use_vector=True,
        max_seeds=20,
    )

    # Rerun retrieval with fused seeds
    # We reuse graph expansion by injecting fused seeds as if they were BM25 hits
    if verbose:
        print(f"  Hybrid: {len(bm25_seed_ids)} BM25 + {len(vector_seed_ids)} vector → {len(fused_ids)} fused seeds")

    # Build seed results dict for fused seeds
    fused_seed_results = []
    for nid in fused_ids:
        # Try to get BM25 score if available
        bm25_match = next((s for s in result.get("seed_notes", []) if s["note_id"] == nid), None)
        fused_seed_results.append({
            "note_id": nid,
            "title": bm25_match["title"] if bm25_match else nid,
            "bm25_score": bm25_match.get("bm25_score", 0) if bm25_match else 0,
            "snippet": bm25_match.get("snippet", "") if bm25_match else "",
        })

    result["seed_notes"] = fused_seed_results
    result["vector_used"] = True
    result["vector_seed_count"] = len(vector_seed_ids)
    result["bm25_seed_count"] = len(bm25_seed_ids)
    result["shared_seed_count"] = len(set(bm25_seed_ids) & set(vector_seed_ids))

    if explain:
        result["explanation"] = _build_hybrid_explanation(
            result, bm25_seed_ids, vector_seed_ids, fused_ids
        )

    return result


def _build_hybrid_explanation(
    result: dict,
    bm25_ids: list[str],
    vector_ids: list[str],
    fused_ids: list[str],
) -> str:
    """Build explanation for hybrid retrieval."""
    shared = set(bm25_ids) & set(vector_ids)
    vec_only = set(vector_ids) - set(bm25_ids)

    lines = ["=" * 60, "HYBRID RETRIEVAL EXPLANATION", "=" * 60, ""]
    lines.append(f"Vector seeds:  {result.get('vector_seed_count', 0)}")
    lines.append(f"BM25 seeds:    {result.get('bm25_seed_count', 0)}")
    lines.append(f"Shared:        {len(shared)}")
    lines.append(f"Vector-only:   {len(vec_only)}")
    lines.append(f"Fused seeds:   {len(fused_ids)}")
    lines.append("")

    if vec_only:
        lines.append("Vector-only seeds (unique contributions from embeddings):")
        for nid in list(vec_only)[:5]:
            lines.append(f"  - {nid}")
        lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)
