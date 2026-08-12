"""The Archivist Agent: consolidation and pruning of the sovereign graph.

Identifies semantic duplicates, orphaned nodes, dead branches, and
drafts merge/supersede/prune proposals. Keeps the graph clean and
retrieval-efficient.

Uses title embeddings (Tier 1) to find semantic duplicates.
Never silently merges — always drafts proposals for human review.
"""

import json
import os
import sqlite3
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DuplicatePair:
    """Two nodes that appear to represent the same concept."""
    note_a_id: str
    note_a_title: str
    note_b_id: str
    note_b_title: str
    similarity: float
    proposal_id: str = ""
    action: str = "supersedes"  # 'supersedes', 'is-a', 'merge'


@dataclass
class OrphanNode:
    """A node with zero edges."""
    note_id: str
    title: str
    note_type: str
    created_days_ago: float


@dataclass
class ArchivistReport:
    """Results of an archivist audit run."""
    duplicates_found: int
    orphans_found: int
    proposals_generated: int
    duplicate_pairs: list[DuplicatePair] = field(default_factory=list)
    orphan_nodes: list[OrphanNode] = field(default_factory=list)


class ArchivistAgent:
    """Autonomous graph maintenance agent."""

    def __init__(self, db_path: str, proposals_dir: str = ".vaultlens/proposals/pending/"):
        self.db_path = db_path
        self.proposals_dir = proposals_dir

    def find_duplicates(self, similarity_threshold: float = 0.7,
                        max_pairs: int = 20) -> list[DuplicatePair]:
        """Find semantic duplicates using title similarity.

        Uses simple word overlap for MVP. In production: title embeddings.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        notes = conn.execute(
            "SELECT note_id, title, aliases FROM notes ORDER BY title"
        ).fetchall()

        pairs = []
        for i in range(len(notes)):
            for j in range(i + 1, min(i + 50, len(notes))):
                a = notes[i]
                b = notes[j]
                sim = self._title_similarity(a["title"], b["title"])

                # Also check aliases
                if sim < similarity_threshold:
                    a_aliases = json.loads(a["aliases"] or "[]")
                    b_aliases = json.loads(b["aliases"] or "[]")
                    for aa in a_aliases:
                        for ba in b_aliases:
                            alias_sim = self._title_similarity(aa, ba)
                            if alias_sim > sim:
                                sim = alias_sim

                if sim >= similarity_threshold:
                    pairs.append(DuplicatePair(
                        note_a_id=a["note_id"],
                        note_a_title=a["title"],
                        note_b_id=b["note_id"],
                        note_b_title=b["title"],
                        similarity=round(sim, 3),
                    ))

                if len(pairs) >= max_pairs:
                    break
            if len(pairs) >= max_pairs:
                break

        conn.close()
        return pairs

    def find_orphans(self, max_orphans: int = 50) -> list[OrphanNode]:
        """Find nodes with zero edges (dark matter)."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        import time
        now = time.time()
        SECONDS_PER_DAY = 86400

        rows = conn.execute("""
            SELECT n.note_id, n.title, n.note_type
            FROM notes n
            WHERE n.note_id NOT IN (
                SELECT source_note_id FROM edges WHERE resolved = 1
                UNION
                SELECT target_note_id FROM edges WHERE resolved = 1
            )
            LIMIT ?
        """, (max_orphans,)).fetchall()

        orphans = []
        for row in rows:
            orphans.append(OrphanNode(
                note_id=row["note_id"],
                title=row["title"],
                note_type=row["note_type"] or "unknown",
                created_days_ago=0,  # Would need created_at field
            ))

        conn.close()
        return orphans

    def _title_similarity(self, a: str, b: str) -> float:
        """Simple word-overlap similarity between two titles."""
        if not a or not b:
            return 0.0
        a_words = set(a.lower().split())
        b_words = set(b.lower().split())
        if not a_words or not b_words:
            return 0.0
        intersection = a_words & b_words
        union = a_words | b_words

        # Bonus for exact match
        if a.lower() == b.lower():
            return 1.0

        return len(intersection) / len(union)

    def generate_proposals(self, duplicates: list[DuplicatePair],
                           orphans: list[OrphanNode]) -> int:
        """Generate merge/supersede/prune proposals for review."""
        os.makedirs(self.proposals_dir, exist_ok=True)
        count = 0

        for dup in duplicates:
            dup.proposal_id = f"archivist-merge-{dup.note_a_id}-{dup.note_b_id}"
            proposal = {
                "proposal_id": dup.proposal_id,
                "source_title": dup.note_a_title,
                "target_title": dup.note_b_title,
                "relation": dup.action,
                "variant": "hierarchical",
                "confidence": dup.similarity,
                "evidence_span": f"Title similarity: {dup.similarity:.3f}",
                "rationale": (
                    f"Archivist detected semantic duplicate: "
                    f"'{dup.note_a_title}' ({dup.note_a_id}) and "
                    f"'{dup.note_b_title}' ({dup.note_b_id}) "
                    f"share {dup.similarity:.1%} title overlap"
                ),
                "proposer": "archivist-agent",
                "status": "pending",
            }

            fname = f"{dup.proposal_id}.json"
            with open(os.path.join(self.proposals_dir, fname), "w") as f:
                json.dump(proposal, f, indent=2)
            count += 1

        return count

    def run_audit(self, generate_proposals: bool = True) -> ArchivistReport:
        """Run a full archivist audit.

        Returns ArchivistReport with duplicates, orphans, and proposals.
        """
        duplicates = self.find_duplicates(similarity_threshold=0.6)
        orphans = self.find_orphans()
        proposals = 0

        if generate_proposals and (duplicates or orphans):
            proposals = self.generate_proposals(duplicates, orphans)

        return ArchivistReport(
            duplicates_found=len(duplicates),
            orphans_found=len(orphans),
            proposals_generated=proposals,
            duplicate_pairs=duplicates[:10],
            orphan_nodes=orphans[:10],
        )
