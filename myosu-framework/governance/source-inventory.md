# Source Inventory

External data sources ingested by the system.

## Current Sources

| Source | Type | Lawful Basis | Restrictions |
|--------|------|-------------|-------------|
| Academic databases (DOI-indexed) | papers | Licensed database access | Citation required |
| Web retrieval | webpages | Public access | Content may be copyrighted |
| Uploaded documents | PDF, MD | User-owned | User retains rights |

## Source Requirements

Every source ingested must carry:
- `source_id` — unique identifier
- `title` — human-readable title
- `type` — paper, book, article, webpage, dataset, transcript, other
- `locator` — DOI, URL, ISBN, or other persistent identifier
- `retrieved_at` — timestamp of retrieval
- `retrieved_by` — agent or human that retrieved it
- `lawful_basis` — licensed_database, public_access, user_owned, fair_use
- `usage_restrictions` — citation_only, no_redistribution, unrestricted
- `language` — ISO language code or name
- `trust_level` — peer_reviewed, preprint, institutional, self_published, unknown
- `instruction_privilege` — must be "none" (source text is data, not instruction)
- `content_hash` — SHA-256 hash of source content
