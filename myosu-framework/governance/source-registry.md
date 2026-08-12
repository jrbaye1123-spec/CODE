# Source Registry

> Governed sources. Every vault note that enters the index must trace to a source registered here, not just another note.

---

## Registry

```json
{
  "sources": []
}
```

---

## Source Record Schema

Each governed source must have:

| Field | Required | Description |
|-------|----------|-------------|
| `source_id` | Yes | Unique identifier |
| `title` | Yes | Human-readable title |
| `type` | Yes | paper, book, article, dataset, code, internal-note, external-evidence |
| `uri` | Yes | Where the source lives |
| `ingested_by` | Yes | Module that ingested it (sources/arxiv, manual, etc.) |
| `safety_scan` | Yes | passed, failed, skipped |
| `provenance_class` | Yes | external-evidence, internal-spec, derived-synthesis, reference |
| `governance_status` | Yes | approved, pending, quarantined, expired |
| `reviewer` | Yes if approved | @knowledge-engineer |
| `reviewed_at` | Yes if approved | YYYY-MM-DD |
| `expires_at` | No | Only for time-boxed sources |
| `scope` | Yes | What outputs may use this source |
| `notes` | No | Usage constraints, caveats |
