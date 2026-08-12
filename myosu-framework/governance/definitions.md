# Definitions

Controlled terms for the Vault Constitution. These definitions govern
interpretation of all governance requirements.

## Core Terms

**Agent:** A software component with a defined role, capability scope, and
identity token. Agents perform retrieval, extraction, summarization,
contradiction detection, synthesis, or code execution. Agents do not have
moral agency, legal personhood, or the capacity for authorship.

**Synthesis:** Any claim, frame, pattern, or connective insight not directly
present in any single source — even if derived from multiple sources.
Synthesis requires the interpretive threshold marker.

**Extraction:** Content directly traceable to an identifiable source, with
fidelity verification. Extraction preserves verbatim quotes where possible.

**Summarization:** Condensed representation of a bounded source section, with
scope explicitly declared. Distinct from synthesis in that it does not
introduce cross-source inference.

**Speculation:** Agent-generated possibility with no direct evidential anchor.
Must carry speculation flag and confidence ≤ 0.5.

**Claim:** An atomic assertion stored in the vault. Every claim carries
provenance metadata including origin_type, epistemic_status, project_id,
source_refs, handoff_chain, and reviewer.

**Note:** A vault entry containing one or more claims, with associated
metadata. The atomic unit of vault storage.

**Vault:** The complete knowledge base — Obsidian notes, agent outputs,
governance records, and all associated metadata.

**Publication:** Any output that leaves the vault for external consumption —
manuscript, paper, presentation, public statement, collaborator packet.

**Material Scope Change:** Addition of a new agent role, new tool permission,
new data source, model update, prompt change, or expansion to a new research
domain. Material changes trigger governance review.

**Promotion:** The explicit human act of adopting agent-generated content into
human-author spaces. Four valid modes: reconstruction, annotation,
ratification, composition. Promotion is not approval — it is adoption.

**Demotion:** Reclassifying content to a lower epistemic status (e.g.,
stable_finding → abandoned, working_idea → abandoned).

**Quarantine:** Removing a note from agent retrieval due to provenance
failure, firebreak violation, classification breach, or safety concern.
Quarantined notes require human rehabilitation to be restored.

**Handoff:** The transfer of artifacts from one agent to another. Every
handoff must preserve provenance metadata. Handoff loss is a governance event.

**Dual-Use:** Research with plausible misuse potential. Tier 3 classification
required. Gated from general retrieval and export.

**High-Risk Output:** Any output classified Tier 3, any output containing
dual-use content, or any publication-level agent synthesis.

**Incident:** Any violation of a governance requirement detected at runtime.
Severity: S1 (critical — published provenance failure, unauthorized action),
S2 (high — firebreak breach, threshold marker stripped), S3 (medium —
missing metadata, review overload), S4 (low — documentation gap).

**System Designer:** The entity responsible for transparency mechanisms,
review surfaces, acceptance tests, and runtime enforcement. May be the same
person as the author, but the roles are separated in process.

**Operator:** Any human with vault access — John, a collaborator, a reviewer.

**Epistemic Status:** The warrant status of a claim: working_idea (provisional,
exploratory), provisional_claim (under review), stable_finding (ratified,
defensible), abandoned (disowned, retained for history), quarantined
(failed governance check).

**Origin Type:** The provenance category of a claim: human_authored,
extraction, summarization, synthesis, speculation.

**Provenance:** The complete origin trail of a claim — who produced it, from
what sources, through which handoffs, at what confidence, under what
epistemic status. Provenance is mandatory and non-strippable.
