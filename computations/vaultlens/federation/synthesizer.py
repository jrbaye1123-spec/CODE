"""Multi-Expert Synthesizer: compiles isolated expert responses into a coherent answer.

Key rule: NEVER merge underlying data. Each expert's evidence stays in its
own labeled section. Contradictions between experts are disclosed, not hidden.
"""

import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ExpertResponseEnvelope:
    """Signed response from a single expert."""
    expert_id: str
    answer_fragment: str
    evidence_uuids: list[str] = field(default_factory=list)
    provenance: dict = field(default_factory=dict)
    expert_hmac: str = ""

    def to_dict(self) -> dict:
        return {
            "expert_id": self.expert_id,
            "answer_fragment": self.answer_fragment,
            "evidence_uuids": self.evidence_uuids,
            "provenance": self.provenance,
            "expert_hmac": self.expert_hmac,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ExpertResponseEnvelope":
        return cls(
            expert_id=d.get("expert_id", ""),
            answer_fragment=d.get("answer_fragment", ""),
            evidence_uuids=d.get("evidence_uuids", []),
            provenance=d.get("provenance", {}),
            expert_hmac=d.get("expert_hmac", ""),
        )

    def sign(self, secret: str = "") -> str:
        canonical = json.dumps({
            "expert_id": self.expert_id,
            "answer_fragment": self.answer_fragment,
            "evidence_uuids": sorted(self.evidence_uuids),
        }, sort_keys=True)
        self.expert_hmac = hmac.new(
            (secret or "vaultlens").encode(), canonical.encode(), hashlib.sha256
        ).hexdigest()[:16]
        return self.expert_hmac


@dataclass
class FederatedAnswerEnvelope:
    """Final federated answer with routing trail and per-expert evidence."""
    compiled_answer: str
    query_plan: dict = field(default_factory=dict)
    evidence_bundles: list[dict] = field(default_factory=list)
    contradictions: list[dict] = field(default_factory=list)
    hmac_audit_trail: dict = field(default_factory=dict)

    def sign(self, secret: str = "") -> str:
        """Sign the full federated answer envelope."""
        canonical = json.dumps({
            "compiled_answer": self.compiled_answer,
            "query_plan": self.query_plan,
            "evidence_bundles": self.evidence_bundles,
            "contradictions": self.contradictions,
        }, sort_keys=True)
        sig = hmac.new(
            (secret or os.environ.get("VAULTLENS_SECRET", "vaultlens")).encode(),
            canonical.encode(), hashlib.sha256
        ).hexdigest()[:32]
        self.hmac_audit_trail = {
            "algorithm": "HMAC-SHA256",
            "signing_key_id": "vaultlens-root-01",
            "signature": sig,
            "signed_payload_hash": hashlib.sha256(canonical.encode()).hexdigest()[:16],
        }
        return sig

    def to_dict(self) -> dict:
        return {
            "compiled_answer": self.compiled_answer,
            "query_plan": self.query_plan,
            "evidence_bundles": self.evidence_bundles,
            "contradictions": self.contradictions,
            "hmac_audit_trail": self.hmac_audit_trail,
        }


class MultiExpertSynthesizer:
    """Compiles isolated expert responses into a federated answer.

    NEVER merges raw data. Each expert's evidence stays in its own section.
    Contradictions are disclosed, not hidden.
    """

    def synthesize(self, query: str, query_plan: dict,
                   responses: list[ExpertResponseEnvelope],
                   strategy: str = "stitch_summaries_only") -> FederatedAnswerEnvelope:
        """Synthesize multiple expert responses into one federated answer.

        Args:
            query: Original user query
            query_plan: The FederatedQueryPlan that produced these responses
            responses: Signed ExpertResponseEnvelopes from each expert
            strategy: 'single_expert' or 'stitch_summaries_only'

        Returns:
            Signed FederatedAnswerEnvelope
        """
        evidence_bundles = [r.to_dict() for r in responses]
        contradictions = self._detect_contradictions(responses)

        if len(responses) == 0:
            compiled = "No experts responded. Insufficient evidence."
        elif len(responses) == 1:
            compiled = responses[0].answer_fragment
        else:
            compiled = self._stitch(query, responses, strategy, contradictions)

        envelope = FederatedAnswerEnvelope(
            compiled_answer=compiled,
            query_plan=query_plan,
            evidence_bundles=evidence_bundles,
            contradictions=contradictions,
        )
        envelope.sign()
        return envelope

    def _stitch(self, query: str, responses: list[ExpertResponseEnvelope],
                strategy: str, contradictions: list[dict]) -> str:
        """Stitch multiple expert answers into one coherent response."""
        parts = [f"# Federated Answer\n\n*Query: {query}*\n"]

        for i, resp in enumerate(responses):
            expert_name = resp.expert_id.replace("-", " ").title()
            parts.append(f"## Expert {i+1}: {expert_name}")
            parts.append(f"\n{resp.answer_fragment}\n")

            if resp.evidence_uuids:
                parts.append(f"\n*Evidence: {', '.join(resp.evidence_uuids[:5])}*")

            if resp.provenance:
                src = resp.provenance.get("source_dataset", "unknown")
                ts = resp.provenance.get("extraction_timestamp", "unknown")
                parts.append(f"\n*Source: {src} ({ts})*")

            parts.append("")

        if contradictions:
            parts.append("## ⚠️ Conflict Notices\n")
            for c in contradictions:
                parts.append(f"- **{c['type']}**: {c['description']}")
                parts.append(f"  - Expert A ({c.get('expert_a', '?')}): {c.get('claim_a', '?')}")
                parts.append(f"  - Expert B ({c.get('expert_b', '?')}): {c.get('claim_b', '?')}")
                parts.append("")

        parts.append(f"\n---\n*Answer compiled from {len(responses)} isolated expert(s). "
                     f"No underlying data was merged.*")

        return "\n".join(parts)

    def _detect_contradictions(self, responses: list[ExpertResponseEnvelope]) -> list[dict]:
        """Detect contradictions between expert responses.

        Simple keyword-based for MVP. In production: semantic contradiction detection.
        """
        if len(responses) < 2:
            return []

        contradictions = []

        # Check for opposing keywords
        opposing_pairs = [
            (["increase", "rise", "grew", "higher"], ["decrease", "fall", "decline", "lower"]),
            (["effective", "significant", "positive"], ["ineffective", "insignificant", "negative"]),
            (["supports", "confirms"], ["refutes", "contradicts"]),
        ]

        for i in range(len(responses)):
            for j in range(i + 1, len(responses)):
                a_text = responses[i].answer_fragment.lower()
                b_text = responses[j].answer_fragment.lower()

                for pos_words, neg_words in opposing_pairs:
                    a_pos = any(w in a_text for w in pos_words)
                    a_neg = any(w in a_text for w in neg_words)
                    b_pos = any(w in b_text for w in pos_words)
                    b_neg = any(w in b_text for w in neg_words)

                    if (a_pos and b_neg) or (a_neg and b_pos):
                        contradictions.append({
                            "type": "semantic_opposition",
                            "expert_a": responses[i].expert_id,
                            "expert_b": responses[j].expert_id,
                            "claim_a": responses[i].answer_fragment[:100],
                            "claim_b": responses[j].answer_fragment[:100],
                            "description": (
                                f"Expert '{responses[i].expert_id}' and "
                                f"'{responses[j].expert_id}' appear to make "
                                f"opposing claims."
                            ),
                        })
                        break  # One contradiction per pair is enough for MVP

        return contradictions
