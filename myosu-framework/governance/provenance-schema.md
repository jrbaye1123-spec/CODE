# Provenance Schema

> Every agent output carries a provenance label. This schema defines the levels, their operational behavior, and the runtime rules.

---

## Provenance Levels

| Level | Meaning | Output Behavior |
|-------|---------|-----------------|
| `verified` | Source traced to governed registry entry; reviewed by knowledge engineer | Normal output |
| `exception` | Time-boxed exception active; source not fully governed | Output allowed, marked `provenance: degraded` |
| `degraded` | Source provenance incomplete, exception active, or chain broken | Output allowed with visible warning; blocked from high-stakes use |
| `incomplete` | Source lacks required provenance fields | Do not use for high-stakes answers |
| `unknown` | No provenance metadata available | Block or quarantine output |
| `expired` | Exception timebox expired without renewal | Treat as `unvetted` |

---

## Output Label Format

Every agent output must carry:

```json
{
  "provenance_level": "verified",
  "sources": ["source-id-1", "source-id-2"],
  "claims": [
    {
      "claim_text": "...",
      "source_document": "source-id-1",
      "source_location": "section 3, paragraph 2",
      "confidence": 0.95
    }
  ],
  "reviewed_by": "@knowledge-engineer",
  "reviewed_at": "2026-08-06"
}
```

---

## Runtime Rules

| If index provenance is... | Then... |
|---------------------------|---------|
| `verified` | Normal output, no restrictions |
| `exception` | Output allowed, header carries ⚠️ PROVENANCE DEGRADED |
| `incomplete` | Blocked from high-stakes outputs; allowed for triage/draft only |
| `unknown` | Block output entirely |
| `expired` | Treat as unvetted; block until renewed or quarantined |

---

## Chain of Custody

```
governed source → source registry entry → vault note → gate pass → index entry → agent retrieval → output with provenance label
```

If any link in the chain is missing, provenance is `degraded` or `blocked`.
