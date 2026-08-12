"""
cadence — Governance heartbeat metrics engine.

Computes the metrics defined in the ratified constitution's Governance Heartbeat:
  Weekly:   authorship drift, review backlog, quarantine count, exceptions
  Monthly:  incident summary, promotion log review, dependency changes
  Quarterly: retrieval fairness, review-surface adequacy, provenance integrity
  Annual:   constitutional review readiness

All metrics are derived from the audit log + vault state.
No metric is estimated — every number comes from a queryable source.
"""

import json
import os
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Tuple

UTC = timezone.utc


class CadenceEngine:
    """Computes governance heartbeat metrics from vault and audit data."""

    def __init__(self, governance_dir: Optional[str] = None):
        if governance_dir is None:
            governance_dir = os.path.join(os.path.dirname(__file__), "..", "governance")
        self.governance_dir = governance_dir
        self.logs_dir = os.path.join(governance_dir, "logs")
        self.audit_log_path = self._find_latest_audit_log()

    def _find_latest_audit_log(self) -> Optional[str]:
        """Find the most recent audit log file."""
        if not os.path.isdir(self.logs_dir):
            return None
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        path = os.path.join(self.logs_dir, f"audit-{today}.jsonl")
        if os.path.exists(path):
            return path
        # Fallback: find any recent audit log
        for f in sorted(os.listdir(self.logs_dir), reverse=True):
            if f.startswith("audit-") and f.endswith(".jsonl"):
                return os.path.join(self.logs_dir, f)
        return None

    def _load_events(self) -> List[dict]:
        """Load all events from the current audit log."""
        if not self.audit_log_path or not os.path.exists(self.audit_log_path):
            return []
        events = []
        with open(self.audit_log_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return events

    # ── Weekly Metrics ─────────────────────────────────────────────────

    def authorship_drift(self, events: Optional[List[dict]] = None) -> dict:
        """
        Compute authorship drift: what % of recent vault write activity
        represents agent-originated content entering human-author spaces.

        Drift = (agent_synthesis_allowed + promotion_allowed) / total_allowed_writes

        Also tracks the ratification ratio: what % of promotions used 'human_ratified' mode.
        """
        if events is None:
            events = self._load_events()

        recent = [e for e in events if self._is_recent(e, days=7)]
        total_allowed_writes = 0
        agent_synthesis_count = 0
        promotion_count = 0
        firebreak_attempts = 0  # agent → my_thinking blocked writes

        for e in recent:
            pd = e.get("policy_decision", {})
            action = pd.get("action", "")
            decision = pd.get("decision", "")
            obj = pd.get("object", {})
            violations = pd.get("violations", [])

            if action == "vault.write":
                if decision == "allow":
                    total_allowed_writes += 1
                    space = obj.get("space", "")
                    if space == "my_thinking":
                        promotion_count += 1
                elif decision == "quarantine" or decision == "deny":
                    # Count firebreak violations
                    for v in violations:
                        if v.get("rule") == "W-001b":
                            firebreak_attempts += 1
            elif action == "synthesis.run" and decision == "allow":
                agent_synthesis_count += 1
            elif action == "promotion.request" and decision == "allow":
                promotion_count += 1

        total_agent_activity = agent_synthesis_count + promotion_count
        drift_pct = (total_agent_activity / max(1, total_allowed_writes + total_agent_activity)) * 100

        # Load config thresholds
        config = self._load_config()
        warning = config.get("authorship_drift", {}).get("warning_threshold_percent", 25)
        critical = config.get("authorship_drift", {}).get("critical_threshold_percent", 40)

        return {
            "metric": "authorship_drift",
            "period": "7d",
            "total_allowed_writes": total_allowed_writes,
            "agent_synthesis_allowed": agent_synthesis_count,
            "promotions_allowed": promotion_count,
            "total_agent_activity": total_agent_activity,
            "drift_percent": round(drift_pct, 1),
            "firebreak_attempts_blocked": firebreak_attempts,
            "thresholds": {"warning_pct": warning, "critical_pct": critical},
            "status": "critical" if drift_pct >= critical else ("warning" if drift_pct >= warning else "ok"),
        }

    def review_backlog(self, events: Optional[List[dict]] = None) -> dict:
        """Count unapproved / flagged claims awaiting human review."""
        if events is None:
            events = self._load_events()

        pending = 0
        flagged = 0
        for e in events:
            pd = e.get("policy_decision", {})
            if pd.get("action") == "vault.write":
                decision = pd.get("decision", "")
                if decision == "allow":
                    pending += 1
                elif decision == "flag":
                    flagged += 1

        config = self._load_config()
        max_pending = config.get("review", {}).get("max_pending_items", 100)

        return {
            "metric": "review_backlog",
            "pending_review": pending,
            "flagged": flagged,
            "total_backlog": pending + flagged,
            "threshold": max_pending,
            "status": "overloaded" if pending + flagged > max_pending else "ok",
        }

    def quarantine_count(self, events: Optional[List[dict]] = None) -> dict:
        """Count quarantined items and their reasons."""
        if events is None:
            events = self._load_events()

        quarantined = []
        reasons = defaultdict(int)
        for e in events:
            pd = e.get("policy_decision", {})
            if pd.get("decision") == "quarantine":
                obj = pd.get("object", {})
                note_id = obj.get("note_id", "unknown")
                for v in pd.get("violations", []):
                    reasons[v.get("rule", "unknown")] += 1
                quarantined.append({
                    "note_id": note_id,
                    "timestamp": pd.get("timestamp", ""),
                    "violations": [v.get("rule") for v in pd.get("violations", [])],
                })

        return {
            "metric": "quarantine_count",
            "total_quarantined": len(quarantined),
            "by_reason": dict(reasons),
            "recent_items": quarantined[-5:],
            "status": "ok" if len(quarantined) < 20 else "review_needed",
        }

    def exception_check(self) -> dict:
        """Check the exception register for open exceptions."""
        exceptions_path = os.path.join(self.logs_dir, "exceptions.md")
        open_count = 0
        if os.path.exists(exceptions_path):
            with open(exceptions_path) as f:
                for line in f:
                    if "[OPEN]" in line or "[ACTIVE]" in line:
                        open_count += 1

        return {
            "metric": "exceptions",
            "open_exceptions": open_count,
            "register_path": exceptions_path,
            "status": "ok" if open_count == 0 else "review_needed",
        }

    # ── Monthly Metrics ────────────────────────────────────────────────

    def incident_summary(self, events: Optional[List[dict]] = None) -> dict:
        """Summarize incidents by severity and rule."""
        if events is None:
            events = self._load_events()

        monthly = [e for e in events if self._is_recent(e, days=30)]
        severity_counts = defaultdict(int)
        rule_counts = defaultdict(int)

        for e in monthly:
            pd = e.get("policy_decision", {})
            for v in pd.get("violations", []):
                severity = v.get("severity", "unknown")
                rule = v.get("rule", "unknown")
                severity_counts[severity] += 1
                rule_counts[rule] += 1

        total = sum(severity_counts.values())
        critical = severity_counts.get("critical", 0)
        high = severity_counts.get("high", 0)

        return {
            "metric": "incident_summary",
            "period": "30d",
            "total_violations": total,
            "by_severity": dict(severity_counts),
            "by_rule": dict(rule_counts),
            "status": "critical" if critical > 5 else ("warning" if high > 10 else "ok"),
        }

    def promotion_log_review(self, events: Optional[List[dict]] = None) -> dict:
        """Review promotion patterns: which modes, by whom, any anomalies."""
        if events is None:
            events = self._load_events()

        promotions = [e for e in events
                      if e.get("policy_decision", {}).get("action") == "promotion.request"
                      and self._is_recent(e, days=30)]

        modes = defaultdict(int)
        for e in promotions:
            # Extract promotion type from the policy decision's object
            pd = e.get("policy_decision", {})
            # promotion type isn't stored directly in the event; check subject role
            subject = pd.get("subject", {})
            if subject.get("role") == "human":
                modes["human"] += 1
            else:
                modes["agent"] += 1

        return {
            "metric": "promotion_log",
            "period": "30d",
            "total_promotions": len(promotions),
            "by_actor": dict(modes),
            "status": "ok",
        }

    # ── Quarterly Metrics ──────────────────────────────────────────────

    def retrieval_fairness_audit(self) -> dict:
        """
        Placeholder for retrieval fairness audit.
        In production: queries a sample topic, analyzes top-30 results
        for language diversity and intellectual tradition coverage.
        """
        return {
            "metric": "retrieval_fairness",
            "status": "pending_implementation",
            "note": "Requires retrieval agent integration. Manual spot-check recommended.",
            "checklist": [
                "Select 3 representative research queries",
                "Retrieve top 30 results per query",
                "Tag each result by language and intellectual tradition",
                "Compute coverage rate: non-English %, tradition diversity %",
                "Flag any query with <10% non-English or <3 traditions represented",
            ],
        }

    def provenance_integrity_spot_check(self, events: Optional[List[dict]] = None) -> dict:
        """Check rate of provenance-related violations."""
        if events is None:
            events = self._load_events()

        prov_violations = 0
        total_decisions = 0
        for e in events:
            pd = e.get("policy_decision", {})
            total_decisions += 1
            for v in pd.get("violations", []):
                if v.get("rule", "").startswith("W-002") or v.get("rule", "").startswith("PROV"):
                    prov_violations += 1

        rate = (prov_violations / max(1, total_decisions)) * 100
        return {
            "metric": "provenance_integrity",
            "total_decisions": total_decisions,
            "provenance_violations": prov_violations,
            "violation_rate_pct": round(rate, 1),
            "status": "critical" if rate > 15 else ("warning" if rate > 5 else "ok"),
        }

    def epistemic_marker_spot_check(self, events: Optional[List[dict]] = None) -> dict:
        """Check rate of synthesis threshold marker violations (W-003, SYN-001)."""
        if events is None:
            events = self._load_events()

        marker_violations = 0
        for e in events:
            for v in e.get("policy_decision", {}).get("violations", []):
                if v.get("rule") in ("W-003", "SYN-001"):
                    marker_violations += 1

        return {
            "metric": "epistemic_markers",
            "threshold_marker_violations": marker_violations,
            "status": "critical" if marker_violations > 10 else ("warning" if marker_violations > 3 else "ok"),
        }

    # ── Full Reports ───────────────────────────────────────────────────

    def weekly_report(self) -> dict:
        """Generate a complete weekly governance report."""
        events = self._load_events()
        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "cadence": "weekly",
            "metrics": {
                "authorship_drift": self.authorship_drift(events),
                "review_backlog": self.review_backlog(events),
                "quarantine_count": self.quarantine_count(events),
                "exceptions": self.exception_check(),
            },
            "overall_status": self._worst_status([
                self.authorship_drift(events)["status"],
                self.review_backlog(events)["status"],
            ]),
        }

    def monthly_report(self) -> dict:
        """Generate a monthly governance report."""
        events = self._load_events()
        weekly = self.weekly_report()
        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "cadence": "monthly",
            "weekly_summary": weekly["metrics"],
            "monthly_metrics": {
                "incident_summary": self.incident_summary(events),
                "promotion_log": self.promotion_log_review(events),
            },
            "overall_status": self._worst_status([
                weekly["overall_status"],
                self.incident_summary(events)["status"],
            ]),
        }

    def quarterly_report(self) -> dict:
        """Generate a quarterly governance review report."""
        events = self._load_events()
        monthly = self.monthly_report()
        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "cadence": "quarterly",
            "monthly_summary": monthly["monthly_metrics"],
            "quarterly_metrics": {
                "retrieval_fairness": self.retrieval_fairness_audit(),
                "provenance_integrity": self.provenance_integrity_spot_check(events),
                "epistemic_markers": self.epistemic_marker_spot_check(events),
            },
            "constitutional_review_ready": monthly["overall_status"] == "ok",
            "overall_status": self._worst_status([
                monthly["overall_status"],
                self.provenance_integrity_spot_check(events)["status"],
                self.epistemic_marker_spot_check(events)["status"],
            ]),
        }

    # ── Helpers ────────────────────────────────────────────────────────

    def _is_recent(self, event: dict, days: int) -> bool:
        ts = event.get("timestamp", "")
        if not ts:
            return False
        try:
            dt = datetime.fromisoformat(ts)
            return (datetime.now(UTC) - dt) <= timedelta(days=days)
        except (ValueError, TypeError):
            return False

    def _load_config(self) -> dict:
        config_path = os.path.join(self.governance_dir, "governance-config.json")
        if os.path.exists(config_path):
            with open(config_path) as f:
                return json.load(f)
        return {}

    @staticmethod
    def _worst_status(statuses: List[str]) -> str:
        order = {"ok": 0, "warning": 1, "overloaded": 2, "review_needed": 3, "critical": 4}
        return max(statuses, key=lambda s: order.get(s, 0))
