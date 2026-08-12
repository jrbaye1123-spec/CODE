"""LLM Compiler: prompts local Llama-3.2-3B to generate TraversalPlan JSON.

The LLM acts as a navigator — it proposes search strategies, never facts.
Invalid JSON → graceful fallback to heuristic planner.
"""

import json
import os
import re
import subprocess
from typing import Optional

from .directives import TraversalPlan


SYSTEM_PROMPT = """You are the Query Planner for VaultLens, a sovereign knowledge graph.
Your job is to translate user questions into a JSON TraversalPlan.

Available Graph Variants:
- causal (causes, enables, prevents)
- evidential (supports, refutes, qualifies)
- temporal (precedes, follows)
- hierarchical (part-of, is-a)
- provenance (derived-from, cited-by)
- semantic (similar-to)
- procedural (step-before, input-to)

Output schema:
{
  "intent_summary": "brief description of what the query is asking",
  "seeds": [
    {"method": "bm25", "query": "search terms", "limit": 5}
  ],
  "expansions": [
    {"direction": "incoming|outgoing|both", "variants": ["causal"], "max_hops": 2, "max_nodes": 20}
  ],
  "filters": [
    {"type": "min_confidence|exclude_status|require_tag|require_type", "value": 0.5}
  ]
}

Rules:
1. Start by finding seed nodes using BM25 (keywords) or exact_title.
2. Define how to expand from those seeds using the graph variants.
3. Do not invent facts. Only define the search path.
4. Output ONLY valid JSON matching the schema. No markdown, no explanation.
"""

USER_PROMPT_TEMPLATE = """Query: {query}

Generate a TraversalPlan JSON:"""

REVISION_PROMPT_TEMPLATE = """Your previous plan for the query failed.

Query: {query}
Previous plan: {previous_plan}
Failure reason: {reason}
Nodes found: {node_count}

Revise the search strategy. Consider:
- Broader BM25 search terms
- Different graph variants
- More hops
- Starting from different seed nodes

Output ONLY the revised TraversalPlan JSON:"""


class LLMCompiler:
    """Compiles natural language queries into TraversalPlans using local LLM."""

    def __init__(self, model_path: str = "", llama_cli: str = ""):
        if not model_path:
            model_path = os.path.expanduser("~/models/Llama-3.2-3B-Instruct-Q4_K_M.gguf")
        if not llama_cli:
            llama_cli = os.path.expanduser("~/llama.cpp/build/bin/llama-cli")
        self.model_path = model_path
        self.llama_cli = llama_cli
        self._available = os.path.exists(model_path) and os.path.exists(llama_cli)

    @property
    def available(self) -> bool:
        return self._available

    def compile(self, query: str) -> Optional[TraversalPlan]:
        """Generate a TraversalPlan from a natural language query."""
        if not self.available:
            return None

        prompt = (
            SYSTEM_PROMPT + "\n\n" +
            USER_PROMPT_TEMPLATE.format(query=query)
        )

        raw = self._run_llm(prompt)
        if not raw:
            return None

        plan_dict = _parse_json(raw)
        if not plan_dict:
            return None

        try:
            return TraversalPlan.from_dict(plan_dict)
        except Exception:
            return None

    def revise(self, query: str, previous_plan: TraversalPlan,
               reason: str, node_count: int = 0) -> Optional[TraversalPlan]:
        """Revise a failed plan based on error feedback."""
        if not self.available:
            return None

        prompt = (
            SYSTEM_PROMPT + "\n\n" +
            REVISION_PROMPT_TEMPLATE.format(
                query=query,
                previous_plan=json.dumps(previous_plan.to_dict(), indent=2),
                reason=reason,
                node_count=node_count,
            )
        )

        raw = self._run_llm(prompt)
        if not raw:
            return None

        plan_dict = _parse_json(raw)
        if not plan_dict:
            return None

        try:
            return TraversalPlan.from_dict(plan_dict)
        except Exception:
            return None

    def _run_llm(self, prompt: str) -> Optional[str]:
        """Run the local LLM with a prompt. Returns raw output or None."""
        try:
            result = subprocess.run(
                [
                    self.llama_cli,
                    "-m", self.model_path,
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
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return None


def _parse_json(raw: str) -> Optional[dict]:
    """Parse JSON from LLM output. Handles markdown wrapping and stray text."""
    # Direct
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
    # Outermost braces
    m = re.search(r'\{.*\}', raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return None
