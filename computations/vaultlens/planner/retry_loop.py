"""Agentic Retry Loop: self-correcting plan execution.

When a TraversalPlan fails (zero nodes, wrong variants), the system
feeds the failure back to the LLM to revise the plan.
"""

from typing import Optional

from .directives import TraversalPlan, ExecutionResult, SeedDirective, ExpansionDirective
from .llm_compiler import LLMCompiler
from .executor import PlanExecutor


def _heuristic_plan(query: str) -> TraversalPlan:
    """Generate a TraversalPlan using keyword heuristics (no LLM)."""
    from ..query_router import detect_variants, analyze_query
    analysis = analyze_query(query, verbose=False)
    detected = analysis["variants"]
    key_terms = analysis["key_terms"]

    seeds = [
        SeedDirective(method="bm25",
                      query=" ".join(key_terms[:5]) if key_terms else query,
                      limit=8)
    ]
    expansions = []
    for variant in detected[:3]:
        expansions.append(ExpansionDirective(
            direction="both", variants=[variant], max_hops=2, max_nodes=20
        ))
    return TraversalPlan(
        intent_summary=f"Heuristic: variants={detected}",
        seeds=seeds,
        expansions=expansions,
    )


def run_agentic_query(
    query: str,
    compiler: LLMCompiler,
    executor: PlanExecutor,
    max_retries: int = 2,
    min_nodes: int = 2,
) -> dict:
    """Run an agentic query with automatic plan revision on failure.

    Returns dict with: success, attempts, final_result, plan_history,
    failure_reasons, used_llm, mode
    """
    plan_history = []
    failure_reasons = []
    used_llm = False
    mode = "heuristic"

    # Try LLM-based planning
    if compiler.available:
        used_llm = True
        mode = "agentic"
        current_plan = compiler.compile(query)

        if current_plan is None:
            mode = "heuristic"
            current_plan = _heuristic_plan(query)
    else:
        current_plan = _heuristic_plan(query)

    exec_result = None

    # Agentic loop
    for attempt in range(max_retries + 1):
        exec_result = executor.execute(current_plan)

        history_entry = {
            "attempt": attempt,
            "plan": current_plan.to_dict(),
            "nodes_found": exec_result.node_count,
            "edges_found": exec_result.edge_count,
            "success": exec_result.success and exec_result.node_count >= min_nodes,
            "source": "llm" if (used_llm and attempt == 0) else ("llm-revision" if used_llm else "heuristic"),
        }
        plan_history.append(history_entry)

        # Success
        if exec_result.success and exec_result.node_count >= min_nodes:
            return {
                "query": query,
                "success": True,
                "attempts": attempt + 1,
                "final_result": exec_result,
                "plan_history": plan_history,
                "failure_reasons": failure_reasons,
                "used_llm": used_llm,
                "mode": mode,
            }

        # Failure — record and try revision
        reason = (exec_result.reason if not exec_result.success
                  else f"Only {exec_result.node_count} nodes found (min {min_nodes})")
        failure_reasons.append(reason)

        if attempt < max_retries and compiler.available:
            revised = compiler.revise(
                query=query,
                previous_plan=current_plan,
                reason=reason,
                node_count=exec_result.node_count,
            )
            if revised is not None:
                current_plan = revised
                continue
        break

    # Exhausted retries — best effort
    return {
        "query": query,
        "success": False,
        "attempts": max_retries + 1,
        "final_result": exec_result,
        "plan_history": plan_history,
        "failure_reasons": failure_reasons,
        "used_llm": used_llm,
        "mode": mode,
    }


def run_heuristic_query(query: str, executor: PlanExecutor) -> dict:
    """Run a query using heuristic planner only (no LLM)."""
    plan = _heuristic_plan(query)
    exec_result = executor.execute(plan)
    return {
        "query": query,
        "success": exec_result.success and exec_result.node_count >= 1,
        "attempts": 1,
        "final_result": exec_result,
        "plan_history": [{
            "attempt": 0,
            "plan": plan.to_dict(),
            "nodes_found": exec_result.node_count,
            "edges_found": exec_result.edge_count,
            "success": exec_result.success,
            "source": "heuristic",
        }],
        "failure_reasons": [],
        "used_llm": False,
        "mode": "heuristic",
    }


def format_agent_explanation(result: dict) -> str:
    """Format an agentic query result as a human-readable explanation."""
    lines = []
    lines.append("=" * 60)
    lines.append(f"AGENTIC PLANNER — {result['mode'].upper()} MODE")
    lines.append("=" * 60)
    lines.append(f"Query: {result['query']}")
    lines.append(f"Used LLM: {result['used_llm']}")
    lines.append(f"Attempts: {result['attempts']}")
    lines.append(f"Success: {result['success']}")
    lines.append("")

    for entry in result["plan_history"]:
        a = entry["attempt"]
        plan = entry["plan"]
        nodes = entry["nodes_found"]
        ok = entry["success"]
        src = entry["source"]
        status = "SUCCESS" if ok else "FAILED"
        lines.append(f"--- Attempt {a + 1} ({src}) — {status} ---")
        lines.append(f"  Intent: {plan.get('intent_summary', 'N/A')}")
        if plan.get("seeds"):
            seeds_str = ", ".join(
                f"{s['method']}({s['query'][:30]})" for s in plan["seeds"][:3]
            )
            lines.append(f"  Seeds: {seeds_str}")
        for e in plan.get("expansions", [])[:3]:
            lines.append(f"  Expansion: {e['direction']} {e.get('variants',[])} "
                        f"({e.get('max_hops','?')} hops, max {e.get('max_nodes','?')} nodes)")
        lines.append(f"  Nodes found: {nodes}")
        lines.append("")

    if result.get("final_result") and result["final_result"].nodes:
        lines.append("--- Retrieved Nodes ---")
        for n in result["final_result"].nodes[:10]:
            lines.append(f"  - {n.get('title', n.get('note_id', '?'))} "
                        f"(dist={n.get('graph_distance', '?')})")
        lines.append("")

    if result.get("failure_reasons"):
        lines.append("--- Failure Reasons ---")
        for r in result["failure_reasons"]:
            lines.append(f"  - {r}")
        lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)
