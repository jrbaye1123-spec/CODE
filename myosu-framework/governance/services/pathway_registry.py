"""
pathway_registry — Compositional safety for agent pipelines.

Every permitted pipeline pathway must be registered and approved.
Unapproved pathways are blocked. Dangerous compositions are flagged.
"""
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Dict

UTC = timezone.utc


@dataclass
class Pathway:
    pathway_id: str
    description: str = ""
    agents: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    human_gates: List[str] = field(default_factory=list)
    risk_tier: int = 2
    approval_status: str = "pending"
    approved_by: str = ""
    approved_at: str = ""

    def is_approved(self) -> bool:
        return self.approval_status == "approved"

    def to_dict(self) -> dict:
        return {
            "pathway_id": self.pathway_id,
            "description": self.description,
            "agents": self.agents,
            "tools": self.tools,
            "human_gates": self.human_gates,
            "risk_tier": self.risk_tier,
            "approval_status": self.approval_status,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Pathway":
        return cls(**d)


# ── Dangerous capability combinations ─────────────────────────────────────────

DANGEROUS_COMBINATIONS = [
    ({"retrieval", "code_execution"}, "Retrieval + code execution: risk of executing untrusted content"),
    ({"retrieval", "export"}, "Retrieval + export: risk of unauthorized data exfiltration"),
    ({"synthesis", "export"}, "Synthesis + export without human gate: risk of undisclosed agent output in public"),
    ({"code_execution", "file_modification"}, "Code execution + file modification: risk of system compromise"),
    ({"synthesis", "promotion", "export"}, "Full autonomous pipeline: synthesis → promotion → export without human gate"),
]


class PathwayRegistry:
    """Registry of approved agent-to-agent pathways."""

    def __init__(self, storage_path: Optional[str] = None):
        self.pathways: Dict[str, Pathway] = {}
        self.storage_path = storage_path
        self._register_defaults()

    def _register_defaults(self):
        defaults = [
            Pathway("path_retrieval_extraction", "Retrieval → extraction",
                    agents=["retrieval", "extraction"], risk_tier=1,
                    approval_status="approved", approved_by="system", approved_at=datetime.now(UTC).isoformat()),
            Pathway("path_extraction_synthesis", "Extraction → summarization → tension → synthesis",
                    agents=["extraction", "summarization", "contradiction_detection", "synthesis"],
                    human_gates=["pre_promotion", "pre_export"], risk_tier=2,
                    approval_status="approved", approved_by="system", approved_at=datetime.now(UTC).isoformat()),
            Pathway("path_full_research", "Retrieval → extraction → synthesis with human gates",
                    agents=["retrieval", "extraction", "contradiction_detection", "synthesis"],
                    human_gates=["pre_promotion", "pre_export"], risk_tier=2,
                    approval_status="approved", approved_by="john", approved_at=datetime.now(UTC).isoformat()),
        ]
        for p in defaults:
            self.pathways[p.pathway_id] = p

    def is_approved(self, agents: List[str]) -> bool:
        """Check if any registered pathway covers this agent sequence."""
        agent_set = set(agents)
        for pathway in self.pathways.values():
            if pathway.is_approved() and set(pathway.agents) == agent_set:
                return True
        return False

    def check_dangerous(self, agents: List[str]) -> List[str]:
        """Return warnings for dangerous capability combinations."""
        agent_set = set(agents)
        warnings = []
        for combo, msg in DANGEROUS_COMBINATIONS:
            if combo.issubset(agent_set):
                warnings.append(msg)
        return warnings

    def register(self, pathway: Pathway):
        self.pathways[pathway.pathway_id] = pathway
        if self.storage_path:
            self.save()

    def approve(self, pathway_id: str, approved_by: str = "john"):
        if pathway_id in self.pathways:
            self.pathways[pathway_id].approval_status = "approved"
            self.pathways[pathway_id].approved_by = approved_by
            self.pathways[pathway_id].approved_at = datetime.now(UTC).isoformat()

    def save(self):
        if self.storage_path:
            data = {k: v.to_dict() for k, v in self.pathways.items()}
            with open(self.storage_path, "w") as f:
                json.dump(data, f, indent=2)

    @classmethod
    def load(cls, path: str) -> "PathwayRegistry":
        reg = cls(storage_path=path)
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)
            reg.pathways = {k: Pathway.from_dict(v) for k, v in data.items()}
        return reg
