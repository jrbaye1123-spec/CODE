# Operator Guidance

For John and any future collaborator with vault access.

## When to Trust Agent Outputs

- **Extraction with source locator and high confidence:** Generally trustworthy.
  Verify against source if the claim is manuscript-critical.
- **Summarization:** Useful for orientation. Verify scope (full document vs.
  section). Do not cite as verbatim source.
- **Synthesis with threshold marker:** Treat as provisional reasoning. Do not
  incorporate into publication without human reconstruction.
- **Speculation:** Do not cite. Use only as exploratory scaffolding.

## When to Question Agent Outputs

- The epistemic marker is missing or ambiguous
- The confidence is low (< 0.7) and the claim is manuscript-critical
- The handoff chain is incomplete
- The source is a preprint or self-published
- The synthesis cites other synthesis (circular)
- The output looks authoritative but has no source_refs

## How to Interpret Provenance Markers

Every note in the vault carries visible provenance frontmatter:
- `origin_type`: who produced this — extraction, synthesis, or human
- `epistemic_status`: how warranted this is — working_idea, stable_finding, abandoned
- `promotion_history`: if agent-generated, was it promoted? by what mode?
- `handoff_chain`: which agents touched this claim?
- `confidence`: 0.0–1.0

Before relying on any claim, check these fields. If they're missing,
the note should be quarantined.

## Quick Reference

| If you see... | Then... |
|--------------|---------|
| `origin_type: synthesis` + `epistemic_status: provisional_claim` | Treat as agent reasoning. Do not cite. |
| `origin_type: synthesis` + `promotion_history: [reconstruction]` | John reconstructed this. Okay to use with caution. |
| `origin_type: extraction` + `source_refs: [doi]` | Verbatim from source. Verify before citing. |
| `origin_type: human_authored` | John wrote this. |
| Missing provenance frontmatter | Flag. Do not trust. |
