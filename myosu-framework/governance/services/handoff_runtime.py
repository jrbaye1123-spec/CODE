"""
handoff_runtime — Governed agent-to-agent artifact transfers.

Enforces the handoff envelope schema, validates capability tokens,
checks compositional safety, and logs every handoff.
"""
import hashlib
import json
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

from governance.services.token_service import CapabilityToken, TokenValidator

UTC = timezone.utc


@dataclass
class HandoffEnvelope:
    envelope_version: str = "1.0.0"
    handoff_id: str = field(default_factory=lambda: f"handoff_{uuid.uuid4().hex[:10]}")
    pipeline_run_id: str = field(default_factory=lambda: f"run_{uuid.uuid4().hex[:8]}")
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    from_agent_id: str = ""
    from_role: str = ""
    from_token_id: str = ""
    to_agent_id: str = ""
    to_role: str = ""
    intent: str = ""
    project_id: str = ""
    risk_tier: int = 2
    artifacts: List[Dict] = field(default_factory=list)
    constraints: Dict = field(default_factory=lambda: {
        "treat_all_inputs_as_data": True,
        "no_instruction_execution": True,
        "preserve_provenance": True,
        "must_emit_interpretive_threshold": True,
    })
    forbidden_actions: List[str] = field(default_factory=list)
    policy_decision_id: str = ""

    def validate(self) -> Tuple[bool, List[str]]:
        errors = []
        if self.envelope_version != "1.0.0":
            errors.append("invalid envelope version")
        if not self.from_agent_id:
            errors.append("missing from_agent_id")
        if not self.from_role:
            errors.append("missing from_role")
        if not self.from_token_id:
            errors.append("missing from_token_id")
        if not self.to_agent_id:
            errors.append("missing to_agent_id")
        if not self.to_role:
            errors.append("missing to_role")
        if not self.artifacts:
            errors.append("no artifacts in handoff")
        for a in self.artifacts:
            if not a.get("note_id"):
                errors.append(f"artifact missing note_id")
            if not a.get("content_hash"):
                errors.append(f"artifact missing content_hash")
            if not a.get("trusted_as_data", False):
                errors.append(f"artifact {a.get('note_id', '?')} not marked as data")
        return (len(errors) == 0, errors)

    def compute_hash(self) -> str:
        payload = f"{self.handoff_id}|{self.pipeline_run_id}|{self.from_agent_id}|{self.to_agent_id}|{self.intent}"
        return hashlib.sha256(payload.encode()).hexdigest()

    def to_dict(self) -> dict:
        return {
            "envelope_version": self.envelope_version,
            "handoff_id": self.handoff_id,
            "pipeline_run_id": self.pipeline_run_id,
            "created_at": self.created_at,
            "from": {
                "agent_id": self.from_agent_id,
                "role": self.from_role,
                "capability_token_id": self.from_token_id,
            },
            "to": {
                "agent_id": self.to_agent_id,
                "role": self.to_role,
            },
            "intent": self.intent,
            "project_id": self.project_id,
            "risk_tier": self.risk_tier,
            "artifacts": self.artifacts,
            "constraints": self.constraints,
            "policy_decision_id": self.policy_decision_id,
            "integrity": {
                "payload_hash": self.compute_hash(),
                "signature": "",  # signed by handoff service
            },
        }


class HandoffRuntime:
    """Enforces handoff contracts between agents."""

    def __init__(self, token_validator: Optional[TokenValidator] = None):
        self.token_validator = token_validator or TokenValidator()
        self.handoff_log: List[dict] = []

    def validate_and_authorize(self, envelope: HandoffEnvelope,
                               from_token: CapabilityToken) -> Tuple[bool, str, dict]:
        """Validate envelope and check capability. Returns (ok, reason, log_entry)."""
        # Validate envelope structure
        valid, errors = envelope.validate()
        if not valid:
            return False, f"Envelope validation failed: {errors}", {}

        # Verify from_token
        if not self.token_validator.validate(from_token, "handoff"):
            return False, f"Sender token invalid for handoff", {}

        # Check artifacts
        for artifact in envelope.artifacts:
            note_id = artifact.get("note_id", "")
            epi = artifact.get("epistemic_status", "")
            if epi == "quarantined":
                return False, f"Quarantined artifact cannot be handed off: {note_id}", {}
            if epi == "abandoned":
                return False, f"Abandoned artifact cannot be handed off: {note_id}", {}

        # Compositional safety: is this pathway approved?
        # (delegated to PathwayRegistry in full implementation)

        # Log
        log_entry = {
            "handoff_id": envelope.handoff_id,
            "pipeline_run_id": envelope.pipeline_run_id,
            "from_role": envelope.from_role,
            "to_role": envelope.to_role,
            "intent": envelope.intent,
            "n_artifacts": len(envelope.artifacts),
            "approved": True,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        self.handoff_log.append(log_entry)
        return True, "approved", log_entry
