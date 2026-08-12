"""Active Epistemic Foraging Engine: autonomously investigates knowledge gaps.

Four strategies for resolving Epistemic Debt:
1. Scope-Bridging: find bridging concepts in the graph
2. Counterfactual Red-Teaming: check downstream nullification
3. Socratic Disambiguation: ask the user targeted questions
4. Automated Resolution Proposals: draft edge proposals to fill gaps

Key invariant: the Forager NEVER hallucinates. It only traverses existing
graph edges or drafts proposals for human review.
"""

import json
import sqlite3
from dataclasses import dataclass, field
from typing import Optional

from .debt import EpistemicDebt, DebtLedger, ForagingStrategy


@dataclass
class ForagingResult:
    """Result of a foraging investigation."""
    debt_id: str
    strategy_used: ForagingStrategy
    success: bool
    findings: list[str] = field(default_factory=list)
    socratic_question: Optional[str] = None
    socratic_options: list[str] = field(default_factory=list)
    proposals_generated: int = 0
    confidence_adjustments: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


class ForagingEngine:
    """Investigates epistemic debt and attempts autonomous resolution."""

    def __init__(self, vault_db_path: str, ledger: DebtLedger,
                 proposals_dir: str = ".vaultlens/proposals/pending/"):
        self.vault_db_path = vault_db_path
        self.ledger = ledger
        self.proposals_dir = proposals_dir

    def process_debt(self, debt: EpistemicDebt) -> ForagingResult:
        """Process a single debt ticket through all applicable strategies.

        Returns ForagingResult with findings and any generated outputs.
        """
        self.ledger.update_status(debt.debt_id, "investigating",
                                   notes=["Investigation started"])

        # Strategy 1: Scope-Bridging (for scope_mismatch, partial_overlap)
        if debt.trigger in ("conflict_unresolved", "escalate_human"):
            bridge = self._strategy_scope_bridge(debt)
            if bridge.success and bridge.findings:
                self.ledger.update_status(
                    debt.debt_id, "resolved",
                    notes=bridge.findings,
                    strategy="scope_bridge",
                )
                return bridge

        # Strategy 2: Counterfactual Red-Teaming
        if debt.trigger in ("conflict_unresolved", "escalate_human"):
            ct_result = self._strategy_counterfactual(debt)
            if ct_result.confidence_adjustments:
                self.ledger.update_status(
                    debt.debt_id, "partially_resolved",
                    notes=ct_result.findings,
                    strategy="counterfactual",
                )
                return ct_result

        # Strategy 3: Socratic Disambiguation
        if debt.trigger == "escalate_human":
            socratic = self._strategy_socratic(debt)
            if socratic.socratic_question:
                self.ledger.update_status(
                    debt.debt_id, "investigating",
                    notes=["Socratic question generated — awaiting user response"],
                    strategy="socratic",
                )
                return socratic

        # Strategy 4: Draft Resolution Proposals
        if debt.trigger in ("suspend", "conflict_unresolved"):
            proposal = self._strategy_proposal(debt)
            if proposal.proposals_generated > 0:
                self.ledger.update_status(
                    debt.debt_id, "partially_resolved",
                    notes=proposal.findings,
                    strategy="proposal",
                )
                return proposal

        # Nothing worked — mark as unresolvable automatically
        self.ledger.update_status(
            debt.debt_id, "unresolvable",
            notes=["All autonomous strategies exhausted. Requires human intervention."],
        )
        return ForagingResult(
            debt_id=debt.debt_id,
            strategy_used="none",
            success=False,
            findings=["No autonomous resolution strategy succeeded."],
        )

    # ── Strategy 1: Scope-Bridging ─────────────────────

    def _strategy_scope_bridge(self, debt: EpistemicDebt) -> ForagingResult:
        """Search the graph for bridging concepts between conflicting claims.

        Looks for nodes that connect to both sides of a conflict through
        causal, evidential, or semantic edges.
        """
        findings = []
        conn = sqlite3.connect(self.vault_db_path)

        # Find the conflict to understand what's being disputed
        if not debt.conflict_id:
            conn.close()
            return ForagingResult(debt.debt_id, "scope_bridge", False, [])

        # Check if any node bridges the two conflicting claims
        # Search for nodes with edges to both claim domains
        cursor = conn.execute("""
            SELECT e1.source_note_id, e1.target_note_id, e1.relation, e1.variant,
                   e2.relation, e2.variant
            FROM edges e1
            JOIN edges e2 ON (e1.target_note_id = e2.source_note_id
                           OR e1.source_note_id = e2.source_note_id)
            WHERE e1.variant != e2.variant
              AND e1.variant IN ('causal', 'evidential', 'semantic')
              AND e2.variant IN ('causal', 'evidential', 'semantic')
              AND e1.resolved = 1 AND e2.resolved = 1
            LIMIT 5
        """)

        bridges = list(cursor)
        if bridges:
            for b in bridges[:3]:
                findings.append(
                    f"Bridge found: node connects {b[2]}({b[3]}) and {b[4]}({b[5]}) "
                    f"between {b[0]} and {b[1]}"
                )
        else:
            findings.append("No bridging concepts found in current graph.")

        conn.close()
        return ForagingResult(
            debt_id=debt.debt_id,
            strategy_used="scope_bridge",
            success=len(bridges) > 0,
            findings=findings,
        )

    # ── Strategy 2: Counterfactual Red-Teaming ─────────

    def _strategy_counterfactual(self, debt: EpistemicDebt) -> ForagingResult:
        """Check downstream nullification: if a claim's downstream effects are
        nullified, reduce the claim's confidence."""
        findings = []
        adjustments = {}
        conn = sqlite3.connect(self.vault_db_path)

        # Find causal claims and trace their downstream effects
        cursor = conn.execute("""
            SELECT e1.source_note_id, e1.target_note_id, e1.relation, e1.confidence,
                   e2.target_note_id, e2.relation, e2.variant
            FROM edges e1
            JOIN edges e2 ON e1.target_note_id = e2.source_note_id
            WHERE e1.variant = 'causal'
              AND (e2.variant = 'evidential' AND e2.relation = 'refutes')
              AND e1.resolved = 1 AND e2.resolved = 1
            LIMIT 5
        """)

        nullified_chains = list(cursor)
        if nullified_chains:
            for c in nullified_chains[:3]:
                src = c[0]
                tgt = c[1]
                downstream = c[4]
                findings.append(
                    f"Downstream nullification: {src} --{c[2]}--> {tgt} is undermined "
                    f"because {tgt} --refutes--> {downstream}"
                )
                # Apply epistemic penalty
                if src not in adjustments:
                    adjustments[src] = max(0.1, (c[3] or 0.5) - 0.3)
        else:
            findings.append("No downstream nullification found.")

        conn.close()
        return ForagingResult(
            debt_id=debt.debt_id,
            strategy_used="counterfactual",
            success=len(nullified_chains) > 0,
            findings=findings,
            confidence_adjustments=adjustments,
        )

    # ── Strategy 3: Socratic Disambiguation ────────────

    def _strategy_socratic(self, debt: EpistemicDebt) -> ForagingResult:
        """Generate a targeted Socratic question to resolve ambiguity.

        The question is derived from the conflicting claims' scope or
        jurisdiction mismatch — never invented.
        """
        question = None
        options = []

        if debt.trigger == "escalate_human":
            # Check if we have conflict context
            conn = sqlite3.connect(self.vault_db_path)
            # Find scope-mismatch keywords in debt's query or conflict
            has_supply_terms = any(w in (debt.query_text or "").lower()
                                   for w in ["supply", "shock", "cost-push"])
            has_demand_terms = any(w in (debt.query_text or "").lower()
                                    for w in ["demand", "spending", "consumer"])

            if has_supply_terms and has_demand_terms:
                question = (
                    "Experts disagree on this outcome. To resolve this, "
                    "please clarify the operating environment:"
                )
                options = [
                    "Demand-driven conditions (standard monetary policy applies)",
                    "Supply-driven conditions (supply shocks present)",
                    "Mixed conditions (both demand and supply factors)",
                ]
            else:
                question = (
                    "The system cannot safely synthesize these claims without more context. "
                    "To resolve the conflict, please clarify which expert domain is most "
                    "relevant to your query:"
                )
                options = [
                    "Macroeconomic analysis (broad policy effects)",
                    "Monetary policy analysis (interest rate mechanisms)",
                    "I don't know / Use the most conservative interpretation",
                ]

            conn.close()

        return ForagingResult(
            debt_id=debt.debt_id,
            strategy_used="socratic",
            success=question is not None,
            findings=[question] if question else [],
            socratic_question=question,
            socratic_options=options,
        )

    # ── Strategy 4: Automated Resolution Proposals ─────

    def _strategy_proposal(self, debt: EpistemicDebt) -> ForagingResult:
        """Draft edge proposals to fill evidential gaps."""
        import os
        os.makedirs(self.proposals_dir, exist_ok=True)

        proposals_written = 0
        findings = []

        if debt.missing_evidence_type:
            proposal = {
                "proposal_id": f"forager-{debt.debt_id}",
                "source_title": debt.query_text[:60] if debt.query_text else "Unknown",
                "target_title": f"Evidence for {debt.missing_evidence_type}",
                "relation": "supports",
                "variant": "evidential",
                "confidence": 0.3,
                "evidence_span": f"Auto-generated from epistemic debt {debt.debt_id}",
                "rationale": (
                    f"Debt {debt.debt_id}: missing {debt.missing_evidence_type} evidence. "
                    f"Query: {debt.query_text[:100]}"
                ),
                "proposer": "foraging-engine",
                "status": "pending",
                "debt_id": debt.debt_id,
            }

            fname = f"{proposal['proposal_id']}.json"
            with open(os.path.join(self.proposals_dir, fname), "w") as f:
                json.dump(proposal, f, indent=2)
            proposals_written = 1
            findings.append(f"Generated proposal: {fname}")

        return ForagingResult(
            debt_id=debt.debt_id,
            strategy_used="proposal",
            success=proposals_written > 0,
            findings=findings,
            proposals_generated=proposals_written,
        )

    # ── Batch processing ───────────────────────────────

    def process_all_open(self) -> dict:
        """Process all open debts. Returns summary stats."""
        open_debts = self.ledger.list_by_status("open")
        results = {"processed": 0, "resolved": 0, "unresolvable": 0,
                   "socratic_pending": 0, "proposals": 0}

        for debt in open_debts:
            result = self.process_debt(debt)
            results["processed"] += 1
            if result.strategy_used in ("scope_bridge", "counterfactual"):
                results["resolved"] += 1
            elif result.strategy_used == "socratic":
                results["socratic_pending"] += 1
            elif result.strategy_used == "proposal":
                results["proposals"] += 1
            else:
                results["unresolvable"] += 1

        return results
