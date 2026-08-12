"""VaultLens v0.5: The Verifiable Answer Compiler.

Orchestrates the full answer pipeline:
    retrieved subgraph → LLM generation → validation → proof rendering → manifest

The LLM writes the answer. The validator determines if it's true.
No claim without citation. No citation without active graph evidence.
"""

import os
import time
import hashlib
from typing import Optional

from .schema import GroundedAnswer, ValidationResult
from .generator import generate_answer
from .validator import AnswerValidator
from .refusal import build_refusal, should_refuse, generate_gap_proposals
from .provenance import build_manifest, render_proof


def compile_answer(
    query: str,
    nodes: list[dict],
    edges: list[dict],
    variants: list[str] = None,
    session_id: str = "",
    strict: bool = True,
    use_llm: bool = True,
    model_path: str = "",
    llama_cli: str = "",
    traversal_plan: dict = None,
) -> dict:
    """Compile a verifiable answer from retrieved subgraph.

    Full pipeline:
    1. Check if subgraph is sufficient (refuse if not)
    2. Generate GroundedAnswer via LLM or template
    3. Validate every claim against subgraph
    4. Detect contradictions
    5. Render proof chain
    6. Build signed manifest

    Returns dict with: answer, validation, proof_text, manifest, gap_proposals
    """
    variants = variants or []
    run_id = f"run_{int(time.time())}_{hashlib.sha256(os.urandom(8)).hexdigest()[:6]}"

    # ── Check for refusal ──────────────────────────────
    should_ref, reason = should_refuse(nodes, edges, required_variants=variants)
    if should_ref:
        answer = build_refusal(reason, variants=", ".join(variants))
        validation = ValidationResult(passed=True, claims_grounded=0, claims_total=0)
        gap_proposals = generate_gap_proposals(query, nodes, edges, variants)

        manifest = build_manifest(
            run_id=run_id, query=query, session_id=session_id,
            traversal_plan=traversal_plan, nodes=nodes, edges=edges,
            answer=answer, validation=validation,
        )
        return {
            "answer": answer,
            "validation": validation,
            "proof_text": render_proof(answer, validation, nodes, edges, query, session_id),
            "manifest": manifest.to_dict(),
            "gap_proposals": gap_proposals,
            "refused": True,
        }

    # ── Generate answer ────────────────────────────────
    answer = None
    if use_llm:
        answer = generate_answer(query, nodes, edges, model_path, llama_cli)

    if answer is None:
        # Fallback: template-based answer from graph structure
        answer = _template_answer(query, nodes, edges, variants)

    # ── Validate ───────────────────────────────────────
    validator = AnswerValidator(nodes, edges, strict=strict)
    validation = validator.validate(answer)

    # Also check for contradictions
    raw_contradictions = validator.find_contradictions(answer)
    from .schema import Contradiction as ContradictionCls, Citation as CitationCls
    for c in raw_contradictions:
        answer.contradictions.append(ContradictionCls(
            claim_id=c.get("claim_id", ""),
            explanation=c.get("explanation", ""),
            conflicting_citations=[
                CitationCls(
                    edge_id=c.get("opposing_edge_id"),
                    relation=c.get("opposing_relation"),
                )
            ],
        ))

    # Re-validate after contradiction merge
    validation = validator.validate(answer)

    # ── If strict mode fails, retry with higher temp or refuse ──
    if strict and not validation.passed and use_llm:
        # One retry with higher temperature
        retry_answer = generate_answer(query, nodes, edges, model_path, llama_cli,
                                        temperature=0.3)
        if retry_answer:
            retry_validator = AnswerValidator(nodes, edges, strict=strict)
            retry_validation = retry_validator.validate(retry_answer)
            if retry_validation.passed:
                answer = retry_answer
                validation = retry_validation

    # ── Build manifest ─────────────────────────────────
    manifest = build_manifest(
        run_id=run_id, query=query, session_id=session_id,
        traversal_plan=traversal_plan, nodes=nodes, edges=edges,
        answer=answer, validation=validation,
    )

    return {
        "answer": answer,
        "validation": validation,
        "proof_text": render_proof(answer, validation, nodes, edges, query, session_id),
        "manifest": manifest.to_dict(),
        "gap_proposals": generate_gap_proposals(query, nodes, edges, variants)
        if not validation.passed else [],
        "refused": False,
    }


def _template_answer(query: str, nodes: list[dict], edges: list[dict],
                     variants: list[str]) -> GroundedAnswer:
    """Build a simple template answer from graph structure when LLM unavailable."""
    from .schema import Claim, Citation

    claims = []
    for i, edge in enumerate(edges[:5]):
        src = edge.get("source", edge.get("source_note_id", ""))
        tgt = edge.get("target", edge.get("target_note_id", ""))
        rel = edge.get("relation", "links-to")
        var = edge.get("variant", "generic")

        # Find titles
        src_title = next((n.get("title", src) for n in nodes if n.get("note_id") == src), src)
        tgt_title = next((n.get("title", tgt) for n in nodes if n.get("note_id") == tgt), tgt)

        claims.append(Claim(
            claim_id=f"c{i+1}",
            text=f"{src_title} {rel} {tgt_title}.",
            claim_type=var if var in ("causal", "evidential", "temporal",
                        "provenance", "procedural", "semantic") else "definitional",
            confidence=edge.get("confidence", 0.5),
            citations=[Citation(
                note_id=src,
                edge_id=edge.get("edge_id", f"e{i}"),
                relation=rel,
                variant=var,
                source_note_title=src_title,
                target_note_title=tgt_title,
            )],
        ))

    answer_text = ". ".join(c.text for c in claims) if claims else (
        f"No structured answer available for: {query}"
    )

    return GroundedAnswer(
        answer_text=answer_text,
        claims=claims,
        insufficient_evidence=len(claims) == 0,
    )
