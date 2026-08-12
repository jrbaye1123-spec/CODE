"""Session consolidation: the Sleep Cycle that persists session learning.

When a session ends, this module:
1. Diffs the Session Graph against the Sovereign Graph
2. Identifies LLM-inferred edges not in the sovereign graph
3. Formats them as standard VaultLens proposals
4. Pushes them to the HMAC-signed proposal queue

Key invariant: session consolidation is one-way. Session → proposals.
The sovereign graph is never mutated directly.
"""

import json
import os
import time
from dataclasses import dataclass
from typing import Optional

from .memory import SessionContext, SessionEdge


@dataclass
class ConsolidationReport:
    """Report from a session sleep cycle."""
    session_id: str
    session_duration_seconds: float
    total_session_edges: int
    sovereign_edges: int
    inferred_edges: int
    new_proposals: int
    existing_edges: int
    proposals_written: list[str] = None  # list of proposal filenames

    def __post_init__(self):
        if self.proposals_written is None:
            self.proposals_written = []


class SessionConsolidator:
    """Consolidates session learning into pending proposals."""

    def __init__(self, vault_db_path: str, proposals_dir: str = ".vaultlens/proposals/pending/"):
        self.vault_db_path = vault_db_path
        self.proposals_dir = proposals_dir

    def consolidate(self, session: SessionContext) -> ConsolidationReport:
        """Run the sleep cycle on a completed session.

        Returns a ConsolidationReport with details of what was found.
        """
        import sqlite3
        conn = sqlite3.connect(self.vault_db_path)

        proposals_written = []
        new_count = 0
        existing_count = 0

        inferred = session.get_llm_inferred_edges()

        for edge in inferred:
            # Check if this edge exists in the sovereign graph
            exists = self._edge_exists(conn, edge)

            if exists:
                existing_count += 1
                continue

            # Create proposal
            proposal = self._edge_to_proposal(session, edge)
            fname = self._write_proposal(proposal)
            proposals_written.append(fname)
            new_count += 1

        conn.close()

        return ConsolidationReport(
            session_id=session.session_id,
            session_duration_seconds=round(time.time() - session.started_at, 1),
            total_session_edges=len(session.edges),
            sovereign_edges=sum(1 for e in session.edges if e.from_sovereign),
            inferred_edges=len(inferred),
            new_proposals=new_count,
            existing_edges=existing_count,
            proposals_written=proposals_written,
        )

    def _edge_exists(self, conn, edge: SessionEdge) -> bool:
        """Check if an edge already exists in the sovereign graph."""
        cursor = conn.execute(
            """SELECT COUNT(*) FROM edges
               WHERE source_note_id = ? AND target_note_id = ?
                 AND relation = ? AND resolved = 1""",
            (edge.source_id, edge.target_id, edge.relation)
        )
        return cursor.fetchone()[0] > 0

    def _edge_to_proposal(self, session: SessionContext,
                          edge: SessionEdge) -> dict:
        """Convert a session edge to a standard VaultLens proposal."""
        import hashlib
        pid = hashlib.sha256(
            f"{session.session_id}|{edge.source_id}|{edge.relation}|{edge.target_id}".encode()
        ).hexdigest()[:12]

        return {
            "proposal_id": f"session-{pid}",
            "source_title": edge.source_id,
            "target_title": edge.target_id,
            "relation": edge.relation,
            "variant": edge.variant,
            "confidence": min(edge.confidence, 0.5),  # Cap session-inferred confidence
            "evidence_span": edge.evidence or f"Inferred during session {session.session_id}",
            "rationale": f"Session consolidation: inferred relationship not yet in sovereign graph. Session: {session.session_id}",
            "proposer": "session-consolidator",
            "status": "pending",
            "session_id": session.session_id,
        }

    def _write_proposal(self, proposal: dict) -> str:
        """Write a proposal to the pending directory. Returns filename."""
        os.makedirs(self.proposals_dir, exist_ok=True)
        fname = f"{proposal['proposal_id']}.json"
        path = os.path.join(self.proposals_dir, fname)
        with open(path, "w") as f:
            json.dump(proposal, f, indent=2)
        return fname
