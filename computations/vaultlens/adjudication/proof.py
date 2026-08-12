"""Federated proof chain renderer and audit manifest for v0.7 adjudication.

Produces human-readable proof chains showing: routing, claims, conflicts,
policy checks, resolution strategy, disclosures, and final mode.
Every decision is signed and auditable.
"""

import json
from .claims import ExpertClaim
from .conflicts import Conflict
from .adjudicator import AdjudicationDecision


def render_federated_proof(
    query: str,
    decision: AdjudicationDecision,
    routing_log: dict = None,
    session_id: str = "",
) -> str:
    """Render a complete federated proof chain for an adjudicated answer.

    Shows the full decision path: routing → claims → conflicts →
    policy → strategy → disclosures → final mode.
    """
    lines = []
    lines.append("=" * 60)
    lines.append("FEDERATED ADJUDICATION — PROOF CHAIN")
    lines.append("=" * 60)

    if query:
        lines.append(f"Query: {query}")
    if session_id:
        lines.append(f"Session: {session_id}")
    lines.append(f"Decision: {decision.decision_id}")
    lines.append(f"Timestamp: {decision.created_at}")
    lines.append("")

    # Routing
    if routing_log:
        lines.append("── Routing ──")
        if routing_log.get("selected_experts"):
            lines.append(f"Selected: {', '.join(routing_log['selected_experts'])}")
        if routing_log.get("rejected_experts"):
            lines.append("Rejected:")
            for r in routing_log["rejected_experts"]:
                lines.append(f"  - {r.get('expert_id', '?')}: {r.get('reason', '?')}")
        lines.append("")

    # Claims
    if decision.claims:
        lines.append(f"── Expert Claims ({len(decision.claims)} total, "
                    f"{len(decision.allowed_claims)} allowed, "
                    f"{len(decision.excluded_claims)} excluded) ──")
        lines.append("")

        for cdict in decision.claims:
            cid = cdict.get("claim_id", "?")
            allowed = cid in decision.allowed_claims
            status = "ALLOWED" if allowed else "EXCLUDED"

            lines.append(f"  [{status}] Claim {cid}")
            lines.append(f"    Expert: {cdict.get('expert_id', '?')}")
            lines.append(f"    Domain: {cdict.get('domain', '?')} "
                        f"({cdict.get('jurisdiction', '?')})")
            lines.append(f"    Type: {cdict.get('claim_type', '?')} "
                        f"| Confidence: {cdict.get('confidence', 0):.2f}")
            lines.append(f"    Text: {cdict.get('text', '?')[:120]}")
            lines.append("")

    # Conflicts
    if decision.conflicts:
        lines.append(f"── Conflicts ({len(decision.conflicts)}) ──")
        lines.append("")
        for cdict in decision.conflicts:
            sev = cdict.get("severity", "?").upper()
            ctype = cdict.get("conflict_type", "?")
            lines.append(f"  [{sev}] {ctype}")
            lines.append(f"    {cdict.get('explanation', '?')}")
            lines.append("")

    # Policy
    if decision.policy_checks:
        lines.append("── Policy Checks ──")
        lines.append("")
        for pc in decision.policy_checks:
            cid = pc.get("claim_id", "?")
            for check in pc.get("checks", []):
                icon = "PASS" if check.get("passed") else "FAIL"
                lines.append(f"  [{icon}] {cid}: {check.get('detail', '?')}")
        lines.append("")

    # Strategy
    lines.append(f"── Resolution Strategy ──")
    lines.append(f"  {decision.strategy}")
    lines.append("")

    # Disclosures
    if decision.disclosures:
        lines.append("── Disclosures ──")
        for d in decision.disclosures:
            lines.append(f"  - {d}")
        lines.append("")

    # Final mode
    mode_labels = {
        "conservative": "Conservative (safe claims only)",
        "disclosed": "Disclosed (conflicts shown, no synthesis)",
        "provisional": "Provisional (low confidence, review recommended)",
        "refused": "Refused (insufficient compliant evidence)",
        "escalated": "Escalated (requires human adjudication)",
    }
    lines.append(f"── Final Mode ──")
    lines.append(f"  {mode_labels.get(decision.final_mode, decision.final_mode)}")
    lines.append(f"  Confidence: {decision.confidence:.2f}")
    lines.append(f"  Human review: {'REQUIRED' if decision.requires_human_review else 'not required'}")
    lines.append("")

    # Audit
    lines.append("── Audit ──")
    lines.append(f"  Decision hash: {decision.audit_hash}")
    lines.append(f"  HMAC: {decision.hmac_sig[:16]}...")
    lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)


def render_federated_answer(decision: AdjudicationDecision,
                            query: str = "") -> str:
    """Render the actual answer text from an adjudication decision."""
    if decision.final_mode == "refused":
        return ("Insufficient policy-compliant evidence to answer this query. "
                f"Strategy: {decision.strategy}. "
                f"Excluded claims: {len(decision.excluded_claims)}. "
                "No answer can be provided without violating sovereignty policy.")

    if decision.final_mode == "escalated":
        return ("This query requires human adjudication due to critical conflicts "
                f"({len(decision.conflicts)} conflict(s) detected). "
                "No automated answer is provided.")

    allowed_claim_texts = []
    for cdict in decision.claims:
        if cdict.get("claim_id") in decision.allowed_claims:
            allowed_claim_texts.append(
                f"[{cdict.get('expert_id', '?')}] {cdict.get('text', '?')}"
            )

    if not allowed_claim_texts:
        return "No policy-compliant claims available for synthesis."

    answer = "\n".join(f"- {t}" for t in allowed_claim_texts)

    if decision.final_mode == "conservative":
        prefix = "Conservative synthesis (policy-compliant claims only):\n\n"
    elif decision.final_mode == "disclosed":
        prefix = ("Disclosed synthesis — expert claims differ. No unified conclusion is asserted. "
                  "See conflicts above.\n\n")
    elif decision.final_mode == "provisional":
        prefix = ("Provisional synthesis — confidence below threshold. "
                  "Human review recommended.\n\n")
    else:
        prefix = ""

    return prefix + answer
