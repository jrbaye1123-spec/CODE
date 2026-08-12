"""Retriever: coordinates BM25 seed retrieval + variant-aware graph expansion.

This is the core retrieval pipeline that avoids single-vector embeddings.
"""

import sqlite3
from typing import Optional

from .graph_store import GraphStore, Edge
from .query_router import analyze_query


def bm25_search(conn: sqlite3.Connection, query: str, limit: int = 20) -> list[dict]:
    """Search notes using SQLite FTS5 (BM25 scoring).

    Args:
        conn: SQLite connection
        query: Search query string
        limit: Maximum results

    Returns:
        List of {note_id, title, bm25_score, body_snippet}
    """
    # Sanitize query for FTS5
    safe_query = query.replace('"', '""')

    try:
        cursor = conn.execute("""
            SELECT n.note_id, n.title, bm25(notes_fts) as score,
                   snippet(notes_fts, 1, '<mark>', '</mark>', '...', 40) as snippet
            FROM notes_fts f
            JOIN notes n ON f.note_id = n.note_id
            WHERE notes_fts MATCH ?
            ORDER BY score
            LIMIT ?
        """, (safe_query, limit))
        results = []
        for row in cursor:
            results.append({
                "note_id": row[0],
                "title": row[1],
                "bm25_score": row[2],
                "snippet": row[3],
            })
        return results
    except sqlite3.OperationalError:
        # Fallback: LIKE search if FTS match fails
        terms = [t for t in query.lower().split() if len(t) > 2]
        if not terms:
            return []
        conditions = " OR ".join(["n.title LIKE ? OR n.body LIKE ?"] * len(terms))
        params = []
        for t in terms:
            params.extend([f"%{t}%", f"%{t}%"])
        cursor = conn.execute(f"""
            SELECT n.note_id, n.title, 0.5 as score,
                   substr(n.body, 1, 200) as snippet
            FROM notes n
            WHERE {conditions}
            LIMIT ?
        """, (*params, limit))
        results = []
        for row in cursor:
            results.append({
                "note_id": row[0],
                "title": row[1],
                "bm25_score": row[2],
                "snippet": row[3],
            })
        return results


def get_note_by_id(conn: sqlite3.Connection, note_id: str) -> Optional[dict]:
    """Retrieve a single note by ID."""
    cursor = conn.execute("""
        SELECT note_id, file_path, title, aliases, tags, note_type, body
        FROM notes WHERE note_id = ?
    """, (note_id,))
    row = cursor.fetchone()
    if not row:
        return None
    import json
    return {
        "note_id": row[0],
        "file_path": row[1],
        "title": row[2],
        "aliases": json.loads(row[3] or "[]"),
        "tags": json.loads(row[4] or "[]"),
        "note_type": row[5],
        "body": row[6],
    }


def get_edges_between(conn: sqlite3.Connection, note_ids: list[str],
                      variants: Optional[set[str]] = None) -> list[dict]:
    """Get edges connecting any pair of the given note IDs."""
    if not note_ids:
        return []
    placeholders = ",".join(["?"] * len(note_ids))
    query = f"""
        SELECT source_note_id, target_note_id, relation, variant, text_span, confidence
        FROM edges
        WHERE source_note_id IN ({placeholders})
          AND target_note_id IN ({placeholders})
          AND resolved = 1
    """
    params = list(note_ids) + list(note_ids)
    if variants:
        v_placeholders = ",".join(["?"] * len(variants))
        query += f" AND variant IN ({v_placeholders})"
        params += list(variants)

    cursor = conn.execute(query, params)
    return [
        {
            "source_note_id": row[0],
            "target_note_id": row[1],
            "relation": row[2],
            "variant": row[3],
            "text_span": row[4],
            "confidence": row[5],
        }
        for row in cursor
    ]


def retrieve(
    conn: sqlite3.Connection,
    graph: GraphStore,
    query: str,
    variants: Optional[list[str]] = None,
    max_hops: int = 2,
    max_notes: int = 25,
    explain: bool = False,
    verbose: bool = False,
) -> dict:
    """Execute the full retrieval pipeline.

    Pipeline stages:
    1. Query analysis (detect variants, key terms)
    2. BM25 seed retrieval
    3. Graph expansion through selected variants
    4. Reranking (BM25 + graph proximity)
    5. Context serialization

    Args:
        conn: SQLite connection
        graph: GraphStore instance (must be loaded)
        query: Natural language query
        variants: Override auto-detected variants
        max_hops: Max graph traversal depth
        max_notes: Max notes to return
        explain: Include explanation details
        verbose: Print progress

    Returns:
        Dict with 'query', 'detected_variants', 'seed_notes', 'retrieved_notes',
        'paths', 'edges', 'explanation' (if explain=True)
    """
    # Stage 1: Query analysis
    if variants is None:
        analysis = analyze_query(query, verbose=verbose)
        variants = analysis["variants"]
    else:
        analysis = analyze_query(query, verbose=False)
        analysis["variants"] = variants

    variant_set: set[str] = set(variants)
    if verbose:
        print(f"\n  Variants: {', '.join(variants[:5])}")

    # Stage 2: BM25 seed retrieval
    seed_results = bm25_search(conn, query, limit=20)
    if verbose:
        print(f"  BM25 seeds: {len(seed_results)}")

    if not seed_results:
        return {
            "query": query,
            "detected_variants": variants,
            "seed_notes": [],
            "retrieved_notes": [],
            "paths": [],
            "edges": [],
        }

    seed_ids = [s["note_id"] for s in seed_results]

    # Stage 3: Graph expansion
    graph.load()
    visited, paths = graph.expand(
        seeds=seed_ids,
        variants=variant_set,
        max_hops=max_hops,
        max_nodes=max_notes,
    )

    if verbose:
        print(f"  Graph nodes visited: {len(visited)}")
        print(f"  Paths found: {len(paths)}")

    # Stage 4: Rerank - combine BM25 + graph proximity
    # Build scored candidates
    candidates: dict[str, dict] = {}

    for seed in seed_results:
        nid = seed["note_id"]
        candidates[nid] = {
            "note_id": nid,
            "title": seed["title"],
            "bm25_score": seed.get("bm25_score", 0),
            "snippet": seed.get("snippet", ""),
            "graph_distance": 0,  # seeds are distance 0
            "final_score": 0,
        }

    for nid, dist in visited.items():
        if nid not in candidates:
            note = get_note_by_id(conn, nid)
            if note:
                # Graph-only nodes get a base BM25 score
                candidates[nid] = {
                    "note_id": nid,
                    "title": note["title"],
                    "bm25_score": 0.1,  # graph-only bonus
                    "snippet": note.get("body", "")[:200],
                    "graph_distance": dist,
                    "final_score": 0,
                }

    # Score: BM25 (55%) + graph proximity (25%) + variant bonus (15%) + freshness (5%)
    max_bm25 = max((c["bm25_score"] for c in candidates.values()), default=1.0) or 1.0
    max_dist = max((c["graph_distance"] for c in candidates.values()), default=1) or 1

    for nid, cand in candidates.items():
        bm25_norm = cand["bm25_score"] / max_bm25 if max_bm25 else 0
        proximity_norm = 1.0 - (cand["graph_distance"] / (max_dist + 1))

        # Check if note has edges matching the selected variants
        variant_bonus = 0.0
        if cand["graph_distance"] > 0:
            # Notes reached through graph traversal get variant bonus
            variant_bonus = 1.0
        elif cand["graph_distance"] == 0:
            # Seeds that also have matching variant edges
            outgoing = graph.get_outgoing(nid, variant_set)
            incoming = graph.get_incoming(nid, variant_set)
            if outgoing or incoming:
                variant_bonus = 0.5

        cand["final_score"] = (
            0.55 * bm25_norm +
            0.25 * proximity_norm +
            0.15 * variant_bonus +
            0.05 * 1.0  # freshness placeholder
        )
        cand["variant_bonus"] = variant_bonus

    # Sort by final score
    ranked = sorted(candidates.values(), key=lambda c: c["final_score"], reverse=True)

    # Limit
    ranked = ranked[:max_notes]

    # Get the full note bodies for top results
    for cand in ranked:
        note = get_note_by_id(conn, cand["note_id"])
        if note:
            cand["body"] = note["body"]
            cand["tags"] = note["tags"]
            cand["note_type"] = note["note_type"]

    # Get connecting edges among retrieved notes
    retrieved_ids = [r["note_id"] for r in ranked]
    connecting_edges = get_edges_between(conn, retrieved_ids, variant_set)

    result = {
        "query": query,
        "detected_variants": variants,
        "seed_notes": seed_results[:10],
        "retrieved_notes": ranked,
        "paths": [
            [{"source": e.source_note_id, "target": e.target_note_id,
              "relation": e.relation, "variant": e.variant}
             for e in path]
            for path in paths[:20]
        ],
        "edges": connecting_edges,
    }

    if explain:
        result["explanation"] = _build_explanation(ranked, seed_results, variants, paths)

    return result


def _build_explanation(
    ranked: list[dict],
    seeds: list[dict],
    variants: list[str],
    paths: list,
) -> str:
    """Build a human-readable explanation of the retrieval."""
    lines = []
    lines.append("=" * 60)
    lines.append("RETRIEVAL EXPLANATION")
    lines.append("=" * 60)
    lines.append(f"")
    lines.append(f"Active variants: {', '.join(variants)}")
    lines.append(f"BM25 seed notes: {len(seeds)}")
    lines.append(f"Graph paths found: {len(paths)}")
    lines.append(f"")
    lines.append(f"--- Top Retrieved Notes ---")
    for i, note in enumerate(ranked[:10]):
        score = note.get("final_score", 0)
        bm25 = note.get("bm25_score", 0)
        dist = note.get("graph_distance", "?")
        title = note.get("title", note.get("note_id", "unknown"))
        lines.append(f"")
        lines.append(f"  #{i+1}: {title}")
        lines.append(f"      Final score: {score:.3f} | BM25: {bm25:.3f} | Graph dist: {dist}")
        if note.get("graph_distance", 0) == 0:
            lines.append(f"      Source: BM25 seed match")
        else:
            lines.append(f"      Source: Graph expansion ({dist} hop(s))")

    if paths:
        lines.append(f"")
        lines.append(f"--- Sample Paths ---")
        for i, path in enumerate(paths[:5]):
            path_str = " -> ".join(
                f"[{e['source']}] --{e['relation']}--> [{e['target']}]"
                for e in path
            )
            lines.append(f"  Path {i+1}: {path_str}")

    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)
