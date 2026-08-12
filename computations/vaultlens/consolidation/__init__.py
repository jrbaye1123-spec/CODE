"""Sleep cycle worker: asynchronous memory consolidation.

After a chat session ends, the sleep worker feeds the transcript to the
local Llama-3.2-3B model to extract structured edge proposals. These are
written to the pending proposals queue for human review.

The sleep cycle operates asynchronously — it never blocks the interactive
session. The fast, lossy LLM context handles real-time interaction; the
sleep cycle consolidates ephemeral chat into permanent graph edges.

Architecture:
    Chat transcript → local Llama-3.2-3B → structured triples → proposals/
"""

import json
import os
import sqlite3
import subprocess
import hashlib
from pathlib import Path
from typing import Optional


# ── Prompt template for consolidation ──────────────────

CONSOLIDATION_PROMPT = """You are a memory consolidation agent for VaultLens.

Your job: read the following conversation transcript and extract structured
knowledge as typed graph edges. Only extract factual claims, causal links,
evidence relationships, and contradictions that are explicitly stated.

Format your response as a JSON array of edge proposals. Each proposal must have:
- source_title: the source concept (capitalized)
- target_title: the target concept (capitalized)
- relation: one of [causes, enables, prevents, supports, refutes, qualifies,
  precedes, follows, is-a, part-of, depends-on, similar-to, contrasts-with,
  derived-from, cited-by, input-to, output-of, step-before]
- variant: one of [causal, evidential, temporal, hierarchical, semantic,
  provenance, procedural]
- confidence: 0.0 to 1.0 (how confident are you this edge is correct?)
- evidence_span: the exact sentence(s) from the transcript that support this
- rationale: why this edge should be added to the knowledge graph

Rules:
1. Only extract edges that are explicitly stated or clearly implied.
2. Do not invent relationships that don't exist in the transcript.
3. Set confidence LOW (0.4-0.6) for implied relationships.
4. Set confidence HIGH (0.7-0.9) for explicitly stated relationships.
5. If the transcript contains contradictions, mark them with refutes/qualifies.
6. Return ONLY the JSON array, no other text.

Conversation transcript:
---
{transcript}
---

JSON array of edge proposals:"""


# ── Consolidation worker ───────────────────────────────

def run_sleep_cycle(
    transcript: str,
    model_path: Optional[str] = None,
    llama_cli: Optional[str] = None,
    proposals_dir: str = ".vaultlens/proposals/pending/",
    session_id: Optional[str] = None,
    max_tokens: int = 1024,
    temperature: float = 0.1,
) -> dict:
    """Run a consolidation sleep cycle on a chat transcript.

    Feeds the transcript to a local LLM (Llama-3.2-3B by default),
    extracts structured edge proposals, and writes them to the
    pending proposals directory.

    Args:
        transcript: Full conversation transcript
        model_path: Path to GGUF model file
        llama_cli: Path to llama-cli binary
        proposals_dir: Directory for pending proposals
        session_id: Session identifier
        max_tokens: Max tokens for LLM generation
        temperature: LLM sampling temperature

    Returns:
        Dict with consolidation statistics
    """
    # Default paths
    if model_path is None:
        model_path = os.path.expanduser("~/models/Llama-3.2-3B-Instruct-Q4_K_M.gguf")
    if llama_cli is None:
        llama_cli = os.path.expanduser("~/llama.cpp/build/bin/llama-cli")
    if session_id is None:
        session_id = f"sleep-{hashlib.sha256(os.urandom(8)).hexdigest()[:8]}"

    # Truncate transcript if too long (leave room for prompt + response)
    max_transcript_chars = 8000
    if len(transcript) > max_transcript_chars:
        transcript = transcript[:max_transcript_chars] + "\n... (transcript truncated)"

    prompt = CONSOLIDATION_PROMPT.format(transcript=transcript)

    # Check if model is available
    if not os.path.exists(model_path) or not os.path.exists(llama_cli):
        return {
            "session_id": session_id,
            "status": "skipped",
            "reason": "Local model or llama-cli not available",
            "proposals_extracted": 0,
        }

    # Run local model
    try:
        result = subprocess.run(
            [
                llama_cli,
                "-m", model_path,
                "-c", "8192",
                "-t", "8",
                "-ctk", "q8_0",
                "-ctv", "q8_0",
                "--temp", str(temperature),
                "-n", str(max_tokens),
                "--no-display-prompt",
                "-p", prompt,
            ],
            capture_output=True,
            text=True,
            timeout=120,
            env={**os.environ, "OMP_NUM_THREADS": "8"},
        )

        if result.returncode != 0:
            return {
                "session_id": session_id,
                "status": "error",
                "reason": f"llama-cli error: {result.stderr[:200]}",
                "proposals_extracted": 0,
            }

        raw_output = result.stdout.strip()

    except subprocess.TimeoutExpired:
        return {
            "session_id": session_id,
            "status": "timeout",
            "reason": "Local model inference timed out",
            "proposals_extracted": 0,
        }
    except FileNotFoundError:
        return {
            "session_id": session_id,
            "status": "skipped",
            "reason": "llama-cli binary not found",
            "proposals_extracted": 0,
        }

    # Parse JSON from LLM output
    proposals = _parse_llm_proposals(raw_output)

    # Write proposals to pending directory
    os.makedirs(proposals_dir, exist_ok=True)
    written = 0
    for i, prop in enumerate(proposals):
        prop["proposal_id"] = f"{session_id}-{i:03d}"
        prop["proposer"] = "sleep-cycle"
        prop["status"] = "pending"
        prop["session_id"] = session_id

        fname = f"{prop['proposal_id']}.json"
        with open(os.path.join(proposals_dir, fname), "w") as f:
            json.dump(prop, f, indent=2)
        written += 1

    return {
        "session_id": session_id,
        "status": "completed",
        "proposals_extracted": written,
        "raw_output_length": len(raw_output),
    }


def _parse_llm_proposals(raw: str) -> list[dict]:
    """Parse JSON proposals from LLM output. Handles common formatting issues."""
    # Try direct JSON parse
    try:
        proposals = json.loads(raw)
        if isinstance(proposals, dict):
            proposals = [proposals]
        if isinstance(proposals, list):
            return proposals
    except json.JSONDecodeError:
        pass

    # Try extracting JSON block from markdown
    import re
    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', raw, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try finding array brackets
    bracket_match = re.search(r'\[.*\]', raw, re.DOTALL)
    if bracket_match:
        try:
            return json.loads(bracket_match.group(0))
        except json.JSONDecodeError:
            pass

    return []


# ── Manual consolidation (no LLM) ──────────────────────

def extract_edges_from_transcript_heuristic(transcript: str) -> list[dict]:
    """Fallback heuristic extraction when LLM is unavailable.

    Uses regex patterns similar to the proposer's heuristic mode.
    Less accurate but doesn't require a model.
    """
    from ..proposer import propose_from_text
    proposals = propose_from_text(transcript, title="Transcript", mode="heuristic",
                                  min_confidence=0.5)
    return [
        {
            "source_title": p.source_title,
            "target_title": p.target_title,
            "relation": p.relation,
            "variant": p.variant,
            "confidence": p.confidence,
            "evidence_span": p.evidence_span,
            "rationale": p.rationale,
        }
        for p in proposals
    ]
