# Dual-Use Policy

Research with plausible misuse potential requires Tier 3 classification.

## Classification Criteria

Research is classified Tier 3 (dual-use) if it involves:
- Vulnerabilities in critical infrastructure
- Weaponizable scientific findings
- Mass surveillance or population-scale manipulation techniques
- Biological or chemical threat vectors
- AI safety / capability research that could enable harm at scale
- Personal data at population scale with re-identification risk

## Controls

1. **Classification marker:** Tier 3 notes carry `classification: ["dual_use"]`
2. **Retrieval gating:** Tier 3 content excluded from Tier 0/1 retrieval queries
   (PolicyEngine R-004)
3. **Export gating:** Tier 3 content requires explicit `dual_use_approval` for
   export (PolicyEngine E-003)
4. **Synthesis restriction:** Tier 3 sources may be synthesized but resulting
   synthesis inherits Tier 3 classification
5. **Human authorization:** All Tier 3 exports require human approval
6. **Disclosure:** Publications drawing on Tier 3 research should include a
   dual-use acknowledgment where appropriate

## Classification Authority

John is the classification authority. Classification decisions are documented
in the note metadata and reviewed quarterly.
