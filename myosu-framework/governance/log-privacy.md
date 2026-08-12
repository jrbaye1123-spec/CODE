# Log Privacy

Governance logs must not become a secondary surveillance surface.

## Principles

1. **Minimization:** Logs retain only what is necessary for governance.
2. **Access control:** Logs accessible to John only.
3. **Retention limits:** See retention-schedule.md for per-log retention.
4. **No provisional thought in logs:** Audit events record claim_ids and
   violation rules, not the full text of working_idea or abandoned notes.
5. **Hash-chaining:** Audit log events are hash-chained to detect tampering,
   not to enable surveillance.

## What Logs Do NOT Contain

- Full text of provisional or abandoned thoughts
- Personal data of research subjects (claim_ids only)
- Interaction profile data beyond rubber-stamp detection metrics
- Raw source content (content_hash only)

## What Logs DO Contain

- Policy decisions: allow/deny/quarantine/flag
- Violations: rule ID, reason, severity
- Timestamps and actor identifiers
- Claim IDs (for traceability)
- Hash-chain integrity markers

If a log must retain more detail for a specific incident, the retention
is time-bounded and documented.
