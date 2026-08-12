# Incident Response

## Procedure

1. **Detection:** Incident is detected by policy engine violation, acceptance
   test failure, or manual observation.
2. **Containment:** Quarantine the affected notes. Freeze the offending agent
   role if the incident is S1 or S2.
3. **Root Cause Analysis:** Trace the incident through the audit log.
   Identify: which agent, which rule, which input, which handoff.
4. **Remediation:** Repair or replace affected claims. Trace downstream
   dependents. Issue corrections if published.
5. **Governance Review:** If incident severity is S1 or S2, trigger governance
   review. Update constitution, config, or code as needed.
6. **Log:** Record incident in `/governance/logs/incidents.md` with severity,
   root cause, remediation, and governance changes.

## Incident Log Format

```
## INC-YYYY-MM-DD-NNN
- Severity: S1 | S2 | S3 | S4
- Detected: timestamp
- Agent(s): agent_id(s)
- Rule(s) violated: rule_ids
- Description: what happened
- Root cause: why it happened
- Remediation: what was done
- Governance change: what changed to prevent recurrence
- Status: open | contained | resolved
```
