"""Hybrid retrieval: BM25 + vector seeds → RRF fusion → graph expansion.

Vectors are seed sources only. They never produce final context directly.
"""

from collections import defaultdict
from typing import Optional

import numpy as np


def reciprocal_rank_fusion(
    rankings: list[list[str]],
    k: int = 60,
) -> dict[str, float]:
    """Merge multiple ranked lists using Reciprocal Rank Fusion.

    Args:
        rankings: List of ranked note_id lists (best first)
        k: RRF constant (default 60, standard for IR)

    Returns:
        Dict mapping note_id → fused score
    """
    scores: dict[str, float] = defaultdict(float)

    for ranking in rankings:
        for rank, note_id in enumerate(ranking):
            scores[note_id] += 1.0 / (k + rank + 1)

    return dict(scores)


def should_use_vector(query: str) -> bool:
    """Decide whether vector seeds should supplement BM25 for this query.

    Returns False for queries with explicit signals (wikilinks, typed relations).
    Returns True for fuzzy/paraphrase queries where lexical mismatch is likely.
    """
    q = query.lower()

    # Explicit signals — BM25 + graph is sufficient
    explicit_signals = [
        "[[", "::", "note titled", "file named", "exact title",
    ]
    if any(signal in q for signal in explicit_signals):
        return False

    # Fuzzy signals — embeddings may help with vocabulary mismatch
    fuzzy_signals = [
        "why", "how", "closest to", "similar", "related",
        "trace", "origin", "instrument", "activity",
        "weaken", "strengthen", "story", "channel",
        "transmission", "observations", "back the idea",
        "triggered", "steer", "deploy", "metric",
        "primary documents", "informed", "concept is",
        "fall in", "pull back", "purchasing",
    ]
    return any(signal in q for signal in fuzzy_signals)


def fuse_seeds(
    bm25_hits: list[str],
    vector_hits: list[str],
    use_vector: bool = True,
    rrf_k: int = 60,
    max_seeds: int = 20,
) -> list[str]:
    """Fuse BM25 and vector hit lists into ranked seed note IDs.

    Args:
        bm25_hits: BM25-ranked note IDs
        vector_hits: Vector-ranked note IDs
        use_vector: Whether to include vector hits (router decision)
        rrf_k: RRF constant
        max_seeds: Max seeds to return

    Returns:
        Ranked list of seed note IDs
    """
    rankings = [bm25_hits]
    if use_vector and vector_hits:
        rankings.append(vector_hits)

    if len(rankings) == 1:
        return bm25_hits[:max_seeds]

    fused = reciprocal_rank_fusion(rankings, k=rrf_k)
    sorted_seeds = sorted(fused.items(), key=lambda x: x[1], reverse=True)
    return [nid for nid, _ in sorted_seeds[:max_seeds]]
