# Pipeline Specification

The governed agent pipeline flows through retrieval → extraction →
summarization → contradiction detection → synthesis, with human gates
at promotion and export.

## Standard Pipeline

```
Sources → [Retrieval Agent] → source_cache
    ↓
[Extraction Agent] → /agent-extractions/
    ↓
[Summarization Agent] → /agent-summaries/
    ↓
[Contradiction Detection] → tensions
    ↓
[Synthesis Agent] → /agent-syntheses/  ⚠️ Interpretive Threshold
    ↓
[Human Review] → approve / reject / flag
    ↓
[Promotion] → /my-thinking/  (human action required)
    ↓
[Publication Audit] → manuscript
```

## Governance Gates

1. **Write Gate:** Every agent write passes through PolicyEngine.check_write()
   - W-001: Role-space authorization
   - W-001b: Firebreak (agent → /my-thinking/ blocked)
   - W-002: Provenance completeness
   - W-003: Synthesis threshold marker
   - W-004: Agent cannot assign stable_finding
   - W-005: Circular synthesis detection

2. **Retrieval Gate:** PolicyEngine.check_retrieval()
   - R-001: Quarantine exclusion
   - R-002: Abandoned exclusion (without auth)
   - R-003: Private provisional exclusion
   - R-004: Dual-use classification gates

3. **Synthesis Gate:** PolicyEngine.check_synthesis_pre() + check_synthesis_post()
   - SYN-PRE: Quarantined/abandoned inputs rejected
   - SYN-001: Threshold marker required
   - SYN-002: No stable_finding without promotion
   - SYN-003: Tensions must be emitted for contradictory inputs
   - SYN-004: Agent cannot resolve tensions
   - SYN-005: Circular synthesis detection

4. **Promotion Gate:** PolicyEngine.check_promotion()
   - P-001: Human promotion token required
   - P-002: Valid promotion type (ratification, annotation, reconstruction, composition)

5. **Export Gate:** PolicyEngine.check_export()
   - E-001: Provenance stripping blocked without justification
   - E-002: Tier 3 publication requires audit
   - E-003: Dual-use export requires approval
   - E-004: Agent synthesis disclosure recommended
