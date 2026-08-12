"""VaultLens as Angel #2: graph-native query responder.

Answers queries by traversing the sovereign graph and returning
retrieved subgraph + structured answer. No external services needed.
Uses the existing retriever, session, and answer compiler.

Key integration: this makes VaultLens queryable as an Angel so that
queries about gap, neurovisceral models, and body axioms are answered
directly from the graph with provenance.
"""

import sqlite3
from typing import Optional

from ..retriever import retrieve
from ..graph_store import GraphStore
from ..answer.compiler import compile_answer
from ..answer.provenance import render_proof


class VaultLensAngel:
    """Graph-native query responder using the sovereign vault.

    Unlike the DuckDB Angel which queries relational tables, this Angel
    traverses typed graph edges and returns grounded answers with citations.
    """

    def __init__(self, vault_db_path: str,
                 vector_db_path: Optional[str] = None):
        self.vault_db_path = vault_db_path
        self.vector_db_path = vector_db_path

    def query(self, text: str, strict: bool = True,
              use_llm: bool = False) -> dict:
        """Answer a natural language query from the sovereign graph.

        Args:
            text: Natural language query
            strict: Require grounded citations (reject unsupported claims)
            use_llm: Use local LLM for answer generation (slower)

        Returns:
            Dict with answer, proof, nodes, edges, grounding status
        """
        conn = sqlite3.connect(self.vault_db_path)
        conn.row_factory = sqlite3.Row
        graph = GraphStore(conn)
        graph.load()

        # Retrieve subgraph
        result = retrieve(
            conn=conn, graph=graph, query=text,
            max_hops=2, max_notes=25, explain=False,
        )

        nodes = result.get("retrieved_notes", [])
        edges = result.get("edges", [])
        variants = result.get("detected_variants", [])

        # Compile answer
        compiled = compile_answer(
            query=text, nodes=nodes, edges=edges,
            variants=variants, strict=strict, use_llm=use_llm,
        )

        conn.close()

        return {
            "angel": "vaultlens-graph",
            "query": text,
            "answer": compiled["answer"].answer_text,
            "proof": compiled["proof_text"],
            "grounded": compiled["validation"].passed,
            "claims_grounded": compiled["validation"].claims_grounded,
            "claims_total": compiled["validation"].claims_total,
            "insufficient_evidence": compiled["answer"].insufficient_evidence,
            "nodes_retrieved": len(nodes),
            "edges_retrieved": len(edges),
            "variants_used": variants,
            "gap_proposals": len(compiled.get("gap_proposals", [])),
        }

    def health(self) -> dict:
        """Return health and stats for this Angel."""
        conn = sqlite3.connect(self.vault_db_path)
        notes = conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
        edges = conn.execute(
            "SELECT COUNT(*) FROM edges WHERE resolved = 1"
        ).fetchone()[0]
        pending = 0
        try:
            pending = conn.execute(
                "SELECT COUNT(*) FROM proposals WHERE status = 'pending'"
            ).fetchone()[0]
        except sqlite3.OperationalError:
            pass
        conn.close()

        return {
            "angel": "vaultlens-graph",
            "status": "ready",
            "notes": notes,
            "edges": edges,
            "pending_proposals": pending,
        }
