"""The Night Watchman: daemon orchestrator for continuous epistemic hygiene.

Orchestrates the three immune system agents on a schedule:
1. Decay Engine: apply temporal confidence decay
2. Skeptic Agent: red-team load-bearing nodes
3. Archivist Agent: find duplicates and orphans

Generates Epistemic Dashboard metrics after each cycle.
"""

import json
import os
import time
from dataclasses import dataclass, field
from typing import Optional

from .decay import DecayEngine, DecayConfig
from .skeptic import SkepticAgent, SkepticReport
from .archivist import ArchivistAgent, ArchivistReport


@dataclass
class DashboardMetrics:
    """Health metrics for the Epistemic Dashboard."""
    truth_index: float             # Active high-confidence edges / total edges
    epistemic_debt_load: int       # Open debt tickets
    contradiction_count: int       # Active contradictions
    decayed_edges: int             # Edges below active threshold
    macro_nodes: int               # Compiled macro-nodes
    consolidation_queue: int       # Pending proposals
    timestamp: str = ""

    def to_dict(self) -> dict:
        return {
            "truth_index": round(self.truth_index, 3),
            "epistemic_debt_load": self.epistemic_debt_load,
            "contradiction_count": self.contradiction_count,
            "decayed_edges": self.decayed_edges,
            "macro_nodes": self.macro_nodes,
            "consolidation_queue": self.consolidation_queue,
            "timestamp": self.timestamp or time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }


@dataclass
class WatchmanReport:
    """Complete night watchman cycle report."""
    cycle_id: str
    decay_stats: dict = field(default_factory=dict)
    skeptic_report: Optional[SkepticReport] = None
    archivist_report: Optional[ArchivistReport] = None
    metrics: Optional[DashboardMetrics] = None
    duration_seconds: float = 0.0


class NightWatchman:
    """Orchestrates autonomous maintenance agents."""

    def __init__(self, vault_db_path: str, proposals_dir: str = ".vaultlens/proposals/pending/"):
        self.vault_db_path = vault_db_path
        self.proposals_dir = proposals_dir
        self.decay = DecayEngine(vault_db_path)
        self.skeptic = SkepticAgent(vault_db_path)
        self.archivist = ArchivistAgent(vault_db_path, proposals_dir)

    def run_cycle(self, cycle_id: str = "", dry_run: bool = False) -> WatchmanReport:
        """Run a full maintenance cycle.

        Order matters: decay first (reduces old confidences), then skeptic
        (checks what's still load-bearing), then archivist (cleans up).
        """
        import hashlib, os
        if not cycle_id:
            cycle_id = f"cycle_{hashlib.sha256(os.urandom(8)).hexdigest()[:8]}"

        t0 = time.time()

        # 1. Apply decay
        decay_stats = self.decay.apply_decay(dry_run=dry_run)

        # 2. Run skeptic audit
        skeptic_report = self.skeptic.run_audit(top_k=30)

        # 3. Run archivist audit
        archivist_report = self.archivist.run_audit(generate_proposals=not dry_run)

        # 4. Compute dashboard metrics
        metrics = self._compute_metrics(decay_stats, skeptic_report, archivist_report)

        elapsed = time.time() - t0

        return WatchmanReport(
            cycle_id=cycle_id,
            decay_stats=decay_stats,
            skeptic_report=skeptic_report,
            archivist_report=archivist_report,
            metrics=metrics,
            duration_seconds=round(elapsed, 2),
        )

    def _compute_metrics(self, decay_stats: dict,
                         skeptic: SkepticReport,
                         archivist: ArchivistReport) -> DashboardMetrics:
        """Compute Epistemic Dashboard metrics from agent reports."""
        import sqlite3

        conn = sqlite3.connect(self.vault_db_path)
        total_edges = conn.execute(
            "SELECT COUNT(*) FROM edges WHERE resolved = 1"
        ).fetchone()[0]
        high_conf_edges = conn.execute(
            "SELECT COUNT(*) FROM edges WHERE resolved = 1 AND confidence >= 0.7"
        ).fetchone()[0]
        contradiction_count = conn.execute(
            "SELECT COUNT(*) FROM edges WHERE relation = 'refutes' AND resolved = 1"
        ).fetchone()[0]
        conn.close()

        # Truth Index: ratio of active high-confidence edges
        truth_index = high_conf_edges / max(total_edges, 1)

        # Count pending proposals
        proposals_count = 0
        if os.path.isdir(self.proposals_dir):
            proposals_count = len([
                f for f in os.listdir(self.proposals_dir)
                if f.endswith(".json")
            ])

        return DashboardMetrics(
            truth_index=truth_index,
            epistemic_debt_load=0,  # Would query debt ledger
            contradiction_count=contradiction_count,
            decayed_edges=decay_stats.get("decayed", 0),
            macro_nodes=0,
            consolidation_queue=proposals_count,
        )

    def print_report(self, report: WatchmanReport) -> str:
        """Format a watchman cycle report for CLI output."""
        lines = []
        lines.append("=" * 60)
        lines.append(f"NIGHT WATCHMAN — Cycle {report.cycle_id}")
        lines.append("=" * 60)
        lines.append(f"Duration: {report.duration_seconds}s")
        lines.append("")

        # Decay
        lines.append("── Decay Engine ──")
        ds = report.decay_stats
        lines.append(f"  Edges checked: {ds.get('total_edges', 0)}")
        lines.append(f"  Decayed: {ds.get('decayed', 0)}")
        lines.append(f"  Unchanged: {ds.get('unchanged', 0)}")
        lines.append(f"  Provisional: {ds.get('provisional', 0)}")
        lines.append(f"  Needs review: {ds.get('needs_review', 0)}")
        lines.append("")

        # Skeptic
        if report.skeptic_report:
            sr = report.skeptic_report
            lines.append("── Skeptic Agent ──")
            lines.append(f"  Nodes audited: {sr.nodes_audited}")
            lines.append(f"  Contradictions: {sr.contradictions_found}")
            lines.append(f"  High-risk nodes: {len(sr.high_risk_nodes)}")
            lines.append(f"  Debt tickets: {sr.debt_tickets_generated}")
            if sr.high_risk_nodes:
                lines.append("  Top risks:")
                for node in sr.high_risk_nodes[:3]:
                    lines.append(f"    [{node.risk_score:.2f}] {node.title} "
                                f"(in-degree={node.in_degree})")
            lines.append("")

        # Archivist
        if report.archivist_report:
            ar = report.archivist_report
            lines.append("── Archivist Agent ──")
            lines.append(f"  Duplicates: {ar.duplicates_found}")
            lines.append(f"  Orphans: {ar.orphans_found}")
            lines.append(f"  Proposals: {ar.proposals_generated}")
            lines.append("")

        # Metrics
        if report.metrics:
            m = report.metrics
            lines.append("── Dashboard Metrics ──")
            lines.append(f"  Truth Index: {m.truth_index:.1%}")
            lines.append(f"  Epistemic Debt: {m.epistemic_debt_load}")
            lines.append(f"  Contradictions: {m.contradiction_count}")
            lines.append(f"  Decayed edges: {m.decayed_edges}")
            lines.append(f"  Pending proposals: {m.consolidation_queue}")
            lines.append("")

        lines.append("=" * 60)
        return "\n".join(lines)
