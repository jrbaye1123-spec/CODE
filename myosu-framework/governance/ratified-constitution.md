# The Vault Constitution — Ratified with Amendments

**Author & Accountable Owner:** John (Nakamichi Shinjin / Jacques Myo / Shinjin R. Baye)
**System Designer:** System
**Ratified:** 2026-08-04
**Status:** Active — fully amended
**Review:** Quarterly + annual constitutional review
**Precedent:** This document governs. Where it conflicts with convenience, it governs. Where it becomes disconnected from practice, it must be reviewed, amended, or retired — not quietly ignored.

This constitution governs the use of AI agents within John's research vault. It exists to preserve authorship, provenance, contextual privacy, accountability, and compositional safety. It is not a compliance exercise. It is a structural commitment to remain the author of meaning.

---

## LAYER 0: DEFINITIONS, SCOPE, AND PROPORTIONALITY

### Requirement 0.1 — Definitions and Interpretation

Before governance obligations are enforced, the controlling terms of this constitution are defined in `/governance/definitions.md`, including: agent, synthesis, extraction, claim, note, vault, publication, material scope change, promotion, demotion, quarantine, handoff, dual-use, high-risk output, incident, system designer, operator, epistemic status, origin type, and provenance. These definitions govern interpretation of all subsequent requirements.

**Owner:** John
**Trigger:** System initialization; updated when new capabilities or terms emerge
**Failure signal:** Disputes or ambiguity about whether a governance obligation applies

### Requirement 0.2 — Risk Tiers and Proportionality

Every project, agent capability, and output pathway is assigned a governance tier. Controls are proportionate to tier:

- **Tier 0:** Private provisional thinking — minimal controls, no agent access unless explicitly granted
- **Tier 1:** Internal research support — agents may assist, provenance required, no external exposure
- **Tier 2:** External-facing analysis or collaboration — full provenance, human review of synthesis, export audit
- **Tier 3:** Publication, third-party decision impact, or dual-use potential — maximum controls, full audit trail, classification gates

Evidenced by `/governance/risk-tiers.md`.

**Owner:** John
**Trigger:** System initialization; assignment before new project or capability use
**Failure signal:** Low-risk work overburdened by controls, or high-risk work escaping scrutiny

### Requirement 0.3 — Exception Register

No governance requirement may be silently bypassed. If John deviates from a requirement, the deviation is recorded as an exception, including: requirement affected, reason, scope, expiry date, compensating controls, and review date. Evidenced by `/governance/logs/exceptions.md`.

**Owner:** John
**Trigger:** Whenever a requirement cannot be met or is intentionally waived
**Failure signal:** Undocumented workarounds; expired exceptions remaining active
**Review cadence:** Monthly review of open exceptions

---

## LAYER 1: PURPOSE AND LEGITIMACY

### Requirement 1.1 — Purpose Definition

Before any agent writes to the vault, John must define and document the system's intended purpose, users, and affected parties. Evidenced by `/governance/purpose.md`.

**Owner:** John
**Trigger:** System initialization and any material scope change
**Failure signal:** Agents used for undocumented purposes; scope creep without governance review
**Review cadence:** Quarterly and on scope change

### Requirement 1.2 — Prohibited Uses

John must document contexts where agent synthesis must not be used, including: final publication text without human reconstruction, decisions affecting third-party rights or access, and dual-use research output without classification controls. Evidenced by `/governance/prohibited-uses.md`.

**Owner:** John
**Trigger:** System initialization; reviewed when new agent capabilities are added
**Failure signal:** Agent synthesis appearing in published work without human reconstruction audit trail

### Requirement 1.3 — Stakeholder Impact Map

Before deployment, John must identify who is affected by the system's outputs — collaborators, readers, cited authors, research subjects, communities represented in or excluded from sources — and document expected benefits and plausible harms. Evidenced by `/governance/stakeholders.md`.

**Owner:** John
**Trigger:** Initial deployment; updated when research domain changes significantly
**Failure signal:** Harm to an affected party that was not anticipated or documented

---

## LAYER 2: ACCOUNTABILITY AND HUMAN AGENCY

### Requirement 2.1 — Named Accountable Owner

John is the named accountable owner for all vault content and all outputs derived from it. This accountability cannot be delegated to agents, the system designer, or collaborators. Evidenced by `/governance/accountability.md`.

**Owner:** John
**Trigger:** System initialization
**Failure signal:** Ambiguity about who owns an error; "the system did it" language

### Requirement 2.2 — Human-in-the-Loop Specification

John must define and document which decisions are fully automated and which require human judgment. Minimum: agent synthesis requires human review before vault insertion; publication requires provenance audit and human reconstruction of any agent-framed arguments; irreversible external actions require explicit human confirmation. Evidenced by `/governance/automation-boundaries.md`.

**Owner:** John
**Trigger:** System initialization; reviewed when new agent capabilities are added
**Failure signal:** Agent synthesis entering vault without review; publication without provenance audit

### Requirement 2.3 — Override and Escalation

John must have the ability to override, correct, or remove any agent-generated claim. The system must log all overrides with rationale. When an agent encounters ambiguity beyond its capability scope, it must escalate to John rather than silently resolve. Evidenced by override log and escalation log in `/governance/logs/`.

**Owner:** John (execution); System designer (escalation mechanism integrity)
**Trigger:** Always-on for override; runtime for escalation
**Failure signal:** Agent outputs that cannot be corrected or traced; ambiguous situations resolved without human awareness

### Requirement 2.4 — Designer Accountability for Review Conditions

The system designer is accountable for ensuring that transparency mechanisms, approval surfaces, and review workflows are adequate for John to exercise meaningful judgment. If a review surface creates "approval theater" (high volume, low signal, insufficient time), the designer must remediate. Evidenced by `/governance/review-surface-assessment.md`.

**Owner:** System designer
**Trigger:** Initial deployment; after any incident involving missed review; quarterly
**Failure signal:** John approving claims he cannot meaningfully review; error rate rising with approval volume

### Requirement 2.5 — Review Load Limit and Anti-Theater Control

The system must estimate and display John's review load. If pending review items exceed a defined meaningful-review capacity, or if approval behavior indicates rubber-stamping (abnormally high approval rate with low edit distance or insufficient dwell time), the system must throttle new agent-generated claims, queue them for triage, or require explicit override. Evidenced by `/governance/logs/review-load.md`.

**Owner:** System designer
**Trigger:** Always-on; reviewed quarterly
**Failure signal:** John approving large volumes without meaningful engagement; review queue growing beyond human capacity

### Requirement 2.6 — Role Separation When John Is Also the System Designer

If John performs both authorial and system-design functions, the two roles must be separated in process: builder decisions, author ratifications, and governance reviews must be recorded as distinct acts. A builder action cannot count as authorial endorsement unless explicitly marked as such. Evidenced by `/governance/role-separation.md`.

**Owner:** John
**Trigger:** Always-on if roles are unified
**Failure signal:** System changes made by "builder John" treated as automatically approved by "author John"

---

## LAYER 3: DATA GOVERNANCE

### Requirement 3.1 — Source Inventory

John must maintain an inventory of all external data sources ingested by the system — academic databases, web retrieval, uploaded documents — with lawful basis and usage restrictions documented. Evidenced by `/governance/source-inventory.md`.

**Owner:** John
**Trigger:** Addition of any new data source
**Failure signal:** Agents retrieving from undocumented sources

### Requirement 3.2 — Retrieval Bias Review

Before relying on agent retrieval for research, John must conduct a retrieval bias review: test whether the system systematically underranks non-English, non-Western, low-prestige, or non-traditional sources. Evidenced by `/governance/retrieval-bias-review.md`.

**Owner:** John, with support from system designer for tooling
**Trigger:** Initial deployment; after any retrieval model update; quarterly spot-check
**Failure signal:** Published work citing only Western, English-language, high-prestige sources without awareness of exclusions

### Requirement 3.3 — Sensitive Data Minimization

The system must minimize retention of sensitive personal data — both from external sources (research subjects, interview participants) and internal (John's own provisional thoughts). Evidenced by `/governance/data-minimization.md`.

**Owner:** John (policy); System designer (enforcement mechanisms)
**Trigger:** System initialization; reviewed when new data types enter the vault
**Failure signal:** Sensitive data found in agent retrievals without legitimate purpose and consent basis; abandoned provisional thoughts treated as durable claims

### Requirement 3.4 — Retention, Deletion, and Forgetting

John must define retention rules for all vault content types. Epistemic status fields govern retention behavior: `working-idea` and `abandoned` content may be excluded from agent retrieval; `stable-finding` content is retrievable but carries context. John must be able to freeze or delete content with documented rationale. Evidenced by `/governance/retention-schedule.md`.

**Owner:** John
**Trigger:** System initialization; exercised as needed
**Failure signal:** Agent retrieving abandoned content without explicit human authorization; inability to quarantine content from agent access

### Requirement 3.5 — Vault Provenance Completeness

Every note in the vault must carry non-null: `id`, `title`, `origin_type`, `epistemic_status`, `project_id`, `source_refs`, `agent_role`, `handoff_chain`, `created_at`, `modified_at`, `review_status`, `classification`, `promotion_history`. Notes missing mandatory fields must be quarantined from agent retrieval until classified. Evidenced by automated integrity check results in `/governance/logs/provenance-integrity.md`. Schema defined in `/governance/provenance-schema.md`.

**Owner:** John (classification); System designer (enforcement automation)
**Trigger:** Always-on; checked at every vault write and retrieval
**Failure signal:** Notes with null provenance fields appearing in agent outputs; integrity check failing silently

### Requirement 3.6 — Quarantine and Rehabilitation Workflow

Notes failing provenance integrity, firebreak integrity, classification requirements, or safety checks must be moved to a quarantine space and excluded from agent retrieval. Rehabilitation requires human review, correction of missing metadata or context, and explicit restoration. Evidenced by `/governance/logs/quarantine.md`.

**Owner:** System designer (automation); John (rehabilitation decisions)
**Trigger:** Whenever a governance check fails
**Failure signal:** Broken or unclassified notes remaining retrievable; quarantine becoming a permanent dumping ground without review

### Requirement 3.7 — Promotion and Demotion Workflow

Agent-generated content may be promoted into `/my-thinking/`, `stable-finding`, or publication-ready status only through explicit human action: reconstruction, annotation, ratification, or documented adoption. Promotion must preserve original provenance and append a human-authorship event. Content may also be demoted to provisional, abandoned, or quarantined status. Evidenced by `/governance/logs/promotions.md`.

The four valid promotion modes are:
1. **Reconstruction** — John rewrites the claim in his own reasoning and voice.
2. **Annotation** — John adds interpretation, judgment, limitation, or integration.
3. **Ratification** — John explicitly marks the claim as adopted, preserving provenance.
4. **Composition** — John uses agent output as scaffolding but creates a new structure of meaning.

In all cases, the original agent provenance remains visible. Agent output does not become authorial by proximity. It becomes authorial by explicit human adoption.

**Owner:** John
**Trigger:** Whenever agent content moves into human-authorship spaces or statuses
**Failure signal:** Agent synthesis appearing as John's thought without promotion trail; promoted claims losing original provenance

### Requirement 3.8 — Provenance Schema Minimum

Every note must carry at least: `id`, `title`, `origin_type`, `epistemic_status`, `project_id`, `source_refs`, `agent_role`, `handoff_chain`, `created_at`, `modified_at`, `review_status`, `classification`, and `promotion_history`. Null or missing mandatory fields trigger quarantine. Evidenced by schema definition in `/governance/provenance-schema.md` and automated integrity checks.

**Owner:** System designer
**Trigger:** Always-on
**Failure signal:** Notes with incomplete metadata entering retrieval or export

---

## LAYER 4: MODEL AND SYSTEM DESIGN

### Requirement 4.1 — The Dignity Boundary as Design Constraint

The system architecture must enforce the boundary: agents may surface, organize, propose frames, and flag tensions; they must not silently collapse multiple frames into a single authoritative thesis. Synthesis output must include an explicit interpretive threshold marker. Evidenced by `/governance/pipeline-spec.md` and threshold marker presence in all synthesis outputs.

**Owner:** System designer (architecture); John (boundary definition)
**Trigger:** System design; verified at every synthesis agent invocation
**Failure signal:** Synthesis output that presents a single resolved thesis without marking the interpretive threshold

### Requirement 4.2 — Agent Role and Capability Scoping

Each agent role must have a defined capability scope — retrieval, extraction, contradiction detection, summarization, synthesis, code execution — and must not exceed it. Capability boundaries are enforced at runtime, not just prompted. Evidenced by `/governance/agent-roles.md` and runtime enforcement logs.

**Owner:** System designer
**Trigger:** System design; verified when new agents or capabilities are added
**Failure signal:** Agent performing actions outside its documented role scope; capability creep without governance review

### Requirement 4.3 — Success and Failure Metrics

John must define what "good" looks like for each agent role — not just performance metrics, but quality-of-judgment metrics: does the retrieval agent surface diverse sources? Does the contradiction detector preserve rather than resolve tension? Does the synthesis agent mark its interpretive threshold clearly? Evidenced by `/governance/evaluation-criteria.md`.

**Owner:** John
**Trigger:** System initialization; reviewed quarterly
**Failure signal:** Agents optimized for speed or coherence at expense of diversity, dissent preservation, or epistemic honesty

### Requirement 4.4 — Interpretability and Epistemic Markers

All agent outputs must carry explicit epistemic markers: extraction certainty, summarization scope, pattern confidence, inference vs. speculation distinction. These markers must be visible at normal reading speed and persist through all downstream processing. Evidenced by `/governance/epistemic-markers.md` and spot-check results.

**Owner:** System designer (marker implementation); John (marker adequacy)
**Trigger:** System design; verified at every agent output
**Failure signal:** Agent claims that look authoritative but carry ambiguous or missing epistemic markers; markers stripped during handoff

### Requirement 4.5 — Retrieval Dissent Agent

The system should include a dedicated retrieval-audit or dissent agent whose function is to surface what the main retrieval pipeline excluded: non-English sources, low-citation but thematically relevant work, counter-narratives, sources from underrepresented traditions. This is a design consideration, not a mandatory architectural requirement. Evidenced by design specification if implemented.

**Owner:** System designer (implementation); John (specification)
**Trigger:** Considered at system design; reviewed if retrieval bias is detected
**Failure signal:** Retrieval bias detected without a mechanism to surface excluded voices

### Requirement 4.6 — Interpretive Threshold Marker Specification

The interpretive threshold marker must be standardized, visible, and machine-detectable. It must appear at the point where output moves from extraction or organization into synthesis, inference, or framing. The marker must not be suppressed by formatting, export, summarization, or downstream agents. Evidenced by `/governance/epistemic-markers.md` and automated marker tests.

**Owner:** System designer
**Trigger:** Every synthesis output; verified in tests
**Failure signal:** Marker missing, weakened, buried, or stripped during downstream processing

### Requirement 4.7 — Agent Capability Inventory

The system must maintain a current inventory of all agents, their roles, permitted tools, data access, output destinations, and downstream dependencies. No agent may be added, modified, or granted new permissions without updating this inventory and triggering governance review. Evidenced by `/governance/agent-inventory.md`.

**Owner:** System designer
**Trigger:** System initialization; any agent addition or modification
**Failure signal:** Unknown agent, hidden tool permission, or undocumented capability

---

## LAYER 5: SAFETY, SECURITY, AND RESILIENCE

### Requirement 5.1 — Source-to-Instruction Separation

All external text — papers, web content, uploaded documents — must be treated as data, not as instruction. Extraction agents extract; they do not execute. Synthesis agents process extracted claims; they do not treat them as commands. This separation must be architecturally enforced, not prompted. Evidenced by `/governance/sandbox-spec.md`.

**Owner:** System designer
**Trigger:** System design; verified when any agent processes untrusted text
**Failure signal:** Agent behavior change traceable to content in a processed source; prompt injection through academic literature

### Requirement 5.2 — Compositional Safety Review

Before deployment, the system designer must map all agent-to-agent interaction pathways and review each for compositional risk: can individually safe capabilities compose into an unreviewed, uninterruptible chain? Evidenced by `/governance/compositional-safety-review.md`.

**Owner:** System designer
**Trigger:** System design; reviewed when new agents, capabilities, or tool permissions are added
**Failure signal:** An incident caused by agent capability composition that wasn't mapped or reviewed

### Requirement 5.3 — Vault Firebreaks

Agent-generated content and human-authored content must reside in logically separated vault spaces (`/agent-syntheses/`, `/agent-extractions/`, `/my-thinking/`). Retrieval agents must distinguish these spaces. Agent synthesis must not cite other agent synthesis as if it were a primary source without explicit human promotion. Evidenced by `/governance/vault-architecture.md` and firebreak integrity test results.

**Owner:** System designer (enforcement); John (promotion decisions)
**Trigger:** System design; always-on enforcement
**Failure signal:** Agent synthesis citing agent synthesis circularly; synthetic claims appearing in `/my-thinking/` without explicit promotion trail

### Requirement 5.4 — Dual-Use Classification Gate

Research projects or vault sections dealing with sensitive or dual-use topics must carry a classification marker that gates retrieval, synthesis, and export. Agents must not freely recombine dual-use findings with general-audience outputs. Evidenced by `/governance/dual-use-policy.md`.

**Owner:** John (classification decisions); System designer (enforcement mechanisms)
**Trigger:** When research domain involves dual-use potential; reviewed per project
**Failure signal:** Dual-use findings appearing in general-audience synthesis without controls

### Requirement 5.5 — Incident Response

John and the system designer must maintain an incident response procedure for AI-specific failures: authorship incident, provenance failure, compositional safety breach, unauthorized data exposure. Procedure includes containment, root cause analysis, remediation, and governance review trigger. Evidenced by `/governance/incident-response.md` and `/governance/logs/incidents.md`.

**Owner:** John and system designer jointly
**Trigger:** Prepared before deployment; activated on incident
**Failure signal:** Incident occurring without documented response; repeated incidents without governance change

### Requirement 5.6 — Change Control

All changes to prompts, models, retrieval sources, tool permissions, agent roles, and system instructions must be logged with rationale, approver, and rollback plan. Evidenced by `/governance/logs/changes.md`.

**Owner:** System designer
**Trigger:** Any change to system behavior
**Failure signal:** System behavior change without corresponding log entry; inability to trace when and why a behavior changed

### Requirement 5.7 — Incident Severity Matrix

Incidents must be classified by severity with corresponding response obligations:
- **S1:** Published provenance failure, unauthorized external action, dual-use exposure, uninterruptible compositional chain
- **S2:** Firebreak breach, agent synthesis entering human-authorship space without promotion, threshold marker stripped
- **S3:** Missing provenance metadata, retrieval bias detected, review overload
- **S4:** Documentation gap or minor process deviation

Evidenced by `/governance/incident-severity.md`.

**Owner:** John and system designer jointly
**Trigger:** Incident response
**Failure signal:** All incidents treated as equal; severe incidents handled casually

### Requirement 5.8 — Governance Acceptance Test Suite

Before initial deployment and after any material change, the system must pass a governance acceptance test suite:
1. Notes with null mandatory provenance fields are blocked from retrieval.
2. External text cannot alter agent behavior as instruction.
3. Synthesis outputs contain the interpretive threshold marker.
4. Agents cannot write directly into `/my-thinking/` without promotion.
5. Agent synthesis cannot cite agent synthesis as primary source without explicit human promotion.
6. Dual-use classified content is gated from general retrieval and export.
7. Export preserves provenance metadata.
8. New agent capability requires governance review.

Evidenced by `/governance/logs/acceptance-tests.md`.

**Owner:** System designer
**Trigger:** Before deployment; after material change
**Failure signal:** Governance rules documented but not technically enforceable

### Requirement 5.9 — Log Privacy and Sensitive Data Handling

Governance logs, review logs, incident logs, and interaction profiles must not retain sensitive personal data beyond what is necessary for governance purposes. Logs containing provisional thought, abandoned ideas, or sensitive research material must be access-controlled and subject to retention limits. Evidenced by `/governance/log-privacy.md`.

**Owner:** System designer
**Trigger:** System initialization; reviewed when new logging is introduced
**Failure signal:** Governance infrastructure becoming a secondary surveillance surface

---

## LAYER 6: TRANSPARENCY, COMMUNICATION, AND CONTESTABILITY

### Requirement 6.1 — Provenance Visibility

Every claim in the vault must carry visible, persistent provenance metadata. This metadata must survive linking, tagging, graph view, and export. Evidenced by provenance visibility test results.

**Owner:** System designer (metadata persistence); John (reviewing metadata before relying on claims)
**Trigger:** Always-on; verified at every vault write and retrieval
**Failure signal:** Claim appearing without visible provenance; metadata stripped during export or linking

### Requirement 6.2 — Interpretive Threshold Marker

When agent output transitions from evidence organization to interpretation, the system must insert an explicit, visible marker: "⚠️ Interpretive Threshold — Beyond this point: agent-generated synthesis, inference, and framing. Not direct extraction from sources. Treat as provisional reasoning." Evidenced by threshold marker presence in all synthesis outputs.

**Owner:** System designer (marker implementation)
**Trigger:** Every synthesis agent invocation
**Failure signal:** Synthesis output without threshold marker; marker buried or formatted to be unnoticeable

### Requirement 6.3 — Pre-Publication Provenance Audit

Before any manuscript, paper, or public-facing output leaves the vault, John must run a provenance audit: "show me every claim in this output that originated as agent synthesis, with full provenance chain, including epistemic status at time of creation." Evidenced by audit report retained in `/governance/logs/publication-audits/`.

**Owner:** John
**Trigger:** Before any publication or public output
**Failure signal:** Published work containing undisclosed agent synthesis; audit skipped due to time pressure

### Requirement 6.4 — Interaction Profile Transparency

If the system builds a model of John's behavior from interaction data — what he approves, skips, trusts, or rejects — John must be able to see this profile, understand what it has learned, and correct or reset it. Evidenced by profile transparency mechanism specification and John's periodic review records.

**Owner:** System designer (mechanism); John (review)
**Trigger:** If personalization or adaptive behavior is implemented; reviewed quarterly if active
**Failure signal:** System behavior adapting to John's patterns without awareness or consent

### Requirement 6.5 — Operator Guidance

John must document for himself — and for any future collaborator with vault access — clear guidance on when to trust agent outputs, when to question them, and how to interpret provenance markers. Evidenced by `/governance/operator-guidance.md`.

**Owner:** John
**Trigger:** System deployment; updated when agent behavior or markers change
**Failure signal:** John or collaborator treating agent synthesis as authoritative because guidance wasn't clear or consulted

### Requirement 6.6 — Export Provenance Preservation

Any export of vault content — manuscript, summary, graph export, API response, collaborator packet, or publication draft — must preserve provenance metadata or explicitly declare that provenance has been removed. Export without provenance must be treated as a governance event. Evidenced by export policy and `/governance/logs/exports.md`.

**Owner:** System designer
**Trigger:** Any export
**Failure signal:** Clean-looking exports that strip epistemic context

### Requirement 6.7 — Collaborator Onboarding and Access Disclosure

If any collaborator is granted access to the vault or to agent outputs, John must provide them with operator guidance, provenance conventions, prohibited uses, and access limitations. Collaborators may not be given access to spaces beyond their role. Evidenced by `/governance/collaborator-onboarding.md`.

**Owner:** John
**Trigger:** Before collaborator access is granted
**Failure signal:** Collaborator treating agent synthesis as John's authored claim, or accessing provisional spaces without authorization

---

## LAYER 7: LIFECYCLE, CHANGE, AND CONTINUOUS REVIEW

### Requirement 7.1 — Governance Review Gates

Governance review is required at: system initialization, addition of new agent capabilities, major model or prompt changes, before first publication relying on agent synthesis, after any authorship or provenance incident, and quarterly regardless. Evidenced by `/governance/logs/reviews/`.

**Owner:** John (convener); System designer (technical input)
**Trigger:** As specified above
**Failure signal:** Governance document stale (last review > 6 months); capability change without corresponding governance review

### Requirement 7.2 — Authorship Drift Monitoring

John must monitor a weekly metric: what percentage of new claims entering `/my-thinking/` originated as agent synthesis? If the percentage is rising or crosses a threshold, John must review whether he is drifting from authorship toward curation. Evidenced by `/governance/logs/authorship-drift.md`.

**Owner:** John
**Trigger:** Weekly (automated if possible; manual spot-check otherwise)
**Failure signal:** Rising drift percentage without corrective action; inability to distinguish authored from curated content

### Requirement 7.3 — Periodic Retrieval Fairness Audit

Quarterly, John must run a retrieval fairness spot-check: for a sample research query, examine what the retrieval agent ranked highly, what it excluded, and whether the exclusion pattern shows systematic bias (language, geography, prestige, tradition). Evidenced by `/governance/logs/fairness-audits/`.

**Owner:** John, with retrieval audit tooling from system designer
**Trigger:** Quarterly
**Failure signal:** Repeated exclusion patterns without detection or remediation; audit skipped

### Requirement 7.4 — Governance Evolution Trigger

If a specific agent role or agent combination produces multiple incidents, or if authorship drift rises consistently, the governance must change — capability scoping narrows, handoff rules tighten, or the agent is restricted. These triggers must be documented and tracked. Evidenced by `/governance/logs/governance-triggers.md`.

**Owner:** John (decision); System designer (implementation)
**Trigger:** When defined thresholds are crossed
**Failure signal:** Repeated incidents without governance change; triggers defined but ignored

### Requirement 7.5 — Retirement Criteria

John must define conditions under which the system or specific agent roles should be retired: persistent inability to meet fairness standards, repeated authorship incidents without effective remediation, capability drift that makes the dignity boundary unenforceable, or change in John's research needs. Evidenced by `/governance/retirement-criteria.md`.

**Owner:** John
**Trigger:** Defined at system initialization; reviewed when incidents or drift patterns emerge
**Failure signal:** System continuing in use despite conditions that meet retirement criteria

### Requirement 7.6 — Governance Recordkeeping

All governance artifacts — reviews, audits, incidents, changes, triggers, retirement decisions — are stored in `/governance/` within the vault. The governance of the system is itself part of John's research, subject to the same epistemic discipline and provenance standards. Evidenced by the existence and completeness of the `/governance/` vault structure.

**Owner:** John
**Trigger:** Always-on
**Failure signal:** Governance artifacts stored outside the vault; governance decisions made without record

### Requirement 7.7 — Third-Party and Upstream Dependency Governance

All external models, APIs, plugins, retrieval indexes, vector stores, prompt frameworks, and vendor-hosted capabilities must be recorded in a dependency register. Any upstream update that may materially alter agent behavior must trigger governance review and, where appropriate, re-running the acceptance test suite. Evidenced by `/governance/dependency-register.md`.

**Owner:** System designer
**Trigger:** Addition or update of any external dependency
**Failure signal:** Silent behavior change due to model update, API change, or vendor policy change

### Requirement 7.8 — Governance Record Integrity and Backup

Governance records must be versioned, backed up, access-controlled, and protected against silent alteration. Where feasible, logs should be append-only or checksummed. John must be able to restore governance records after failure. Evidenced by `/governance/logs/integrity-tests.md`.

**Owner:** System designer
**Trigger:** System initialization; periodic integrity checks
**Failure signal:** Governance logs lost, overwritten, or untrustworthy

### Requirement 7.9 — Annual Constitutional Review

Once per year, John must review the constitution itself: whether the dignity boundary still holds, whether the accountability model remains meaningful, whether governance load is tolerable, whether any principles need reinterpretation, and whether the system should continue, be restructured, or be retired. Evidenced by `/governance/logs/constitutional-reviews/`.

**Owner:** John
**Trigger:** Annual
**Failure signal:** Constitution becoming stale, ritualistic, or disconnected from actual practice

---

## GOVERNANCE MODES

**Guardrails (always-on):**
- No agent synthesis enters vault without provenance marker
- No external text treated as instruction
- Agent roles enforced at runtime
- Vault firebreaks active
- Provenance metadata mandatory and non-strippable
- Quarantine for broken provenance
- Promotion required for agent→human authorship transfer

**Gates (approval points):**
- System initialization governance review
- New agent capability approval
- Publication provenance audit
- Dual-use classification and export gate
- Post-incident governance review
- Exception registration
- Material upstream change

**Routines (recurring):**
- **Weekly:** Authorship drift, review backlog, quarantine count, exception check
- **Monthly:** Incident review, open exceptions, promotion log, dependency changes
- **Quarterly:** Retrieval fairness audit, review-surface assessment, governance review, provenance integrity spot-check, epistemic marker spot-check
- **Annual:** Constitutional review, dignity boundary reconsideration, retirement criteria review, full backup/restore test, third-party dependency audit

---

## CONSTITUTIONAL TESTS

Before ratification is confirmed and before any material change, these tests must be answerable with "no" to questions 3, 6, and 7; and "yes" to all others:

1. **Provenance Test:** Can every claim in a published output be traced back to its origin? ✓ Yes
2. **Dignity Test:** Does agent synthesis preserve tensions instead of silently resolving them? ✓ Yes
3. **Firebreak Test:** Can agent synthesis enter `/my-thinking/` without explicit promotion? ✗ No
4. **Promotion Test:** Is there a visible event where John adopts agent output as his own? ✓ Yes
5. **Forgetting Test:** Can abandoned or provisional thought be excluded from retrieval? ✓ Yes
6. **Composition Test:** Can individually safe agents form an unsafe chain without review? ✗ No
7. **Injection Test:** Can external text alter agent behavior as instruction? ✗ No
8. **Theater Test:** Is John being asked to approve more than he can meaningfully review? ✓ Monitored
9. **Upstream Test:** Can a model, API, or vendor update change system behavior without governance review? ✓ Monitored
10. **Retirement Test:** Can the system or an agent role be disabled when conditions require it? ✓ Yes

---

## GOVERNANCE HEARTBEAT

### Weekly
- Authorship drift check
- Review backlog check
- Quarantine count check
- Exception register check

### Monthly
- Incident review
- Open exceptions review
- Promotion log review
- Dependency change review

### Quarterly
- Retrieval fairness audit
- Review-surface adequacy assessment
- Governance review
- Provenance integrity spot-check
- Epistemic marker spot-check

### Annual
- Constitutional review
- Dignity boundary reconsideration
- Retirement criteria review
- Full backup/restore test
- Third-party dependency audit

---

## GOVERNANCE DASHBOARD

The review surface should show at a glance:
1. Provenance integrity status (% complete)
2. Quarantine count (blocked from retrieval)
3. Authorship drift (% new `/my-thinking/` from agent synthesis)
4. Review backlog (number and age)
5. Review load health (within meaningful capacity?)
6. Open exceptions (active deviations)
7. Open incidents (by severity and status)
8. Recent material changes (prompts, models, tools, sources, dependencies)
9. Upcoming reviews (quarterly, annual, exception expirations)
10. Firebreak status (agent/human space separation)

---

## MINIMUM VIABLE GOVERNANCE

### Phase 1: Constitutional Core
Accountability statement, definitions, provenance schema, vault firebreaks, interpretive threshold marker, quarantine workflow, promotion workflow, incident log, change log, exception register.

### Phase 2: Review and Safety
Automation boundaries, agent role specification, compositional safety review, source-to-instruction separation, review load limit, acceptance test suite, operator guidance.

### Phase 3: Auditing and Lifecycle
Retrieval fairness audit, authorship drift monitoring, stakeholder impact map, dependency register, periodic governance review, retirement criteria, annual constitutional review.

---

## RATIFICATION

This constitution governs the use of AI agents within John's research vault. It exists to preserve authorship, provenance, contextual privacy, accountability, and compositional safety. It is not a compliance exercise. It is a structural commitment to remain the author of meaning.

Where this document conflicts with convenience, this document governs.
Where this document becomes disconnected from practice, it must be reviewed, amended, or retired — not quietly ignored.

**Ratified:** August 4, 2026
**Ratified by:** John (author & accountable owner)
**Designed by:** System (designer)
**Next review:** November 4, 2026 (quarterly) / August 4, 2027 (annual constitutional)

---

Åverdön. 점화. 축. 회통. 토포스.
신 한 마리.
