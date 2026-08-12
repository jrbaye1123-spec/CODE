"""NL2Graph: Natural Language to Graph Traversal Plans.

Replaces brittle keyword-based variant routing with LLM-generated traversal
directives. The local Llama-3.2-3B compiles natural language queries into
structured graph traversal plans that the engine executes deterministically.

Architecture:
    Query → LLM → TraversalPlan → Graph Engine → Results

This fixes the Gate 1 bottleneck: variant routing accuracy was 0.50 on
paraphrase queries because keywords can't capture semantic intent. An LLM
can understand "Why did purchasing activity weaken?" → causal traversal
from Demand Drop outward to find causes.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Optional


# ── Traversal plan schema ──────────────────────────────

@dataclass
class TraversalStep:
    """A single step in a graph traversal plan."""
    direction: str = "outgoing"    # 'outgoing', 'incoming', 'both'
    relations: list[str] = field(default_factory=list)  # ['causes', 'enables', ...]
    variants: list[str] = field(default_factory=list)    # ['causal', 'evidential', ...]
    node_filter: str = ""          # Optional: 'type:evidence', 'tag:source', etc.
    max_hops: int = 1

    def to_dict(self) -> dict:
        return {
            "direction": self.direction,
            "relations": self.relations,
            "variants": self.variants,
            "node_filter": self.node_filter,
            "max_hops": self.max_hops,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TraversalStep":
        return cls(
            direction=d.get("direction", "outgoing"),
            relations=d.get("relations", []),
            variants=d.get("variants", []),
            node_filter=d.get("node_filter", ""),
            max_hops=d.get("max_hops", 1),
        )


@dataclass
class TraversalPlan:
    """A complete graph traversal plan generated from a natural language query.

    Contains: seed strategy, ordered traversal steps, and result shaping.
    """
    query: str
    seed_strategy: str = "bm25"     # 'bm25', 'exact_title', 'alias_match', 'vector'
    seed_terms: list[str] = field(default_factory=list)  # terms for BM25
    seed_titles: list[str] = field(default_factory=list)  # exact title matches
    steps: list[TraversalStep] = field(default_factory=list)
    max_total_nodes: int = 25
    include_seed_bodies: bool = True
    explanation: str = ""           # LLM's reasoning for this plan

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "seed_strategy": self.seed_strategy,
            "seed_terms": self.seed_terms,
            "seed_titles": self.seed_titles,
            "steps": [s.to_dict() for s in self.steps],
            "max_total_nodes": self.max_total_nodes,
            "include_seed_bodies": self.include_seed_bodies,
            "explanation": self.explanation,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TraversalPlan":
        return cls(
            query=d.get("query", ""),
            seed_strategy=d.get("seed_strategy", "bm25"),
            seed_terms=d.get("seed_terms", []),
            seed_titles=d.get("seed_titles", []),
            steps=[TraversalStep.from_dict(s) for s in d.get("steps", [])],
            max_total_nodes=d.get("max_total_nodes", 25),
            include_seed_bodies=d.get("include_seed_bodies", True),
            explanation=d.get("explanation", ""),
        )


# ── Prompt template for NL2Graph ────────────────────────

NL2GRAPH_PROMPT = """You are a graph query compiler for VaultLens, a knowledge graph system with 7 typed relationship variants.

Given a natural language query, produce a structured graph traversal plan as JSON.

Graph Variants and their relations:
- causal: causes, enables, prevents
- evidential: supports, refutes, qualifies
- temporal: precedes, follows, contemporaneous-with
- hierarchical: is-a, part-of, depends-on
- semantic: similar-to, analogous-to, contrasts-with
- provenance: derived-from, cited-by, contradicts-source
- procedural: input-to, output-of, step-before

For seed discovery:
- seed_strategy: "bm25" (default) or "exact_title" for named entities
- seed_terms: key terms for BM25 search
- seed_titles: exact note titles if you know them

For each traversal step, specify:
- direction: "outgoing" (follow edges FROM seed), "incoming" (follow edges TO seed), or "both"
- relations: specific relation names to traverse (e.g., ["causes", "enables"])
- variants: variant names to traverse (e.g., ["causal", "evidential"])
- max_hops: how many hops to expand (1-3)

Examples:

Query: "What causes demand drop?"
Plan:
{{"seed_strategy": "bm25", "seed_terms": ["demand drop"], "steps": [{{"direction": "incoming", "variants": ["causal"], "max_hops": 1}}], "max_total_nodes": 15, "explanation": "Find nodes that have causal edges pointing TO Demand Drop"}}

Query: "What evidence supports rate hikes and where did that evidence come from?"
Plan:
{{"seed_strategy": "bm25", "seed_terms": ["rate hikes"], "steps": [{{"direction": "incoming", "variants": ["evidential"], "max_hops": 1}}, {{"direction": "incoming", "variants": ["provenance"], "max_hops": 1}}], "max_total_nodes": 20, "explanation": "First find evidence nodes supporting rate hikes, then trace provenance of that evidence"}}

Now compile a plan for this query. Return ONLY the JSON object, no other text.

Query: {query}

Plan:"""


# ── Heuristic fallback (no LLM) ────────────────────────

def heuristic_plan(query: str) -> TraversalPlan:
    """Generate a traversal plan using keyword heuristics when LLM is unavailable.

    This is the current variant router logic, formalized as a TraversalPlan.
    """
    from ..query_router import detect_variants, analyze_query
    analysis = analyze_query(query, verbose=False)
    detected = analysis["variants"]
    key_terms = analysis["key_terms"]

    # Build steps from detected variants
    steps = []
    for variant in detected[:3]:
        steps.append(TraversalStep(
            direction="both",
            variants=[variant],
            max_hops=2,
        ))

    return TraversalPlan(
        query=query,
        seed_strategy="bm25",
        seed_terms=key_terms[:5] if key_terms else [query],
        steps=steps,
        max_total_nodes=25,
        explanation=f"Heuristic plan: variants={detected}, terms={key_terms[:5]}",
    )


# ── LLM-based plan generation ──────────────────────────

def llm_plan(query: str, model_path: str = "",
             llama_cli: str = "") -> Optional[TraversalPlan]:
    """Generate a traversal plan using the local LLM.

    Falls back to heuristic if LLM is unavailable or fails.
    """
    import subprocess
    import os

    if not model_path:
        model_path = os.path.expanduser("~/models/Llama-3.2-3B-Instruct-Q4_K_M.gguf")
    if not llama_cli:
        llama_cli = os.path.expanduser("~/llama.cpp/build/bin/llama-cli")

    if not os.path.exists(model_path) or not os.path.exists(llama_cli):
        return None

    prompt = NL2GRAPH_PROMPT.format(query=query)

    try:
        result = subprocess.run(
            [
                llama_cli,
                "-m", model_path,
                "-c", "4096",
                "-t", "8",
                "-ctk", "q8_0", "-ctv", "q8_0",
                "--temp", "0.0",
                "-n", "512",
                "--no-display-prompt",
                "-p", prompt,
            ],
            capture_output=True, text=True, timeout=60,
            env={**os.environ, "OMP_NUM_THREADS": "8"},
        )

        if result.returncode != 0:
            return None

        raw = result.stdout.strip()
        plan_dict = _parse_json_plan(raw)

        if plan_dict:
            plan = TraversalPlan.from_dict(plan_dict)
            plan.query = query
            return plan

    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return None


def _parse_json_plan(raw: str) -> Optional[dict]:
    """Parse a JSON plan from LLM output. Handles common formatting quirks."""
    # Direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Markdown code block
    m = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # Find outermost braces
    m = re.search(r'\{.*\}', raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    return None


# ── Plan generation (with fallback) ────────────────────

def generate_plan(query: str, use_llm: bool = True,
                  model_path: str = "", llama_cli: str = "") -> TraversalPlan:
    """Generate a traversal plan, preferring LLM with heuristic fallback.

    Args:
        query: Natural language query
        use_llm: Whether to try LLM-based planning
        model_path: Path to GGUF model
        llama_cli: Path to llama-cli binary

    Returns:
        TraversalPlan (never None — falls back to heuristic)
    """
    if use_llm:
        plan = llm_plan(query, model_path, llama_cli)
        if plan is not None:
            return plan

    return heuristic_plan(query)


# ── Plan executor ──────────────────────────────────────

def execute_plan(plan: TraversalPlan, conn, graph) -> list[dict]:
    """Execute a TraversalPlan against the graph and return ranked results.

    Args:
        plan: TraversalPlan to execute
        conn: SQLite connection
        graph: GraphStore instance

    Returns:
        List of note dicts with scores and traversal metadata
    """
    from ..retriever import bm25_search, get_note_by_id

    graph.load()

    # Stage 1: Find seeds
    seeds = []
    if plan.seed_strategy == "bm25" and plan.seed_terms:
        query_str = " ".join(plan.seed_terms)
        bm25_results = bm25_search(conn, query_str, limit=15)
        seeds = [r["note_id"] for r in bm25_results]

    if plan.seed_titles:
        from ..parser import _generate_note_id
        for title in plan.seed_titles:
            nid = _generate_note_id(title)
            if nid not in seeds:
                seeds.insert(0, nid)  # exact matches first

    if not seeds:
        return []

    # Stage 2: Execute traversal steps
    all_visited: dict[str, int] = {}
    all_paths = []

    for step in plan.steps:
        variant_set = set(step.variants) if step.variants else None
        relation_set = set(step.relations) if step.relations else None

        for seed in seeds:
            frontier = [seed]
            visited_local: dict[str, int] = {seed: 0}

            for hop in range(step.max_hops):
                next_frontier = []
                for node_id in frontier:
                    edges = []
                    if step.direction in ("outgoing", "both"):
                        edges.extend(graph.get_outgoing(node_id, variant_set))
                    if step.direction in ("incoming", "both"):
                        edges.extend(graph.get_incoming(node_id, variant_set))

                    for edge in edges:
                        # Determine neighbor
                        neighbor = (edge.target_note_id if edge.source_note_id == node_id
                                    else edge.source_note_id)
                        if not neighbor:
                            continue

                        # Relation filter
                        if relation_set and edge.relation not in relation_set:
                            continue

                        if neighbor not in visited_local:
                            visited_local[neighbor] = hop + 1
                            next_frontier.append(neighbor)

                            # Record globally
                            if neighbor not in all_visited:
                                all_visited[neighbor] = hop + 1

                frontier = next_frontier
                if not frontier:
                    break

    # Also include seeds in results
    for seed in seeds:
        if seed not in all_visited:
            all_visited[seed] = 0

    # Stage 3: Fetch and rank results
    results = []
    for nid, dist in all_visited.items():
        note = get_note_by_id(conn, nid)
        if note:
            note["graph_distance"] = dist
            note["final_score"] = 1.0 / (1.0 + dist)  # closer = higher score
            results.append(note)

    results.sort(key=lambda n: n["final_score"], reverse=True)
    return results[:plan.max_total_nodes]
