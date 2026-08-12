"""Federated Adjudicator: selects resolution strategies for conflicting expert claims.

Takes claims, conflicts, and policy results. Outputs an AdjudicationDecision
with allowed/excluded claims, disclosures, and a final answer mode.

Key invariant: the adjudicator NEVER merges evidence. It decides what is
safe to include in the final answer and what must be disclosed or refused.
"""

import hashlib
import hmac
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from .claims import ExpertClaim
from .conflicts import Conflict, ConflictDetector
from .policy import (AdjudicationPolicyEngine, ResolutionStrategy, FinalMode,
                      DomainPolicy)


@dataclass
class AdjudicationDecision:
    """Complete adjudication decision for a federated query."""
    decision_id: str
    query_id: str = ""
    claims: list[dict] = field(default_factory=list)
    conflicts: list[dict] = field(default_factory=list)
    policy_checks: list[dict] = field(default_factory=list)
    strategy: ResolutionStrategy = "disclose_only"
    allowed_claims: list[str] = field(default_factory=list)
    excluded_claims: list[str] = field(default_factory=list)
    disclosures: list[str] = field(default_factory=list)
    final_mode: FinalMode = "disclosed"
    confidence: float = 0.5
    requires_human_review: bool = False
    audit_hash: str = ""
    hmac_sig: str = ""
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "decision_id": self.decision_id,
            "query_id": self.query_id,
            "claims": self.claims,
            "conflicts": self.conflicts,
            "policy_checks": self.policy_checks,
            "strategy": self.strategy,
            "allowed_claims": self.allowed_claims,
            "excluded_claims": self.excluded_claims,
            "disclosures": self.disclosures,
            "final_mode": self.final_mode,
            "confidence": self.confidence,
            "requires_human_review": self.requires_human_review,
            "audit_hash": self.audit_hash,
            "hmac": self.hmac_sig,
            "created_at": self.created_at,
        }

    def sign(self, secret: str = "") -> str:
        secret = secret or os.environ.get("VAULTLENS_SECRET", "vaultlens")
        canonical = json.dumps({
            "decision_id": self.decision_id,
            "strategy": self.strategy,
            "allowed_claims": sorted(self.allowed_claims),
            "excluded_claims": sorted(self.excluded_claims),
            "final_mode": self.final_mode,
        }, sort_keys=True)
        self.audit_hash = hashlib.sha256(canonical.encode()).hexdigest()[:16]
        self.hmac_sig = hmac.new(
            secret.encode(), canonical.encode(), hashlib.sha256
        ).hexdigest()[:32]
        return self.hmac_sig


class FederatedAdjudicator:
    """Adjudicates conflicts between expert claims and produces decisions."""

    def __init__(self, policy_engine: AdjudicationPolicyEngine = None):
        self.policy = policy_engine or AdjudicationPolicyEngine()
        self.detector = ConflictDetector()

    def adjudicate(self, query_id: str, claims: list[ExpertClaim],
                   query_domain: str = "general") -> AdjudicationDecision:
        """Adjudicate a set of expert claims and produce a decision.

        Pipeline:
        1. Detect conflicts
        2. Run policy checks on each claim
        3. Determine allowed/excluded claims
        4. Select resolution strategy
        5. Generate disclosures
        6. Determine final mode
        7. Sign decision
        """
        decision_id = f"dec_{uuid.uuid4().hex[:8]}"

        # 1. Detect conflicts
        conflicts = self.detector.detect(claims)

        # 2. Policy checks
        policy_results = self.policy.check_all(claims)

        # 3. Classify claims: allowed vs excluded
        allowed_ids = []
        excluded_ids = []
        disclosures = []

        for claim in claims:
            if claim.is_nullified():
                excluded_ids.append(claim.claim_id)
                disclosures.append(f"Claim {claim.claim_id} excluded: {claim.status}")
                continue

            if not claim.is_valid_temporally():
                excluded_ids.append(claim.claim_id)
                disclosures.append(f"Claim {claim.claim_id} excluded: outside valid time window")
                continue

            claim_checks = policy_results["per_claim"].get(claim.claim_id, [])
            violations = [c for c in claim_checks if not c["passed"]]

            if violations:
                excluded_ids.append(claim.claim_id)
                for v in violations:
                    disclosures.append(f"Policy violation: {v['detail']}")
            else:
                allowed_ids.append(claim.claim_id)

        # 4. Select strategy
        strategy = self._select_strategy(conflicts, claims, query_domain)
        requires_human = strategy in ("escalate_human",)

        # 5. Determine final mode
        final_mode = self._determine_mode(strategy, conflicts, allowed_ids, excluded_ids)

        # 6. Compute aggregate confidence
        allowed_claims_list = [c for c in claims if c.claim_id in allowed_ids]
        conf = (sum(c.confidence for c in allowed_claims_list) / len(allowed_claims_list)
                if allowed_claims_list else 0.0)

        decision = AdjudicationDecision(
            decision_id=decision_id,
            query_id=query_id,
            claims=[c.to_dict() for c in claims],
            conflicts=[c.to_dict() for c in conflicts],
            policy_checks=[
                {"claim_id": cid, "checks": checks}
                for cid, checks in policy_results["per_claim"].items()
            ],
            strategy=strategy,
            allowed_claims=allowed_ids,
            excluded_claims=excluded_ids,
            disclosures=disclosures,
            final_mode=final_mode,
            confidence=round(conf, 2),
            requires_human_review=requires_human,
            created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )
        decision.sign()
        return decision

    def _select_strategy(self, conflicts: list[Conflict],
                         claims: list[ExpertClaim],
                         query_domain: str) -> ResolutionStrategy:
        """Select the resolution strategy based on conflict severity and policy."""
        if not conflicts:
            return "disclose_only"  # No conflicts → safe to disclose

        severities = [c.severity for c in conflicts]

        if "critical" in severities:
            return "escalate_human"

        if "high" in severities:
            policy = self.policy.get_policy(query_domain)
            if policy.hard_conflict_action in ("escalate_human", "refuse"):
                return policy.hard_conflict_action
            return "disclose_only"

        # Medium/low conflicts: check policy preferences
        policy = self.policy.get_policy(query_domain)

        # Check for temporal supersession
        if policy.allow_recency_preference:
            for c in conflicts:
                if c.conflict_type == "temporal_supersession":
                    return "prefer_recency"

        # Check for accreditation preference
        if policy.allow_accreditation_preference:
            for c in conflicts:
                if c.conflict_type == "jurisdiction_conflict":
                    return "prefer_accreditation"

        # Check for policy violation
        for c in conflicts:
            if c.conflict_type == "policy_violation":
                return "quarantine"

        return "disclose_only"

    def _determine_mode(self, strategy: ResolutionStrategy,
                        conflicts: list[Conflict],
                        allowed_ids: list[str],
                        excluded_ids: list[str]) -> FinalMode:
        """Determine the final answer mode from strategy and state."""
        if strategy == "refuse":
            return "refused"
        if strategy == "escalate_human":
            return "escalated"
        if not allowed_ids:
            return "refused"
        if strategy == "quarantine" and len(excluded_ids) > 0:
            return "conservative"
        if conflicts and any(c.severity in ("high", "critical") for c in conflicts):
            return "disclosed"
        if strategy == "disclose_only" and conflicts:
            return "disclosed"
        if any(c.confidence < 0.6 for c in [
            claim for claim in [] if hasattr(claim, 'confidence')
        ]) or (allowed_ids and len(conflicts) > 0):
            return "provisional"
        return "conservative"
