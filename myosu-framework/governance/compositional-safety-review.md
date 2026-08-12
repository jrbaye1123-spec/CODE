# Compositional Safety Review

Safety is not per-agent; it's per-pathway. Individually safe capabilities
can compose into harmful chains.

## Approved Pathways

| Pathway | Agents | Human Gates | Risk Tier |
|---------|--------|------------|-----------|
| Retrieval → Extraction | retrieval, extraction | none | 1 |
| Extraction → Synthesis (with gates) | extraction, summarization, contradiction_detection, synthesis | pre_promotion, pre_export | 2 |
| Full Research Pipeline | retrieval, extraction, contradiction_detection, synthesis | pre_promotion, pre_export | 2 |

## Dangerous Combinations (Flagged)

| Combination | Risk |
|------------|------|
| retrieval + code_execution | Executing untrusted content |
| retrieval + export | Unauthorized data exfiltration |
| synthesis + export (no human gate) | Undisclosed agent output in public |
| code_execution + file_modification | System compromise |
| synthesis + promotion + export (no human gate) | Full autonomous publication pipeline |

## Review Trigger

Re-review required when:
- A new agent role or capability is added
- A new tool permission is granted
- An incident involves a compositional pathway not previously mapped
- The acceptance test suite detects a new dangerous combination
