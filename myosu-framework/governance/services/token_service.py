"""
capability_tokens — Runtime identity and capability enforcement.

Every actor (human, agent, service) carries a scoped capability token.
No actor may act outside their token scope.
"""
import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict

UTC = timezone.utc


@dataclass
class CapabilityToken:
    token_id: str = field(default_factory=lambda: f"tok_{uuid.uuid4().hex[:10]}")
    subject_id: str = ""
    subject_role: str = ""
    allowed_actions: List[str] = field(default_factory=list)
    forbidden_actions: List[str] = field(default_factory=list)
    project_id: str = ""
    risk_tier: int = 0
    issued_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    expires_at: str = field(default_factory=lambda: (datetime.now(UTC) + timedelta(hours=1)).isoformat())
    signature: str = ""

    def is_expired(self) -> bool:
        return datetime.now(UTC) > datetime.fromisoformat(self.expires_at)

    def allows(self, action: str) -> bool:
        if action in self.forbidden_actions:
            return False
        if "*" in self.allowed_actions:
            return True
        return action in self.allowed_actions

    def sign(self, secret: str = "vault-governance-secret") -> str:
        payload = f"{self.token_id}|{self.subject_id}|{self.subject_role}|{self.issued_at}|{self.expires_at}"
        self.signature = hashlib.sha256((payload + secret).encode()).hexdigest()
        return self.signature

    def verify(self, secret: str = "vault-governance-secret") -> bool:
        expected = self.sign(secret)
        return self.signature == expected

    def to_dict(self) -> dict:
        return {
            "token_id": self.token_id,
            "subject_id": self.subject_id,
            "subject_role": self.subject_role,
            "allowed_actions": self.allowed_actions,
            "forbidden_actions": self.forbidden_actions,
            "project_id": self.project_id,
            "risk_tier": self.risk_tier,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CapabilityToken":
        return cls(
            token_id=d.get("token_id", ""),
            subject_id=d.get("subject_id", ""),
            subject_role=d.get("subject_role", ""),
            allowed_actions=d.get("allowed_actions", []),
            forbidden_actions=d.get("forbidden_actions", []),
            project_id=d.get("project_id", ""),
            risk_tier=d.get("risk_tier", 0),
            issued_at=d.get("issued_at", ""),
            expires_at=d.get("expires_at", ""),
            signature=d.get("signature", ""),
        )


# ── Token presets ────────────────────────────────────────────────────────────

def human_token() -> CapabilityToken:
    return CapabilityToken(
        subject_id="john", subject_role="human",
        allowed_actions=["*"], forbidden_actions=[],
        project_id="proj_vault", risk_tier=0,
    )

def retrieval_token() -> CapabilityToken:
    return CapabilityToken(
        subject_id="agent_retrieval_v1", subject_role="retrieval",
        allowed_actions=["read_sources", "write_source_cache", "query_registries"],
        forbidden_actions=["write_my_thinking", "synthesize", "promote", "export", "execute_tools"],
        risk_tier=1,
    )

def extraction_token() -> CapabilityToken:
    return CapabilityToken(
        subject_id="agent_extraction_v1", subject_role="extraction",
        allowed_actions=["read_sources", "write_agent_extractions", "read_agent_extractions", "handoff"],
        forbidden_actions=["write_my_thinking", "synthesize", "promote", "export", "execute_tools", "web_access"],
        risk_tier=1,
    )

def synthesis_token() -> CapabilityToken:
    return CapabilityToken(
        subject_id="agent_synthesis_v1", subject_role="synthesis",
        allowed_actions=["read_agent_extractions", "read_agent_summaries",
                         "read_agent_dissent", "write_agent_syntheses"],
        forbidden_actions=["write_my_thinking", "promote", "export", "execute_tools"],
        risk_tier=2,
    )

def promotion_token(human: bool = True) -> CapabilityToken:
    if human:
        return CapabilityToken(
            subject_id="john", subject_role="promotion",
            allowed_actions=["write_my_thinking", "promote", "ratify", "annotate", "reconstruct"],
            forbidden_actions=["synthesize", "execute_tools"],
            risk_tier=2,
        )
    return CapabilityToken(
        subject_id="svc_promotion_v1", subject_role="promotion",
        allowed_actions=["write_my_thinking"],
        forbidden_actions=["synthesize", "export", "execute_tools"],
        risk_tier=2,
    )


# ── Token Validator ──────────────────────────────────────────────────────────

class TokenValidator:
    """Validates capability tokens at runtime."""

    def __init__(self, secret: str = "vault-governance-secret"):
        self.secret = secret

    def validate(self, token: CapabilityToken, action: str) -> bool:
        """Return True if token is valid and allows the action."""
        if token.is_expired():
            return False
        if not token.verify(self.secret):
            return False
        return token.allows(action)

    def validate_or_raise(self, token: CapabilityToken, action: str):
        if not self.validate(token, action):
            raise PermissionError(
                f"Token {token.token_id} ({token.subject_role}) cannot perform '{action}'"
            )
