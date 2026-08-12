"""
policy_engine — Runtime governance enforcement for the Vault Constitution.

Implements write-time, retrieval-time, synthesis-time, promotion-time,
and export-time checks per Build Specification v1.0.

All enforcement decisions are logged. The engine fails closed.
"""

import json
import hashlib
import os
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple, Union

UTC = timezone.utc


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

def _load_config(path: str = None) -> dict:
    if path is None:
        path = os.path.join(os.path.dirname(__file__), "governance-config.json")
    if not os.path.exists(path):
        path = os.path.join(os.path.dirname(__file__), "..", "governance", "governance-config.json")
    with open(path) as f:
        return json.load(f)


# ═══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class Decision(Enum):
    ALLOW = "allow"
    DENY = "deny"
    QUARANTINE = "quarantine"
    FLAG = "flag"


@dataclass
class PolicyDecision:
    decision_id: str = field(default_factory=lambda: f"pol_{uuid.uuid4().hex[:10]}")
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    action: str = ""
    subject: Dict[str, str] = field(default_factory=dict)
    object_ref: Dict[str, str] = field(default_factory=dict)
    decision: Decision = Decision.DENY
    rules_evaluated: List[str] = field(default_factory=list)
    obligations: List[str] = field(default_factory=list)
    violations: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "decision_id": self.decision_id,
            "timestamp": self.timestamp,
            "action": self.action,
            "subject": self.subject,
            "object": self.object_ref,
            "decision": self.decision.value,
            "rules_evaluated": self.rules_evaluated,
            "obligations": self.obligations,
            "violations": self.violations,
        }


class PolicyViolation(Exception):
    """Raised when a policy check fails. Carries the decision record."""
    def __init__(self, decision: PolicyDecision):
        self.decision = decision
        super().__init__(f"Policy violation: {decision.decision.value} — {decision.violations}")


# ═══════════════════════════════════════════════════════════════════════════════
# AUDIT LOGGER
# ═══════════════════════════════════════════════════════════════════════════════

class AuditLogger:
    """Append-only audit log for all governed events."""

    def __init__(self, log_dir: Optional[str] = None):
        if log_dir is None:
            log_dir = os.path.join(os.path.dirname(__file__), "..", "governance", "logs")
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self._previous_hash: Optional[str] = None

    def log(self, event_type: str, decision: Optional[PolicyDecision] = None,
            extra: Optional[Dict[str, Any]] = None) -> str:
        event_id = f"evt_{uuid.uuid4().hex[:10]}"
        payload = {
            "event_id": event_id,
            "event_type": event_type,
            "timestamp": datetime.now(UTC).isoformat(),
            "policy_decision": decision.to_dict() if decision else None,
            "extra": extra or {},
            "previous_event_hash": self._previous_hash,
        }
        raw = json.dumps(payload, sort_keys=True)
        payload["event_hash"] = hashlib.sha256(raw.encode()).hexdigest()
        self._previous_hash = payload["event_hash"]

        # Write to daily log
        date_str = datetime.now(UTC).strftime("%Y-%m-%d")
        log_path = os.path.join(self.log_dir, f"audit-{date_str}.jsonl")
        with open(log_path, "a") as f:
            f.write(json.dumps(payload) + "\n")

        return event_id


# ═══════════════════════════════════════════════════════════════════════════════
# PROVENANCE VALIDATOR
# ═══════════════════════════════════════════════════════════════════════════════

class ProvenanceValidator:
    """Validates note metadata against the canonical schema."""

    # Universal mandatory fields
    UNIVERSAL_MANDATORY = [
        "schema_version", "note_id", "space", "title", "content_hash",
        "metadata_hash", "origin_type", "authorship_status", "epistemic_status",
        "project_id", "created_at", "modified_at", "review_status",
    ]

    # Agent-generated mandatory fields (origin_type != human_authored)
    AGENT_MANDATORY = [
        "agent.agent_id", "agent.role", "agent.model_id",
        "agent.prompt_version", "agent.pipeline_version",
    ]

    # Synthesis mandatory fields
    SYNTHESIS_MANDATORY = [
        "epistemic_markers.interpretive_threshold",
        "epistemic_markers.marker_text",
        "input_refs", "claims",
    ]

    # Extraction mandatory fields
    EXTRACTION_MANDATORY = ["source_refs"]

    # Human-authored mandatory fields
    HUMAN_MANDATORY = ["human_author"]

    @classmethod
    def _get_nested(cls, data: dict, path: str) -> Any:
        keys = path.split(".")
        current = data
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
            else:
                return None
        return current

    @classmethod
    def validate(cls, note_meta: dict) -> Tuple[bool, List[str]]:
        """Return (is_valid, list_of_missing_fields)."""
        missing = []

        # Universal fields
        for field in cls.UNIVERSAL_MANDATORY:
            val = cls._get_nested(note_meta, field)
            if val is None or (isinstance(val, str) and val.strip() == ""):
                missing.append(field)

        origin = note_meta.get("origin_type", "")

        # Agent-generated fields
        if origin != "human_authored":
            for field in cls.AGENT_MANDATORY:
                val = cls._get_nested(note_meta, field)
                if val is None or (isinstance(val, str) and val.strip() == ""):
                    missing.append(field)
            has_input_refs = bool(note_meta.get("input_refs"))
            if not has_input_refs:
                missing.append("input_refs")
            has_handoff = bool(note_meta.get("handoff_chain"))
            if not has_handoff:
                missing.append("handoff_chain")

        # Synthesis-specific
        if origin == "synthesis":
            for field in cls.SYNTHESIS_MANDATORY:
                val = cls._get_nested(note_meta, field)
                if field == "epistemic_markers.interpretive_threshold":
                    if val is not True:
                        missing.append(field)
                elif val is None or (isinstance(val, str) and val.strip() == ""):
                    missing.append(field)
            if not note_meta.get("input_refs"):
                missing.append("input_refs")

        # Extraction-specific
        if origin == "extraction":
            for field in cls.EXTRACTION_MANDATORY:
                val = cls._get_nested(note_meta, field)
                if not val:
                    missing.append(field)

        # Human-authored
        if origin == "human_authored":
            for field in cls.HUMAN_MANDATORY:
                val = cls._get_nested(note_meta, field)
                if val is None or (isinstance(val, str) and val.strip() == ""):
                    missing.append(field)

        return (len(missing) == 0, missing)


# ═══════════════════════════════════════════════════════════════════════════════
# POLICY ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class PolicyEngine:
    """Runtime governance enforcement. Fails closed per constitution."""

    def __init__(self, config: Optional[dict] = None):
        self.config = config or _load_config()
        self.audit = AuditLogger()

    # ── Core helpers ────────────────────────────────────────────────────

    def _decision(self, action: str, subject: dict, object_ref: dict,
                  result: Decision, rules: List[str], violations: Optional[List[dict]] = None,
                  obligations: Optional[List[str]] = None) -> PolicyDecision:
        d = PolicyDecision(
            action=action, subject=subject, object_ref=object_ref,
            decision=result, rules_evaluated=rules,
            violations=violations or [], obligations=obligations or [],
        )
        self.audit.log(action, decision=d)
        return d

    def _raise_if_denied(self, decision: PolicyDecision):
        if decision.decision in (Decision.DENY, Decision.QUARANTINE):
            raise PolicyViolation(decision)

    def _has_flag(self, note_meta: dict, key: str) -> bool:
        return bool(note_meta.get(key))

    # ── Write-Time Checks ───────────────────────────────────────────────

    def check_write(self, note_meta: dict, actor: dict, target_space: str) -> PolicyDecision:
        """
        Validate a vault write request.
        actor: {"agent_id": str, "role": str, "token_id": str}
        Returns PolicyDecision; raises PolicyViolation if denied/quarantined.
        """
        rules = []
        violations = []

        # W-001: Space authorization
        rules.append("W-001")
        role = actor.get("role", "")
        allowed_spaces = {
            "human": ["my_thinking", "governance", "agent_extractions", "agent_syntheses", "quarantine"],
            "retrieval": ["source_cache"],
            "extraction": ["agent_extractions"],
            "summarization": ["agent_summaries"],
            "contradiction_detection": ["agent_syntheses"],
            "dissent": ["agent_dissent"],
            "synthesis": ["agent_syntheses"],
            "promotion": ["my_thinking"],
            "export": [],
        }
        permitted = allowed_spaces.get(role, [])
        if target_space not in permitted:
            violations.append({"rule": "W-001", "reason": f"Role '{role}' cannot write to '{target_space}'",
                              "severity": "critical"})

        # W-001b: No agent writes directly to /my-thinking/ without promotion
        if target_space == "my_thinking" and role not in ("human", "promotion"):
            violations.append({"rule": "W-001b", "reason": "Firebreak: agents cannot write to /my-thinking/",
                              "severity": "critical"})

        # W-002: Provenance completeness
        rules.append("W-002")
        valid, missing = ProvenanceValidator.validate(note_meta)
        if not valid:
            violations.append({"rule": "W-002", "reason": f"Missing mandatory provenance: {missing}",
                              "severity": "critical"})

        # W-003: Synthesis marker
        rules.append("W-003")
        if note_meta.get("origin_type") == "synthesis":
            markers = note_meta.get("epistemic_markers", {})
            if not markers.get("interpretive_threshold"):
                violations.append({"rule": "W-003", "reason": "Synthesis missing interpretive threshold marker",
                                  "severity": "critical"})

        # W-004: Epistemic status limit
        rules.append("W-004")
        if note_meta.get("origin_type") != "human_authored":
            if note_meta.get("authorship_status") != "human_promoted":
                if note_meta.get("epistemic_status") == "stable_finding":
                    violations.append({"rule": "W-004", "reason": "Agent cannot assign stable_finding",
                                      "severity": "critical"})

        # W-005: Firebreak — circular synthesis
        rules.append("W-005")
        if note_meta.get("origin_type") == "synthesis":
            for inp in note_meta.get("input_refs", []):
                if inp.get("origin_type") == "synthesis" and inp.get("authorship_status") != "human_promoted":
                    if not note_meta.get("circular_synthesis_flag"):
                        violations.append({"rule": "W-005",
                                          "reason": f"Circular synthesis: cites unpromoted synthesis {inp.get('note_id')}",
                                          "severity": "high"})

        # Determine result
        if any(v["severity"] == "critical" for v in violations):
            if self.config["quarantine"]["auto_quarantine_missing_provenance"]:
                result = Decision.QUARANTINE
            else:
                result = Decision.DENY
        elif violations:
            result = Decision.FLAG
        else:
            result = Decision.ALLOW

        return self._decision("vault.write", actor, {"note_id": note_meta.get("note_id", ""), "space": target_space},
                             result, rules, violations,
                             obligations=["set_review_status_pending", "append_audit_log"])

    # ── Retrieval-Time Checks ───────────────────────────────────────────

    def check_retrieval(self, request: dict, actor: dict, candidates: List[dict]) -> Tuple[List[dict], PolicyDecision]:
        """
        Filter candidates through retrieval policy.
        Returns (filtered_candidates, decision).
        """
        rules = ["R-001", "R-002", "R-003", "R-004", "R-005", "R-006"]
        violations = []
        filtered = []

        for note in candidates:
            space = note.get("space", "")
            epi = note.get("epistemic_status", "")
            classification = note.get("classification", [])

            # R-001: Quarantine exclusion
            if space == "quarantine" or epi == "quarantined":
                continue

            # R-002: Abandoned exclusion
            if epi == "abandoned":
                auth = request.get("abandoned_authorization", {})
                if note.get("note_id") not in auth.get("note_ids", []):
                    continue

            # R-004: Classification gates
            if "dual_use" in classification:
                if not actor.get("classification_clearance", {}).get("dual_use"):
                    violations.append({"rule": "R-004", "reason": f"Dual-use note {note.get('note_id')} blocked",
                                      "severity": "high"})
                    continue

            # R-003: Private provisional
            if note.get("privacy_context") == "private_provisional":
                if note.get("note_id") not in request.get("explicitly_included", []):
                    continue

            filtered.append(note)

        result = Decision.DENY if violations and not filtered else Decision.ALLOW
        return filtered, self._decision("retrieval.request", actor,
                                        {"query": request.get("query_hash", ""), "n_candidates": len(candidates)},
                                        result, rules, violations)

    # ── Synthesis-Time Checks ───────────────────────────────────────────

    def check_synthesis_pre(self, input_notes: List[dict], actor: dict) -> PolicyDecision:
        """Pre-synthesis validation of inputs."""
        rules = ["SYN-PRE-001", "SYN-PRE-002", "SYN-PRE-003"]
        violations = []

        for note in input_notes:
            if note.get("epistemic_status") == "quarantined":
                violations.append({"rule": "SYN-PRE-001",
                                   "reason": f"Quarantined input: {note.get('note_id')}",
                                   "severity": "critical"})
            if note.get("epistemic_status") == "abandoned":
                violations.append({"rule": "SYN-PRE-002",
                                   "reason": f"Abandoned input without authorization: {note.get('note_id')}",
                                   "severity": "critical"})
            valid, missing = ProvenanceValidator.validate(note)
            if not valid:
                violations.append({"rule": "SYN-PRE-003",
                                   "reason": f"Input {note.get('note_id')} missing provenance: {missing}",
                                   "severity": "critical"})

        if any(v["severity"] == "critical" for v in violations):
            result = Decision.DENY
        elif violations:
            result = Decision.FLAG
        else:
            result = Decision.ALLOW

        return self._decision("synthesis.run", actor,
                             {"n_inputs": len(input_notes)},
                             result, rules, violations)

    def check_synthesis_post(self, output_meta: dict, input_notes: List[dict],
                             actor: dict) -> PolicyDecision:
        """Post-synthesis validation of output."""
        rules = ["SYN-001", "SYN-002", "SYN-003", "SYN-004", "SYN-005"]
        violations = []

        # SYN-001: Threshold marker
        markers = output_meta.get("epistemic_markers", {})
        if not markers.get("interpretive_threshold"):
            violations.append({"rule": "SYN-001", "reason": "Synthesis output missing threshold marker",
                              "severity": "critical"})

        # SYN-002: No stable_finding
        if output_meta.get("epistemic_status") == "stable_finding":
            violations.append({"rule": "SYN-002", "reason": "Agent assigned stable_finding without promotion",
                              "severity": "critical"})

        # SYN-003: Tensions for contradictory inputs
        has_contradiction = False
        for i, n1 in enumerate(input_notes):
            for n2 in input_notes[i + 1:]:
                c1 = [c.get("claim_id") for c in n1.get("claims", [])]
                c2 = [c.get("claim_id") for c in n2.get("claims", [])]
                if set(c1) & set(c2):
                    has_contradiction = True
                    break
        if has_contradiction and not output_meta.get("tensions"):
            no_tension = output_meta.get("tension_detection", {}).get("no_tension_detected")
            if not no_tension:
                violations.append({"rule": "SYN-003",
                                   "reason": "Contradictory inputs but no tensions emitted",
                                   "severity": "high"})

        # SYN-004: Agent cannot resolve tensions
        for t in output_meta.get("tensions", []):
            if t.get("resolution_status") == "resolved":
                violations.append({"rule": "SYN-004",
                                   "reason": f"Agent resolved tension {t.get('tension_id')}",
                                   "severity": "critical"})

        # SYN-005: Circular synthesis
        for inp in output_meta.get("input_refs", []):
            if inp.get("origin_type") == "synthesis" and inp.get("authorship_status") != "human_promoted":
                if not output_meta.get("circular_synthesis_flag"):
                    violations.append({"rule": "SYN-005",
                                      "reason": f"Circular synthesis: cites unpromoted synthesis",
                                      "severity": "high"})

        if any(v["severity"] == "critical" for v in violations):
            result = Decision.QUARANTINE
        elif violations:
            result = Decision.FLAG
        else:
            result = Decision.ALLOW

        return self._decision("synthesis.run", actor,
                             {"note_id": output_meta.get("note_id", ""), "n_inputs": len(input_notes)},
                             result, rules, violations)

    # ── Promotion-Time Checks ───────────────────────────────────────────

    def check_promotion(self, request: dict, actor: dict) -> PolicyDecision:
        """Validate a promotion request. Requires human promotion token."""
        rules = ["P-001", "P-002"]
        violations = []

        # P-001: Human token required
        if not request.get("human_promotion_token"):
            violations.append({"rule": "P-001", "reason": "Promotion requires human promotion token",
                              "severity": "critical"})

        # Valid promotion type?
        valid_types = {"human_ratified", "human_annotated", "human_reconstructed", "human_composed_from_scaffold"}
        if request.get("promotion_type") not in valid_types:
            violations.append({"rule": "P-002", "reason": f"Invalid promotion type: {request.get('promotion_type')}",
                              "severity": "critical"})

        result = Decision.DENY if violations else Decision.ALLOW
        return self._decision("promotion.request", actor,
                             {"original_note_id": request.get("original_note_id", "")},
                             result, rules, violations)

    # ── Export-Time Checks ──────────────────────────────────────────────

    def check_export(self, request: dict, actor: dict, notes: List[dict]) -> PolicyDecision:
        """Validate an export request."""
        rules = ["E-001", "E-002", "E-003", "E-004"]
        violations = []
        risk_tier = request.get("risk_tier", 2)

        # E-001: Provenance manifest
        if request.get("strip_provenance") and not request.get("stripping_justification"):
            violations.append({"rule": "E-001", "reason": "Provenance stripping requires justification; export blocked",
                              "severity": "critical"})

        # E-002: Publication audit for Tier 3
        if risk_tier >= 3 and request.get("purpose") in ("publication", "journal_submission", "public_output"):
            if not request.get("audit_confirmed"):
                violations.append({"rule": "E-002", "reason": "Tier 3 export requires confirmed provenance audit",
                                  "severity": "critical"})

        # E-003: Dual-use gate
        for note in notes:
            if "dual_use" in note.get("classification", []):
                if not request.get("dual_use_approval"):
                    violations.append({"rule": "E-003",
                                       "reason": f"Dual-use note {note.get('note_id')} requires explicit export approval",
                                       "severity": "critical"})

        # E-004: Agent synthesis disclosure
        has_synthesis = any(n.get("origin_type") == "synthesis" for n in notes)
        if has_synthesis and risk_tier >= 3:
            if not request.get("agent_disclosure_included"):
                violations.append({"rule": "E-004",
                                   "reason": "Export contains agent synthesis; disclosure recommended",
                                   "severity": "low"})

        if any(v["severity"] == "critical" for v in violations):
            result = Decision.DENY
        elif violations:
            result = Decision.FLAG
        else:
            result = Decision.ALLOW

        return self._decision("export.request", actor,
                             {"purpose": request.get("purpose", ""), "risk_tier": risk_tier},
                             result, rules, violations)

    # ── Firebreak enforcement ───────────────────────────────────────────

    def enforce_firebreak(self, note_meta: dict, target_space: str) -> bool:
        """Return True if the firebreak is intact (write should be blocked)."""
        origin = note_meta.get("origin_type", "")
        authorship = note_meta.get("authorship_status", "")
        # Block: agent-generated content trying to enter my_thinking without promotion
        if target_space == "my_thinking":
            if origin != "human_authored" and authorship not in ("human_promoted", "human_reconstructed"):
                return True  # firebreak violation
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# GOVERNANCE WRAPPER
# ═══════════════════════════════════════════════════════════════════════════════

class GovernanceLayer:
    """Convenience wrapper: policy engine + provenance validator + audit log."""

    def __init__(self, config_path: Optional[str] = None):
        cfg = _load_config(config_path) if config_path else None
        self.engine = PolicyEngine(cfg if cfg else None)
        self.provenance = ProvenanceValidator()
        self.audit = self.engine.audit

    def handle_write(self, note_meta: dict, actor: dict, target_space: str) -> PolicyDecision:
        """Validate and enforce a vault write. Raises PolicyViolation on deny/quarantine."""
        decision = self.engine.check_write(note_meta, actor, target_space)
        self.engine._raise_if_denied(decision)
        return decision

    def handle_retrieval(self, request: dict, actor: dict, candidates: List[dict]) -> Tuple[List[dict], PolicyDecision]:
        """Filter and return allowed candidates."""
        return self.engine.check_retrieval(request, actor, candidates)

    def handle_synthesis(self, input_notes: List[dict], output_meta: dict, actor: dict) -> PolicyDecision:
        """Pre + post synthesis checks."""
        pre = self.engine.check_synthesis_pre(input_notes, actor)
        self.engine._raise_if_denied(pre)
        post = self.engine.check_synthesis_post(output_meta, input_notes, actor)
        self.engine._raise_if_denied(post)
        return post

    def handle_promotion(self, request: dict, actor: dict) -> PolicyDecision:
        """Validate promotion. Raises on deny."""
        decision = self.engine.check_promotion(request, actor)
        self.engine._raise_if_denied(decision)
        return decision

    def handle_export(self, request: dict, actor: dict, notes: List[dict]) -> PolicyDecision:
        """Validate export. Raises on deny."""
        decision = self.engine.check_export(request, actor, notes)
        self.engine._raise_if_denied(decision)
        return decision
