"""Deterministic Plan Executor: runs TraversalPlans against the graph store.

Three-phase execution:
1. Seeding: BM25 or exact_title to find starting nodes
2. Expansion: variant-filtered BFS through typed graph edges
3. Filtering: post-traversal confidence/status/tag/type filters

The executor NEVER invents facts. It only traverses existing graph edges.
"""

import sqlite3
from typing import Optional

from .directives import TraversalPlan, ExecutionResult, ExpansionDirective
from ..graph_store import GraphStore
from ..parser import _generate_note_id


class PlanExecutor:
    """Executes TraversalPlans against the sovereign graph."""

    def __init__(self, conn: sqlite3.Connection, graph: GraphStore):
        self.conn = conn
        self.graph = graph
        graph.load()

    def execute(self, plan: TraversalPlan) -> ExecutionResult:
        """Execute a TraversalPlan and return results.

        Phase 1: Seeding — find starting nodes via BM25 or exact title.
        Phase 2: Expansion — traverse graph edges per expansion directives.
        Phase 3: Filtering — apply post-traversal filters.
        """
        # Phase 1: Seeding
        seed_ids: set[str] = set()
        seed_details: list[dict] = []

        for seed_directive in plan.seeds:
            if seed_directive.method == "bm25":
                from ..retriever import bm25_search
                hits = bm25_search(self.conn, seed_directive.query, limit=seed_directive.limit)
                for h in hits:
                    seed_ids.add(h["note_id"])
                    seed_details.append(h)

            elif seed_directive.method == "exact_title":
                nid = _generate_note_id(seed_directive.query)
                from ..retriever import get_note_by_id
                note = get_note_by_id(self.conn, nid)
                if note:
                    seed_ids.add(nid)
                    seed_details.append({"note_id": nid, "title": note["title"], "bm25_score": 1.0})
                # Also try alias match
                cursor = self.conn.execute(
                    "SELECT note_id FROM notes WHERE title = ?", (seed_directive.query,)
                )
                for row in cursor:
                    seed_ids.add(row[0])

            elif seed_directive.method == "alias":
                # Search aliases field
                cursor = self.conn.execute(
                    "SELECT note_id FROM notes WHERE aliases LIKE ?",
                    (f"%{seed_directive.query}%",)
                )
                for row in cursor:
                    seed_ids.add(row[0])

        if not seed_ids:
            return ExecutionResult(
                success=False,
                reason="No seed nodes found. Try broader BM25 terms or exact titles.",
                plan_used=plan,
            )

        # Phase 2: Expansion
        all_visited: dict[str, int] = {}
        for sid in seed_ids:
            all_visited[sid] = 0

        all_edges: list[dict] = []

        for exp in plan.expansions:
            variant_set = set(exp.variants) if exp.variants else None
            relation_set = set(exp.relations) if exp.relations else None
            max_total = exp.max_nodes

            for seed in list(seed_ids):
                frontier = {seed}
                visited_local = {seed: 0}

                for hop in range(exp.max_hops):
                    next_frontier = set()

                    for node_id in frontier:
                        edges = []
                        if exp.direction in ("outgoing", "both"):
                            edges.extend(self.graph.get_outgoing(node_id, variant_set))
                        if exp.direction in ("incoming", "both"):
                            edges.extend(self.graph.get_incoming(node_id, variant_set))

                        for edge in edges:
                            neighbor = (edge.target_note_id
                                        if edge.source_note_id == node_id
                                        else edge.source_note_id)
                            if not neighbor:
                                continue
                            if relation_set and edge.relation not in relation_set:
                                continue
                            if neighbor in visited_local:
                                continue
                            if len(all_visited) >= max_total:
                                break

                            visited_local[neighbor] = hop + 1
                            next_frontier.add(neighbor)

                            if neighbor not in all_visited:
                                all_visited[neighbor] = hop + 1

                            all_edges.append({
                                "source": edge.source_note_id,
                                "target": edge.target_note_id,
                                "relation": edge.relation,
                                "variant": edge.variant,
                                "confidence": edge.confidence,
                            })

                    frontier = next_frontier
                    if not frontier or len(all_visited) >= max_total:
                        break

        # Phase 3: Filtering
        from ..retriever import get_note_by_id

        nodes = []
        for nid, dist in all_visited.items():
            note = get_note_by_id(self.conn, nid)
            if not note:
                continue

            # Apply filters
            skip = False
            for f in plan.filters:
                if f.type == "exclude_status" and note.get("note_type") == f.value:
                    skip = True
                elif f.type == "require_type" and note.get("note_type") != f.value:
                    skip = True
                elif f.type == "require_tag" and isinstance(f.value, str):
                    tags = note.get("tags", [])
                    if f.value not in tags:
                        skip = True
                elif f.type == "min_confidence":
                    # Check if all incoming edges meet min confidence
                    note_edges = [e for e in all_edges
                                  if e["target"] == nid or e["source"] == nid]
                    if note_edges:
                        min_conf = min(e.get("confidence", 1.0) for e in note_edges)
                        if min_conf < float(f.value):
                            skip = True

            if skip:
                continue

            note["graph_distance"] = dist
            note["final_score"] = 1.0 / (1.0 + dist)
            nodes.append(note)

        nodes.sort(key=lambda n: n["final_score"], reverse=True)

        return ExecutionResult(
            success=True,
            reason=f"Found {len(nodes)} nodes, {len(all_edges)} edges",
            nodes=nodes,
            edges=all_edges,
            seed_count=len(seed_ids),
            plan_used=plan,
        )
