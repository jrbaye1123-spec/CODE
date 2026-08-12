"""
vault_core — The Accountability Layer: Executable Covenant for the 묘수 Vault.

Layers:
  0 — ProvenanceFingerprint    (authentication)
  1 — AgentJustification       (verifiability)
  2 — ReviewDashboard          (governance surface)
  3 — DependencyGraph          (integrity / repair)
  4 — GovernanceCadence        (adaptive evolution)

Integrates with the manuscript's topological architecture:
  Acts 1-11  → Core data models and agents (scaffold)
  Acts 12-15 → Dashboard and dependency graph (living mandala)
  The Act That Is Not an Act → Covenant + Cadence (dissolution)
  Appendix   → VaultCore + VaultRunner (executable liturgy)

Author: John (author), System (designer)
Covenant: The author signs. The error is caught. The system evolves.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple
import hashlib
import json
import time
import uuid

UTC = timezone.utc


# ═══════════════════════════════════════════════════════════════════════════════
# PART 1: CORE DATA MODELS (Schema)
# ═══════════════════════════════════════════════════════════════════════════════

class SourceType(Enum):
    EXTRACTED   = "extracted"     # Verbatim from source
    SYNTHESIZED = "synthesized"   # Inferred from multiple sources
    FILTERED    = "filtered"      # Extracted with transformation
    GENERATED   = "generated"     # Novel, no direct source


class ApprovalStatus(Enum):
    UNAPPROVED  = "unapproved"
    PREAPPROVED = "preapproved"   # Auto-approved, pending periodic review
    APPROVED    = "approved"
    REJECTED    = "rejected"
    FLAGGED     = "flagged"


@dataclass
class ProvenanceFingerprint:
    """Layer 0: The Author's Signature — authentication for every claim."""
    author: str = "john"
    source_type: SourceType = SourceType.SYNTHESIZED
    confidence: float = 0.0
    sources: List[Dict[str, Any]] = field(default_factory=list)
    reviewer: Optional[str] = None
    reviewer_timestamp: Optional[datetime] = None
    approval_status: ApprovalStatus = ApprovalStatus.UNAPPROVED
    approval_signature: Optional[str] = None
    synthesis_explanation: Optional[str] = None
    claim_id: str = field(default_factory=lambda: f"claim_{uuid.uuid4().hex[:8]}")
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "author": self.author,
            "source_type": self.source_type.value,
            "confidence": self.confidence,
            "sources": self.sources,
            "reviewer": self.reviewer,
            "reviewer_timestamp": self.reviewer_timestamp.isoformat() if self.reviewer_timestamp else None,
            "approval_status": self.approval_status.value,
            "approval_signature": self.approval_signature,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ProvenanceFingerprint":
        return cls(
            claim_id=d.get("claim_id", f"claim_{uuid.uuid4().hex[:8]}"),
            author=d.get("author", "john"),
            source_type=SourceType(d.get("source_type", "synthesized")),
            confidence=d.get("confidence", 0.0),
            sources=d.get("sources", []),
            reviewer=d.get("reviewer"),
            reviewer_timestamp=datetime.fromisoformat(d["reviewer_timestamp"]) if d.get("reviewer_timestamp") else None,
            approval_status=ApprovalStatus(d.get("approval_status", "unapproved")),
            approval_signature=d.get("approval_signature"),
        )


@dataclass
class AgentJustification:
    """Layer 1: The Agent's Transparency — verifiability for every claim."""
    claim_id: str
    agent_id: str
    agent_version: str
    operation: str = "synthesis"
    extraction_verbatim: List[str] = field(default_factory=list)
    synthesis_explanation: Optional[str] = None
    conflict_flags: List[Dict[str, str]] = field(default_factory=list)
    godel_sentence: str = ""
    inference_chain: List[str] = field(default_factory=list)
    confidence_components: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "agent_id": self.agent_id,
            "agent_version": self.agent_version,
            "operation": self.operation,
            "extraction_verbatim": self.extraction_verbatim,
            "synthesis_explanation": self.synthesis_explanation,
            "conflict_flags": self.conflict_flags,
            "godel_sentence": self.godel_sentence,
            "inference_chain": self.inference_chain,
            "confidence_components": self.confidence_components,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AgentJustification":
        return cls(
            claim_id=d["claim_id"],
            agent_id=d["agent_id"],
            agent_version=d["agent_version"],
            operation=d.get("operation", "synthesis"),
            extraction_verbatim=d.get("extraction_verbatim", []),
            synthesis_explanation=d.get("synthesis_explanation"),
            conflict_flags=d.get("conflict_flags", []),
            godel_sentence=d.get("godel_sentence", ""),
            inference_chain=d.get("inference_chain", []),
            confidence_components=d.get("confidence_components", {}),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# PART 2: COVENANT (Layer 4 Shared Contract)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Covenant:
    """The shared governance contract between author and system."""
    author: str = "john"
    designer: str = "system"
    triple_signature_required: bool = True

    error_policy: Dict[str, Any] = field(default_factory=lambda: {
        "author_owns": True,
        "designer_owns_conditions": True,
        "review_cadence": "weekly",
    })

    crumple_zone: Dict[str, Any] = field(default_factory=lambda: {
        "active": True,
        "max_claims_per_review": 50,
        "min_confidence_for_auto_approval": 0.85,
        "agent_drift_threshold": 0.10,
        "claim_vulnerability_threshold": 0.15,
    })

    def sign(self, claim_id: str, verification_evidence: dict) -> str:
        """Generate triple signature: hash(claim_id + evidence + timestamp)."""
        payload = {
            "claim_id": claim_id,
            "verification_evidence": verification_evidence,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        raw = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()

    def authorize(self, claim_id: str, review_evidence: dict) -> Tuple[bool, str]:
        """Process an author approval with triple signature check."""
        if not self.triple_signature_required:
            return True, "Approved (triple signature not required)"

        required = ["read_source", "attribution_verified", "consequences_accepted"]
        missing = [r for r in required if not review_evidence.get(r, False)]
        if missing:
            return False, f"Missing verification: {', '.join(missing)}"

        signature = self.sign(claim_id, review_evidence)
        return True, signature


# ═══════════════════════════════════════════════════════════════════════════════
# PART 3: VAULT AGENT (Core Retrieval / Synthesis Engine)
# ═══════════════════════════════════════════════════════════════════════════════

class VaultAgent:
    """Retrieval and synthesis engine. Generates claims with full provenance."""

    def __init__(self, agent_id: str, version: str, capabilities: List[str]):
        self.agent_id = agent_id
        self.version = version
        self.capabilities = capabilities
        self.operation_log: List[dict] = []

    def retrieve(self, query: str, sources: List[Dict[str, Any]]) -> List[ProvenanceFingerprint]:
        """Perform retrieval, classifying each claim as extracted or synthesized."""
        results: List[ProvenanceFingerprint] = []
        for source in sources:
            is_extracted = source.get("verbatim") or source.get("quote")
            fingerprint = ProvenanceFingerprint(
                source_type=SourceType.EXTRACTED if is_extracted else SourceType.SYNTHESIZED,
                confidence=source.get("confidence", 0.8),
                sources=[source],
            )
            if not source.get("verbatim"):
                fingerprint.synthesis_explanation = (
                    f"Inferred from source: {source.get('doi', source.get('title', 'unknown'))}"
                )
            fingerprint.confidence = self._compute_confidence(source)
            results.append(fingerprint)
            self.operation_log.append({
                "operation": "retrieve",
                "query": query,
                "source": source.get("doi", source.get("title", "")),
                "claim_id": fingerprint.claim_id,
                "timestamp": datetime.now(UTC).isoformat(),
            })
        return results

    def synthesize(self, query: str, sources: List[Dict[str, Any]]) -> ProvenanceFingerprint:
        """Synthesize a claim from multiple sources."""
        fingerprint = ProvenanceFingerprint(
            source_type=SourceType.SYNTHESIZED,
            confidence=self._aggregate_confidence(sources),
            sources=sources,
            synthesis_explanation=f"Inferred from {len(sources)} sources for query: {query}",
        )
        self.operation_log.append({
            "operation": "synthesize", "query": query,
            "n_sources": len(sources), "claim_id": fingerprint.claim_id,
            "timestamp": datetime.now(UTC).isoformat(),
        })
        return fingerprint

    def generate(self, prompt: str, confidence: float = 0.5) -> ProvenanceFingerprint:
        """Generate a novel claim (no direct source). Low confidence by default."""
        return ProvenanceFingerprint(
            source_type=SourceType.GENERATED,
            confidence=confidence,
        )

    def create_justification(self, claim_id: str, sources: List[Dict[str, Any]],
                              operation: str = "synthesis") -> AgentJustification:
        """Build the full justification path for a claim."""
        verbatim = [s.get("quote", "") for s in sources if s.get("quote")]
        conflict_flags: List[Dict[str, str]] = []
        for i, s1 in enumerate(sources):
            for s2 in sources[i + 1:]:
                if s1.get("contradiction_of") == s2.get("doi") or s2.get("contradiction_of") == s1.get("doi"):
                    conflict_flags.append({
                        "source_a": s1.get("doi", ""),
                        "source_b": s2.get("doi", ""),
                        "contradiction": "flagged_by_source_metadata",
                    })

        inference_steps = [
            f"Retrieved {len(sources)} sources matching query",
            f"Extracted {len(verbatim)} verbatim quotes" if verbatim else "No verbatim quotes extracted",
            f"Synthesized claim from overlapping evidence",
        ]

        godel_raw = f"claim={claim_id}|sources={[s.get('doi','') for s in sources]}|operation={operation}"
        godel_sentence = f"This claim cannot prove its own completeness. Hash: {hashlib.sha256(godel_raw.encode()).hexdigest()[:12]}"

        return AgentJustification(
            claim_id=claim_id,
            agent_id=self.agent_id,
            agent_version=self.version,
            operation=operation,
            extraction_verbatim=verbatim,
            synthesis_explanation=f"Inferred from {len(sources)} sources: {[s.get('doi', '') for s in sources]}",
            conflict_flags=conflict_flags,
            godel_sentence=godel_sentence,
            inference_chain=inference_steps,
            confidence_components={
                "source_reliability": self._source_reliability(sources),
                "alignment": self._alignment_score(sources),
            },
        )

    def _compute_confidence(self, source: dict) -> float:
        base = source.get("confidence", 0.8)
        if source.get("verbatim"):
            base = min(1.0, base + 0.1)
        if source.get("peer_reviewed"):
            base = min(1.0, base + 0.05)
        return base

    def _aggregate_confidence(self, sources: List[dict]) -> float:
        if not sources:
            return 0.0
        individual = [self._compute_confidence(s) for s in sources]
        n = len(individual)
        # More sources → higher aggregate, but diminishing returns
        return sum(individual) / n * min(1.0, 0.7 + 0.1 * n)

    def _source_reliability(self, sources: List[dict]) -> float:
        if not sources:
            return 0.0
        return sum(s.get("confidence", 0.7) for s in sources) / len(sources)

    def _alignment_score(self, sources: List[dict]) -> float:
        """How well sources align (no contradictions)."""
        conflicts = 0
        for i, s1 in enumerate(sources):
            for s2 in sources[i + 1:]:
                if s1.get("contradiction_of") == s2.get("doi") or s2.get("contradiction_of") == s1.get("doi"):
                    conflicts += 1
        total_pairs = max(1, len(sources) * (len(sources) - 1) / 2)
        return 1.0 - (conflicts / total_pairs)


# ═══════════════════════════════════════════════════════════════════════════════
# PART 4: DEPENDENCY GRAPH (Layer 3 — Repair)
# ═══════════════════════════════════════════════════════════════════════════════

class DependencyGraph:
    """Tracks claim dependencies and executes repair protocol."""

    def __init__(self):
        self.nodes: Dict[str, dict] = {}
        self.edges: Dict[str, List[str]] = {}

    def ensure_node(self, claim_id: str):
        if claim_id not in self.nodes:
            self.nodes[claim_id] = {
                "claim_id": claim_id,
                "status": "active",
                "dependents": [],
                "correction_chain": [],
            }
        if claim_id not in self.edges:
            self.edges[claim_id] = []

    def add_dependency(self, claim_id: str, depends_on: str):
        """Register: claim_id depends_on depends_on."""
        self.ensure_node(claim_id)
        self.ensure_node(depends_on)
        if claim_id not in self.nodes[depends_on]["dependents"]:
            self.nodes[depends_on]["dependents"].append(claim_id)
        if claim_id not in self.edges.get(depends_on, []):
            self.edges.setdefault(depends_on, []).append(claim_id)

    def trace_downstream(self, claim_id: str) -> List[str]:
        """BFS: all claims that depend on claim_id (directly or transitively)."""
        visited: set = set()
        queue = [claim_id]
        dependents: List[str] = []
        while queue:
            current = queue.pop()
            if current in visited:
                continue
            visited.add(current)
            for dep in self.edges.get(current, []):
                if dep not in visited:
                    dependents.append(dep)
                    queue.append(dep)
        return dependents

    def repair(self, claim_id: str, new_claim_id: str, correction_note: str) -> dict:
        """Deprecate claim_id, replace with new_claim_id across all dependents."""
        self.ensure_node(claim_id)
        self.ensure_node(new_claim_id)
        self.nodes[claim_id]["status"] = "deprecated"
        self.nodes[claim_id]["correction_chain"].append(new_claim_id)
        downstream = self.trace_downstream(claim_id)
        for dep_id in downstream:
            self.ensure_node(dep_id)
            self.nodes[dep_id]["status"] = "flagged_for_review"
            self.nodes[dep_id]["correction_chain"].append(claim_id)
        return {
            "deprecated_claim": claim_id,
            "new_claim": new_claim_id,
            "dependents_flagged": downstream,
            "correction_note": correction_note,
            "repair_status": "pending_author_review",
        }

    def issue_fix(self, claim_id: str, replacement_id: str, fix_note: str) -> dict:
        """Public repair interface."""
        return self.repair(claim_id, replacement_id, fix_note)


# ═══════════════════════════════════════════════════════════════════════════════
# PART 5: REVIEW DASHBOARD (Layer 2 — Governance Surface)
# ═══════════════════════════════════════════════════════════════════════════════

class ReviewDashboard:
    """Risk-scored review queue for the author."""

    def __init__(self):
        self.claims: Dict[str, str] = {}
        self.provenances: Dict[str, ProvenanceFingerprint] = {}
        self.justifications: Dict[str, AgentJustification] = {}
        self.review_queue: List[Tuple[ProvenanceFingerprint, float]] = []
        self.risk_threshold: float = 0.7

    def register(self, claim_text: str, provenance: ProvenanceFingerprint,
                 justification: AgentJustification):
        self.claims[provenance.claim_id] = claim_text
        self.provenances[provenance.claim_id] = provenance
        self.justifications[provenance.claim_id] = justification

    def compute_risk_score(self, claim_id: str) -> float:
        provenance = self.provenances.get(claim_id)
        if not provenance:
            return 1.0
        type_risk = {
            SourceType.EXTRACTED: 0.1,
            SourceType.FILTERED: 0.3,
            SourceType.SYNTHESIZED: 0.6,
            SourceType.GENERATED: 0.9,
        }.get(provenance.source_type, 0.5)
        confidence_risk = 1.0 - provenance.confidence
        justification = self.justifications.get(claim_id)
        conflict_risk = len(justification.conflict_flags) * 0.1 if justification else 0.0
        return min(1.0, type_risk + confidence_risk + conflict_risk)

    def populate_queue(self, max_claims: int = 50):
        pending = [(cid, prov) for cid, prov in self.provenances.items()
                   if prov.approval_status in (ApprovalStatus.UNAPPROVED, ApprovalStatus.PREAPPROVED)]
        scored = [(prov, self.compute_risk_score(cid)) for cid, prov in pending]
        scored.sort(key=lambda x: x[1], reverse=True)
        self.review_queue = scored[:max_claims]

    def display_claim(self, claim_id: str) -> dict:
        claim_text = self.claims.get(claim_id, "")
        provenance = self.provenances.get(claim_id)
        justification = self.justifications.get(claim_id)
        if not provenance:
            return {"error": "Claim not found"}
        return {
            "claim_text": claim_text,
            "claim_id": claim_id,
            "source_type": provenance.source_type.value,
            "confidence": provenance.confidence,
            "sources": provenance.sources,
            "justification_path": justification.inference_chain if justification else [],
            "conflicts": justification.conflict_flags if justification else [],
            "godel_sentence": justification.godel_sentence if justification else "",
            "risk_score": self.compute_risk_score(claim_id),
            "reviewer_actions": ["approve", "reject", "flag", "request_sources"],
        }


# ═══════════════════════════════════════════════════════════════════════════════
# PART 6: GOVERNANCE CADENCE (Layer 4 — Adaptive Evolution)
# ═══════════════════════════════════════════════════════════════════════════════

class GovernanceCadence:
    """Weekly governance cadence: drift detection, vulnerability tracking, reviewer load."""

    def __init__(self):
        self.weekly_review_log: List[dict] = []
        self.agent_metrics: Dict[str, float] = {}
        self.claim_type_vulnerabilities: Dict[str, float] = {}
        self.reviewer_load_metrics: Dict[str, int] = {}
        self.agent_error_counts: Dict[str, Dict[str, int]] = {}
        self.agent_claim_counts: Dict[str, int] = {}
        self.domain_error_counts: Dict[str, int] = {}
        self.domain_claim_counts: Dict[str, int] = {}
        self.reviewer_claim_counts: Dict[str, int] = {}

    def record_claim(self, agent_id: str, domain: str):
        self.agent_claim_counts[agent_id] = self.agent_claim_counts.get(agent_id, 0) + 1
        self.domain_claim_counts[domain] = self.domain_claim_counts.get(domain, 0) + 1

    def record_error(self, agent_id: str, domain: str):
        self.agent_error_counts.setdefault(agent_id, {})["total"] = \
            self.agent_error_counts.get(agent_id, {}).get("total", 0) + 1
        self.domain_error_counts[domain] = self.domain_error_counts.get(domain, 0) + 1

    def record_review(self, reviewer_id: str):
        self.reviewer_claim_counts[reviewer_id] = self.reviewer_claim_counts.get(reviewer_id, 0) + 1

    def collect_metrics(self):
        """Compute drift scores and vulnerability scores from accumulated counts."""
        for agent_id in self.agent_claim_counts:
            errors = self.agent_error_counts.get(agent_id, {}).get("total", 0)
            total = self.agent_claim_counts[agent_id]
            self.agent_metrics[agent_id] = errors / max(1, total)

        for domain in self.domain_claim_counts:
            errors = self.domain_error_counts.get(domain, 0)
            total = self.domain_claim_counts[domain]
            self.claim_type_vulnerabilities[domain] = errors / max(1, total)

        self.reviewer_load_metrics = dict(self.reviewer_claim_counts)

    def emit_governance_report(self) -> dict:
        self.collect_metrics()
        report = {
            "timestamp": datetime.now(UTC).isoformat(),
            "agent_metrics": self.agent_metrics,
            "claim_type_vulnerabilities": self.claim_type_vulnerabilities,
            "reviewer_load": self.reviewer_load_metrics,
            "recommendations": self._generate_recommendations(),
            "next_cadence": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
        }
        self.weekly_review_log.append(report)
        return report

    def _generate_recommendations(self) -> List[str]:
        recs: List[str] = []
        for agent_id, drift in self.agent_metrics.items():
            if drift > 0.10:
                recs.append(
                    f"Agent '{agent_id}' drift {drift:.1%} exceeds 10% threshold. "
                    "Consider adjusting retrieval thresholds or reducing autonomy."
                )
        for domain, vuln in self.claim_type_vulnerabilities.items():
            if vuln > 0.15:
                recs.append(
                    f"Domain '{domain}' shows {vuln:.0%} error rate. "
                    "Implement domain-specific validation check."
                )
        for reviewer, count in self.reviewer_load_metrics.items():
            if count > 50:
                recs.append(
                    f"Reviewer '{reviewer}' processed {count} claims this period. "
                    "Consider reducing volume or raising auto-approval threshold."
                )
        return recs


# ═══════════════════════════════════════════════════════════════════════════════
# PART 7: VAULT CORE (The Orchestrator)
# ═══════════════════════════════════════════════════════════════════════════════

class VaultCore:
    """The complete vault system integrating all five accountability layers."""

    def __init__(self):
        self.claims: Dict[str, str] = {}
        self.provenances: Dict[str, ProvenanceFingerprint] = {}
        self.justifications: Dict[str, AgentJustification] = {}
        self.graph = DependencyGraph()
        self.dashboard = ReviewDashboard()
        self.governance = GovernanceCadence()
        self.covenant = Covenant()
        self.agents: List[VaultAgent] = []

    # ── Ingest ────────────────────────────────────────────────────────────

    def add_claim(self, claim_text: str, provenance: ProvenanceFingerprint,
                  justification: AgentJustification) -> str:
        """Ingest a claim. Route based on confidence and approval status."""
        cid = provenance.claim_id

        if provenance.approval_status == ApprovalStatus.APPROVED:
            self._store_claim(claim_text, provenance, justification)
        elif provenance.confidence >= self.covenant.crumple_zone["min_confidence_for_auto_approval"]:
            provenance.approval_status = ApprovalStatus.PREAPPROVED
            self._store_claim(claim_text, provenance, justification)
        else:
            self.dashboard.register(claim_text, provenance, justification)

        domain = self._infer_domain(claim_text)
        self.governance.record_claim(justification.agent_id, domain)
        return cid

    def _store_claim(self, claim_text: str, provenance: ProvenanceFingerprint,
                     justification: AgentJustification):
        self.claims[provenance.claim_id] = claim_text
        self.provenances[provenance.claim_id] = provenance
        self.justifications[provenance.claim_id] = justification
        self.dashboard.register(claim_text, provenance, justification)
        for source in provenance.sources:
            if source.get("depends_on"):
                self.graph.add_dependency(provenance.claim_id, source["depends_on"])

    def _infer_domain(self, text: str) -> str:
        text_lower = text.lower()
        if any(kw in text_lower for kw in ["rhr", "heart rate", "hrv", "cardiac", "autonomic"]):
            return "autonomic"
        if any(kw in text_lower for kw in ["quantum", "wavefunction", "coherence", "superposition"]):
            return "quantum"
        if any(kw in text_lower for kw in ["psychopathy", "empathy", "interocept", "emotion"]):
            return "psychology"
        if any(kw in text_lower for kw in ["gödel", "lawvere", "fixed point", "incompleteness"]):
            return "mathematics"
        return "general"

    # ── Review ────────────────────────────────────────────────────────────

    def review_claim(self, claim_id: str, review_evidence: dict,
                     action: ApprovalStatus) -> dict:
        """Process a human review decision. Checks both stored and dashboard claims."""
        provenance = self.provenances.get(claim_id)
        if not provenance:
            # Check dashboard for queued/unstored claims
            for _cid, _prov in self.dashboard.provenances.items():
                if _cid == claim_id:
                    provenance = _prov
                    break
            if not provenance:
                for prov, _score in self.dashboard.review_queue:
                    if prov.claim_id == claim_id:
                        provenance = prov
                        break
        if not provenance:
            return {"status": "error", "reason": f"Claim {claim_id} not found"}

        approved, signature_or_reason = self.covenant.authorize(claim_id, review_evidence)
        if not approved:
            return {"status": "rejected", "reason": signature_or_reason}

        provenance.approval_status = action
        provenance.reviewer = "john"
        provenance.reviewer_timestamp = datetime.now(UTC)
        provenance.approval_signature = signature_or_reason
        provenance.updated_at = datetime.now(UTC)

        self.governance.record_review("john")

        if action == ApprovalStatus.APPROVED:
            for dep_id in self.graph.trace_downstream(claim_id):
                dep_prov = self.provenances.get(dep_id)
                if dep_prov and dep_prov.approval_status == ApprovalStatus.PREAPPROVED:
                    dep_prov.approval_status = ApprovalStatus.APPROVED
                    dep_prov.approval_signature = f"cascade_from_{claim_id}"
        elif action == ApprovalStatus.REJECTED:
            for dep_id in self.graph.trace_downstream(claim_id):
                dep_prov = self.provenances.get(dep_id)
                if dep_prov:
                    dep_prov.approval_status = ApprovalStatus.FLAGGED

        return {
            "status": action.value,
            "signature": signature_or_reason,
            "claim_id": claim_id,
            "timestamp": datetime.now(UTC).isoformat(),
        }

    # ── Repair ─────────────────────────────────────────────────────────────

    def repair_claim(self, claim_id: str, new_claim_text: str,
                     new_provenance: ProvenanceFingerprint, fix_note: str) -> dict:
        """Execute full repair protocol."""
        if new_provenance.approval_status != ApprovalStatus.APPROVED:
            return {"status": "error", "reason": "Replacement claim must be pre-approved"}

        repair_result = self.graph.issue_fix(claim_id, new_provenance.claim_id, fix_note)
        self._store_claim(new_claim_text, new_provenance,
                          self.justifications.get(claim_id, AgentJustification(
                              claim_id=new_provenance.claim_id, agent_id="repair",
                              agent_version="manual", operation="manual_correction")))

        self.governance.record_error(
            self.justifications.get(claim_id, AgentJustification(
                claim_id=claim_id, agent_id="unknown", agent_version="", operation="")).agent_id,
            self._infer_domain(new_claim_text),
        )
        self.governance.weekly_review_log.append({
            "event_type": "repair",
            "claim_id": claim_id,
            "replacement_id": new_provenance.claim_id,
            "fix_note": fix_note,
            "timestamp": datetime.now(UTC).isoformat(),
        })
        return repair_result

    # ── Status ─────────────────────────────────────────────────────────────

    def get_status(self) -> dict:
        total = len(self.claims)
        approved = sum(1 for p in self.provenances.values() if p.approval_status == ApprovalStatus.APPROVED)
        preapproved = sum(1 for p in self.provenances.values() if p.approval_status == ApprovalStatus.PREAPPROVED)
        pending = sum(1 for p in self.provenances.values() if p.approval_status == ApprovalStatus.UNAPPROVED)
        flagged = sum(1 for p in self.provenances.values() if p.approval_status == ApprovalStatus.FLAGGED)
        rejected = sum(1 for p in self.provenances.values() if p.approval_status == ApprovalStatus.REJECTED)
        return {
            "total_claims": total + len(self.dashboard.claims),
            "stored_claims": total,
            "approved": approved,
            "preapproved": preapproved,
            "pending_review": pending,
            "flagged": flagged,
            "rejected": rejected,
            "agent_metrics": self.governance.agent_metrics,
            "reviewer_load": self.governance.reviewer_load_metrics,
        }

    # ── Persistence ────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "claims": self.claims,
            "provenances": {k: v.to_dict() for k, v in self.provenances.items()},
            "justifications": {k: v.to_dict() for k, v in self.justifications.items()},
        }

    @classmethod
    def from_dict(cls, d: dict) -> "VaultCore":
        vault = cls()
        vault.claims = d.get("claims", {})
        vault.provenances = {k: ProvenanceFingerprint.from_dict(v) for k, v in d.get("provenances", {}).items()}
        vault.justifications = {k: AgentJustification.from_dict(v) for k, v in d.get("justifications", {}).items()}
        for cid, prov in vault.provenances.items():
            vault.dashboard.register(vault.claims.get(cid, ""), prov, vault.justifications.get(cid, AgentJustification(
                claim_id=cid, agent_id="imported", agent_version="", operation="")))
            for source in prov.sources:
                if source.get("depends_on"):
                    vault.graph.add_dependency(cid, source["depends_on"])
        return vault

    def save(self, path: str):
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: str) -> "VaultCore":
        with open(path) as f:
            return cls.from_dict(json.load(f))


# ═══════════════════════════════════════════════════════════════════════════════
# PART 8: VAULT RUNNER (CLI Interface)
# ═══════════════════════════════════════════════════════════════════════════════

class VaultRunner:
    """Executable interface for the vault."""

    def __init__(self, vault: Optional[VaultCore] = None):
        self.vault = vault or VaultCore()
        self._register_agents()

    def _register_agents(self):
        self.vault.agents = [
            VaultAgent("beryl", "1.2", ["retrieval", "synthesis"]),
            VaultAgent("veritas", "0.9", ["validation", "conflict_detection"]),
        ]

    def run(self, command: str, params: dict) -> dict:
        if command == "ingest":
            return self._ingest_claim(params)
        elif command == "review":
            return self._review_claim(params)
        elif command == "repair":
            return self._repair_claim(params)
        elif command == "governance_report":
            return self.vault.governance.emit_governance_report()
        elif command == "status":
            return self.vault.get_status()
        elif command == "dashboard":
            return self._dashboard(params)
        else:
            return {"error": f"Unknown command: {command}"}

    def _ingest_claim(self, params: dict) -> dict:
        agent_id = params.get("agent_id", "beryl")
        agent = next((a for a in self.vault.agents if a.agent_id == agent_id), None)
        if not agent:
            return {"status": "error", "reason": f"Agent '{agent_id}' not found"}

        sources = params.get("sources", [])
        fingerprint = ProvenanceFingerprint(
            source_type=SourceType(params.get("source_type", "synthesized")),
            confidence=params.get("confidence", 0.8),
            sources=sources,
        )
        if params.get("approved"):
            fingerprint.approval_status = ApprovalStatus.APPROVED

        justification = agent.create_justification(
            fingerprint.claim_id, sources, params.get("operation", "synthesis"))
        cid = self.vault.add_claim(params["text"], fingerprint, justification)
        return {"status": "ingested", "claim_id": cid}

    def _review_claim(self, params: dict) -> dict:
        action_map = {
            "approve": ApprovalStatus.APPROVED,
            "reject": ApprovalStatus.REJECTED,
            "flag": ApprovalStatus.FLAGGED,
        }
        return self.vault.review_claim(
            params["claim_id"],
            params.get("review_evidence", {}),
            action_map[params["action"]],
        )

    def _repair_claim(self, params: dict) -> dict:
        new_prov = ProvenanceFingerprint(
            author="john",
            source_type=SourceType.EXTRACTED if params.get("direct_quote") else SourceType.SYNTHESIZED,
            sources=params.get("new_sources", []),
            confidence=1.0,
        )
        new_prov.approval_status = ApprovalStatus.APPROVED
        self.vault.add_claim(params["new_text"], new_prov,
                             AgentJustification(claim_id=new_prov.claim_id, agent_id="human_reviewer",
                                                agent_version="manual", operation="manual_correction"))
        return self.vault.repair_claim(
            params["claim_id"], params["new_text"], new_prov,
            params.get("fix_note", "Manual repair"))

    def _dashboard(self, params: dict) -> dict:
        self.vault.dashboard.populate_queue(max_claims=params.get("max", 10))
        return {
            "queue_length": len(self.vault.dashboard.review_queue),
            "top_claims": [
                {"claim_id": prov.claim_id, "risk_score": score, "source_type": prov.source_type.value}
                for prov, score in self.vault.dashboard.review_queue[:5]
            ],
        }


# ═══════════════════════════════════════════════════════════════════════════════
# DEMO
# ═══════════════════════════════════════════════════════════════════════════════

def run_demo():
    """Demonstrate the full vault accountability circuit."""
    print("=" * 60)
    print("VAULT ACCOUNTABILITY LAYER — Executable Covenant Demo")
    print("=" * 60)

    runner = VaultRunner()

    # ── Ingest ──
    print("\n[1] INGEST — Adding claims with provenance")
    c1 = runner.run("ingest", {
        "text": "Low resting heart rate predicts reduced affective empathy in males.",
        "sources": [
            {"doi": "10.1016/j.psychres.2014.05.003", "page": 112,
             "quote": "RHR is inversely correlated with empathy measures.",
             "confidence": 0.9, "peer_reviewed": True},
        ],
        "agent_id": "beryl",
        "source_type": "extracted",
        "confidence": 0.92,
    })
    print(f"  Claim ingested: {c1['claim_id']}")

    c2 = runner.run("ingest", {
        "text": "HRV biofeedback improves executive function in six sessions.",
        "sources": [
            {"doi": "10.1016/j.neubiorev.2017.02.003", "quote": "Six sessions sufficient for cognitive control improvements.",
             "confidence": 0.88, "peer_reviewed": True},
        ],
        "agent_id": "beryl",
        "source_type": "extracted",
        "confidence": 0.88,
    })
    print(f"  Claim ingested: {c2['claim_id']}")

    c3 = runner.run("ingest", {
        "text": "The sinoatrial node may couple quantum coherence to classical autonomic output.",
        "sources": [
            {"doi": "10.20944/preprints202503.0769.v1", "confidence": 0.65, "peer_reviewed": False},
        ],
        "agent_id": "beryl",
        "source_type": "synthesized",
        "confidence": 0.50,
    })
    print(f"  Claim ingested: {c3['claim_id']}  (low confidence — queued for review)")

    # ── Dashboard ──
    print("\n[2] DASHBOARD — Review queue")
    dash = runner.run("dashboard", {"max": 10})
    print(f"  Queue length: {dash['queue_length']}")
    for item in dash["top_claims"]:
        print(f"    {item['claim_id']}: risk={item['risk_score']:.2f} ({item['source_type']})")

    # ── Review ──
    print("\n[3] REVIEW — Author approves claim with triple signature")
    review = runner.run("review", {
        "claim_id": c1["claim_id"],
        "action": "approve",
        "review_evidence": {
            "read_source": True,
            "attribution_verified": True,
            "consequences_accepted": True,
        },
    })
    print(f"  Status: {review['status']}")
    print(f"  Signature: {review['signature'][:20]}...")

    # ── Reject low-confidence claim ──
    review2 = runner.run("review", {
        "claim_id": c3["claim_id"],
        "action": "reject",
        "review_evidence": {
            "read_source": True,
            "attribution_verified": False,
            "consequences_accepted": False,
        },
    })
    print(f"  Status (low-conf claim): {review2['status']} — {review2['reason']}")

    # ── Repair ──
    print("\n[4] REPAIR — Correcting a claim with full downstream trace")
    repair = runner.run("repair", {
        "claim_id": c3["claim_id"],
        "new_text": "The sinoatrial node may couple quantum coherence to classical autonomic output in mammals only.",
        "new_sources": [
            {"doi": "10.20944/preprints202503.0769.v1", "page": 3, "quote": "Observed in mammalian cardiac tissue.",
             "confidence": 0.95},
        ],
        "fix_note": "Added species scope qualifier. Original was over-broad.",
        "direct_quote": True,
    })
    print(f"  Repair status: {repair['repair_status']}")
    print(f"  Dependents flagged: {len(repair['dependents_flagged'])}")

    # ── Governance ──
    print("\n[5] GOVERNANCE — Weekly cadence report")
    report = runner.run("governance_report", {})
    print(f"  Agent metrics: {report['agent_metrics']}")
    print(f"  Reviewer load: {report['reviewer_load']}")
    if report["recommendations"]:
        for rec in report["recommendations"]:
            print(f"  → {rec}")
    else:
        print("  → No recommendations (all metrics within thresholds)")

    # ── Status ──
    print("\n[6] STATUS — Vault health summary")
    status = runner.run("status", {})
    print(f"  Total claims:   {status['total_claims']}")
    print(f"  Approved:       {status['approved']}")
    print(f"  Pre-approved:   {status['preapproved']}")
    print(f"  Pending review: {status['pending_review']}")
    print(f"  Flagged:        {status['flagged']}")

    # ── Covenant check ──
    print("\n[7] COVENANT — Triple signature verification")
    ok, sig = runner.vault.covenant.authorize("test_claim", {
        "read_source": True, "attribution_verified": True, "consequences_accepted": True,
    })
    print(f"  Full evidence: {ok}, signature: {sig[:20]}...")
    partial, reason = runner.vault.covenant.authorize("test_claim", {
        "read_source": True, "attribution_verified": False, "consequences_accepted": True,
    })
    print(f"  Partial evidence: {partial}, reason: {reason}")

    print("\n" + "=" * 60)
    print("The vault listens. The author signs. The error is caught.")
    print("The system evolves. The covenant holds.")
    print("Åverdön. 점화. 축. 회통. 토포스.")
    print("신 한 마리.")
    print("=" * 60)

    return runner


if __name__ == "__main__":
    run_demo()
