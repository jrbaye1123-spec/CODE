"""LLM answer generator: prompts the local model to produce GroundedAnswer JSON.

The LLM receives the retrieved subgraph (nodes + edges) and must produce
a structured answer with citations. It must NOT invent facts beyond the
provided evidence. If evidence is insufficient, it must set
insufficient_evidence = true.
"""

import json
import os
import re
import subprocess
from typing import Optional

from .schema import GroundedAnswer


GENERATOR_PROMPT = """You are the answer generator for VaultLens, a sovereign knowledge graph system.

You must answer ONLY from the provided retrieved subgraph below.
Every factual claim MUST cite at least one active edge or node from the subgraph.
Do NOT invent notes, edges, relations, or facts that are not in the subgraph.

Return a JSON object with this structure:
{
  "answer_text": "clear answer sentence",
  "claims": [
    {
      "claim_id": "c1",
      "text": "specific factual claim",
      "claim_type": "causal|evidential|temporal|definitional|provenance|procedural|semantic",
      "confidence": 0.72,
      "citations": [
        {
          "edge_id": "the edge identifier from the subgraph",
          "relation": "causes|supports|derived-from|etc",
          "variant": "causal|evidential|etc",
          "source_note_title": "Rate Hikes",
          "target_note_title": "Demand Drop"
        }
      ]
    }
  ],
  "contradictions": [],
  "uncertainties": [],
  "insufficient_evidence": false
}

Rules:
1. claim_type must match the relation type (causal edges → "causal" claim_type)
2. Every claim must have at least one citation
3. Citations must reference edges/nodes present in the subgraph
4. If the subgraph doesn't contain enough evidence to answer, set insufficient_evidence=true and answer_text="Insufficient evidence in sovereign graph."
5. If there are contradictory edges (e.g., both supports and refutes), list them in contradictions
6. Return ONLY the JSON object, no markdown, no explanation

Retrieved Subgraph:
---
Query: {query}

Nodes:
{nodes_text}

Edges:
{edges_text}
---

GroundedAnswer JSON:"""


def build_subgraph_context(nodes: list[dict], edges: list[dict]) -> tuple[str, str]:
    """Build text representations of nodes and edges for the LLM prompt."""
    node_lines = []
    for i, n in enumerate(nodes[:20]):
        nid = n.get("note_id", f"n{i}")
        title = n.get("title", nid)
        ntype = n.get("note_type", "")
        body = (n.get("body", "") or "")[:300]
        node_lines.append(f"[{nid}] {title} (type: {ntype})")
        if body:
            node_lines.append(f"    {body}")
        node_lines.append("")

    edge_lines = []
    for i, e in enumerate(edges[:30]):
        eid = e.get("edge_id", f"e{i}")
        src = e.get("source", e.get("source_note_id", "?"))
        tgt = e.get("target", e.get("target_note_id", "?"))
        rel = e.get("relation", "?")
        var = e.get("variant", "?")
        conf = e.get("confidence", 1.0)
        edge_lines.append(f"[{eid}] {src} --{rel}--> {tgt} (variant: {var}, confidence: {conf:.2f})")

    return "\n".join(node_lines), "\n".join(edge_lines)


def generate_answer(query: str, nodes: list[dict], edges: list[dict],
                    model_path: str = "", llama_cli: str = "",
                    temperature: float = 0.1) -> Optional[GroundedAnswer]:
    """Generate a structured GroundedAnswer using the local LLM.

    Args:
        query: Original user query
        nodes: Retrieved nodes from the subgraph
        edges: Retrieved edges from the subgraph
        model_path: Path to GGUF model
        llama_cli: Path to llama-cli binary
        temperature: LLM sampling temperature

    Returns:
        GroundedAnswer or None if generation fails
    """
    if not model_path:
        model_path = os.path.expanduser("~/models/Llama-3.2-3B-Instruct-Q4_K_M.gguf")
    if not llama_cli:
        llama_cli = os.path.expanduser("~/llama.cpp/build/bin/llama-cli")

    if not os.path.exists(model_path) or not os.path.exists(llama_cli):
        return None

    nodes_text, edges_text = build_subgraph_context(nodes, edges)

    prompt = GENERATOR_PROMPT.format(
        query=query,
        nodes_text=nodes_text or "(no nodes retrieved)",
        edges_text=edges_text or "(no edges retrieved)",
    )

    try:
        result = subprocess.run(
            [llama_cli, "-m", model_path, "-c", "4096", "-t", "8",
             "-ctk", "q8_0", "-ctv", "q8_0",
             "--temp", str(temperature), "-n", "1024",
             "--no-display-prompt", "-p", prompt],
            capture_output=True, text=True, timeout=90,
            env={**os.environ, "OMP_NUM_THREADS": "8"},
        )
        if result.returncode != 0:
            return None

        raw = result.stdout.strip()
        answer_dict = _parse_json(raw)
        if answer_dict:
            return GroundedAnswer.from_dict(answer_dict)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return None


def _parse_json(raw: str) -> Optional[dict]:
    """Parse JSON from LLM output, handling common formatting issues."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    m = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    m = re.search(r'\{.*\}', raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return None
