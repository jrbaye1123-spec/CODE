"""Provenance tracking — claim-level source tracing and attribution ledger.

Per Nullresearch strategy:
- Every assertion carries a pointer back to the source paragraph.
- Structured output: (claim_text, source_document, source_location).
- Attribution ledger tracks which sources informed which outputs,
  weighted by semantic contribution.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import json
import hashlib
import uuid


@dataclass
class Claim:
    """A single claim with full provenance chain."""
    claim_id: str
    claim_text: str
    source_document: str  # Path, URL, or paper ID
    source_location: str  # Section, paragraph, line number
    confidence: float  # 0.0 to 1.0
    extraction_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class AgentOutput:
    """An agent output with provenance attached to every claim."""
    output_id: str
    workflow: str
    session_id: str
    summary: str
    claims: list[Claim]
    sources_consulted: list[str]  # All documents read to produce this output
    agent_version: str
    model_provider: str
    model_version: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class AttributionEntry:
    """Records which contributor's work informed which output."""
    entry_id: str
    output_id: str
    contributor: str  # Author ID from vault
    source_document: str
    contribution_weight: float  # 0.0 to 1.0, semantic contribution score
    claims_derived: list[str]  # Claim IDs derived from this source
    recorded_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ProvenanceTracker:
    """Ensures every agent output carries auditable claim-level provenance.

    This is the foundation for both verifiability and fair attribution.
    """

    def __init__(self, storage_path: str = "data/logs"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def create_claim(
        self,
        claim_text: str,
        source_document: str,
        source_location: str = "unknown",
        confidence: float = 1.0,
    ) -> Claim:
        """Create a claim with provenance attached."""
        claim_id = f"claim_{uuid.uuid4().hex[:12]}"
        return Claim(
            claim_id=claim_id,
            claim_text=claim_text,
            source_document=source_document,
            source_location=source_location,
            confidence=confidence,
        )

    def create_output(
        self,
        workflow: str,
        session_id: str,
        summary: str,
        claims: list[Claim],
        sources_consulted: list[str],
        agent_version: str = "0.1.0",
        model_provider: str = "unknown",
        model_version: str = "unknown",
    ) -> AgentOutput:
        """Create an agent output with full provenance attached to every claim."""
        output_id = f"output_{uuid.uuid4().hex[:12]}"

        output = AgentOutput(
            output_id=output_id,
            workflow=workflow,
            session_id=session_id,
            summary=summary,
            claims=claims,
            sources_consulted=sources_consulted,
            agent_version=agent_version,
            model_provider=model_provider,
            model_version=model_version,
        )

        self._save_output(output)
        return output

    def _save_output(self, output: AgentOutput):
        """Persist agent output with provenance."""
        output_file = self.storage_path / f"output_{output.output_id}.json"
        output_file.write_text(json.dumps({
            "output_id": output.output_id,
            "workflow": output.workflow,
            "session_id": output.session_id,
            "summary": output.summary,
            "claims": [
                {
                    "claim_id": c.claim_id,
                    "claim_text": c.claim_text,
                    "source_document": c.source_document,
                    "source_location": c.source_location,
                    "confidence": c.confidence,
                    "extraction_timestamp": c.extraction_timestamp,
                }
                for c in output.claims
            ],
            "sources_consulted": output.sources_consulted,
            "agent_version": output.agent_version,
            "model_provider": output.model_provider,
            "model_version": output.model_version,
            "created_at": output.created_at,
        }, indent=2, default=str))

    def trace_claim(self, claim_id: str) -> Optional[dict]:
        """Trace a claim back to its source. Returns full provenance chain."""
        for output_file in self.storage_path.glob("output_*.json"):
            data = json.loads(output_file.read_text())
            for claim in data.get("claims", []):
                if claim["claim_id"] == claim_id:
                    return {
                        "claim": claim,
                        "output_id": data["output_id"],
                        "workflow": data["workflow"],
                        "all_sources_consulted": data["sources_consulted"],
                    }
        return None

    def verify_provenance(self, output_id: str) -> dict:
        """Verify that every claim in an output has provenance."""
        output_file = self.storage_path / f"output_{output_id}.json"
        if not output_file.exists():
            return {"verified": False, "error": "Output not found"}

        data = json.loads(output_file.read_text())
        claims = data.get("claims", [])
        total = len(claims)
        traced = 0
        untraced = []

        for claim in claims:
            if claim.get("source_document") and claim.get("source_document") != "unknown":
                traced += 1
            else:
                untraced.append(claim["claim_id"])

        return {
            "verified": traced == total,
            "total_claims": total,
            "traced_claims": traced,
            "untraced_claims": untraced,
            "provenance_completeness": traced / total if total > 0 else 0.0,
        }


class AttributionLedger:
    """Tracks which contributors' work informed which outputs.

    Enables fair compensation proportional to semantic contribution.
    """

    def __init__(self, storage_path: str = "data/logs"):
        self.storage_path = Path(storage_path)
        self.ledger_path = self.storage_path / "attribution_ledger.jsonl"

    def record_attribution(self, entry: AttributionEntry):
        """Record a contributor's influence on an agent output."""
        with open(self.ledger_path, "a") as f:
            f.write(json.dumps({
                "entry_id": entry.entry_id,
                "output_id": entry.output_id,
                "contributor": entry.contributor,
                "source_document": entry.source_document,
                "contribution_weight": entry.contribution_weight,
                "claims_derived": entry.claims_derived,
                "recorded_at": entry.recorded_at,
            }) + "\n")

    def get_contributor_influence(self, contributor: str) -> dict:
        """Get aggregate influence stats for a contributor."""
        if not self.ledger_path.exists():
            return {"contributor": contributor, "total_weight": 0.0, "outputs_influenced": 0}

        entries = []
        with open(self.ledger_path) as f:
            for line in f:
                entry = json.loads(line)
                if entry["contributor"] == contributor:
                    entries.append(entry)

        return {
            "contributor": contributor,
            "total_weight": sum(e["contribution_weight"] for e in entries),
            "outputs_influenced": len(set(e["output_id"] for e in entries)),
            "sources_used": list(set(e["source_document"] for e in entries)),
            "entries": entries,
        }

    def get_output_attribution(self, output_id: str) -> list[dict]:
        """Get all contributors for a specific output."""
        if not self.ledger_path.exists():
            return []

        entries = []
        with open(self.ledger_path) as f:
            for line in f:
                entry = json.loads(line)
                if entry["output_id"] == output_id:
                    entries.append(entry)

        return sorted(entries, key=lambda e: e["contribution_weight"], reverse=True)
