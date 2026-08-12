# Retention Schedule

## By Epistemic Status

| Status | Agent Retrieval | Direct Access | Review Cadence | Deletion |
|--------|----------------|---------------|----------------|----------|
| working_idea | Excluded | John only | Never (private) | Manual only |
| provisional_claim | Included with marker | All authorized | On promotion | Manual only |
| stable_finding | Included | All authorized | Annual | Manual only |
| abandoned | Excluded | John only | Annual | Eligible after 2 years |
| quarantined | Excluded | John only | On rehabilitation | Manual only |

## By Origin Type

| Type | Default Retention | Notes |
|------|------------------|-------|
| human_authored | Indefinite | John's thinking; never auto-deleted |
| extraction | Duration of project + 2 years | Source-attributed; may be regenerated |
| summarization | Duration of project + 2 years | Derivative; may be regenerated |
| synthesis | Indefinite (with provenance) | Retained for audit trail |
| speculation | Review after 1 year | Low-confidence; candidate for demotion |

## Governance Logs

| Log | Retention |
|-----|-----------|
| Audit log (JSONL) | Duration of system operation + 1 year |
| Incident log | Duration of system operation + 3 years |
| Change log | Indefinite |
| Exception register | Duration of system operation + 1 year |
| Publication audits | Indefinite |
| Constitutional reviews | Indefinite |

## Forgetting Procedure

To freeze a note or project from agent retrieval:
1. Set epistemic_status to "abandoned" or "working_idea"
2. Move note to /frozen/ directory
3. Document rationale in note metadata
4. Verify: retrieval agent excludes the note
