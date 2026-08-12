"""Session memory: ephemeral working memory for conversational continuity.

SessionNode: a note pulled into the active session context.
SessionEdge: a relationship active in the session (from sovereign or LLM-inferred).
SessionContext: the complete ephemeral state of a conversation session.

Key invariant: this is a scratchpad, never a truth store.
All permanent mutations go through the HMAC proposal pipeline.
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SessionNode:
    """A note active in the current session."""
    note_id: str
    title: str
    variant: str = ""               # Which variant retrieved it
    retrieved_by: str = ""          # Which query brought this in
    relevance_score: float = 0.0
    accessed_at: float = 0.0
    pinned: bool = False            # User explicitly pinned this
    note_type: str = ""
    body: str = ""

    def __post_init__(self):
        if self.accessed_at == 0.0:
            self.accessed_at = time.time()


@dataclass
class SessionEdge:
    """A relationship active in the current session."""
    source_id: str
    target_id: str
    relation: str
    variant: str
    from_sovereign: bool = True     # False if LLM-inferred during session
    confidence: float = 1.0
    evidence: str = ""


@dataclass
class ResolvedQuery:
    """Result of anaphora resolution — determines how to handle a query."""
    intent: str                     # 'new_query', 'causal_expansion', 'evidential_expansion',
                                    # 'followup_expansion', 'focus_shift'
    focus_nodes: list[str]          # note_ids to expand from (empty for new queries)
    variants: list[str]             # graph variants to use
    raw_query: str = ""             # original query (for new queries)
    resolved_terms: list[str] = field(default_factory=list)  # explicit node references
    is_followup: bool = False       # True if this is a follow-up to prior context
    skip_llm: bool = False          # True for fast-path follow-ups


@dataclass
class SessionContext:
    """Complete ephemeral state of a conversation session."""
    session_id: str
    started_at: float
    nodes: dict[str, SessionNode] = field(default_factory=dict)
    edges: list[SessionEdge] = field(default_factory=list)
    query_history: list[dict] = field(default_factory=list)

    # Anaphora resolution state
    last_focus_nodes: list[str] = field(default_factory=list)
    last_variants: list[str] = field(default_factory=list)
    last_intent: str = ""

    @classmethod
    def create(cls, session_id: Optional[str] = None) -> "SessionContext":
        return cls(
            session_id=session_id or f"session-{uuid.uuid4().hex[:8]}",
            started_at=time.time(),
        )

    # ── Node management ───────────────────────────────

    def add_node(self, note: dict, retrieved_by: str = "",
                 variant: str = "", score: float = 0.0) -> None:
        """Add or update a node in the session."""
        nid = note.get("note_id", "")
        if not nid:
            return
        if nid in self.nodes:
            self.nodes[nid].accessed_at = time.time()
            if score > self.nodes[nid].relevance_score:
                self.nodes[nid].relevance_score = score
        else:
            self.nodes[nid] = SessionNode(
                note_id=nid,
                title=note.get("title", nid),
                variant=variant,
                retrieved_by=retrieved_by,
                relevance_score=score,
                note_type=note.get("note_type", ""),
                body=note.get("body", "")[:500],
            )

    def add_edge(self, edge: dict, from_sovereign: bool = True) -> None:
        """Add an edge to the session."""
        self.edges.append(SessionEdge(
            source_id=edge.get("source", edge.get("source_note_id", "")),
            target_id=edge.get("target", edge.get("target_note_id", "")),
            relation=edge.get("relation", "links-to"),
            variant=edge.get("variant", "generic"),
            from_sovereign=from_sovereign,
            confidence=edge.get("confidence", 1.0),
            evidence=edge.get("evidence", edge.get("evidence_span", "")),
        ))

    def merge_result(self, result: dict, query: str = "",
                     variants: list[str] = None) -> None:
        """Merge a retrieval result into the session context.

        Updates nodes, edges, focus, and query history.
        """
        # Merge nodes
        for note in result.get("retrieved_notes", result.get("nodes", [])):
            self.add_node(
                note,
                retrieved_by=query,
                variant=variants[0] if variants else "",
                score=note.get("final_score", note.get("relevance_score", 0.5)),
            )

        # Merge edges
        for edge in result.get("edges", []):
            self.add_edge(edge, from_sovereign=True)

        # Update query history
        self.query_history.append({
            "query": query,
            "timestamp": time.time(),
            "nodes_found": len(result.get("retrieved_notes", result.get("nodes", []))),
            "variants": variants or [],
        })

    def set_focus(self, node_ids: list[str], variants: list[str] = None,
                  intent: str = "") -> None:
        """Set the current focus for anaphora resolution."""
        self.last_focus_nodes = node_ids[:5]  # Keep top 5
        if variants:
            self.last_variants = variants
        if intent:
            self.last_intent = intent

    # ── Querying ───────────────────────────────────────

    def get_active_nodes(self, limit: int = 20) -> list[SessionNode]:
        """Get most recently accessed session nodes."""
        sorted_nodes = sorted(
            self.nodes.values(),
            key=lambda n: (n.pinned, n.accessed_at),
            reverse=True,
        )
        return sorted_nodes[:limit]

    def get_subgraph_edges(self) -> list[SessionEdge]:
        """Get edges connecting currently active session nodes."""
        active_ids = set(self.nodes.keys())
        return [e for e in self.edges
                if e.source_id in active_ids and e.target_id in active_ids]

    def get_llm_inferred_edges(self) -> list[SessionEdge]:
        """Get edges that were inferred during the session (not from sovereign)."""
        return [e for e in self.edges if not e.from_sovereign]

    # ── Serializable snapshot ─────────────────────────

    def snapshot(self) -> dict:
        """Return a JSON-safe summary of session state."""
        return {
            "session_id": self.session_id,
            "started_at": self.started_at,
            "elapsed_seconds": round(time.time() - self.started_at, 1),
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "sovereign_edges": sum(1 for e in self.edges if e.from_sovereign),
            "inferred_edges": sum(1 for e in self.edges if not e.from_sovereign),
            "query_count": len(self.query_history),
            "focus_nodes": self.last_focus_nodes,
            "last_variants": self.last_variants,
            "active_titles": [n.title for n in self.get_active_nodes(10)],
        }

    def to_context_string(self) -> str:
        """Serialize session as LLM context."""
        lines = [f"## Session: {self.session_id}", ""]
        if self.query_history:
            lines.append("### Conversation")
            for h in self.query_history[-5:]:
                lines.append(f"- Q: {h['query']}")
            lines.append("")
        if self.nodes:
            lines.append("### Active Notes")
            for n in self.get_active_nodes(15):
                tag = " [PINNED]" if n.pinned else ""
                lines.append(f"- **{n.title}** ({n.note_type}) [{n.note_id}]{tag}")
                if n.body:
                    lines.append(f"  {n.body[:200]}")
            lines.append("")
        if self.edges:
            lines.append("### Active Relationships")
            for e in self.edges:
                src = self.nodes.get(e.source_id, SessionNode(e.source_id, e.source_id))
                tgt = self.nodes.get(e.target_id, SessionNode(e.target_id, e.target_id))
                tag = "" if e.from_sovereign else " [INFERRED]"
                lines.append(f"- {src.title} --{e.relation}--> {tgt.title} ({e.variant}){tag}")
            lines.append("")
        return "\n".join(lines)
