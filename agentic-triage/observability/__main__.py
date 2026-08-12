"""Standalone observability — python -m observability [check|verify]"""
from . import daily_health_check, IndexHealthMonitor
import sys

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "dashboard"
    if cmd == "check":
        result = daily_health_check()
        IndexHealthMonitor().print_dashboard()
        if result["snapshot"]["eligibility_rate"] < 0.95 and result["snapshot"]["active_exceptions"] == 0:
            sys.exit(1)
        elif result["snapshot"]["gate_status"] == "paused":
            sys.exit(1)
    elif cmd == "verify":
        m = IndexHealthMonitor()
        v = m.verify_audit_chain()
        if not v["verified"]:
            for f in v["failures"]:
                print(f)
            sys.exit(1)
        print(f"Chain VERIFIED — {v['entries']} entries")
    else:
        daily_health_check()
        IndexHealthMonitor().print_dashboard()
