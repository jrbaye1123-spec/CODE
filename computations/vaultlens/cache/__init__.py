"""Macro-node compiler: structural caching for dense subgraphs.

Identifies frequently co-traversed subgraphs and compiles them into summary
Macro-Nodes. This reduces hop-count for global queries from 5+ hops to 1 hop
without losing the underlying discrete edges.

Key invariant: Macro-Nodes retain `comprises::` edges back to source notes.
The sovereign graph is never altered — this is a read-only structural cache.

Algorithm: Simple degree-based community detection (Leiden/Girvan-Newman
would be overkill for MVP). Identifies cliques and near-cliques by finding
sets of densely interconnected notes.
"""

import sqlite3
import json
import hashlib
import os
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MacroNode:
    """A compiled summary node representing a dense subgraph."""
    macro_id: str
    title: str
    summary: str = ""
    member_ids: list[str] = field(default_factory=list)
    edge_count: int = 0
    internal_density: float = 0.0
    variant: str = "generic"
    created_at: str = ""
    content_hash: str = ""


# ── Community detection ────────────────────────────────

def detect_dense_subgraphs(conn: sqlite3.Connection,
                           min_members: int = 3,
                           max_members: int = 12,
                           min_density: float = 0.4,
                           max_communities: int = 10) -> list[list[str]]:
    """Detect dense subgraphs using a simple greedy approach.

    For MVP: finds sets of nodes that are all connected to each other
    (cliques and near-cliques) by checking co-occurrence in edges.

    Args:
        conn: SQLite connection
        min_members: Minimum nodes per community
        max_members: Maximum nodes per community
        min_density: Minimum internal edge density (0-1)
        max_communities: Max communities to return

    Returns:
        List of lists of note_ids, each a detected community
    """
    # Build adjacency from edges
    edges = conn.execute(
        "SELECT source_note_id, target_note_id FROM edges WHERE resolved = 1"
    ).fetchall()

    adj: dict[str, set[str]] = defaultdict(set)
    for src, tgt in edges:
        if src and tgt:
            adj[src].add(tgt)
            adj[tgt].add(src)

    # Get degree-sorted nodes (start from hubs)
    nodes = sorted(adj.keys(), key=lambda n: len(adj[n]), reverse=True)

    communities = []
    visited = set()

    for seed in nodes:
        if seed in visited:
            continue
        if len(adj[seed]) < min_members - 1:
            continue

        # Try to grow a community from this seed
        candidates = {seed} | adj[seed]
        # Restrict to nodes that connect to most of the seed's neighbors
        community = {seed}
        for other in sorted(candidates - {seed}, key=lambda n: len(adj[n] & candidates), reverse=True):
            if other in visited:
                continue
            # Check if adding this node keeps density above threshold
            new_community = community | {other}
            internal_edges = sum(
                1 for a in new_community for b in new_community
                if a < b and b in adj[a]
            )
            n = len(new_community)
            max_edges = n * (n - 1) / 2
            density = internal_edges / max_edges if max_edges > 0 else 0

            if density >= min_density and n <= max_members:
                community.add(other)

        if len(community) >= min_members:
            communities.append(sorted(community))
            visited.update(community)

        if len(communities) >= max_communities:
            break

    return communities


def compute_community_density(member_ids: list[str],
                              adj: dict[str, set[str]]) -> float:
    """Compute internal edge density of a community."""
    n = len(member_ids)
    if n < 2:
        return 0.0
    internal = sum(
        1 for i, a in enumerate(member_ids)
        for b in member_ids[i + 1:]
        if b in adj.get(a, set())
    )
    max_edges = n * (n - 1) / 2
    return internal / max_edges if max_edges > 0 else 0.0


# ── Macro-node generation ──────────────────────────────

def compile_macro_node(conn: sqlite3.Connection,
                       member_ids: list[str],
                       title: Optional[str] = None) -> MacroNode:
    """Compile a set of notes into a Macro-Node.

    Generates: a summary title, a text summary, and `comprises::` edges.
    The underlying notes remain untouched.
    """
    # Get member info
    placeholders = ",".join(["?"] * len(member_ids))
    rows = conn.execute(
        f"SELECT note_id, title, body, note_type FROM notes WHERE note_id IN ({placeholders})",
        member_ids
    ).fetchall()

    member_map = {r[0]: r for r in rows}
    note_types = [r[3] for r in rows if r[3]]

    # Generate title from most common type + key members
    if not title:
        type_counts = defaultdict(int)
        for nt in note_types:
            type_counts[nt] += 1
        dominant_type = max(type_counts, key=type_counts.get) if type_counts else "concept"
        key_members = [member_map[mid][1] for mid in member_ids[:3] if mid in member_map]
        title = f"{dominant_type.title()} Cluster: {' | '.join(key_members)}"

    # Generate summary from member bodies
    summary_parts = []
    for mid in member_ids[:5]:
        if mid in member_map:
            body = member_map[mid][2] or ""
            first_line = body.strip().split("\n")[0][:200]
            if first_line:
                summary_parts.append(f"- {member_map[mid][1]}: {first_line}")
    summary = "\n".join(summary_parts) if summary_parts else "(empty cluster)"

    # Compute density
    edges = conn.execute(
        "SELECT source_note_id, target_note_id FROM edges WHERE resolved = 1"
    ).fetchall()
    adj: dict[str, set[str]] = defaultdict(set)
    for src, tgt in edges:
        if src and tgt:
            adj[src].add(tgt)
            adj[tgt].add(src)
    density = compute_community_density(member_ids, adj)

    # Count internal edges
    internal_edges = sum(
        1 for a in member_ids for b in member_ids
        if a < b and b in adj.get(a, set())
    )

    macro_id = f"macro-{hashlib.sha256('|'.join(sorted(member_ids)).encode()).hexdigest()[:12]}"

    import datetime
    return MacroNode(
        macro_id=macro_id,
        title=title,
        summary=summary,
        member_ids=member_ids,
        edge_count=internal_edges,
        internal_density=round(density, 3),
        created_at=datetime.datetime.now().isoformat(),
        content_hash=hashlib.sha256(summary.encode()).hexdigest()[:16],
    )


# ── Cache store ────────────────────────────────────────

CACHE_SCHEMA = """
CREATE TABLE IF NOT EXISTS macro_nodes (
    macro_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    summary TEXT,
    member_ids TEXT NOT NULL,
    edge_count INTEGER DEFAULT 0,
    internal_density REAL DEFAULT 0.0,
    variant TEXT DEFAULT 'generic',
    created_at TEXT DEFAULT (datetime('now')),
    content_hash TEXT
);

CREATE TABLE IF NOT EXISTS macro_comprises (
    macro_id TEXT NOT NULL,
    member_note_id TEXT NOT NULL,
    PRIMARY KEY (macro_id, member_note_id),
    FOREIGN KEY (macro_id) REFERENCES macro_nodes(macro_id)
);
"""


class MacroCache:
    """Structural cache of compiled Macro-Nodes.

    Stored in a separate SQLite DB or alongside the shard DB.
    Completely read-only in terms of source notes.
    """

    def __init__(self, db_path: str = ".vaultlens/macro_cache.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.executescript(CACHE_SCHEMA)
        self.conn.commit()

    def store(self, macro: MacroNode) -> None:
        """Store a compiled Macro-Node."""
        self.conn.execute(
            """INSERT OR REPLACE INTO macro_nodes
               (macro_id, title, summary, member_ids, edge_count,
                internal_density, variant, content_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (macro.macro_id, macro.title, macro.summary,
             json.dumps(macro.member_ids), macro.edge_count,
             macro.internal_density, macro.variant, macro.content_hash)
        )
        # Store comprises edges
        for mid in macro.member_ids:
            self.conn.execute(
                "INSERT OR REPLACE INTO macro_comprises (macro_id, member_note_id) VALUES (?, ?)",
                (macro.macro_id, mid)
            )
        self.conn.commit()

    def lookup_by_members(self, member_ids: list[str]) -> Optional[MacroNode]:
        """Find existing macro-node by its member set."""
        # Quick check: any macro that contains ALL these members
        for mid in member_ids:
            rows = self.conn.execute(
                "SELECT macro_id FROM macro_comprises WHERE member_note_id = ?", (mid,)
            ).fetchall()
            for (macro_id,) in rows:
                row = self.conn.execute(
                    "SELECT * FROM macro_nodes WHERE macro_id = ?", (macro_id,)
                ).fetchone()
                if row:
                    stored_members = set(json.loads(row[3]))
                    if stored_members == set(member_ids):
                        return MacroNode(
                            macro_id=row[0], title=row[1], summary=row[2],
                            member_ids=json.loads(row[3]), edge_count=row[4],
                            internal_density=row[5], variant=row[6],
                            created_at=row[7], content_hash=row[8],
                        )
        return None

    def get_all(self) -> list[MacroNode]:
        """List all cached macro-nodes."""
        rows = self.conn.execute(
            "SELECT * FROM macro_nodes ORDER BY internal_density DESC"
        ).fetchall()
        return [
            MacroNode(
                macro_id=r[0], title=r[1], summary=r[2],
                member_ids=json.loads(r[3]), edge_count=r[4],
                internal_density=r[5], variant=r[6],
                created_at=r[7], content_hash=r[8],
            )
            for r in rows
        ]

    def get_members(self, macro_id: str) -> list[str]:
        """Get member note IDs for a macro-node."""
        rows = self.conn.execute(
            "SELECT member_note_id FROM macro_comprises WHERE macro_id = ?",
            (macro_id,)
        ).fetchall()
        return [r[0] for r in rows]

    def stats(self) -> dict:
        n = self.conn.execute("SELECT COUNT(*) FROM macro_nodes").fetchone()[0]
        total_members = self.conn.execute(
            "SELECT COUNT(*) FROM macro_comprises"
        ).fetchone()[0]
        return {"macro_nodes": n, "total_members": total_members}

    def close(self):
        self.conn.commit()
        self.conn.close()


# ── Full build pipeline ────────────────────────────────

def build_macro_cache(vault_db_path: str, cache_db_path: str,
                      min_members: int = 3, min_density: float = 0.4,
                      verbose: bool = False) -> dict:
    """Build macro-node cache from a vault database.

    Args:
        vault_db_path: Path to vault SQLite DB
        cache_db_path: Path to macro cache SQLite DB
        min_members: Minimum nodes per community
        min_density: Minimum internal edge density
        verbose: Print progress

    Returns:
        Stats dict
    """
    conn = sqlite3.connect(vault_db_path)
    cache = MacroCache(cache_db_path)

    communities = detect_dense_subgraphs(
        conn, min_members=min_members, min_density=min_density
    )

    if verbose:
        print(f"Detected {len(communities)} dense subgraphs")

    compiled = 0
    for member_ids in communities:
        existing = cache.lookup_by_members(member_ids)
        if existing:
            continue

        macro = compile_macro_node(conn, member_ids)
        cache.store(macro)
        compiled += 1

        if verbose:
            print(f"  {macro.macro_id}: {macro.title} "
                  f"({len(macro.member_ids)} members, density={macro.internal_density:.3f})")

    conn.close()
    cache_stats = cache.stats()
    cache.close()

    return {
        "communities_detected": len(communities),
        "macros_compiled": compiled,
        "total_macros": cache_stats["macro_nodes"],
        "total_comprises_edges": cache_stats["total_members"],
    }
