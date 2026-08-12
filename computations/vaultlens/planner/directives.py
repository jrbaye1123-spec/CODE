"""Planner directives schema for LLM-generated graph traversal plans.

Three-phase execution: Seeding → Expansion → Filtering.
"""

from dataclasses import dataclass, field
from typing import Literal, Optional


@dataclass
class SeedDirective:
    """How to find starting nodes."""
    method: Literal["bm25", "exact_title", "alias"]
    query: str
    limit: int = 5


@dataclass
class ExpansionDirective:
    """How to expand from seed nodes through the graph."""
    direction: Literal["incoming", "outgoing", "both"]
    variants: list[str]
    max_hops: int = 2
    max_nodes: int = 20
    relations: Optional[list[str]] = None


@dataclass
class FilterDirective:
    """Post-traversal filtering."""
    type: Literal["min_confidence", "exclude_status", "require_tag", "require_type"]
    value: float | str


@dataclass
class TraversalPlan:
    """Complete graph traversal plan from LLM."""
    intent_summary: str
    seeds: list[SeedDirective]
    expansions: list[ExpansionDirective]
    filters: list[FilterDirective] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "intent_summary": self.intent_summary,
            "seeds": [{"method": s.method, "query": s.query, "limit": s.limit}
                       for s in self.seeds],
            "expansions": [{
                "direction": e.direction, "variants": e.variants,
                "max_hops": e.max_hops, "max_nodes": e.max_nodes,
                "relations": e.relations,
            } for e in self.expansions],
            "filters": [{"type": f.type, "value": f.value} for f in self.filters],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TraversalPlan":
        return cls(
            intent_summary=d.get("intent_summary", ""),
            seeds=[SeedDirective(
                method=s.get("method", "bm25"), query=s.get("query", ""),
                limit=s.get("limit", 5),
            ) for s in d.get("seeds", [])],
            expansions=[ExpansionDirective(
                direction=e.get("direction", "both"),
                variants=e.get("variants", []),
                max_hops=e.get("max_hops", 2),
                max_nodes=e.get("max_nodes", 20),
                relations=e.get("relations"),
            ) for e in d.get("expansions", [])],
            filters=[FilterDirective(
                type=f.get("type", "min_confidence"),
                value=f.get("value", 0.0),
            ) for f in d.get("filters", [])],
        )


@dataclass
class ExecutionResult:
    """Result of executing a TraversalPlan."""
    success: bool
    reason: str = ""
    nodes: list[dict] = field(default_factory=list)
    edges: list[dict] = field(default_factory=list)
    seed_count: int = 0
    plan_used: Optional[TraversalPlan] = None
    attempt: int = 0

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)
