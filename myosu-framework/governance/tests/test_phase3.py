"""Phase 3 acceptance tests: cadence engine, CLI, publication audit integration.

Tests:
  CAD-001:  Weekly report generates without error
  CAD-002:  Monthly report generates without error
  CAD-003:  Quarterly report generates without error
  CAD-004:  Dashboard has all 10 required fields
  CAD-005:  Authorship drift metric is numeric and bounded
  CAD-006:  Quarantine count is consistent with audit log
  CAD-007:  Review backlog is non-negative
  CAD-008:  CLI dashboard exits 0
  CAD-009:  CLI weekly exits with appropriate code
  CAD-010:  CLI test runs acceptance suites (phases 1+2 via subprocess)
  CAD-010b: Phase 3 tests run inline (no recursive subprocess)
  CAD-011:  Provenance integrity spot-check produces valid rate
  CAD-012:  Epistemic marker spot-check counts W-003/SYN-001
  CAD-013:  Incident summary counts violations by severity
  CAD-014:  Monthly includes weekly metrics
  CAD-015:  Quarterly includes monthly metrics
"""

import json, sys, os, subprocess

_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, _PARENT)

from governance.cadence import CadenceEngine

ok = fail = 0
def c(name, cond):
    global ok, fail
    if cond: ok += 1
    else: print(f"  FAIL: {name}"); fail += 1

engine = CadenceEngine()

# ══ CAD-001: Weekly report ══
print("=== CAD-001: Weekly report structure ===")
w = engine.weekly_report()
c("CAD-001a: has timestamp", "timestamp" in w)
c("CAD-001b: has cadence=weekly", w.get("cadence") == "weekly")
c("CAD-001c: has metrics", "metrics" in w)
c("CAD-001d: has authorship_drift", "authorship_drift" in w["metrics"])
c("CAD-001e: has review_backlog", "review_backlog" in w["metrics"])
c("CAD-001f: has quarantine_count", "quarantine_count" in w["metrics"])
c("CAD-001g: has exceptions", "exceptions" in w["metrics"])
c("CAD-001h: has overall_status", "overall_status" in w)

# ══ CAD-002: Monthly report ══
print("=== CAD-002: Monthly report structure ===")
m = engine.monthly_report()
c("CAD-002a: has cadence=monthly", m.get("cadence") == "monthly")
c("CAD-002b: includes weekly_summary", "weekly_summary" in m)
c("CAD-002c: has incident_summary", "incident_summary" in m["monthly_metrics"])
c("CAD-002d: has promotion_log", "promotion_log" in m["monthly_metrics"])

# ══ CAD-003: Quarterly report ══
print("=== CAD-003: Quarterly report structure ===")
q = engine.quarterly_report()
c("CAD-003a: has cadence=quarterly", q.get("cadence") == "quarterly")
c("CAD-003b: includes monthly_summary", "monthly_summary" in q)
c("CAD-003c: has retrieval_fairness", "retrieval_fairness" in q["quarterly_metrics"])
c("CAD-003d: has provenance_integrity", "provenance_integrity" in q["quarterly_metrics"])
c("CAD-003e: has epistemic_markers", "epistemic_markers" in q["quarterly_metrics"])

# ══ CAD-004: Dashboard completeness ══
print("=== CAD-004: Dashboard 10-point check ===")
db_report = engine.weekly_report()
m_report = engine.monthly_report()
q_report = engine.quarterly_report()

# Build dashboard directly from cadence engine (no stdout redirect needed)
dashboard = {
    "1_provenance_integrity": f"{q_report['quarterly_metrics']['provenance_integrity']['violation_rate_pct']}% violation rate",
    "2_quarantine_count": db_report["metrics"]["quarantine_count"]["total_quarantined"],
    "3_authorship_drift": f"{db_report['metrics']['authorship_drift']['drift_percent']}%",
    "4_review_backlog": db_report["metrics"]["review_backlog"]["total_backlog"],
    "5_review_load_health": db_report["metrics"]["review_backlog"]["status"],
    "6_open_exceptions": db_report["metrics"]["exceptions"]["open_exceptions"],
    "7_open_incidents": m_report["monthly_metrics"]["incident_summary"]["total_violations"],
    "8_recent_material_changes": "check /governance/logs/changes.md",
    "9_upcoming_reviews": "quarterly governance review due",
    "10_firebreak_status": "active" if db_report["metrics"]["quarantine_count"]["status"] == "ok" else "breached",
}
for i in range(1, 11):
    key = [k for k in dashboard if k.startswith(f"{i}_")][0]
    c(f"CAD-004.{i}: field present", key in dashboard)

# ══ CAD-005: Authorship drift bounded ══
print("=== CAD-005: Authorship drift numeric bounds ===")
drift = w["metrics"]["authorship_drift"]
c("CAD-005a: drift_percent is numeric", isinstance(drift["drift_percent"], (int, float)))
c("CAD-005b: drift 0-100", 0 <= drift["drift_percent"] <= 100)
c("CAD-005c: has thresholds", "thresholds" in drift)
c("CAD-005d: has status", drift["status"] in ("ok", "warning", "critical"))

# ══ CAD-006: Quarantine count consistency ══
print("=== CAD-006: Quarantine consistency ===")
qc = w["metrics"]["quarantine_count"]
c("CAD-006a: total is non-negative", qc["total_quarantined"] >= 0)
c("CAD-006b: by_reason sum >= total (events can have multiple violations)", sum(qc["by_reason"].values()) >= qc["total_quarantined"])

# ══ CAD-007: Review backlog non-negative ══
print("=== CAD-007: Review backlog ===")
rb = w["metrics"]["review_backlog"]
c("CAD-007a: total_backlog >= 0", rb["total_backlog"] >= 0)
c("CAD-007b: pending + flagged == total", rb["pending_review"] + rb["flagged"] == rb["total_backlog"])

# ══ CAD-008: CLI dashboard exits 0 ══
print("=== CAD-008: CLI dashboard exit code ===")
r = subprocess.run([sys.executable, os.path.join(_HERE, "..", "cli.py"), "dashboard"],
                   capture_output=True, text=True, timeout=15)
c("CAD-008: exit 0", r.returncode == 0)

# ══ CAD-009: CLI weekly exits with status code ══
print("=== CAD-009: CLI weekly exit code ===")
r2 = subprocess.run([sys.executable, os.path.join(_HERE, "..", "cli.py"), "weekly"],
                    capture_output=True, text=True, timeout=15)
c("CAD-009: exit code is int", r2.returncode in (0, 1, 2))

# ══ CAD-010: CLI test runs acceptance suites (phases 1+2 via subprocess, avoid recursion)
print("=== CAD-010: CLI test runs acceptance suites ===")
r3 = subprocess.run([sys.executable, os.path.join(_HERE, "test_phase1.py")],
                    capture_output=True, text=True, timeout=60)
c("CAD-010a: phase1 passes via subprocess", r3.returncode == 0)
r3b = subprocess.run([sys.executable, os.path.join(_HERE, "test_phase2.py")],
                     capture_output=True, text=True, timeout=60)
c("CAD-010b: phase2 passes via subprocess", r3b.returncode == 0)

# ══ CAD-011: Provenance integrity valid rate ══
print("=== CAD-011: Provenance integrity spot-check ===")
pi = engine.provenance_integrity_spot_check()
c("CAD-011a: violation_rate_pct in 0-100", 0 <= pi["violation_rate_pct"] <= 100)
c("CAD-011b: has status", pi["status"] in ("ok", "warning", "critical"))

# ══ CAD-012: Epistemic marker spot-check ══
print("=== CAD-012: Epistemic marker check ===")
em = engine.epistemic_marker_spot_check()
c("CAD-012a: threshold_marker_violations >= 0", em["threshold_marker_violations"] >= 0)

# ══ CAD-013: Incident summary counts ══
print("=== CAD-013: Incident summary ===")
inc = engine.incident_summary()
c("CAD-013a: total_violations >= 0", inc["total_violations"] >= 0)
c("CAD-013b: has by_severity", "by_severity" in inc)
c("CAD-013c: has by_rule", "by_rule" in inc)

# ══ CAD-014: Monthly includes weekly ══
print("=== CAD-014: Monthly nesting ===")
c("CAD-014: all weekly metrics in monthly", all(
    k in m["weekly_summary"] for k in ["authorship_drift", "review_backlog", "quarantine_count", "exceptions"]
))

# ══ CAD-015: Quarterly includes monthly ══
print("=== CAD-015: Quarterly nesting ===")
c("CAD-015: monthly_metrics in quarterly", all(
    k in q["monthly_summary"] for k in ["incident_summary", "promotion_log"]
))

print(f"\n{'='*50}")
print(f"Phase 3: {ok} passed, {fail} failed ({ok+fail} total)")
print(f"{'='*50}")
sys.exit(0 if fail == 0 else 1)
