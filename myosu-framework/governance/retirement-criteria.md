# Retirement Criteria

Conditions under which the system or specific agent roles should be retired.

## System-Wide Retirement

The vault governance system should be retired or restructured if:
1. Authorship drift exceeds 40% for more than 8 consecutive weeks without
   effective remediation.
2. Provenance integrity violation rate exceeds 15% for more than one quarter.
3. Three or more S1 incidents occur within a single quarter.
4. The dignity boundary becomes unenforceable due to capability drift
   (agents routinely producing outputs indistinguishable from human-authored
   content without reliable detection).
5. John's research needs change such that the governed multi-agent workflow
   no longer serves its intended purpose.

## Agent-Specific Retirement

An individual agent role should be retired if:
1. The agent produces multiple S2+ incidents without effective remediation.
2. The agent's capability scope creeps beyond its defined role without
   governance approval.
3. The agent's error rate (per GovernanceCadence metrics) exceeds 15%
   for more than 4 consecutive weeks.
4. The agent's function is superseded by a safer or more reliable alternative.

## Retirement Procedure

1. Document the retirement decision and rationale.
2. Freeze the agent role (revoke capability token).
3. Quarantine all outputs from the retired agent for human review.
4. Trace and flag all dependents of retired agent claims.
5. Update agent inventory and dependency register.
6. Log in governance records.

## Last Review

Pending. First review: August 4, 2027 (annual constitutional review).
