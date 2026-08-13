"""AgentOps pipeline — prompt versioning, output quality, and drift detection.

Per Nullresearch strategy: "initial demos accumulate invisible technical debt —
prompts degrade, models shift, vault schema evolves, and nobody notices until
outputs are subtly wrong. The only defense is treating agent workflows as
maintained products, not one-off experiments."
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import json
import hashlib


@dataclass
class PromptVersion:
    """A versioned prompt template for the triage workflow."""
    version_id: str
    workflow: str
    role: str  # e.g., "system", "classification", "summarization"
    template: str
    variables: list[str]  # Variable names in the template
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    created_by: str = ""
    changelog: str = ""
    is_active: bool = False


@dataclass
class ModelRun:
    """Metadata for a single model inference run."""
    run_id: str
    workflow: str
    prompt_version_id: str
    model_provider: str
    model_version: str
    input_hash: str  # Hash of input to detect changes
    output_hash: str  # Hash of output for drift detection
    latency_ms: float
    token_count: int
    cost_estimate: float
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class DriftAlert:
    """Alert triggered when output patterns deviate from baseline."""
    alert_id: str
    workflow: str
    metric: str  # What drifted (classification_distribution, relevance_scores, etc.)
    baseline_value: float
    current_value: float
    deviation_pct: float
    severity: str  # "info", "warning", "critical"
    timestamp: str


class AgentOps:
    """Pipeline for versioning, monitoring, and maintaining agent workflows."""

    def __init__(self, storage_path: str = "data"):
        self.storage_path = Path(storage_path)
        self.prompts_path = self.storage_path / "prompts"
        self.logs_path = self.storage_path / "logs"
        self.prompts_path.mkdir(parents=True, exist_ok=True)
        self.logs_path.mkdir(parents=True, exist_ok=True)

    # --- Prompt Versioning ---

    def save_prompt(self, prompt: PromptVersion) -> str:
        """Save a versioned prompt template."""
        prompt_file = self.prompts_path / f"{prompt.workflow}_{prompt.version_id}.json"
        prompt_file.write_text(json.dumps({
            "version_id": prompt.version_id,
            "workflow": prompt.workflow,
            "role": prompt.role,
            "template": prompt.template,
            "variables": prompt.variables,
            "created_at": prompt.created_at,
            "created_by": prompt.created_by,
            "changelog": prompt.changelog,
            "is_active": prompt.is_active,
        }, indent=2))
        return prompt.version_id

    def load_prompt(self, workflow: str, version_id: str) -> Optional[PromptVersion]:
        """Load a specific version of a prompt."""
        prompt_file = self.prompts_path / f"{workflow}_{version_id}.json"
        if not prompt_file.exists():
            return None
        data = json.loads(prompt_file.read_text())
        return PromptVersion(**data)

    def get_active_prompt(self, workflow: str) -> Optional[PromptVersion]:
        """Get the currently active prompt for a workflow."""
        manifests = list(self.prompts_path.glob(f"{workflow}_*.json"))
        for manifest in manifests:
            data = json.loads(manifest.read_text())
            if data.get("is_active"):
                return PromptVersion(**data)
        return None

    def list_versions(self, workflow: str) -> list[PromptVersion]:
        """List all prompt versions for a workflow, newest first."""
        versions = []
        for manifest in sorted(
            self.prompts_path.glob(f"{workflow}_*.json"),
            reverse=True,
        ):
            data = json.loads(manifest.read_text())
            versions.append(PromptVersion(**data))
        return versions

    def activate_prompt(self, workflow: str, version_id: str):
        """Set a specific prompt version as active, deactivating others."""
        for manifest in self.prompts_path.glob(f"{workflow}_*.json"):
            data = json.loads(manifest.read_text())
            data["is_active"] = (data["version_id"] == version_id)
            manifest.write_text(json.dumps(data, indent=2))

    # --- Run Logging ---

    def log_run(self, run: ModelRun):
        """Log a single inference run for quality tracking."""
        log_file = self.logs_path / "runs.jsonl"
        with open(log_file, "a") as f:
            f.write(json.dumps({
                "run_id": run.run_id,
                "workflow": run.workflow,
                "prompt_version_id": run.prompt_version_id,
                "model_provider": run.model_provider,
                "model_version": run.model_version,
                "input_hash": run.input_hash,
                "output_hash": run.output_hash,
                "latency_ms": run.latency_ms,
                "token_count": run.token_count,
                "cost_estimate": run.cost_estimate,
                "timestamp": run.timestamp,
            }) + "\n")

    def get_recent_runs(self, workflow: str, limit: int = 100) -> list[ModelRun]:
        """Get recent inference runs for a workflow."""
        log_file = self.logs_path / "runs.jsonl"
        if not log_file.exists():
            return []
        runs = []
        with open(log_file) as f:
            for line in f:
                data = json.loads(line)
                if data.get("workflow") == workflow:
                    runs.append(ModelRun(**data))
        return runs[-limit:]

    # --- Drift Detection ---

    def detect_classification_drift(
        self, workflow: str, window_size: int = 50
    ) -> Optional[DriftAlert]:
        """Detect shifts in classification distribution.

        Compares recent classifications against historical baseline.
        """
        runs = self.get_recent_runs(workflow, limit=window_size * 2)
        if len(runs) < window_size:
            return None

        recent = runs[-window_size:]
        baseline = runs[:window_size]

        # Compare latency as a proxy for output pattern changes
        recent_avg_latency = sum(r.latency_ms for r in recent) / len(recent)
        baseline_avg_latency = sum(r.latency_ms for r in baseline) / len(baseline)

        if baseline_avg_latency > 0:
            deviation = abs(recent_avg_latency - baseline_avg_latency) / baseline_avg_latency
            if deviation > 0.25:  # 25% deviation triggers alert
                severity = "critical" if deviation > 0.50 else "warning"
                return DriftAlert(
                    alert_id=hashlib.md5(str(datetime.now(timezone.utc).isoformat()).encode(), usedforsecurity=False).hexdigest()[:8],
                    workflow=workflow,
                    metric="latency",
                    baseline_value=baseline_avg_latency,
                    current_value=recent_avg_latency,
                    deviation_pct=deviation,
                    severity=severity,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )

        return None

    def detect_output_hash_drift(
        self, workflow: str, window_size: int = 50
    ) -> Optional[DriftAlert]:
        """Detect if output patterns have shifted by comparing hash diversity."""
        runs = self.get_recent_runs(workflow, limit=window_size * 2)
        if len(runs) < window_size:
            return None

        recent = runs[-window_size:]
        baseline = runs[:window_size]

        recent_hashes = set(r.output_hash for r in recent)
        baseline_hashes = set(r.output_hash for r in baseline)

        # Check hash overlap
        overlap = len(recent_hashes & baseline_hashes)
        total_unique = len(recent_hashes | baseline_hashes)
        jaccard = overlap / total_unique if total_unique > 0 else 0.0

        if jaccard < 0.5:  # Less than 50% overlap in output patterns
            return DriftAlert(
                alert_id=hashlib.md5(str(datetime.now(timezone.utc).isoformat()).encode(), usedforsecurity=False).hexdigest()[:8],
                workflow=workflow,
                metric="output_hash_diversity",
                baseline_value=float(len(baseline_hashes)),
                current_value=float(len(recent_hashes)),
                deviation_pct=1.0 - jaccard,
                severity="warning" if jaccard > 0.2 else "critical",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        return None

    def run_drift_checks(self, workflow: str) -> list[DriftAlert]:
        """Run all drift checks for a workflow. Returns triggered alerts."""
        alerts = []
        latency_drift = self.detect_classification_drift(workflow)
        if latency_drift:
            alerts.append(latency_drift)
        hash_drift = self.detect_output_hash_drift(workflow)
        if hash_drift:
            alerts.append(hash_drift)
        return alerts

    # --- Quality Dashboard ---

    def get_quality_summary(self, workflow: str, days: int = 7) -> dict:
        """Generate a quality summary for the workflow."""
        runs = self.get_recent_runs(workflow, limit=1000)
        if not runs:
            return {"status": "no_data", "message": "No runs logged yet."}

        # Filter to recent days
        cutoff = datetime.now(timezone.utc).isoformat()
        # Simple filter: just use last N runs as proxy
        recent_runs = runs[-min(len(runs), 500):]

        total_runs = len(recent_runs)
        avg_latency = sum(r.latency_ms for r in recent_runs) / total_runs if total_runs else 0
        total_cost = sum(r.cost_estimate for r in recent_runs)
        total_tokens = sum(r.token_count for r in recent_runs)
        active_prompt = self.get_active_prompt(workflow)

        drift_alerts = self.run_drift_checks(workflow)

        return {
            "workflow": workflow,
            "total_runs": total_runs,
            "avg_latency_ms": round(avg_latency, 1),
            "total_cost_estimate": round(total_cost, 4),
            "total_tokens": total_tokens,
            "active_prompt_version": active_prompt.version_id if active_prompt else "none",
            "drift_alerts": len(drift_alerts),
            "drift_details": [
                {"metric": a.metric, "severity": a.severity, "deviation": f"{a.deviation_pct:.1%}"}
                for a in drift_alerts
            ],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
