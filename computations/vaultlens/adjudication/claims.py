"""Expert claims: policy-safe manifest schema for cross-domain adjudication.

Experts do NOT send raw evidence. They send signed claim manifests with
evidence hashes, policy flags, and confidence. The adjudicator never
touches the underlying confidential data.
"""

import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass, field
from typing import Literal, Optional


ClaimType = Literal[
    "causal", "evidential", "temporal", "definitional",
    "provenance", "procedural", "legal", "medical",
    "financial", "semantic", "informational",
]


@dataclass
class EvidenceManifest:
    """Policy-safe evidence reference: hash + metadata, no raw data."""
    evidence_id: str
    expert_id: str
    hash: str
    status: str = "active"
    confidence: float = 1.0
    accessible_under_policy: bool = False

    def to_dict(self) -> dict:
        return {
            "evidence_id": self.evidence_id,
            "expert_id": self.expert_id,
            "hash": self.hash,
            "status": self.status,
            "confidence": self.confidence,
            "accessible_under_policy": self.accessible_under_policy,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "EvidenceManifest":
        return cls(**{k: v for k, v in d.items()
                      if k in cls.__dataclass_fields__})


@dataclass
class ExpertClaim:
    """A policy-safe claim from a sovereign expert."""
    claim_id: str
    expert_id: str
    domain: str
    jurisdiction: str
    text: str
    claim_type: ClaimType = "definitional"
    confidence: float = 0.5
    evidence_manifests: list[EvidenceManifest] = field(default_factory=list)
    status: str = "active"
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None
    policy_flags: list[str] = field(default_factory=list)
    hmac_sig: str = ""

    def to_dict(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "expert_id": self.expert_id,
            "domain": self.domain,
            "jurisdiction": self.jurisdiction,
            "text": self.text,
            "claim_type": self.claim_type,
            "confidence": self.confidence,
            "evidence_manifests": [e.to_dict() for e in self.evidence_manifests],
            "status": self.status,
            "valid_from": self.valid_from,
            "valid_until": self.valid_until,
            "policy_flags": self.policy_flags,
            "hmac": self.hmac_sig,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ExpertClaim":
        return cls(
            claim_id=d.get("claim_id", ""),
            expert_id=d.get("expert_id", ""),
            domain=d.get("domain", ""),
            jurisdiction=d.get("jurisdiction", ""),
            text=d.get("text", ""),
            claim_type=d.get("claim_type", "definitional"),
            confidence=d.get("confidence", 0.5),
            evidence_manifests=[EvidenceManifest.from_dict(e)
                               for e in d.get("evidence_manifests", [])],
            status=d.get("status", "active"),
            valid_from=d.get("valid_from"),
            valid_until=d.get("valid_until"),
            policy_flags=d.get("policy_flags", []),
            hmac_sig=d.get("hmac", ""),
        )

    def sign(self, secret: str = "") -> str:
        """Sign the claim manifest."""
        secret = secret or os.environ.get("VAULTLENS_SECRET", "vaultlens")
        canonical = json.dumps({
            "claim_id": self.claim_id,
            "expert_id": self.expert_id,
            "text": self.text,
            "claim_type": self.claim_type,
            "confidence": self.confidence,
            "status": self.status,
        }, sort_keys=True)
        self.hmac_sig = hmac.new(
            secret.encode(), canonical.encode(), hashlib.sha256
        ).hexdigest()[:16]
        return self.hmac_sig

    def verify(self, secret: str = "") -> bool:
        stored = self.hmac_sig
        computed = hmac.new(
            (secret or os.environ.get("VAULTLENS_SECRET", "vaultlens")).encode(),
            json.dumps({"claim_id": self.claim_id, "expert_id": self.expert_id,
                        "text": self.text, "claim_type": self.claim_type,
                        "confidence": self.confidence, "status": self.status},
                       sort_keys=True).encode(),
            hashlib.sha256
        ).hexdigest()[:16]
        return hmac.compare_digest(stored, computed)

    def is_valid_temporally(self) -> bool:
        """Check if claim is within its valid time window."""
        now = time.strftime("%Y-%m-%d", time.gmtime())
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        return True

    def is_nullified(self) -> bool:
        return self.status in ("nullified", "retracted", "superseded")
