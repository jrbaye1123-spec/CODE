"""Graph store: loads edges from SQLite and provides graph traversal.

Uses adjacency lists (no NetworkX dependency) for efficient traversal.
"""

import sqlite3
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Edge:
    """A typed edge between two notes."""
    edge_id: int
    source_note_id: str
    target_note_id: str
    relation: str
    variant: str
    text_span: str = ""
    confidence: float = 1.0
    resolved: bool = True


@dataclass
class GraphStats:
    """Statistics about the graph."""
    total_notes: int = 0
    total_edges: int = 0
    variant_counts: dict[str, int] = field(default_factory=dict)
    unresolved_links: int = 0
    top_connected: list[tuple[str, str, int]] = field(default_factory=list)
    index_size_bytes: int = 0


class GraphStore:
    """In-memory graph representation backed by SQLite edges table.

    Provides variant-filtered traversal, expansion, and statistics.
    """

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        # Adjacency: source_note_id -> list of outgoing Edge objects
        self._outgoing: dict[str, list[Edge]] = defaultdict(list)
        # Reverse adjacency: target_note_id -> list of incoming Edge objects
        self._incoming: dict[str, list[Edge]] = defaultdict(list)
        self._loaded = False

    def load(self) -> None:
        """Load all edges from the database into memory."""
        if self._loaded:
            return
        cursor = self.conn.execute("""
            SELECT edge_id, source_note_id, target_note_id, relation, variant, text_span, confidence, resolved
            FROM edges
        """)
        for row in cursor:
            edge_id, src, tgt, rel, var, span, conf, res = row
            edge = Edge(
                edge_id=edge_id,
                source_note_id=src,
                target_note_id=tgt or "",
                relation=rel,
                variant=var,
                text_span=span or "",
                confidence=conf or 1.0,
                resolved=bool(res),
            )
            self._outgoing[src].append(edge)
            if tgt:
                self._incoming[tgt].append(edge)
        self._loaded = True

    def get_outgoing(self, note_id: str, variants: Optional[set[str]] = None) -> list[Edge]:
        """Get outgoing edges from a note, optionally filtered by variant."""
        edges = self._outgoing.get(note_id, [])
        if variants:
            edges = [e for e in edges if e.variant in variants and e.resolved]
        return edges

    def get_incoming(self, note_id: str, variants: Optional[set[str]] = None) -> list[Edge]:
        """Get incoming edges to a note, optionally filtered by variant."""
        edges = self._incoming.get(note_id, [])
        if variants:
            edges = [e for e in edges if e.variant in variants and e.resolved]
        return edges

    def get_neighbors(self, note_id: str, variants: Optional[set[str]] = None) -> list[Edge]:
        """Get all edges (both directions) for a note."""
        outgoing = self.get_outgoing(note_id, variants)
        incoming = self.get_incoming(note_id, variants)
        return outgoing + incoming

    def expand(
        self,
        seeds: list[str],
        variants: Optional[set[str]] = None,
        max_hops: int = 2,
        max_nodes: int = 50,
        edge_weight_by_variant: bool = True,
    ) -> tuple[dict[str, int], list[list[Edge]]]:
        """BFS expansion from seed notes through selected variants.

        Args:
            seeds: List of seed note IDs
            variants: Set of variant names to traverse (all if None)
            max_hops: Maximum traversal depth
            max_nodes: Maximum total nodes to visit
            edge_weight_by_variant: Unused in MVP, placeholder

        Returns:
            (visited: dict mapping note_id -> min_distance,
             paths: list of paths, each path is list of Edges from a seed)
        """
        visited: dict[str, int] = {}
        paths: list[list[Edge]] = []
        queue: deque[tuple[str, int, list[Edge]]] = deque()

        for seed in seeds:
            queue.append((seed, 0, []))
            visited[seed] = 0

        while queue and len(visited) < max_nodes:
            current, dist, current_path = queue.popleft()

            if dist >= max_hops:
                continue

            for edge in self.get_neighbors(current, variants):
                # Determine neighbor (could be source or target)
                neighbor = edge.target_note_id if edge.source_note_id == current else edge.source_note_id
                if not neighbor:
                    continue

                if neighbor in visited and visited[neighbor] <= dist + 1:
                    continue

                new_path = current_path + [edge]
                visited[neighbor] = dist + 1
                queue.append((neighbor, dist + 1, new_path))
                if len(new_path) > 1:
                    paths.append(new_path)

        return visited, paths

    def get_stats(self) -> GraphStats:
        """Compute graph statistics."""
        stats = GraphStats()

        # Count notes
        cursor = self.conn.execute("SELECT COUNT(*) FROM notes")
        stats.total_notes = cursor.fetchone()[0]

        # Count edges by variant
        cursor = self.conn.execute("SELECT variant, COUNT(*) FROM edges GROUP BY variant")
        for row in cursor:
            stats.variant_counts[row[0]] = row[1]
            stats.total_edges += row[1]

        # Count unresolved
        cursor = self.conn.execute("SELECT COUNT(*) FROM edges WHERE resolved = 0")
        stats.unresolved_links = cursor.fetchone()[0]

        # Top connected notes
        cursor = self.conn.execute("""
            SELECT n.title, n.note_id, COUNT(e.edge_id) as edge_count
            FROM notes n
            LEFT JOIN edges e ON n.note_id = e.source_note_id OR n.note_id = e.target_note_id
            GROUP BY n.note_id
            ORDER BY edge_count DESC
            LIMIT 10
        """)
        stats.top_connected = [(row[0], row[1], row[2]) for row in cursor]

        return stats
