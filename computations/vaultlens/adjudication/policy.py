"""Domain-specific policy rules for adjudication.

Policy is machine-readable YAML/dict, never hardcoded. The adjudicator
checks every claim against domain policy before allowing synthesis.

Safety domains: medical, legal, financial have strict prohibitions.
"""

from dataclasses import dataclass, field
from typing import Literal, Optional


ResolutionStrategy = Literal[
    "disclose_only", "quarantine", "suspend",
    "prefer_policy", "prefer_recency", "prefer_accreditation",
    "escalate_human", "refuse",
]

FinalMode = Literal[
    "conservative", "disclosed", "provisional", "refused", "escalated",
]


@dataclass
class DomainPolicy:
    """Policy rules for a specific domain."""
    policy_id: str
    domain: str
    allowed_claim_types: list[str] = field(default_factory=list)
    prohibited_claim_types: list[str] = field(default_factory=list)
    require_disclosure: bool = True
    max_confidence_without_review: float = 0.7
    hard_conflict_action: ResolutionStrategy = "disclose_only"
    allow_recency_preference: bool = False
    allow_accreditation_preference: bool = True


# ── Default domain policies ──────────────────────────

DEFAULT_POLICIES: dict[str, DomainPolicy] = {
    "medical": DomainPolicy(
        policy_id="medical_sovereignty",
        domain="medical",
        allowed_claim_types=["informational", "definitional", "evidential", "semantic"],
        prohibited_claim_types=["diagnosis", "treatment_prescription", "emergency_direction"],
        require_disclosure=True,
        max_confidence_without_review=0.6,
        hard_conflict_action="escalate_human",
    ),
    "legal": DomainPolicy(
        policy_id="legal_sovereignty",
        domain="legal",
        allowed_claim_types=["informational", "definitional", "provenance", "semantic"],
        prohibited_claim_types=["legal_advice", "jurisdiction_specific_counsel"],
        require_disclosure=True,
        max_confidence_without_review=0.5,
        hard_conflict_action="refuse",
    ),
    "financial": DomainPolicy(
        policy_id="financial_sovereignty",
        domain="financial",
        allowed_claim_types=["informational", "causal", "evidential", "definitional"],
        prohibited_claim_types=["investment_advice", "transaction_instruction"],
        require_disclosure=True,
        max_confidence_without_review=0.6,
        hard_conflict_action="disclose_only",
    ),
    "economics": DomainPolicy(
        policy_id="economics_default",
        domain="economics",
        allowed_claim_types=["causal", "evidential", "temporal", "provenance",
                            "definitional", "semantic", "informational"],
        prohibited_claim_types=[],
        require_disclosure=True,
        max_confidence_without_review=0.8,
        hard_conflict_action="disclose_only",
        allow_recency_preference=True,
    ),
    "general": DomainPolicy(
        policy_id="general_default",
        domain="general",
        allowed_claim_types=["causal", "evidential", "temporal", "provenance",
                            "procedural", "definitional", "semantic", "informational"],
        prohibited_claim_types=[],
        require_disclosure=False,
        max_confidence_without_review=0.9,
        hard_conflict_action="disclose_only",
        allow_recency_preference=True,
    ),
}


class AdjudicationPolicyEngine:
    """Checks claims against domain policies."""

    def __init__(self, policies: dict[str, DomainPolicy] = None):
        self.policies = policies or DEFAULT_POLICIES

    def get_policy(self, domain: str) -> DomainPolicy:
        """Get the policy for a domain. Falls back to 'general'."""
        return self.policies.get(domain, self.policies["general"])

    def check_claim(self, claim) -> list[dict]:
        """Check a single claim against its domain policy.

        Returns list of {check: str, passed: bool, detail: str}.
        """
        policy = self.get_policy(claim.domain)
        results = []

        # Check: claim type allowed
        if policy.allowed_claim_types:
            allowed = claim.claim_type in policy.allowed_claim_types
            results.append({
                "check": "claim_type_allowed",
                "passed": allowed,
                "detail": f"Type '{claim.claim_type}' {'allowed' if allowed else 'NOT allowed'} in {claim.domain}",
            })

        # Check: claim type prohibited
        if policy.prohibited_claim_types:
            prohibited = claim.claim_type in policy.prohibited_claim_types
            results.append({
                "check": "claim_type_prohibited",
                "passed": not prohibited,
                "detail": f"Type '{claim.claim_type}' {'PROHIBITED' if prohibited else 'not prohibited'} in {claim.domain}",
            })

        # Check: confidence ceiling
        over_confident = claim.confidence > policy.max_confidence_without_review
        results.append({
            "check": "confidence_ceiling",
            "passed": not over_confident,
            "detail": f"Confidence {claim.confidence:.2f} {'exceeds' if over_confident else 'within'} limit {policy.max_confidence_without_review}",
        })

        # Check: nullified
        if claim.is_nullified():
            results.append({
                "check": "not_nullified",
                "passed": False,
                "detail": f"Claim {claim.claim_id} is {claim.status}",
            })

        # Check: temporal validity
        if not claim.is_valid_temporally():
            results.append({
                "check": "temporal_validity",
                "passed": False,
                "detail": f"Claim {claim.claim_id} is outside valid time window",
            })

        return results

    def check_all(self, claims) -> dict:
        """Check all claims against their domain policies.

        Returns {claim_id: [check_results], all_passed: bool}
        """
        all_results = {}
        all_passed = True

        for claim in claims:
            results = self.check_claim(claim)
            all_results[claim.claim_id] = results
            if not all(r["passed"] for r in results):
                all_passed = False

        return {"per_claim": all_results, "all_passed": all_passed}

    def get_conflict_action(self, claim, conflicts: list) -> ResolutionStrategy:
        """Determine the required action for a hard conflict involving this claim."""
        policy = self.get_policy(claim.domain)

        # Critical conflicts always escalate
        for c in conflicts:
            if c.severity == "critical":
                return "escalate_human"
            if c.conflict_type == "policy_violation":
                return "refuse"

        return policy.hard_conflict_action
