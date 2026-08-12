"""Session-aware conversational loop — ties v0.3 planner + v0.4 session memory.

The core loop:
    User Query → Anaphora Resolver → [Fast Path | LLM Planner] → Executor
    → Session Merge → Focus Update → Context Serialize → User Sees Result

Session end → Consolidation → HMAC proposals
"""

import sqlite3
import time
from typing import Optional

from .memory import SessionContext, ResolvedQuery
from .anaphora import AnaphoraResolver
from .consolidation import SessionConsolidator, ConsolidationReport


class SessionLoop:
    """Stateful conversational query loop with session memory.

    Maintains a SessionContext across queries within a session.
    Routes follow-ups to fast paths, new queries to the v0.3 planner.
    Consolidates on session end.
    """

    def __init__(self, vault_db_path: str, compiler=None, executor=None):
        self.vault_db_path = vault_db_path
        self.compiler = compiler       # LLMCompiler from v0.3 planner
        self.executor = executor       # PlanExecutor from v0.3 planner
        self.session: Optional[SessionContext] = None
        self.consolidator = SessionConsolidator(vault_db_path)
        self._conn: Optional[sqlite3.Connection] = None

    # ── Session lifecycle ──────────────────────────────

    def start(self, session_id: Optional[str] = None) -> SessionContext:
        """Start a new conversation session."""
        self.session = SessionContext.create(session_id)
        self._conn = sqlite3.connect(self.vault_db_path)
        self._conn.row_factory = sqlite3.Row
        return self.session

    def end(self, consolidate: bool = True) -> Optional[ConsolidationReport]:
        """End the session. Runs consolidation if requested."""
        if not self.session:
            return None

        report = None
        if consolidate:
            report = self.consolidator.consolidate(self.session)

        if self._conn:
            self._conn.close()
            self._conn = None

        self.session = None
        return report

    @property
    def active(self) -> bool:
        return self.session is not None

    # ── Query handling ─────────────────────────────────

    def query(self, raw_query: str, verbose: bool = False) -> dict:
        """Process a query within the active session.

        Flow:
        1. Resolve anaphora (pronouns, follow-up intent)
        2. Fast path for pure follow-ups (skip LLM)
        3. Full agentic path for new queries
        4. Merge results into session memory
        5. Update focus for next query

        Returns dict with: result (ExecutionResult), resolved (ResolvedQuery),
                          session_snapshot (dict), context_string (str)
        """
        if not self.session or not self._conn:
            raise RuntimeError("No active session. Call start() first.")

        resolver = AnaphoraResolver(self.session)
        resolved = resolver.resolve(raw_query)

        t0 = time.time()

        # ── Fast path: pure follow-up, skip LLM ────────
        if resolved.skip_llm and resolved.focus_nodes:
            result = self._execute_fast_path(resolved)
        else:
            result = self._execute_full_path(raw_query, resolved)

        elapsed = time.time() - t0

        # ── Merge into session ─────────────────────────
        if result and result.get("success", True):
            nodes = result.get("retrieved_notes", result.get("nodes", []))
            edges = result.get("edges", [])

            self.session.merge_result(
                {"retrieved_notes": nodes, "edges": edges},
                query=raw_query,
                variants=resolved.variants,
            )

            # Update focus
            if nodes:
                focus_ids = [n.get("note_id", n.get("note_id", "")) for n in nodes[:5]]
                self.session.set_focus(focus_ids, resolved.variants, resolved.intent)

        return {
            "result": result,
            "resolved": resolved,
            "session_snapshot": self.session.snapshot(),
            "context_string": self.session.to_context_string(),
            "elapsed_ms": round(elapsed * 1000, 1),
        }

    # ── Internal execution paths ───────────────────────

    def _execute_fast_path(self, resolved: ResolvedQuery) -> dict:
        """Execute a fast-path follow-up: direct graph expansion from focus nodes.

        No LLM call. Sub-millisecond for typical queries.
        """
        from ..planner.directives import TraversalPlan, SeedDirective, ExpansionDirective

        # Build seeds from focus nodes (exact title matches)
        seeds = []
        for nid in resolved.focus_nodes:
            note = self._get_note(nid)
            if note:
                seeds.append(SeedDirective(
                    method="exact_title",
                    query=note["title"],
                    limit=1,
                ))

        if not seeds:
            return {"success": False, "reason": "No focus nodes available", "nodes": [], "edges": []}

        # Build expansions from resolved variants
        expansions = [
            ExpansionDirective(
                direction="both",
                variants=resolved.variants,
                max_hops=2,
                max_nodes=20,
            )
        ]

        plan = TraversalPlan(
            intent_summary=f"Fast-path: {resolved.intent}",
            seeds=seeds,
            expansions=expansions,
        )

        exec_result = self.executor.execute(plan) if self.executor else None
        if exec_result:
            return {
                "success": exec_result.success,
                "retrieved_notes": exec_result.nodes,
                "edges": exec_result.edges,
                "nodes": exec_result.nodes,
                "seed_count": exec_result.seed_count,
                "mode": "fast-path",
            }
        return {"success": False, "reason": "No executor", "nodes": [], "edges": []}

    def _execute_full_path(self, raw_query: str, resolved: ResolvedQuery) -> dict:
        """Execute full path: LLM planner or heuristic + executor."""
        if not self.executor:
            return {"success": False, "reason": "No executor", "nodes": [], "edges": []}

        # Enrich query with focus context for follow-ups
        enriched_query = raw_query
        if resolved.is_followup and resolved.focus_nodes:
            focus_titles = []
            for nid in resolved.focus_nodes[:3]:
                note = self._get_note(nid)
                if note:
                    focus_titles.append(note["title"])
            if focus_titles:
                enriched_query = f"{raw_query} (context: {', '.join(focus_titles)})"

        # Try LLM compiler if available
        if self.compiler and self.compiler.available:
            from ..planner.retry_loop import run_agentic_query
            agentic_result = run_agentic_query(
                query=enriched_query, compiler=self.compiler,
                executor=self.executor, max_retries=1, min_nodes=2,
            )
            if agentic_result["success"] and agentic_result["final_result"]:
                er = agentic_result["final_result"]
                return {
                    "success": True, "retrieved_notes": er.nodes, "edges": er.edges,
                    "nodes": er.nodes, "seed_count": er.seed_count,
                    "plan_history": agentic_result.get("plan_history", []),
                    "mode": agentic_result.get("mode", "agentic"),
                }

        # Heuristic fallback
        from ..planner.retry_loop import _heuristic_plan as make_plan
        plan = make_plan(enriched_query)
        er = self.executor.execute(plan)
        return {
            "success": er.success, "retrieved_notes": er.nodes, "edges": er.edges,
            "nodes": er.nodes, "seed_count": er.seed_count, "mode": "heuristic",
        }

    def _get_note(self, note_id: str) -> Optional[dict]:
        """Get a note from the vault DB."""
        if not self._conn:
            return None
        import json
        cursor = self._conn.execute(
            "SELECT note_id, title, body, note_type, tags FROM notes WHERE note_id = ?",
            (note_id,)
        )
        row = cursor.fetchone()
        if row:
            return {
                "note_id": row[0], "title": row[1], "body": row[2],
                "note_type": row[3], "tags": json.loads(row[4] or "[]"),
            }
        return None
