# Vault Architecture

## Directory Structure

```
~/vault/
├── my-thinking/           # Human-authored notes ONLY
├── agent-extractions/     # Direct source pulls (origin_type=extraction)
├── agent-summaries/       # Condensed source sections
├── agent-syntheses/       # Agent-generated claims (origin_type=synthesis)
├── agent-dissent/         # Retrieval audit / excluded sources
├── source-cache/          # Retrieved source documents
├── quarantine/            # Notes failing integrity checks
├── frozen/                # Explicitly frozen/abandoned content
└── governance/            # Constitution, logs, schemas, reviews
```

## Firebreak Rules (Enforced at Write Time)

1. `origin_type=human_authored` → writes to `/my-thinking/` only.
2. `origin_type=extraction` → writes to `/agent-extractions/` only.
3. `origin_type=summarization` → writes to `/agent-summaries/` only.
4. `origin_type=synthesis` or `speculation` → writes to `/agent-syntheses/` only.
5. Promotion: agent-synthesized content may enter `/my-thinking/` ONLY
   through explicit human promotion with promotion_history entry.
6. Retrieval agents distinguish spaces — `/agent-syntheses/` content is
   never treated as primary-source evidence without promotion.

## Enforcement

- Write-time: `PolicyEngine.check_write()` W-001/W-001b
- Retrieval-time: `PolicyEngine.check_retrieval()` R-001 through R-004
- Promotion-time: `PolicyEngine.check_promotion()` P-001/P-002
