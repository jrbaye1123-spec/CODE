"""Lawful refusal: when VaultLens should say "insufficient evidence."

Refusal is not failure — it is the correct response when the sovereign
graph lacks sufficient evidence to ground an answer. This module provides
refusal generation and proposal suggestions for filling gaps.
"""

from .schema import GroundedAnswer, Claim


REFUSAL_TEMPLATES = {
    "no_seeds": "Insufficient evidence: no relevant notes found in the sovereign graph.",
    "no_edges": "Insufficient evidence: relevant notes exist but no typed relationships connect them.",
    "all_nullified": "Insufficient evidence: all supporting edges have been nullified or retracted.",
    "no_variant_match": "Insufficient evidence: no edges of the requested variant type ({variants}) connect the relevant notes.",
    "below_confidence": "Insufficient evidence: available edges are below the confidence threshold ({threshold:.0%}).",
    "generic": "Insufficient evidence in sovereign graph.",
}


def build_refusal(reason: str = "generic", **kwargs) -> GroundedAnswer:
    """Build a lawful refusal answer.

    Args:
        reason: One of 'no_seeds', 'no_edges', 'all_nullified', 'no_variant_match',
                'below_confidence', 'generic'
        **kwargs: Format arguments for the template

    Returns:
        GroundedAnswer with insufficient_evidence=True
    """
    template = REFUSAL_TEMPLATES.get(reason, REFUSAL_TEMPLATES["generic"])
    answer_text = template.format(**kwargs)

    uncertainties = [answer_text]
    if reason == "no_seeds":
        uncertainties.append("Try broader search terms or check note titles.")
    elif reason == "no_edges":
        uncertainties.append("Consider adding typed relationships between these notes.")
    elif reason == "no_variant_match":
        uncertainties.append(f"Available variants may not include the requested type.")

    return GroundedAnswer(
        answer_text=answer_text,
        claims=[],
        uncertainties=uncertainties,
        insufficient_evidence=True,
    )


def should_refuse(nodes: list[dict], edges: list[dict],
                  required_variants: list[str] = None,
                  min_edges: int = 1) -> tuple[bool, str]:
    """Determine if a retrieved subgraph is sufficient to answer.

    Returns (should_refuse, reason).
    """
    if not nodes:
        return True, "no_seeds"

    if not edges:
        return True, "no_edges"

    # Check if all edges are nullified
    active_edges = [e for e in edges
                    if e.get("status", "active") not in ("nullified", "retracted")]
    if not active_edges:
        return True, "all_nullified"

    # Check required variants
    if required_variants:
        matching = [e for e in active_edges
                    if e.get("variant", "") in required_variants]
        if not matching:
            return True, "no_variant_match"

    if len(active_edges) < min_edges:
        return True, "no_edges"

    return False, ""


def generate_gap_proposals(query: str, nodes: list[dict], edges: list[dict],
                           needed_variants: list[str] = None) -> list[dict]:
    """Generate edge proposals to fill gaps when evidence is insufficient.

    Returns list of proposal dicts suitable for the pending queue.
    """
    proposals = []
    needed = needed_variants or ["causal", "evidential"]

    node_titles = [n.get("title", n.get("note_id", "?")) for n in nodes[:5]]
    if not node_titles and query:
        node_titles = [query[:40]]  # Use query as fallback title when no nodes

    for variant in needed[:3]:
        if node_titles:
            proposals.append({
                "proposal_id": f"gap-{variant}-{hash(query) % 10000:04d}",
                "source_title": node_titles[0] if len(node_titles) > 0 else "Unknown",
                "target_title": node_titles[1] if len(node_titles) > 1 else query[:40],
                "relation": "links-to",
                "variant": variant,
                "confidence": 0.3,
                "evidence_span": f"Gap proposal from query: {query[:100]}",
                "rationale": f"Query required {variant} evidence but none found. Auto-generated gap proposal.",
                "proposer": "refusal-gap-detector",
                "status": "pending",
            })

    return proposals
