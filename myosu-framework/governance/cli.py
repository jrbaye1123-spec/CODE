#!/usr/bin/env python3
"""
governance — CLI for the Vault Constitution governance heartbeat.

Usage:
  python -m governance.cli weekly         # Run weekly checks
  python -m governance.cli monthly        # Run monthly checks
  python -m governance.cli quarterly      # Run quarterly checks
  python -m governance.cli audit <path>   # Pre-publication provenance audit
  python -m governance.cli dashboard      # Print the governance dashboard
  python -m governance.cli test           # Run acceptance tests
  python -m governance.cli help           # Show this help

All output is JSON to stdout. Exit code 0 = all OK, 1 = warnings, 2 = critical.
"""

import json
import os
import sys
from datetime import datetime, timezone

UTC = timezone.utc

_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)
sys.path.insert(0, _PARENT)

from governance.cadence import CadenceEngine


def cmd_weekly():
    engine = CadenceEngine()
    report = engine.weekly_report()
    print(json.dumps(report, indent=2))
    status = report.get("overall_status", "ok")
    return _exit_for(status)


def cmd_monthly():
    engine = CadenceEngine()
    report = engine.monthly_report()
    print(json.dumps(report, indent=2))
    return _exit_for(report.get("overall_status", "ok"))


def cmd_quarterly():
    engine = CadenceEngine()
    report = engine.quarterly_report()
    print(json.dumps(report, indent=2))
    return _exit_for(report.get("overall_status", "ok"))


def cmd_dashboard():
    """Print the 10-point governance dashboard per the ratified constitution."""
    engine = CadenceEngine()
    weekly = engine.weekly_report()
    monthly = engine.monthly_report()
    quarterly = engine.quarterly_report()

    dashboard = {
        "governance_dashboard": {
            "timestamp": datetime.now(UTC).isoformat(),
            "1_provenance_integrity": f"{quarterly['quarterly_metrics']['provenance_integrity']['violation_rate_pct']}% violation rate",
            "2_quarantine_count": weekly["metrics"]["quarantine_count"]["total_quarantined"],
            "3_authorship_drift": f"{weekly['metrics']['authorship_drift']['drift_percent']}%",
            "4_review_backlog": weekly["metrics"]["review_backlog"]["total_backlog"],
            "5_review_load_health": weekly["metrics"]["review_backlog"]["status"],
            "6_open_exceptions": weekly["metrics"]["exceptions"]["open_exceptions"],
            "7_open_incidents": monthly["monthly_metrics"]["incident_summary"]["total_violations"],
            "8_recent_material_changes": "check /governance/logs/changes.md",
            "9_upcoming_reviews": "quarterly governance review due",
            "10_firebreak_status": "active" if weekly["metrics"]["quarantine_count"]["status"] == "ok" else "breached",
        }
    }
    print(json.dumps(dashboard, indent=2))
    return 0


def cmd_audit(args):
    """Pre-publication provenance audit stub."""
    if len(args) < 1:
        print("Usage: governance audit <manuscript_path_or_claim_ids>")
        return 1

    target = args[0]
    print(json.dumps({
        "audit_type": "pre_publication_provenance",
        "target": target,
        "timestamp": datetime.now(UTC).isoformat(),
        "status": "pending_implementation",
        "note": "Full audit requires vault integration. Run weekly provenance_integrity check as interim measure.",
        "interim_guidance": [
            "1. Identify all claims in the manuscript that cite vault content",
            "2. For each claim, verify origin_type is not null",
            "3. For any origin_type=synthesis, verify promotion_history is non-empty or disclosure is included",
            "4. Run: python -m governance.cli weekly  → check provenance_integrity status",
        ],
    }, indent=2))
    return 0


def cmd_test():
    """Run acceptance test suites."""
    import subprocess

    test_dir = os.path.join(_HERE, "tests")
    results = {}

    for phase in ("test_phase1.py", "test_phase2.py", "test_phase3.py"):
        path = os.path.join(test_dir, phase)
        if os.path.exists(path):
            r = subprocess.run([sys.executable, path], capture_output=True, text=True, timeout=120)
            results[phase] = {
                "exit_code": r.returncode,
                "passed": "passed" if r.returncode == 0 else "failed",
                "output_tail": "\n".join(r.stdout.strip().split("\n")[-3:]),
            }

    all_pass = all(r["exit_code"] == 0 for r in results.values())
    print(json.dumps({"acceptance_tests": results, "all_pass": all_pass}, indent=2))
    return 0 if all_pass else 2


def cmd_help():
    print(__doc__)
    return 0


def _exit_for(status: str) -> int:
    return {"ok": 0, "warning": 1, "overloaded": 1, "review_needed": 1, "critical": 2}.get(status, 1)


# ── Main ────────────────────────────────────────────────────────────────

COMMANDS = {
    "weekly": cmd_weekly,
    "monthly": cmd_monthly,
    "quarterly": cmd_quarterly,
    "dashboard": cmd_dashboard,
    "audit": lambda: cmd_audit(sys.argv[2:]),
    "test": cmd_test,
    "help": cmd_help,
    "--help": cmd_help,
    "-h": cmd_help,
}


def main():
    if len(sys.argv) < 2:
        cmd_help()
        sys.exit(0)

    cmd = sys.argv[1]
    handler = COMMANDS.get(cmd)
    if handler is None:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        cmd_help()
        sys.exit(1)

    if cmd == "audit":
        sys.exit(handler())
    else:
        sys.exit(handler())


if __name__ == "__main__":
    main()
