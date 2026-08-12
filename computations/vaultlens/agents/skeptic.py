"""The Skeptic Agent: autonomous red-teaming of load-bearing nodes.

Identifies nodes with high in-degree (concepts the entire vault depends on)
and aggressively hunts for contradictions, nullified edges, or refuting
evidence that no user query has ever triggered.

Finds hidden contradictions before users do.
"""

import sqlite3
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LoadBearingNode:
    """A node with high importance in the graph."""
    note_id: str
    title: str = ""
    in_degree: int = 0
    out_degree: int = 0
    active_edges: int = 0
    nullified_edges: int = 0
    contradiction_count: int = 0
    risk_score: float = 0.0
    recommendations: list[str] = field(default_factory=list)


@dataclass
class SkepticReport:
    """Results of a skeptic audit run."""
    nodes_audited: int
    contradictions_found: int
    high_risk_nodes: list[LoadBearingNode] = field(default_factory=list)
    debt_tickets_generated: int = 0


class SkepticAgent:
    """Autonomous red-teaming agent for graph quality assurance."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def find_load_bearing_nodes(self, top_k: int = 50) -> list[LoadBearingNode]:
        """Find nodes that the entire vault depends on.

        Load-bearing = high in-degree (many edges point to this concept).
        If this node is wrong, everything downstream is suspect.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        rows = conn.execute("""
            SELECT e.target_note_id, n.title,
                   COUNT(*) as in_degree
            FROM edges e
            JOIN notes n ON e.target_note_id = n.note_id
            WHERE e.resolved = 1
            GROUP BY e.target_note_id
            ORDER BY in_degree DESC
            LIMIT ?
        """, (top_k,)).fetchall()

        nodes = []
        for row in rows:
            nid = row["target_note_id"]
            out_degree = conn.execute(
                "SELECT COUNT(*) FROM edges WHERE source_note_id = ? AND resolved = 1",
                (nid,)
            ).fetchone()[0]

            active = conn.execute(
                "SELECT COUNT(*) FROM edges WHERE (source_note_id = ? OR target_note_id = ?) AND resolved = 1",
                (nid, nid)
            ).fetchone()[0]

            nullified = conn.execute(
                "SELECT COUNT(*) FROM edges WHERE (source_note_id = ? OR target_note_id = ?) AND resolved = 0",
                (nid, nid)
            ).fetchone()[0]

            nodes.append(LoadBearingNode(
                note_id=nid,
                title=row["title"],
                in_degree=row["in_degree"],
                out_degree=out_degree,
                active_edges=active,
                nullified_edges=nullified,
            ))

        conn.close()
        return nodes

    def audit_node(self, node: LoadBearingNode) -> LoadBearingNode:
        """Audit a single load-bearing node for hidden risks.

        Checks:
        1. Are any edges to this node nullified?
        2. Are there contradictory edges (supports + refutes on same target)?
        3. Do downstream edges reference nullified concepts?
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        # Check for nullified incoming edges
        nullified_in = conn.execute(
            "SELECT COUNT(*) FROM edges WHERE target_note_id = ? AND resolved = 0",
            (node.note_id,)
        ).fetchone()[0]

        if nullified_in > 0:
            node.recommendations.append(
                f"{nullified_in} nullified incoming edges — review whether "
                f"downstream claims relying on this node are still valid"
            )

        # Check for contradictory edge pairs (supports vs refutes on same connection)
        contradictions = conn.execute("""
            SELECT e1.source_note_id, e1.relation, e2.relation
            FROM edges e1
            JOIN edges e2 ON e1.source_note_id = e2.source_note_id
                         AND e1.target_note_id = e2.target_note_id
            WHERE e1.target_note_id = ?
              AND e1.relation = 'supports' AND e2.relation = 'refutes'
              AND e1.resolved = 1 AND e2.resolved = 1
        """, (node.note_id,)).fetchall()

        node.contradiction_count = len(contradictions)
        if contradictions:
            node.recommendations.append(
                f"{len(contradictions)} hidden contradiction(s) found: "
                f"same source both supports and refutes this node"
            )

        # Check if downstream targets are nullified
        downstream_nullified = conn.execute("""
            SELECT e2.target_note_id, e2.relation
            FROM edges e1
            JOIN edges e2 ON e1.target_note_id = e2.source_note_id
            WHERE e1.source_note_id = ?
              AND e2.resolved = 0
              AND e1.resolved = 1
            LIMIT 10
        """, (node.note_id,)).fetchall()

        if downstream_nullified:
            node.recommendations.append(
                f"{len(downstream_nullified)} downstream edges reference nullified nodes"
            )

        conn.close()

        # Compute risk score
        risk = 0.0
        risk += nullified_in * 0.15
        risk += node.contradiction_count * 0.25
        risk += min(len(downstream_nullified) * 0.1, 0.5)
        risk += (node.in_degree / max(node.in_degree + node.out_degree, 1)) * 0.2
        node.risk_score = round(min(risk, 1.0), 3)

        return node

    def run_audit(self, top_k: int = 50, risk_threshold: float = 0.2,
                  generate_debt: bool = True) -> SkepticReport:
        """Run a full skeptic audit on load-bearing nodes.

        Args:
            top_k: Number of top nodes to audit
            risk_threshold: Minimum risk score to flag
            generate_debt: Whether to create EpistemicDebt tickets

        Returns:
            SkepticReport with audit findings
        """
        nodes = self.find_load_bearing_nodes(top_k)
        high_risk = []

        for node in nodes:
            node = self.audit_node(node)
            if node.risk_score >= risk_threshold:
                high_risk.append(node)

        debt_generated = 0
        if generate_debt and high_risk:
            from ..foraging.debt import EpistemicDebt, DebtLedger
            ledger = DebtLedger()
            for node in high_risk[:10]:
                debt = EpistemicDebt(
                    debt_id=f"skeptic-{node.note_id}",
                    query_id=f"audit-{node.note_id}",
                    query_text=f"Load-bearing node audit: {node.title}",
                    trigger="escalate_human",
                    missing_evidence_type="contradiction_check",
                )
                ledger.create(debt)
                debt_generated += 1
            ledger.close()

        return SkepticReport(
            nodes_audited=len(nodes),
            contradictions_found=sum(n.contradiction_count for n in nodes),
            high_risk_nodes=high_risk,
            debt_tickets_generated=debt_generated,
        )
