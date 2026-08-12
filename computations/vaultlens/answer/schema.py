"""Answer schema: structured, verifiable answer types for VaultLens v0.5.

Every LLM-generated answer must conform to GroundedAnswer JSON.
The validator checks every claim against the retrieved subgraph.
"""

from dataclasses import dataclass, field
from typing import Literal, Optional


@dataclass
class Citation:
    """A citation linking a claim to a specific graph edge or node."""
    note_id: Optional[str] = None
    edge_id: Optional[str] = None
    relation: Optional[str] = None
    variant: Optional[str] = None
    status: Optional[str] = None
    confidence: Optional[float] = None
    source_note_title: str = ""
    target_note_title: str = ""


@dataclass
class Claim:
    """A single factual claim within an answer, with citations."""
    claim_id: str
    text: str
    citations: list[Citation] = field(default_factory=list)
    confidence: float = 0.0
    claim_type: Literal["causal", "evidential", "temporal", "definitional",
                        "provenance", "procedural", "semantic"] = "definitional"


@dataclass
class Contradiction:
    """A contradiction found between a claim and existing graph evidence."""
    claim_id: str
    conflicting_citations: list[Citation] = field(default_factory=list)
    explanation: str = ""


@dataclass
class GroundedAnswer:
    """Complete verified answer with claims, proof, and contradictions."""
    answer_text: str
    claims: list[Claim] = field(default_factory=list)
    contradictions: list[Contradiction] = field(default_factory=list)
    uncertainties: list[str] = field(default_factory=list)
    insufficient_evidence: bool = False

    def to_dict(self) -> dict:
        return {
            "answer_text": self.answer_text,
            "claims": [
                {
                    "claim_id": c.claim_id,
                    "text": c.text,
                    "claim_type": c.claim_type,
                    "confidence": c.confidence,
                    "citations": [
                        {
                            "note_id": cit.note_id,
                            "edge_id": cit.edge_id,
                            "relation": cit.relation,
                            "variant": cit.variant,
                            "status": cit.status,
                            "confidence": cit.confidence,
                            "source_note_title": cit.source_note_title,
                            "target_note_title": cit.target_note_title,
                        }
                        for cit in c.citations
                    ],
                }
                for c in self.claims
            ],
            "contradictions": [
                {
                    "claim_id": c.claim_id,
                    "explanation": c.explanation,
                    "conflicting_citations": [
                        {"edge_id": cit.edge_id, "relation": cit.relation,
                         "source_note_title": cit.source_note_title,
                         "target_note_title": cit.target_note_title}
                        for cit in c.conflicting_citations
                    ],
                }
                for c in self.contradictions
            ],
            "uncertainties": self.uncertainties,
            "insufficient_evidence": self.insufficient_evidence,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "GroundedAnswer":
        return cls(
            answer_text=d.get("answer_text", ""),
            claims=[
                Claim(
                    claim_id=c.get("claim_id", f"c{i}"),
                    text=c.get("text", ""),
                    claim_type=c.get("claim_type", "definitional"),
                    confidence=c.get("confidence", 0.0),
                    citations=[
                        Citation(
                            note_id=cit.get("note_id"),
                            edge_id=cit.get("edge_id"),
                            relation=cit.get("relation"),
                            variant=cit.get("variant"),
                            status=cit.get("status"),
                            confidence=cit.get("confidence"),
                            source_note_title=cit.get("source_note_title", ""),
                            target_note_title=cit.get("target_note_title", ""),
                        )
                        for cit in c.get("citations", [])
                    ],
                )
                for i, c in enumerate(d.get("claims", []))
            ],
            contradictions=[
                Contradiction(
                    claim_id=c.get("claim_id", ""),
                    explanation=c.get("explanation", ""),
                    conflicting_citations=[
                        Citation(
                            edge_id=cit.get("edge_id"),
                            relation=cit.get("relation"),
                            source_note_title=cit.get("source_note_title", ""),
                            target_note_title=cit.get("target_note_title", ""),
                        )
                        for cit in c.get("conflicting_citations", [])
                    ],
                )
                for c in d.get("contradictions", [])
            ],
            uncertainties=d.get("uncertainties", []),
            insufficient_evidence=d.get("insufficient_evidence", False),
        )


@dataclass
class ValidationResult:
    """Result of deterministic answer validation."""
    passed: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    claims_grounded: int = 0
    claims_total: int = 0
    nullified_citations: int = 0
    missing_citations: int = 0
    contradictions_found: int = 0
