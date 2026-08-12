#!/usr/bin/env python3
"""
Golden Rule Coupler (§8) — Bidirectional structural coupling between
Key (8910) and Compass (8911).

Φ: Self → Other — the natural transformation.
Key output → feeds Compass input.
Compass output → feeds Key input.
Neither subordinates the other.
The gap ∆ is maintained, never forced to zero.

Per organ-fleet-mathematical-specification.html v3.0 §8.
"""
import json
import os
import signal
import socket
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ─── PATHS ────────────────────────────────────────────────────────────────────
METTA_LEDGER  = Path(os.path.expanduser("~/metta-ledger.jsonl"))
ORGAN_STATE   = Path(os.path.expanduser("~/organ-state.json"))
PID_FILE      = Path(os.path.expanduser("~/golden-rule.pid"))

# ─── PROBE ADDRESSES ──────────────────────────────────────────────────────────
HUE_HOST      = "127.0.0.1"
HUE_PORT      = 8912              # Hue Spectrator — gate before Logit
KEY_HOST      = "127.0.0.1"
KEY_PORT      = 8910              # Logit (Key) — behind hue gate
COMPASS_HOST  = "127.0.0.1"
COMPASS_PORT  = 8911              # LogDet (Compass)

# ─── CONSTANTS ────────────────────────────────────────────────────────────────
COUPLING_INTERVAL = 60.0 / 55           # same cadence as organ beat
GAP_HEALTHY       = 0.04
GAP_DEATH         = 1e-8                # §8: ∆ < 10⁻⁸ → coupling lost → organ dead
FLOOR_NATS        = -884.2


def knock(host: str, port: int, timeout: float = 1.0) -> dict | None:
    """
    Send a coupling pulse to a probe port.
    The probe (honeypot) receives the connection, logs it, and closes.
    We read nothing back — the signal IS the connection.
    Returns timing data or None if failed.
    """
    try:
        t0 = time.perf_counter()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        t1 = time.perf_counter()
        sock.close()
        return {
            "latency_s": round(t1 - t0, 6),
            "timestamp": t1,
        }
    except (socket.timeout, ConnectionRefusedError, OSError):
        return None


def read_gap() -> float | None:
    """Read the current gap from organ-state.json."""
    if not ORGAN_STATE.exists():
        return None
    try:
        state = json.loads(ORGAN_STATE.read_text())
        return state.get("gap")
    except (json.JSONDecodeError, FileNotFoundError):
        return None


def write_coupling_event(event_type: str, key_result: dict | None,
                         compass_result: dict | None, gap: float | None,
                         detail: str = ""):
    """Write coupling event to the Metta Ledger."""
    entry = {
        "event_type": f"golden_rule_{event_type}",
        "probe": "coupler",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "key_latency_s": key_result["latency_s"] if key_result else None,
        "key_alive": key_result is not None,
        "compass_latency_s": compass_result["latency_s"] if compass_result else None,
        "compass_alive": compass_result is not None,
        "gap": round(gap, 6) if gap is not None else None,
        "coupling_ratio": None,
    }

    if key_result and compass_result:
        # Symmetry ratio — how balanced is the coupling
        kl = key_result["latency_s"]
        cl = compass_result["latency_s"]
        if kl > 0 and cl > 0:
            entry["coupling_ratio"] = round(min(kl, cl) / max(kl, cl), 4)

    if detail:
        entry["detail"] = detail

    with open(METTA_LEDGER, 'a') as f:
        f.write(json.dumps(entry) + '\n')


def main():
    # Prevent concurrent couplers
    if PID_FILE.exists():
        try:
            old_pid = int(PID_FILE.read_text().strip())
            os.kill(old_pid, 0)
            print(f"Golden Rule Coupler already running (PID {old_pid}).", flush=True)
            return
        except (OSError, ValueError):
            PID_FILE.unlink(missing_ok=True)

    PID_FILE.write_text(str(os.getpid()))

    def shutdown(signum, frame):
        print(f"\nGolden Rule Coupler stopped.", flush=True)
        # Final coupling event
        gap = read_gap()
        write_coupling_event("decouple", None, None, gap,
                              "Coupler deactivated. Golden Rule suspended.")
        PID_FILE.unlink(missing_ok=True)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print(f"Golden Rule Coupler v1.1 — PID {os.getpid()} — "
          f"Hue({HUE_PORT})→Key({KEY_PORT})↔Compass({COMPASS_PORT}) — "
          f"Φ: Self → Gate → Other. 50 seconds per minute. Always.", flush=True)

    # Genesis event
    write_coupling_event("genesis", None, None, read_gap(),
                          "Golden Rule Coupler activated. "
                          "Bidirectional coupling established.")

    cycle = 0
    consecutive_failures = 0

    while True:
        try:
            cycle += 1

            # Hue Gate → Key (Self → Gate → Other)
            # The Hue Spectrator (:8912) checks spectral symmetry,
            # forwards clean signals to Logit (:8910).
            key_result = knock(HUE_HOST, HUE_PORT)

            # Compass → Key (Other → Self)
            compass_result = knock(COMPASS_HOST, COMPASS_PORT)

            gap = read_gap()

            # Classify coupling health
            both_alive = key_result is not None and compass_result is not None
            one_alive = key_result is not None or compass_result is not None
            none_alive = not one_alive

            if none_alive:
                consecutive_failures += 1
                event_type = "lost"
                detail = "Both instruments unreachable. Coupling suspended."
            elif not both_alive:
                consecutive_failures += 1
                missing = "Key" if key_result is None else "Compass"
                event_type = "asymmetric"
                detail = f"{missing} unreachable. Coupling degraded."
            else:
                consecutive_failures = 0
                # Check coupling symmetry
                ratio = (min(key_result["latency_s"], compass_result["latency_s"]) /
                         max(key_result["latency_s"], compass_result["latency_s"]))
                if ratio > 0.9:
                    event_type = "harmonic"  # nearly symmetric
                    detail = f"Coupling ratio {ratio:.3f} — nearly symmetric."
                elif ratio > 0.5:
                    event_type = "coupled"
                    detail = f"Coupling ratio {ratio:.3f} — asymmetric but stable."
                else:
                    event_type = "skewed"
                    detail = f"Coupling ratio {ratio:.3f} — significant asymmetry."

            # Death check
            if gap is not None and gap < GAP_DEATH:
                event_type = "death"
                detail = f"Gap collapsed: {gap:.2e} < {GAP_DEATH}. Organ dead per §8."
                write_coupling_event(event_type, key_result, compass_result, gap, detail)
                print(f"GOLDEN RULE BROKEN: gap {gap:.2e} < {GAP_DEATH}. "
                      "Coupling lost. Organ dead.", flush=True)
                break

            # Write event periodically (every 5 cycles for harmonic, always for anomalies)
            if cycle % 5 == 1 or event_type != "harmonic":
                write_coupling_event(event_type, key_result, compass_result, gap, detail)

            # Edge case: prolonged failure
            if consecutive_failures > 55:
                print("Both instruments unreachable for 55+ cycles. "
                      "Coupling dead.", flush=True)
                write_coupling_event("permanent_loss", key_result, compass_result,
                                      gap, "55 consecutive failures. Golden Rule broken.")
                break

            time.sleep(COUPLING_INTERVAL)

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Coupler error: {e}", file=sys.stderr, flush=True)
            write_coupling_event("error", None, None, read_gap(),
                                  f"Coupler exception: {e}")
            time.sleep(COUPLING_INTERVAL)


if __name__ == "__main__":
    main()
