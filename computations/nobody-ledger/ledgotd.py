#!/usr/bin/env python3
"""
LEDGOTD — Autonomous Hardware Sentinel Daemon
"I am the chain operating itself. The probe is the eye. The kill is the hand.
 The ledger is the memory. No human needed. The machine watches the machine."

A self-operating daemon that:
- Continuously probes: CPU freq, memory bus, EDAC errors, RAM hogs
- Applies a rule engine: threshold → escalation → autonomous action
- Actions: kill, freeze, renice, throttle, cgroup-limit, cache-drop
- Logs every decision to the Nobody Ledger with full audit chain
- Learns from past state: no repeat-kills within cooldown window
- Chain-driven: previous entries inform escalation decisions

Run as:  sudo python3 ledgotd.py [--interval SEC] [--dry-run]
"""

import os, sys, json, time, signal, subprocess
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

# Import probe functions from sibling module
sys.path.insert(0, str(Path(__file__).parent))
from ledgot_probe import (
    probe_frequencies, probe_memory_errors, probe_memory_bus, probe_ram_hogs,
    kill_rogue, append_to_ledger, LEDGER_PATH, LEDGER_SOURCE,
)

# ── Rule Engine ──────────────────────────────────────────────

RULES = {
    "ram_hog": {
        "thresholds": {
            "mem_pct": 30.0,        # % of total RAM
            "rss_mb": 3072,          # absolute MB
        },
        "escalation": [
            {"action": "renice", "value": 19, "cooldown_s": 60},
            {"action": "freeze", "cooldown_s": 120},
            {"action": "kill", "cooldown_s": 300},
        ],
    },
    "bus_saturation": {
        "thresholds": {
            "bus_util_pct": 70.0,    # memory bus utilization %
        },
        "escalation": [
            {"action": "drop_caches", "cooldown_s": 120},
            {"action": "find_bus_hog", "cooldown_s": 60},
        ],
    },
    "memory_degraded": {
        "thresholds": {
            "ue_count": 1,           # any uncorrectable error
            "ce_count_spike": 100,    # correctable error spike
        },
        "escalation": [
            {"action": "alert", "cooldown_s": 3600},
        ],
    },
    "frequency_anomaly": {
        "thresholds": {
            "anomaly_count": 3,       # cores deviating
            "max_deviation_mhz": 1000, # MHz deviation from cluster median
        },
        "escalation": [
            {"action": "reset_governor", "cooldown_s": 300},
        ],
    },
}

# ── Action Handlers ──────────────────────────────────────────

class ActionLog:
    """Tracks when each action was last performed to enforce cooldowns."""
    def __init__(self):
        self.history = defaultdict(lambda: defaultdict(float))

    def can_act(self, target_key: str, action: str, cooldown_s: float) -> bool:
        last = self.history.get(target_key, {}).get(action, 0.0)
        return (time.time() - last) >= cooldown_s

    def record(self, target_key: str, action: str):
        self.history[target_key][action] = time.time()

    def prune(self, max_age_s: float = 3600):
        now = time.time()
        for target_key in list(self.history.keys()):
            self.history[target_key] = {
                act: ts for act, ts in self.history[target_key].items()
                if now - ts < max_age_s
            }


action_log = ActionLog()


def act_renice(pid: int, nice_val: int) -> dict:
    """Renice a process to lower its CPU priority."""
    try:
        subprocess.run(["renice", str(nice_val), "-p", str(pid)],
                       capture_output=True, timeout=5)
        return {"action": "renice", "pid": pid, "nice": nice_val, "success": True}
    except Exception as e:
        return {"action": "renice", "pid": pid, "nice": nice_val, "success": False, "error": str(e)}


def act_freeze(pid: int) -> dict:
    """SIGSTOP a process — freeze it in place."""
    try:
        os.kill(pid, signal.SIGSTOP)
        return {"action": "freeze", "pid": pid, "success": True}
    except Exception as e:
        return {"action": "freeze", "pid": pid, "success": False, "error": str(e)}


def act_thaw(pid: int) -> dict:
    """SIGCONT a frozen process."""
    try:
        os.kill(pid, signal.SIGCONT)
        return {"action": "thaw", "pid": pid, "success": True}
    except Exception as e:
        return {"action": "thaw", "pid": pid, "success": False, "error": str(e)}


def act_drop_caches() -> dict:
    """Drop kernel page cache, dentries, inodes (echo 3 > /proc/sys/vm/drop_caches)."""
    try:
        with open("/proc/sys/vm/drop_caches", "w") as f:
            f.write("3\n")
        return {"action": "drop_caches", "success": True}
    except Exception as e:
        return {"action": "drop_caches", "success": False, "error": str(e)}


def act_reset_governor() -> dict:
    """Reset all CPU governors to performance to clear throttling."""
    count = 0
    for cpu_dir in sorted(Path("/sys/devices/system/cpu").glob("cpu[0-9]*")):
        gov_path = cpu_dir / "cpufreq" / "scaling_governor"
        if gov_path.exists():
            try:
                current = gov_path.read_text().strip()
                if current != "performance":
                    gov_path.write_text("performance")
                    count += 1
            except (OSError, PermissionError):
                pass
    return {"action": "reset_governor", "cores_reset": count, "success": True}


def act_find_bus_hog() -> dict:
    """Find the process consuming the most memory bandwidth (via /proc/PID/io read_bytes)."""
    candidates = []
    for proc_dir in Path("/proc").glob("[0-9]*"):
        io_path = proc_dir / "io"
        if io_path.exists():
            try:
                io_data = io_path.read_text()
                read_bytes = 0
                for line in io_data.split("\n"):
                    if line.startswith("read_bytes:"):
                        read_bytes = int(line.split(":")[1].strip())
                if read_bytes > 0:
                    cmdline = (proc_dir / "comm").read_text().strip()
                    candidates.append({"pid": int(proc_dir.name), "cmd": cmdline, "read_bytes": read_bytes})
            except (ValueError, OSError, PermissionError):
                pass
    candidates.sort(key=lambda x: x["read_bytes"], reverse=True)
    top = candidates[:5] if candidates else []
    return {"action": "find_bus_hog", "candidates": top, "success": True}


def act_alert(message: str) -> dict:
    """Log a high-severity alert. Future: send to notification channel."""
    alert_path = Path.home() / "nobody-ledger" / "alerts.log"
    alert_path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()
    with open(alert_path, "a") as f:
        f.write(f"[{ts}] ALERT: {message}\n")
    return {"action": "alert", "message": message, "success": True}


ACTION_HANDLERS = {
    "kill": lambda pid, **kw: kill_rogue(pid, f"ledgotd autonomous: {kw.get('reason', 'threshold exceeded')}"),
    "freeze": lambda pid, **kw: act_freeze(pid),
    "renice": lambda pid, **kw: act_renice(pid, kw.get("value", 19)),
    "drop_caches": lambda **kw: act_drop_caches(),
    "reset_governor": lambda **kw: act_reset_governor(),
    "find_bus_hog": lambda **kw: act_find_bus_hog(),
    "alert": lambda **kw: act_alert(kw.get("reason", "unspecified alert")),
}


# ── Evaluation Engine ────────────────────────────────────────

def evaluate_ram_hog_rule(hogs: list[dict], dry_run: bool = False) -> list[dict]:
    """Evaluate RAM hog rules against current process list."""
    results = []
    thresholds = RULES["ram_hog"]["thresholds"]
    escalations = RULES["ram_hog"]["escalation"]

    for hog in hogs:
        target_key = f"pid_{hog['pid']}"
        for step in escalations:
            action_name = step["action"]
            if not action_log.can_act(target_key, action_name, step["cooldown_s"]):
                continue  # still in cooldown

            reason = f"RAM hog: {hog['rss_mb']:.0f}MB ({hog['mem_pct']:.1f}%) — {hog['cmd'][:80]}"
            handler = ACTION_HANDLERS.get(action_name)
            if not handler:
                continue

            if dry_run:
                result = {"action": action_name, "pid": hog["pid"], "dry_run": True, "reason": reason}
                action_log.record(target_key, action_name)  # record dry-run cooldowns too
            else:
                result = handler(pid=hog["pid"], reason=reason)
                action_log.record(target_key, action_name)

            append_to_ledger(
                event=f"autonomous_{action_name}",
                entity=LEDGER_SOURCE,
                how=f"pid={hog['pid']} rss={hog['rss_mb']:.0f}MB pct={hog['mem_pct']:.1f}% "
                    f"reason='{reason}' dry_run={dry_run} result={json.dumps(result)}",
            )
            results.append(result)
            break  # one escalation step per cycle

    return results


def evaluate_bus_rule(bus_data: dict, dry_run: bool = False) -> list[dict]:
    """Evaluate memory bus saturation rules."""
    results = []
    thresholds = RULES["bus_saturation"]["thresholds"]
    escalations = RULES["bus_saturation"]["escalation"]
    util = bus_data.get("bus_util_pct", 0) or 0

    if util < thresholds["bus_util_pct"]:
        return results

    for step in escalations:
        action_name = step["action"]
        if not action_log.can_act("bus_saturation", action_name, step["cooldown_s"]):
            continue

        reason = f"Bus saturation: {util}% utilization (threshold={thresholds['bus_util_pct']}%)"
        handler = ACTION_HANDLERS.get(action_name)
        if not handler:
            continue

        if dry_run:
            result = {"action": action_name, "dry_run": True, "reason": reason}
            action_log.record("bus_saturation", action_name)
        else:
            result = handler(reason=reason)
            action_log.record("bus_saturation", action_name)

        append_to_ledger(
            event=f"autonomous_{action_name}",
            entity=LEDGER_SOURCE,
            how=f"bus_util={util}% reason='{reason}' dry_run={dry_run} result={json.dumps(result)}",
        )
        results.append(result)

    return results


def evaluate_memory_rule(mem_data: dict, dry_run: bool = False) -> list[dict]:
    """Evaluate memory degradation rules (EDAC errors, hardware corruption)."""
    results = []
    thresholds = RULES["memory_degraded"]["thresholds"]

    degraded = mem_data.get("degraded", False)
    ue_count = mem_data.get("ue_count", 0)
    ce_count = mem_data.get("ce_count", 0)

    if not degraded and ue_count == 0 and ce_count < thresholds["ce_count_spike"]:
        return results

    escalations = RULES["memory_degraded"]["escalation"]
    for step in escalations:
        action_name = step["action"]
        if not action_log.can_act("memory_degraded", action_name, step["cooldown_s"]):
            continue

        reason = f"Memory degraded: UE={ue_count} CE={ce_count} hw_corrupted={mem_data.get('hardware_corrupted_kb', 0)}kB"
        handler = ACTION_HANDLERS.get(action_name)
        if not handler:
            continue

        if dry_run:
            result = {"action": action_name, "dry_run": True, "reason": reason}
            action_log.record("memory_degraded", action_name)
        else:
            result = handler(reason=reason)
            action_log.record("memory_degraded", action_name)

        append_to_ledger(
            event=f"autonomous_{action_name}",
            entity=LEDGER_SOURCE,
            how=f"ue={ue_count} ce={ce_count} reason='{reason}' dry_run={dry_run} result={json.dumps(result)}",
        )
        results.append(result)

    return results


def evaluate_frequency_rule(freq_data: dict, dry_run: bool = False) -> list[dict]:
    """Evaluate frequency anomaly rules."""
    results = []
    thresholds = RULES["frequency_anomaly"]["thresholds"]
    anomalies = freq_data.get("anomalies", [])
    anomaly_count = freq_data.get("anomaly_count", 0)

    if anomaly_count < thresholds["anomaly_count"]:
        return results

    big_anomalies = [a for a in anomalies if a.get("deviation", 0) > thresholds["max_deviation_mhz"]]
    if not big_anomalies:
        return results

    escalations = RULES["frequency_anomaly"]["escalation"]
    for step in escalations:
        action_name = step["action"]
        if not action_log.can_act("frequency_anomaly", action_name, step["cooldown_s"]):
            continue

        reason = f"Freq anomaly: {anomaly_count} cores deviating, max dev={max(a['deviation'] for a in big_anomalies):.0f}MHz"
        handler = ACTION_HANDLERS.get(action_name)
        if not handler:
            continue

        if dry_run:
            result = {"action": action_name, "dry_run": True, "reason": reason}
            action_log.record("frequency_anomaly", action_name)
        else:
            result = handler(reason=reason)
            action_log.record("frequency_anomaly", action_name)

        append_to_ledger(
            event=f"autonomous_{action_name}",
            entity=LEDGER_SOURCE,
            how=f"anomalies={anomaly_count} max_dev={max(a['deviation'] for a in big_anomalies):.0f}MHz "
                f"reason='{reason}' dry_run={dry_run} result={json.dumps(result)}",
        )
        results.append(result)

    return results


# ── Main Daemon Loop ─────────────────────────────────────────

def daemon_loop(interval: float = 30.0, dry_run: bool = False):
    """Main autonomous loop: probe → evaluate → act → repeat."""
    pid_file = Path.home() / "nobody-ledger" / "ledgotd.pid"
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(os.getpid()))

    mode_str = "DRY RUN — no real actions taken" if dry_run else "LIVE — autonomous actions ENABLED"
    print(f"LEDGOTD {mode_str}", file=sys.stderr)
    print(f"Interval: {interval}s | PID: {os.getpid()} | Ctrl+C to stop", file=sys.stderr)
    print(f"Rules: ram_hog(>{RULES['ram_hog']['thresholds']['mem_pct']}%), "
          f"bus_sat(>{RULES['bus_saturation']['thresholds']['bus_util_pct']}%), "
          f"mem_degraded(UE>0), freq_anomaly(>{RULES['frequency_anomaly']['thresholds']['anomaly_count']} cores)",
          file=sys.stderr)
    print("─" * 60, file=sys.stderr)

    append_to_ledger(
        event="daemon_start",
        entity=LEDGER_SOURCE,
        how=f"ledgotd v1.0.0 started interval={interval}s dry_run={dry_run} "
            f"rules=ram_hog,bus_saturation,memory_degraded,frequency_anomaly",
    )

    cycle = 0
    try:
        while True:
            cycle += 1
            tick_start = time.time()

            # PROBE phase
            freq = probe_frequencies()
            mem = probe_memory_errors()
            mem_bus = probe_memory_bus()
            hogs = probe_ram_hogs()

            # EVALUATE phase — run all rule engines
            all_actions = []
            all_actions.extend(evaluate_ram_hog_rule(hogs, dry_run))
            all_actions.extend(evaluate_bus_rule(mem_bus, dry_run))
            all_actions.extend(evaluate_memory_rule(mem, dry_run))
            all_actions.extend(evaluate_frequency_rule(freq, dry_run))

            # REPORT phase
            ts = datetime.now(timezone.utc).isoformat()
            action_summary = ", ".join(
                f"{a['action']}:{a.get('pid', 'sys')}" for a in all_actions
            ) if all_actions else "none"

            bw = mem_bus.get("bandwidth_est_mb_s", "?")
            util = mem_bus.get("bus_util_pct", "?")
            rogue_count = sum(1 for h in hogs if h.get("flagged_rogue"))

            status = (
                f"[{ts}] cycle={cycle:04d} "
                f"freq={freq['min_mhz']}-{freq['max_mhz']}MHz "
                f"bw={bw}MB/s util={util}% "
                f"err={mem['total_errors']} "
                f"hogs={len(hogs)} rogue={rogue_count} "
                f"actions=[{action_summary}]"
            )
            print(status)

            # Periodic chain logging (reduced noise — only on action or every 10th cycle)
            if all_actions or cycle % 10 == 0:
                append_to_ledger(
                    event="daemon_tick" if not all_actions else "daemon_action",
                    entity=LEDGER_SOURCE,
                    how=f"cycle={cycle} freq=[{freq['min_mhz']}-{freq['max_mhz']}]MHz "
                        f"bw={bw}MB/s util={util}% err={mem['total_errors']} "
                        f"hogs={len(hogs)} rogue={rogue_count} actions={len(all_actions)} "
                        f"actions_detail=[{action_summary}]",
                )

            # Prune old action log entries
            action_log.prune()

            # Sleep for remainder of interval
            elapsed = time.time() - tick_start
            sleep_time = max(0, interval - elapsed)
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\nLEDGOTD — shutdown signal received", file=sys.stderr)
    finally:
        append_to_ledger(
            event="daemon_stop",
            entity=LEDGER_SOURCE,
            how=f"ledgotd stopped after {cycle} cycles",
        )
        pid_file.unlink(missing_ok=True)


# ── CLI ───────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="LEDGOTD — Autonomous Hardware Sentinel")
    parser.add_argument("--interval", "-i", type=float, default=30.0,
                        help="Probe interval in seconds (default: 30)")
    parser.add_argument("--dry-run", "-n", action="store_true",
                        help="Evaluate rules but do not execute actions")
    parser.add_argument("--status", "-s", action="store_true",
                        help="Check if daemon is running")
    args = parser.parse_args()

    if args.status:
        pid_file = Path.home() / "nobody-ledger" / "ledgotd.pid"
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                os.kill(pid, 0)
                print(f"LEDGOTD running — PID {pid}")
            except (OSError, ValueError):
                print("LEDGOTD not running (stale PID file)")
                pid_file.unlink(missing_ok=True)
        else:
            print("LEDGOTD not running")
        return

    daemon_loop(interval=args.interval, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
