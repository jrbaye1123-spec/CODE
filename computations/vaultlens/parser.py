"""Markdown parser: extracts structured data from markdown notes.

Handles:
- YAML frontmatter
- Wikilinks: [[Target]]
- Markdown links: [text](target)
- Typed inline relations: predicate:: [[Target]]
- Tags from frontmatter
"""

import re
import json
from dataclasses import dataclass, field
from typing import Optional


# Canonical relation predicates mapped to variants
VARIANT_MAP: dict[str, set[str]] = {
    "hierarchical": {"is-a", "part-of", "depends-on"},
    "temporal": {"precedes", "follows", "contemporaneous-with"},
    "causal": {"causes", "enables", "prevents"},
    "evidential": {"supports", "refutes", "qualifies"},
    "semantic": {"similar-to", "analogous-to", "contrasts-with"},
    "provenance": {"derived-from", "cited-by", "contradicts-source"},
    "procedural": {"input-to", "output-of", "step-before"},
}

# Reverse map: relation -> variant
RELATION_TO_VARIANT: dict[str, str] = {}
for variant, relations in VARIANT_MAP.items():
    for rel in relations:
        RELATION_TO_VARIANT[rel] = variant

# Keywords for query intent detection
QUERY_TRIGGERS: dict[str, list[str]] = {
    "causal": ["cause", "causes", "caused", "why ", "leads to", "results in", "enables", "prevents"],
    "temporal": ["before", "after", "preceded", "followed", "timeline", "sequence", "when did"],
    "evidential": ["evidence", "support", "supports", "refute", "proof", "citation", "source", "cite"],
    "hierarchical": ["part of", "belongs to", "contains", "is a ", "depends on", "subset of"],
    "procedural": ["steps", "procedure", "workflow", "input", "output", "how to", "process"],
    "provenance": ["derived from", "where does", "where did", "origin", "came from", "come from", "cited by", "contradicts"],
    "semantic": ["similar to", "analogous", "contrasts with", "like", "unlike"],
}


@dataclass
class ParsedNote:
    """A parsed markdown note with all extracted fields."""
    note_id: str
    file_path: str
    title: str
    aliases: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    note_type: str = ""
    created_at: str = ""
    modified_at: str = ""
    body: str = ""
    links: list[dict] = field(default_factory=list)      # {target, text_span, line_number}
    typed_relations: list[dict] = field(default_factory=list)  # {relation, target, text_span, line_number, variant}


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse YAML frontmatter if present. Returns (metadata, remaining_body)."""
    parts = text.split("---", 2)
    if len(parts) < 3 or not text.startswith("---"):
        return {}, text

    frontmatter_text = parts[1].strip()
    body = parts[2].strip()
    metadata: dict = {}

    # Simple YAML-like parser (no PyYAML dependency)
    for line in frontmatter_text.split("\n"):
        line = line.strip()
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if value.startswith("[") and value.endswith("]"):
                # List: [a, b, c]
                value = [v.strip().strip('"').strip("'") for v in value[1:-1].split(",") if v.strip()]
                metadata[key] = value
            else:
                metadata[key] = value

    return metadata, body


def _extract_wikilinks(text: str, line_offset: int = 0) -> list[dict]:
    """Extract [[Target]] wikilinks."""
    links = []
    for m in re.finditer(r"\[\[([^\]]+)\]\]", text):
        target = m.group(1)
        # Handle aliased wikilinks: [[Target|display]]
        if "|" in target:
            target = target.split("|")[0].strip()
        links.append({
            "target": target.strip(),
            "text_span": m.group(0),
            "line_number": line_offset + text[:m.start()].count("\n") + 1,
        })
    return links


def _extract_markdown_links(text: str, line_offset: int = 0) -> list[dict]:
    """Extract [text](target) markdown links."""
    links = []
    for m in re.finditer(r"\[([^\]]*)\]\(([^)]+)\)", text):
        target = m.group(2).strip()
        if target.startswith("http"):
            continue  # skip external URLs
        links.append({
            "target": target,
            "text_span": m.group(0),
            "line_number": line_offset + text[:m.start()].count("\n") + 1,
        })
    return links


def _extract_typed_relations(text: str, line_offset: int = 0) -> list[dict]:
    """Extract predicate:: [[Target]] typed relations.

    Matches: relation-word:: [[Target]]
    E.g.: causes:: [[Demand Drop]]
          supports:: [[Evidence Note]]
    """
    relations = []
    pattern = r"([a-z][a-z-]*?)::\s*\[\[([^\]]+)\]\]"
    for m in re.finditer(pattern, text, re.IGNORECASE):
        relation = m.group(1).strip().lower()
        target = m.group(2).strip()
        if "|" in target:
            target = target.split("|")[0].strip()
        variant = RELATION_TO_VARIANT.get(relation, "untyped")
        relations.append({
            "relation": relation,
            "target": target,
            "variant": variant,
            "text_span": m.group(0),
            "line_number": line_offset + text[:m.start()].count("\n") + 1,
        })
    return relations


def _generate_note_id(title: str) -> str:
    """Generate a stable note ID from title (slugify)."""
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or "untitled"


def parse_note(file_path: str, content: str) -> ParsedNote:
    """Parse a single markdown note file.

    Args:
        file_path: Relative or absolute path to the note
        content: Raw markdown content

    Returns:
        ParsedNote with all extracted fields
    """
    metadata, body = _parse_frontmatter(content)

    title = metadata.get("title", "")
    aliases = metadata.get("aliases", [])
    if isinstance(aliases, str):
        aliases = [a.strip() for a in aliases.split(",") if a.strip()]
    tags = metadata.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    note_type = metadata.get("type", "")
    created_at = metadata.get("created", "")
    modified_at = metadata.get("modified", "")

    # If no title in frontmatter, use first H1
    if not title:
        h1_match = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
        if h1_match:
            title = h1_match.group(1).strip()

    # Fallback: filename without extension
    if not title:
        import os
        title = os.path.splitext(os.path.basename(file_path))[0]

    note_id = _generate_note_id(title)

    # Extract links and relations from body
    wikilinks = _extract_wikilinks(body)
    md_links = _extract_markdown_links(body)
    typed_relations = _extract_typed_relations(body)

    all_links = wikilinks + md_links

    return ParsedNote(
        note_id=note_id,
        file_path=file_path,
        title=title,
        aliases=aliases,
        tags=tags,
        note_type=note_type,
        created_at=created_at,
        modified_at=modified_at,
        body=body,
        links=all_links,
        typed_relations=typed_relations,
    )
