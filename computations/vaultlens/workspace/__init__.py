"""Ephemeral Working Memory: isolated in-memory graph for LLM reasoning.

The Scratchpad is a temporary, mutable workspace where an LLM can:
- Pull nodes from the Sovereign Vault
- Draft temporary, unverified edges
- Explore hypothetical paths
- Export proposals back to the governance pipeline

Key invariant: The Scratchpad CANNOT alter the Sovereign Vault.
All writes go through the standard HMAC-signed proposal pipeline.
"""

import json
import hashlib
import os
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ScratchpadNode:
    """A note pulled into the ephemeral workspace."""
    note_id: str
    title: str
    body: str = ""
    note_type: str = ""
    tags: list[str] = field(default_factory=list)
    source: str = "vault"     # 'vault', 'drafted', 'generated'
    draft_content: str = ""   # LLM-proposed body for generated notes


@dataclass
class ScratchpadEdge:
    """A relationship in the ephemeral workspace."""
    source_id: str
    target_id: str
    relation: str
    variant: str
    confidence: float = 0.5
    source_type: str = "vault"  # 'vault', 'drafted', 'hypothetical'
    evidence: str = ""


class Scratchpad:
    """Isolated in-memory graph for a single query/session.

    All operations are temporary. Nothing persists to disk unless
    explicitly exported to the proposal pipeline.
    """

    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id or f"session-{hashlib.sha256(os.urandom(16)).hexdigest()[:8]}"
        self.nodes: dict[str, ScratchpadNode] = {}
        self.edges: list[ScratchpadEdge] = []
        self.created_at = ""

        import datetime
        self.created_at = datetime.datetime.now().isoformat()

    # ── Pull from vault ────────────────────────────────

    def pull(self, vault_conn: sqlite3.Connection, note_ids: list[str]) -> int:
        """Pull notes from the Sovereign Vault into the scratchpad.

        Only reads — never writes to vault.

        Returns number of notes pulled.
        """
        if not note_ids:
            return 0

        placeholders = ",".join(["?"] * len(note_ids))
        cursor = vault_conn.execute(
            f"SELECT note_id, title, body, note_type, tags FROM notes WHERE note_id IN ({placeholders})",
            note_ids
        )
        pulled = 0
        for row in cursor:
            nid = row[0]
            if nid not in self.nodes:
                tags = json.loads(row[4] or "[]")
                self.nodes[nid] = ScratchpadNode(
                    note_id=nid,
                    title=row[1],
                    body=row[2] or "",
                    note_type=row[3] or "",
                    tags=tags if isinstance(tags, list) else [],
                    source="vault",
                )
                pulled += 1
        return pulled

    def pull_edges(self, vault_conn: sqlite3.Connection) -> int:
        """Pull relevant edges from vault for all nodes currently in scratchpad.

        Only pulls edges where BOTH endpoints are already in the scratchpad.
        """
        if len(self.nodes) < 2:
            return 0

        note_ids = list(self.nodes.keys())
        placeholders = ",".join(["?"] * len(note_ids))
        cursor = vault_conn.execute(
            f"""SELECT source_note_id, target_note_id, relation, variant, confidence
                FROM edges
                WHERE resolved = 1
                  AND source_note_id IN ({placeholders})
                  AND target_note_id IN ({placeholders})""",
            note_ids + note_ids
        )
        pulled = 0
        for row in cursor:
            edge = ScratchpadEdge(
                source_id=row[0],
                target_id=row[1],
                relation=row[2],
                variant=row[3],
                confidence=row[4] or 1.0,
                source_type="vault",
            )
            self.edges.append(edge)
            pulled += 1
        return pulled

    # ── Draft operations ────────────────────────────────

    def draft_node(self, title: str, body: str = "",
                   note_type: str = "draft") -> str:
        """Create a temporary draft note in the scratchpad.

        Returns the generated note_id.
        """
        nid = f"draft-{hashlib.sha256(title.encode()).hexdigest()[:8]}"
        self.nodes[nid] = ScratchpadNode(
            note_id=nid,
            title=title,
            body=body,
            note_type=note_type,
            source="drafted",
            draft_content=body,
        )
        return nid

    def draft_edge(self, source_id: str, target_id: str,
                   relation: str, variant: str = "generic",
                   confidence: float = 0.5, evidence: str = "",
                   hypothetical: bool = False) -> None:
        """Draft a temporary edge in the scratchpad.

        Args:
            hypothetical: If True, marked as 'hypothetical' — the LLM
                         is exploring a possibility, not asserting a fact.
        """
        self.edges.append(ScratchpadEdge(
            source_id=source_id,
            target_id=target_id,
            relation=relation,
            variant=variant,
            confidence=confidence,
            source_type="hypothetical" if hypothetical else "drafted",
            evidence=evidence,
        ))

    # ── Query the scratchpad ────────────────────────────

    def get_neighbors(self, note_id: str,
                      variant: Optional[str] = None) -> list[ScratchpadEdge]:
        """Get edges connected to a node, optionally filtered by variant."""
        result = []
        for e in self.edges:
            if e.source_id == note_id or e.target_id == note_id:
                if variant is None or e.variant == variant:
                    result.append(e)
        return result

    def get_paths(self, start_id: str, end_id: str,
                  max_hops: int = 3) -> list[list[ScratchpadEdge]]:
        """Find paths between two nodes in the scratchpad (BFS)."""
        from collections import deque
        paths = []
        queue = deque([(start_id, [])])
        visited_depths = {start_id: 0}

        while queue:
            current, current_path = queue.popleft()
            if len(current_path) >= max_hops:
                continue

            for edge in self.edges:
                neighbor = None
                if edge.source_id == current:
                    neighbor = edge.target_id
                elif edge.target_id == current:
                    neighbor = edge.source_id
                else:
                    continue

                new_depth = len(current_path) + 1
                if neighbor in visited_depths and visited_depths[neighbor] <= new_depth:
                    continue

                new_path = current_path + [edge]
                visited_depths[neighbor] = new_depth

                if neighbor == end_id:
                    paths.append(new_path)
                else:
                    queue.append((neighbor, new_path))

        return paths

    def snapshot(self) -> dict:
        """Return a JSON-serializable snapshot of the scratchpad state."""
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "nodes": {
                nid: {
                    "title": n.title,
                    "note_type": n.note_type,
                    "source": n.source,
                    "body_preview": (n.body or n.draft_content)[:200],
                }
                for nid, n in self.nodes.items()
            },
            "edges": [
                {
                    "source": e.source_id,
                    "target": e.target_id,
                    "relation": e.relation,
                    "variant": e.variant,
                    "source_type": e.source_type,
                    "confidence": e.confidence,
                }
                for e in self.edges
            ],
            "stats": self.stats(),
        }

    def stats(self) -> dict:
        """Return scratchpad statistics."""
        vault_nodes = sum(1 for n in self.nodes.values() if n.source == "vault")
        drafted_nodes = sum(1 for n in self.nodes.values() if n.source == "drafted")
        vault_edges = sum(1 for e in self.edges if e.source_type == "vault")
        drafted_edges = sum(1 for e in self.edges if e.source_type == "drafted")
        hypothetical = sum(1 for e in self.edges if e.source_type == "hypothetical")
        return {
            "nodes_vault": vault_nodes,
            "nodes_drafted": drafted_nodes,
            "edges_vault": vault_edges,
            "edges_drafted": drafted_edges,
            "edges_hypothetical": hypothetical,
        }

    # ── Export to governance pipeline ───────────────────

    def export_proposals(self, output_dir: str = ".vaultlens/proposals/pending/") -> int:
        """Export drafted edges as pending proposals for human review.

        Only exports drafted edges (not vault edges, not hypothetical).
        Each exported proposal goes through the standard governance pipeline.

        Returns number of proposals exported.
        """
        os.makedirs(output_dir, exist_ok=True)
        count = 0

        for edge in self.edges:
            if edge.source_type != "drafted":
                continue

            # Skip if either endpoint is also a draft (not yet in vault)
            src_node = self.nodes.get(edge.source_id)
            tgt_node = self.nodes.get(edge.target_id)
            src_title = src_node.title if src_node else edge.source_id
            tgt_title = tgt_node.title if tgt_node else edge.target_id

            proposal = {
                "proposal_id": f"scratchpad-{self.session_id}-{count:03d}",
                "source_title": src_title,
                "target_title": tgt_title,
                "relation": edge.relation,
                "variant": edge.variant,
                "confidence": edge.confidence,
                "evidence_span": edge.evidence,
                "rationale": f"Drafted in scratchpad session {self.session_id}",
                "proposer": "scratchpad",
                "status": "pending",
                "session_id": self.session_id,
            }

            fname = f"{proposal['proposal_id']}.json"
            with open(os.path.join(output_dir, fname), "w") as f:
                json.dump(proposal, f, indent=2)
            count += 1

        return count

    def to_context_string(self) -> str:
        """Serialize the scratchpad as a structured context block for an LLM."""
        lines = []
        lines.append(f"## Scratchpad Session: {self.session_id}")
        lines.append("")

        # Group nodes by source
        vault_nodes = {nid: n for nid, n in self.nodes.items() if n.source == "vault"}
        drafted_nodes = {nid: n for nid, n in self.nodes.items() if n.source != "vault"}

        if vault_nodes:
            lines.append("### Sovereign Vault Notes")
            for nid, n in vault_nodes.items():
                lines.append(f"- **{n.title}** ({n.note_type}) [{nid}]")
                if n.body:
                    lines.append(f"  {n.body[:300]}")
            lines.append("")

        if drafted_nodes:
            lines.append("### Drafted / Working Notes")
            for nid, n in drafted_nodes.items():
                lines.append(f"- **{n.title}** ({n.note_type}) [{nid}] — DRAFT")
                if n.draft_content:
                    lines.append(f"  {n.draft_content[:300]}")
            lines.append("")

        if self.edges:
            lines.append("### Relationships")
            for e in self.edges:
                tag = ""
                if e.source_type == "hypothetical":
                    tag = " [HYPOTHETICAL]"
                elif e.source_type == "drafted":
                    tag = " [DRAFT]"
                src_title = self.nodes.get(e.source_id, ScratchpadNode(e.source_id, e.source_id)).title
                tgt_title = self.nodes.get(e.target_id, ScratchpadNode(e.target_id, e.target_id)).title
                lines.append(f"- {src_title} --{e.relation}--> {tgt_title} ({e.variant}){tag}")
            lines.append("")

        return "\n".join(lines)
