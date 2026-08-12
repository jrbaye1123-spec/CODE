"""Conflict taxonomy and detection for federated expert claims.

Conflicts are first-class objects, not errors. Each has a precise type,
severity, and explanation. The adjudicator uses these to select a
resolution strategy.
"""

from dataclasses import dataclass, field
from typing import Literal

from .claims import ExpertClaim


ConflictType = Literal[
    "direct_negation",
    "partial_overlap",
    "scope_mismatch",
    "temporal_supersession",
    "jurisdiction_conflict",
    "evidential_gap",
    "confidence_divergence",
    "policy_violation",
    "expert_disagreement",
]

ConflictSeverity = Literal["low", "medium", "high", "critical"]


@dataclass
class Conflict:
    """A detected conflict between two expert claims."""
    conflict_id: str
    claim_a_id: str
    claim_b_id: str
    conflict_type: ConflictType
    severity: ConflictSeverity = "medium"
    explanation: str = ""
    policy_refs: list[str] = field(default_factory=list)
    resolution_state: str = "unresolved"

    def to_dict(self) -> dict:
        return {
            "conflict_id": self.conflict_id,
            "claim_a_id": self.claim_a_id,
            "claim_b_id": self.claim_b_id,
            "conflict_type": self.conflict_type,
            "severity": self.severity,
            "explanation": self.explanation,
            "policy_refs": self.policy_refs,
            "resolution_state": self.resolution_state,
        }


# ── Negation word pairs ───────────────────────────────

DIRECT_NEGATION_PAIRS = [
    ({"is", "are", "does", "will", "can", "may", "do", "has", "have", "did"},
     {"is not", "are not", "does not", "will not", "cannot", "may not",
      "do not", "don't", "doesn't", "won't", "can't", "has not", "have not"}),
    ({"increases", "increase", "raises", "raise", "boosts", "boost",
      "improves", "improve", "strengthens", "strengthen", "grew", "higher",
      "grows", "grow"},
     {"decreases", "decrease", "lowers", "lower", "reduces", "reduce",
      "weakens", "weaken", "declines", "decline", "fell", "lower"}),
    ({"effective", "significant", "positive", "beneficial", "supports", "support",
      "confirms", "confirm"},
     {"ineffective", "insignificant", "negative", "harmful", "refutes", "refute",
      "contradicts", "contradict"}),
]

TEMPORAL_INDICATORS = {
    "2024", "2025", "2026", "2027", "2028",
    "previously", "formerly", "updated", "revised",
    "supersedes", "replaces", "new guidance",
}

QUALIFICATION_WORDS = {
    "unless", "except", "however", "but", "although",
    "during", "under", "when", "if", "provided that",
    "in the case of",
}


class ConflictDetector:
    """Detects and classifies conflicts between expert claims."""

    def __init__(self):
        self._counter = 0

    def detect(self, claims: list[ExpertClaim]) -> list[Conflict]:
        """Detect all conflicts between a set of expert claims.

        Only active, non-nullified claims are compared.
        """
        active = [c for c in claims if c.status == "active"]
        conflicts = []

        for i in range(len(active)):
            for j in range(i + 1, len(active)):
                conflict = self._compare(active[i], active[j])
                if conflict:
                    conflicts.append(conflict)

        return conflicts

    def _compare(self, a: ExpertClaim, b: ExpertClaim) -> Conflict | None:
        """Compare two claims and return a Conflict if one exists."""
        self._counter += 1
        cid = f"conflict_{self._counter:04d}"

        a_words = set(a.text.lower().split())
        b_words = set(b.text.lower().split())

        # 1. Policy violation check
        pol_violation = self._check_policy_violation(a, b)
        if pol_violation:
            return Conflict(
                conflict_id=cid, claim_a_id=a.claim_id, claim_b_id=b.claim_id,
                conflict_type="policy_violation", severity="critical",
                explanation=pol_violation,
                policy_refs=list(set(a.policy_flags + b.policy_flags)),
            )

        # 2. Jurisdiction conflict
        if a.jurisdiction != b.jurisdiction and a.domain != b.domain:
            return Conflict(
                conflict_id=cid, claim_a_id=a.claim_id, claim_b_id=b.claim_id,
                conflict_type="jurisdiction_conflict", severity="high",
                explanation=f"Claim domains differ: {a.domain} ({a.jurisdiction}) vs {b.domain} ({b.jurisdiction})",
            )

        # 3. Temporal supersession
        temp = self._check_temporal(a, b)
        if temp:
            return Conflict(
                conflict_id=cid, claim_a_id=a.claim_id, claim_b_id=b.claim_id,
                conflict_type="temporal_supersession", severity="medium",
                explanation=temp,
            )

        # 4. Direct negation
        negation = self._check_negation(a_words, b_words)
        if negation:
            severity = "high" if max(a.confidence, b.confidence) > 0.7 else "medium"
            return Conflict(
                conflict_id=cid, claim_a_id=a.claim_id, claim_b_id=b.claim_id,
                conflict_type="direct_negation", severity=severity,
                explanation=f"Direct negation: {negation}",
            )

        # 5. Scope mismatch (qualification words present)
        scope = self._check_scope(a_words, b_words)
        if scope:
            return Conflict(
                conflict_id=cid, claim_a_id=a.claim_id, claim_b_id=b.claim_id,
                conflict_type="scope_mismatch", severity="medium",
                explanation=scope,
            )

        # 6. Confidence divergence
        conf_diff = abs(a.confidence - b.confidence)
        if conf_diff > 0.3 and a.claim_type == b.claim_type and a.domain == b.domain:
            return Conflict(
                conflict_id=cid, claim_a_id=a.claim_id, claim_b_id=b.claim_id,
                conflict_type="confidence_divergence", severity="low",
                explanation=f"Confidence divergence: {a.confidence:.2f} vs {b.confidence:.2f} (diff={conf_diff:.2f})",
            )

        # 7. Evidential gap
        if a.evidence_manifests and not b.evidence_manifests:
            return Conflict(
                conflict_id=cid, claim_a_id=a.claim_id, claim_b_id=b.claim_id,
                conflict_type="evidential_gap", severity="low",
                explanation=f"Claim {b.claim_id} lacks evidence while {a.claim_id} has {len(a.evidence_manifests)} evidence items",
            )

        return None

    def _check_policy_violation(self, a: ExpertClaim, b: ExpertClaim) -> str | None:
        """Check if either claim violates policy."""
        prohibited = {"diagnosis", "treatment_prescription", "emergency_direction",
                      "legal_advice", "investment_advice", "transaction_instruction"}
        for claim in [a, b]:
            if claim.claim_type in prohibited:
                return (f"Claim {claim.claim_id} ({claim.expert_id}) has prohibited "
                        f"type '{claim.claim_type}' in domain '{claim.domain}'")
        return None

    def _check_temporal(self, a: ExpertClaim, b: ExpertClaim) -> str | None:
        """Check for temporal supersession."""
        a_time = any(w in a.text.lower() for w in TEMPORAL_INDICATORS)
        b_time = any(w in b.text.lower() for w in TEMPORAL_INDICATORS)
        if a_time and b_time:
            return f"Both claims reference temporal indicators — possible supersession"
        if a_time or b_time:
            newer = a if a_time else b
            older = b if a_time else a
            return f"{newer.claim_id} references newer temporal indicator, may supersede {older.claim_id}"
        return None

    def _check_negation(self, a_words: set[str], b_words: set[str]) -> str | None:
        """Check for direct negation between two sets of words."""
        # Also check the raw text for multi-word negations
        neg_words = {"not", "no", "never", "neither", "nor", "n't", "don't", "doesn't",
                     "won't", "can't", "cannot"}

        for pos_set, neg_set in DIRECT_NEGATION_PAIRS:
            a_pos = bool(a_words & pos_set)
            b_pos = bool(b_words & pos_set)
            # Negation: either explicit neg words in one set + pos verb, or neg verb
            a_has_neg = bool(a_words & neg_words) or bool(a_words & neg_set)
            b_has_neg = bool(b_words & neg_words) or bool(b_words & neg_set)

            if a_pos and b_has_neg:
                return (f"A contains positive indicators {pos_set & a_words}, "
                        f"B contains negation: {neg_words & b_words or neg_set & b_words}")
            if b_pos and a_has_neg:
                return (f"B contains positive indicators {pos_set & b_words}, "
                        f"A contains negation: {neg_words & a_words or neg_set & a_words}")
        return None

    def _check_scope(self, a_words: set[str], b_words: set[str]) -> str | None:
        """Check for scope mismatch via qualification words."""
        a_qual = a_words & QUALIFICATION_WORDS
        b_qual = b_words & QUALIFICATION_WORDS
        if a_qual and not b_qual:
            return f"Claim has qualification ({a_qual}) that may limit scope"
        if b_qual and not a_qual:
            return f"Claim has qualification ({b_qual}) that may limit scope"
        if a_qual and b_qual:
            return f"Both claims have scope qualifications: {a_qual} vs {b_qual}"
        return None
