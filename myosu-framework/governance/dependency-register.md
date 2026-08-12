# Dependency Register

External models, APIs, plugins, and vendor-hosted capabilities that the
vault system depends on.

## Current Dependencies

| Dependency | Type | Version | Provider | Governance Impact |
|-----------|------|---------|----------|-------------------|
| Python 3.12 | Runtime | 3.12 | PSF | Standard library only |
| Obsidian | Application | — | Obsidian MD | Vault storage and UI |
| (Add model/API dependencies as they are integrated) | | | | |

## Change Policy

1. Any upstream update that may materially alter agent behavior must trigger
   governance review.
2. Model updates: re-run acceptance test suite.
3. API changes: verify handoff contracts still validate.
4. Prompt changes: log in change log, re-run synthesis tests (SYN-001 through
   SYN-005).
5. New dependencies: register before integration, assess compositional safety.

## Review Cadence

- Monthly: review dependency change log.
- Quarterly: assess whether upstream changes require governance update.
- Annual: full third-party dependency audit.
