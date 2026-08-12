"""Query router: analyzes query intent and routes to appropriate graph variants."""

import re
from typing import Optional


def detect_variants(query: str) -> list[str]:
    """Analyze a natural language query and detect which graph variants to use.

    Uses keyword heuristics to match query intent to variant types.

    Args:
        query: Natural language query string

    Returns:
        List of variant names ordered by relevance (most likely first)
    """
    from .parser import QUERY_TRIGGERS

    query_lower = query.lower()
    variant_scores: dict[str, int] = {}

    for variant, triggers in QUERY_TRIGGERS.items():
        score = 0
        for trigger in triggers:
            if trigger.lower() in query_lower:
                score += 1
                # Bonus for trigger at start of query (stronger intent signal)
                if query_lower.startswith(trigger.lower()):
                    score += 2
        if score > 0:
            variant_scores[variant] = score

    # Sort by score descending
    ranked = sorted(variant_scores.keys(), key=lambda v: variant_scores[v], reverse=True)
    return ranked if ranked else ["generic", "causal"]  # Default when no clear signal


def detect_query_type(query: str) -> str:
    """Return a human-readable query type label.

    Args:
        query: Natural language query string

    Returns:
        Query type label (causal, temporal, evidential, etc.)
    """
    variants = detect_variants(query)
    if not variants:
        return "generic"

    type_map = {
        "causal": "Causal Reasoning",
        "temporal": "Temporal Sequence",
        "evidential": "Evidence Retrieval",
        "hierarchical": "Hierarchical Structure",
        "procedural": "Procedural / Workflow",
        "provenance": "Provenance Tracking",
        "semantic": "Semantic Similarity",
        "generic": "General Retrieval",
    }

    primary = variants[0]
    return type_map.get(primary, f"Multi-Variant ({', '.join(variants[:3])})")


def analyze_query(query: str, verbose: bool = False) -> dict:
    """Full query analysis: detect variants, extract key terms, classify.

    Args:
        query: Natural language query string
        verbose: Print analysis details

    Returns:
        Dict with 'variants', 'query_type', 'key_terms'
    """
    variants = detect_variants(query)
    query_type = detect_query_type(query)

    # Extract key terms (simple: nouns/phrases longer than 3 chars, not stopwords)
    stopwords = {"the", "a", "an", "is", "are", "was", "were", "what", "which",
                 "who", "whom", "where", "when", "why", "how", "does", "did",
                 "do", "can", "will", "would", "could", "should", "may", "might",
                 "and", "or", "but", "in", "on", "at", "to", "for", "of", "with",
                 "from", "by", "about", "as", "into", "through", "during", "before",
                 "after", "above", "below", "between", "under", "this", "that"}
    words = re.findall(r"\b[a-zA-Z]{3,}\b", query.lower())
    key_terms = [w for w in words if w not in stopwords]

    result = {
        "variants": variants,
        "query_type": query_type,
        "key_terms": key_terms,
    }

    if verbose:
        print(f"\n  Query Analysis:")
        print(f"    Type:     {query_type}")
        print(f"    Variants: {', '.join(variants[:5])}")
        print(f"    Terms:    {', '.join(key_terms[:10])}")
        if len(key_terms) > 10:
            print(f"              ... and {len(key_terms) - 10} more")

    return result
