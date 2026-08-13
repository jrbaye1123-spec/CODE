"""Proposer: generates typed edge proposals from ordinary note text.

Two modes:
- heuristic: regex/pattern-based extraction
- llm: delegates to an LLM (optional)

Proposals are stored in SQLite for review, not applied automatically.
"""

import re
import json
import hashlib
from dataclasses import dataclass, field
from typing import Optional

from .parser import VARIANT_MAP, RELATION_TO_VARIANT, _generate_note_id


# ── Heuristic patterns ──────────────────────────────────────────────

# Pattern: "[Source] relation [Target]" in free text
# Each entry: (regex, relation, variant)
CAUSAL_PATTERNS: list[tuple[str, str]] = [
    (r"(\b[A-Z][a-zA-Z ]{3,40}?)\s+(causes?|leads to|results in|triggers?|brings about|produces?)\s+(\b[A-Z][a-zA-Z ]{3,40}?)", "causes"),
    (r"(\b[A-Z][a-zA-Z ]{3,40}?)\s+(reduces?|lowers?|decreases?|diminishes?)\s+(\b[A-Z][a-zA-Z ]{3,40}?)", "causes"),
    (r"(\b[A-Z][a-zA-Z ]{3,40}?)\s+(increases?|raises?|boosts?|amplifies?)\s+(\b[A-Z][a-zA-Z ]{3,40}?)", "causes"),
    (r"(\b[A-Z][a-zA-Z ]{3,40}?)\s+(prevents?|blocks?|inhibits?|stops?)\s+(\b[A-Z][a-zA-Z ]{3,40}?)", "prevents"),
    (r"(\b[A-Z][a-zA-Z ]{3,40}?)\s+(enables?|allows?|facilitates?|permits?)\s+(\b[A-Z][a-zA-Z ]{3,40}?)", "enables"),
]

EVIDENTIAL_PATTERNS: list[tuple[str, str]] = [
    (r"(\b[A-Z][a-zA-Z ]{3,40}?)\s+(supports?|confirms?|validates?|corroborates?)\s+(\b[A-Z][a-zA-Z ]{3,40}?)", "supports"),
    (r"(\b[A-Z][a-zA-Z ]{3,40}?)\s+(contradicts?|refutes?|disproves?|challenges?)\s+(\b[A-Z][a-zA-Z ]{3,40}?)", "refutes"),
    (r"evidence\s+(?:from|in)\s+(\b[A-Z][a-zA-Z ]{3,40}?)\s+(?:shows?|suggests?|indicates?)\s+(\b[A-Z][a-zA-Z ]{3,40}?)", "supports"),
]

PROVENANCE_PATTERNS: list[tuple[str, str]] = [
    (r"(\b[A-Z][a-zA-Z ]{3,40}?)\s+(?:is |was )?(?:based on|derived from|taken from|sourced from)\s+(\b[A-Z][a-zA-Z ]{3,40}?)", "derived-from"),
    (r"(\b[A-Z][a-zA-Z ]{3,40}?)\s+(?:according to|as stated in|as reported by|per)\s+(\b[A-Z][a-zA-Z ]{3,40}?)", "derived-from"),
    (r"(\b[A-Z][a-zA-Z ]{3,40}?)\s+(?:cited by|referenced in|quoted in)\s+(\b[A-Z][a-zA-Z ]{3,40}?)", "cited-by"),
]

TEMPORAL_PATTERNS: list[tuple[str, str]] = [
    (r"(\b[A-Z][a-zA-Z ]{3,40}?)\s+(?:occurred |happened |came )?(before|prior to|preceding)\s+(\b[A-Z][a-zA-Z ]{3,40}?)", "precedes"),
    (r"(\b[A-Z][a-zA-Z ]{3,40}?)\s+(?:occurred |happened |came )?(after|following|subsequent to)\s+(\b[A-Z][a-zA-Z ]{3,40}?)", "follows"),
    (r"(\b[A-Z][a-zA-Z ]{3,40}?)\s+(?:was )?(followed by|succeeded by)\s+(\b[A-Z][a-zA-Z ]{3,40}?)", "precedes"),
    (r"(\b[A-Z][a-zA-Z ]{3,40}?)\s+then\s+(\b[A-Z][a-zA-Z ]{3,40}?)", "precedes"),
]

HIERARCHICAL_PATTERNS: list[tuple[str, str]] = [
    (r"(\b[A-Z][a-zA-Z ]{3,40}?)\s+(?:is |are )?(?:a |an )?(?:part of|component of|element of|subset of)\s+(\b[A-Z][a-zA-Z ]{3,40}?)", "part-of"),
    (r"(\b[A-Z][a-zA-Z ]{3,40}?)\s+(?:is |are )?(?:a |an )?(?:type of|kind of|form of|instance of)\s+(\b[A-Z][a-zA-Z ]{3,40}?)", "is-a"),
    (r"(\b[A-Z][a-zA-Z ]{3,40}?)\s+(?:depends on|relies on|requires?)\s+(\b[A-Z][a-zA-Z ]{3,40}?)", "depends-on"),
    (r"(\b[A-Z][a-zA-Z ]{3,40}?)\s+(?:consists of|comprises|contains?|includes?)\s+(\b[A-Z][a-zA-Z ]{3,40}?)", "part-of"),  # reversed later
]

PROCEDURAL_PATTERNS: list[tuple[str, str]] = [
    (r"(\b[A-Z][a-zA-Z ]{3,40}?)\s+(?:is |are )?(?:input to|fed into|passed to)\s+(\b[A-Z][a-zA-Z ]{3,40}?)", "input-to"),
    (r"(\b[A-Z][a-zA-Z ]{3,40}?)\s+(?:outputs?|produces?|generates?|yields?)\s+(\b[A-Z][a-zA-Z ]{3,40}?)", "output-of"),
    (r"before\s+(\b[A-Z][a-zA-Z ]{3,40}?),\s+(\b[A-Z][a-zA-Z ]{3,40}?)", "step-before"),
    (r"first\s+(\b[A-Z][a-zA-Z ]{3,40}?),\s+then\s+(\b[A-Z][a-zA-Z ]{3,40}?)", "step-before"),
]

SEMANTIC_PATTERNS: list[tuple[str, str]] = [
    (r"(\b[A-Z][a-zA-Z ]{3,40}?)\s+(?:is |are )?(?:similar to|like|analogous to|comparable to)\s+(\b[A-Z][a-zA-Z ]{3,40}?)", "similar-to"),
    (r"(\b[A-Z][a-zA-Z ]{3,40}?)\s+(?:in contrast to|unlike|as opposed to|differs from)\s+(\b[A-Z][a-zA-Z ]{3,40}?)", "contrasts-with"),
]

ALL_PATTERNS: list[tuple[str, str, str]] = []
for variant, patterns in [
    ("causal", CAUSAL_PATTERNS),
    ("evidential", EVIDENTIAL_PATTERNS),
    ("provenance", PROVENANCE_PATTERNS),
    ("temporal", TEMPORAL_PATTERNS),
    ("hierarchical", HIERARCHICAL_PATTERNS),
    ("procedural", PROCEDURAL_PATTERNS),
    ("semantic", SEMANTIC_PATTERNS),
]:
    for pattern, relation in patterns:
        ALL_PATTERNS.append((variant, pattern, relation))


# ── Stop words / noise phrases to filter ────────────────────────────
NOISE_PHRASES = {
    "the following", "this paper", "our results", "the study", "this work",
    "the data", "these findings", "the analysis", "the model", "the system",
    "previous work", "future work", "the method", "our approach",
}


def _clean_phrase(text: str) -> str:
    """Normalize a matched phrase: strip articles, lowercase, reasonable length."""
    text = text.strip()
    text = re.sub(r"^(the |a |an )", "", text, flags=re.IGNORECASE)
    text = text.strip().rstrip(".,;:!?")
    return text


def _is_noise(phrase: str) -> bool:
    """Check if a phrase is likely noise."""
    low = phrase.lower().strip()
    if low in NOISE_PHRASES:
        return True
    if len(low) < 4:
        return True
    if re.match(r"^(this|that|these|those|the|a|an|our|my|your|its|their)\b", low):
        return True
    return False


@dataclass
class EdgeProposal:
    """A proposed typed edge between notes."""
    proposal_id: str
    source_title: str
    target_title: str
    relation: str
    variant: str
    confidence: float = 0.5
    evidence_span: str = ""
    rationale: str = ""
    proposer: str = "heuristic"
    source_note_id: Optional[str] = None
    target_note_id: Optional[str] = None


def propose_heuristic(body: str, title: str) -> list[EdgeProposal]:
    """Generate edge proposals from note body using heuristic patterns.

    Args:
        body: The note body text
        title: The note title (used as default source for patterns
               where the note itself is the source)

    Returns:
        List of EdgeProposal objects
    """
    proposals: list[EdgeProposal] = []

    for variant, pattern, relation in ALL_PATTERNS:
        for m in re.finditer(pattern, body, re.IGNORECASE):
            groups = m.groups()

            # Determine source and target from pattern groups
            if len(groups) == 2:
                source = groups[0].strip()
                target = groups[1].strip()
            elif len(groups) == 3:
                source = groups[0].strip()
                target = groups[2].strip()
                # groups[1] is the relation word
            else:
                continue

            source_clean = _clean_phrase(source)
            target_clean = _clean_phrase(target)

            if _is_noise(source_clean) or _is_noise(target_clean):
                continue

            # Skip if source/target are the same after cleaning
            if source_clean.lower() == target_clean.lower():
                continue

            # Skip if source or target is the note's own title (self-loops)
            if source_clean.lower() == title.lower() or target_clean.lower() == title.lower():
                continue

            # Handle "contains", "comprises" patterns (reversed direction)
            actual_relation = relation
            actual_source = source_clean
            actual_target = target_clean
            if relation == "part-of" and re.search(r"consists of|comprises|contains?|includes?", m.group(0), re.IGNORECASE):
                # "X contains Y" → Y part-of X
                actual_source = target_clean
                actual_target = source_clean

            evidence = m.group(0).strip()
            # Truncate long evidence spans
            if len(evidence) > 200:
                evidence = evidence[:200] + "..."

            # Compute confidence based on pattern specificity
            confidence = 0.55  # baseline for regex match
            if len(evidence.split()) > 6:
                confidence += 0.05  # longer match = more specific
            if re.search(r"\b(the|a|an)\b", evidence, re.IGNORECASE):
                confidence += 0.05  # article suggests noun phrase
            confidence = min(confidence, 0.85)

            # Generate stable proposal ID
            prop_id = hashlib.md5(
                f"{title}|{actual_source}|{actual_relation}|{actual_target}".encode(),
                usedforsecurity=False
            ).hexdigest()[:12]

            proposals.append(EdgeProposal(
                proposal_id=prop_id,
                source_title=actual_source,
                target_title=actual_target,
                relation=actual_relation,
                variant=variant,
                confidence=round(confidence, 2),
                evidence_span=evidence,
                rationale=f"Pattern '{pattern}' matched in body",
                proposer="heuristic",
            ))

    return proposals


def propose_from_text(body: str, title: str = "", mode: str = "heuristic",
                      min_confidence: float = 0.5,
                      allowed_variants: Optional[set[str]] = None) -> list[EdgeProposal]:
    """Main entry point: generate edge proposals from text.

    Args:
        body: Note body text
        title: Note title
        mode: 'heuristic' or 'llm'
        min_confidence: Minimum confidence threshold
        allowed_variants: Optional set of variant names to allow

    Returns:
        Filtered list of EdgeProposal
    """
    if mode == "heuristic":
        proposals = propose_heuristic(body, title)
    elif mode == "llm":
        proposals = propose_llm(body, title)
    else:
        raise ValueError(f"Unknown proposer mode: {mode}")

    # Filter by confidence
    proposals = [p for p in proposals if p.confidence >= min_confidence]

    # Filter by allowed variants
    if allowed_variants:
        proposals = [p for p in proposals if p.variant in allowed_variants]

    return proposals


def propose_llm(body: str, title: str = "") -> list[EdgeProposal]:
    """Generate proposals using an LLM. Requires OPENAI_API_KEY or similar.

    This is optional — the system works fine with heuristic mode only.
    Falls back to heuristic if no LLM is available.
    """
    import os
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        # Fall back to heuristic
        return propose_heuristic(body, title)

    prompt = f"""Analyze this text and extract typed relationships between concepts.

Return a JSON array of objects with these fields:
- source_title: the source concept (capitalized noun phrase)
- target_title: the target concept (capitalized noun phrase)
- relation: one of [causes, enables, prevents, supports, refutes, qualifies,
  precedes, follows, is-a, part-of, depends-on, similar-to, contrasts-with,
  derived-from, cited-by, input-to, output-of, step-before, links-to]
- variant: one of [causal, evidential, temporal, hierarchical, semantic,
  provenance, procedural, generic]
- confidence: a float 0.0-1.0
- evidence_span: the exact sentence that supports this relationship
- rationale: why this relationship was proposed

Only include relationships that are clearly stated.
Do not invent relationships that are not in the text.

Text title: {title}

Text:
{body[:3000]}

Return ONLY the JSON array, no other text."""

    try:
        import urllib.request
        provider = "openai" if os.environ.get("OPENAI_API_KEY") else "anthropic"

        if provider == "openai":
            req = urllib.request.Request(
                "https://api.openai.com/v1/chat/completions",
                data=json.dumps({
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 1000,
                }).encode(),
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
                raw = data["choices"][0]["message"]["content"]
        else:
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=json.dumps({
                    "model": "claude-3-haiku-20240307",
                    "max_tokens": 1000,
                    "messages": [{"role": "user", "content": prompt}],
                }).encode(),
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
                raw = data["content"][0]["text"]

        # Parse JSON from response
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```\w*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
        items = json.loads(raw)
        if isinstance(items, dict):
            items = [items]

        proposals = []
        for item in items:
            variant = item.get("variant", "generic")
            # Normalize variant
            if variant not in VARIANT_MAP:
                variant = RELATION_TO_VARIANT.get(item.get("relation", ""), "generic")

            prop_id = hashlib.md5(
                f"{title}|{item.get('source_title','')}|{item.get('relation','')}|{item.get('target_title','')}".encode(),
                usedforsecurity=False
            ).hexdigest()[:12]

            proposals.append(EdgeProposal(
                proposal_id=prop_id,
                source_title=item.get("source_title", ""),
                target_title=item.get("target_title", ""),
                relation=item.get("relation", "links-to"),
                variant=variant,
                confidence=float(item.get("confidence", 0.5)),
                evidence_span=item.get("evidence_span", ""),
                rationale=item.get("rationale", ""),
                proposer=f"llm-{provider}",
            ))
        return proposals

    except Exception:
        # Fall back to heuristic on any error
        return propose_heuristic(body, title)
