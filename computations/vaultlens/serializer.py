"""Serializer: formats retrieval results into structured LLM context."""


def serialize_context(result: dict) -> str:
    """Serialize retrieval results into an LLM-ready context block.

    Produces a structured markdown context suitable for passing to an LLM.
    Includes query, active variants, retrieved paths, note bodies, and edge provenance.

    Args:
        result: Dict from retriever.retrieve()

    Returns:
        Markdown-formatted context string
    """
    lines = []

    lines.append("## Retrieval Result")
    lines.append("")

    # Query info
    lines.append(f"**Query:** {result['query']}")
    variants = result.get("detected_variants", [])
    lines.append(f"**Active variants:** {', '.join(variants[:7])}")
    lines.append("")

    # Paths
    paths = result.get("paths", [])
    if paths:
        lines.append("### Paths")
        lines.append("")
        seen_paths = set()
        for path in paths:
            # Build a readable path string
            steps = []
            for edge in path:
                src = edge["source"]
                tgt = edge["target"]
                rel = edge["relation"]
                steps.append(f"[[{src}]] --{rel}--> [[{tgt}]]")
            path_str = "\n  ".join(steps)
            path_key = path_str
            if path_key not in seen_paths:
                seen_paths.add(path_key)
                lines.append(f"- {path_str}")
                lines.append("")
        if not seen_paths:
            lines.append("(No typed paths found between retrieved notes)")
            lines.append("")

    # Connecting edges
    edges = result.get("edges", [])
    if edges:
        lines.append("### Edge Provenance")
        lines.append("")
        for edge in edges[:20]:
            src = edge["source_note_id"]
            tgt = edge["target_note_id"]
            rel = edge["relation"]
            var = edge["variant"]
            conf = edge.get("confidence", 1.0)
            lines.append(f"- `{src}` --**{rel}**--> `{tgt}`  (variant: `{var}`, confidence: {conf:.2f})")
        lines.append("")

    # Notes
    lines.append("### Notes")
    lines.append("")

    ranked = result.get("retrieved_notes", [])
    for i, note in enumerate(ranked):
        title = note.get("title", note.get("note_id", "Unknown"))
        body = note.get("body", "")
        tags = note.get("tags", [])
        note_type = note.get("note_type", "")
        score = note.get("final_score", 0)
        dist = note.get("graph_distance", "?")

        lines.append(f"#### {i+1}. {title}")
        lines.append("")
        if note_type:
            lines.append(f"*Type: {note_type}*")
        if tags:
            lines.append(f"*Tags: {', '.join(tags)}*")
        lines.append(f"*Score: {score:.3f} | Graph distance: {dist}*")
        lines.append("")

        if body:
            # Truncate very long bodies
            if len(body) > 2000:
                body = body[:2000] + "\n\n... (truncated)"
            lines.append(body)
            lines.append("")

        lines.append("---")
        lines.append("")

    # Seed info
    seeds = result.get("seed_notes", [])
    if seeds:
        lines.append("### Seed Notes (BM25)")
        lines.append("")
        for seed in seeds[:5]:
            lines.append(f"- **{seed['title']}** (BM25: {seed.get('bm25_score', '?')})")
            snippet = seed.get("snippet", "")
            if snippet:
                lines.append(f"  {snippet}")
        lines.append("")

    return "\n".join(lines)


def serialize_json(result: dict) -> str:
    """Serialize retrieval results as JSON."""
    import json

    # Clean up for JSON serialization (remove large bodies from metadata)
    clean_result = {
        "query": result["query"],
        "detected_variants": result["detected_variants"],
        "seed_notes": [
            {"note_id": s["note_id"], "title": s["title"], "bm25_score": s.get("bm25_score", 0)}
            for s in result.get("seed_notes", [])
        ],
        "retrieved_notes": [
            {
                "note_id": n["note_id"],
                "title": n.get("title", ""),
                "final_score": n.get("final_score", 0),
                "graph_distance": n.get("graph_distance", "?"),
                "body": n.get("body", "")[:500],
                "tags": n.get("tags", []),
                "note_type": n.get("note_type", ""),
            }
            for n in result.get("retrieved_notes", [])
        ],
        "paths_count": len(result.get("paths", [])),
        "edges_count": len(result.get("edges", [])),
    }
    return json.dumps(clean_result, indent=2)
