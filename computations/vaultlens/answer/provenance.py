"""Proof chain renderer and answer audit trail for VaultLens v0.5.

Produces human-readable proof chains and cryptographically-signed
answer manifests for full auditability.
"""

import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass, field
from typing import Optional

from .schema import GroundedAnswer, ValidationResult, Citation


@dataclass
class AnswerManifest:
    """Cryptographic audit trail for a VaultLens answer."""
    run_id: str
    session_id: str = ""
    query: str = ""
    query_hash: str = ""
    traversal_plan: dict = field(default_factory=dict)
    planner_attempts: int = 0
    retrieved_node_ids: list[str] = field(default_factory=list)
    retrieved_edge_ids: list[str] = field(default_factory=list)
    subgraph_hash: str = ""
    answer_json: dict = field(default_factory=dict)
    validation: dict = field(default_factory=dict)
    model_id: str = ""
    created_at: str = ""
    hmac_sig: str = ""

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "session_id": self.session_id,
            "query": self.query,
            "query_hash": self.query_hash,
            "traversal_plan": self.traversal_plan,
            "planner_attempts": self.planner_attempts,
            "retrieved_node_ids": self.retrieved_node_ids,
            "retrieved_edge_ids": self.retrieved_edge_ids,
            "subgraph_hash": self.subgraph_hash,
            "answer_json": self.answer_json,
            "validation": self.validation,
            "model_id": self.model_id,
            "created_at": self.created_at,
            "hmac": self.hmac_sig,
        }

    def sign(self, secret: str = "") -> str:
        """Sign the manifest with HMAC-SHA256."""
        canonical = json.dumps({
            k: v for k, v in self.to_dict().items()
            if k not in ("hmac",)
        }, sort_keys=True)
        self.hmac_sig = hmac.new(
            secret.encode() if secret else b"vaultlens",
            canonical.encode(), hashlib.sha256
        ).hexdigest()[:16]
        return self.hmac_sig


def build_manifest(
    run_id: str,
    query: str,
    session_id: str = "",
    traversal_plan: dict = None,
    planner_attempts: int = 0,
    nodes: list[dict] = None,
    edges: list[dict] = None,
    answer: GroundedAnswer = None,
    validation: ValidationResult = None,
    model_id: str = "llama-3.2-3b-instruct-q4_k_m",
    secret: str = "",
) -> AnswerManifest:
    """Build a signed answer manifest from retrieval and validation results."""
    nodes = nodes or []
    edges = edges or []
    answer = answer or GroundedAnswer(answer_text="")

    node_ids = [n.get("note_id", "") for n in nodes if n.get("note_id")]
    edge_ids = [e.get("edge_id", f"e{i}") for i, e in enumerate(edges)]

    subgraph_hasher = hashlib.sha256()
    subgraph_hasher.update(json.dumps(node_ids, sort_keys=True).encode())
    subgraph_hasher.update(json.dumps(edge_ids, sort_keys=True).encode())

    manifest = AnswerManifest(
        run_id=run_id,
        session_id=session_id,
        query=query,
        query_hash=hashlib.sha256(query.encode()).hexdigest()[:16],
        traversal_plan=traversal_plan or {},
        planner_attempts=planner_attempts,
        retrieved_node_ids=node_ids,
        retrieved_edge_ids=edge_ids,
        subgraph_hash=subgraph_hasher.hexdigest()[:16],
        answer_json=answer.to_dict(),
        validation={
            "passed": validation.passed if validation else False,
            "errors": validation.errors if validation else [],
            "warnings": validation.warnings if validation else [],
            "claims_grounded": validation.claims_grounded if validation else 0,
            "claims_total": validation.claims_total if validation else 0,
        },
        model_id=model_id,
        created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )
    manifest.sign(secret or os.environ.get("VAULTLENS_SECRET", ""))
    return manifest


def render_proof(answer: GroundedAnswer, validation: ValidationResult,
                 nodes: list[dict], edges: list[dict],
                 query: str = "", session_id: str = "") -> str:
    """Render a human-readable proof chain for a grounded answer.

    Includes: answer text, claims with citations, proof edges, contradictions,
    uncertainties, grounding statistics.
    """
    lines = []
    lines.append("=" * 60)
    lines.append("VAULTLENS ANSWER — PROOF CHAIN")
    lines.append("=" * 60)

    if query:
        lines.append(f"Query: {query}")
    if session_id:
        lines.append(f"Session: {session_id}")
    lines.append("")

    # Answer
    lines.append(f"Answer: {answer.answer_text}")
    lines.append("")

    # Claims
    if answer.claims:
        lines.append(f"Claims ({validation.claims_grounded}/{validation.claims_total} grounded):")
        lines.append("")

        for i, claim in enumerate(answer.claims):
            lines.append(f"  Claim {i+1}: {claim.text}")
            lines.append(f"    Type: {claim.claim_type}")
            lines.append(f"    Confidence: {claim.confidence:.2f}")

            for j, cit in enumerate(claim.citations):
                src = cit.source_note_title or "?"
                tgt = cit.target_note_title or "?"
                rel = cit.relation or "?"
                status = cit.status or "active"
                eid = cit.edge_id or "?"
                lines.append(f"    Proof {j+1}: [[{src}]] --{rel}--> [[{tgt}]]")
                lines.append(f"      edge_id: {eid}  status: {status}  confidence: {cit.confidence or '?'}")
            lines.append("")

    # Contradictions
    if answer.contradictions:
        lines.append("Contradictions:")
        for c in answer.contradictions:
            lines.append(f"  {c.explanation}")
        lines.append("")

    # Uncertainties
    if answer.uncertainties:
        lines.append("Uncertainties:")
        for u in answer.uncertainties:
            lines.append(f"  - {u}")
        lines.append("")

    # Insufficient evidence flag
    if answer.insufficient_evidence:
        lines.append("Status: INSUFFICIENT EVIDENCE")
        lines.append("")

    # Grounding summary
    if validation:
        lines.append("Grounding Summary:")
        lines.append(f"  Claims grounded:   {validation.claims_grounded}/{validation.claims_total}")
        lines.append(f"  Missing citations: {validation.missing_citations}")
        lines.append(f"  Nullified citations: {validation.nullified_citations}")
        lines.append(f"  Contradictions:    {validation.contradictions_found}")
        lines.append(f"  Strict validation: {'PASSED' if validation.passed else 'FAILED'}")
        if validation.warnings:
            lines.append(f"  Warnings: {len(validation.warnings)}")
        if validation.errors:
            lines.append(f"  Errors: {len(validation.errors)}")
            for err in validation.errors[:5]:
                lines.append(f"    - {err}")

    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)
