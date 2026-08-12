#!/usr/bin/env python3
"""
Metta Probe — Witness Instrument (§7).
Queries the Organ's gap state, classifies events, writes immutable witness
entries to the Metta Ledger. Radiates peace when the gap is healthy.

Per organ-fleet-mathematical-specification.html v3.0 §7.
"""
import json
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ─── PATHS ────────────────────────────────────────────────────────────────────
METTA_LEDGER   = Path(os.path.expanduser("~/metta-ledger.jsonl"))
ORGAN_STATE    = Path(os.path.expanduser("~/organ-state.json"))
PID_FILE       = Path(os.path.expanduser("~/witness-fleet.pid"))

# ─── CONSTANTS ────────────────────────────────────────────────────────────────
GAP_HEALTHY      = 0.04
GAP_ALIVE_MAX    = 0.015                          # |∆ − 0.04| < 0.015 = ALIVE
POLL_INTERVAL    = 60.0 / 55                       # same cadence as organ
HISTORY_WINDOW   = 30                              # beats for trend detection

# Trend thresholds
DRIFT_THRESHOLD  = 0.0005                          # per-beat drift flags disturbance
SPIKE_THRESHOLD  = 0.005                           # single-beat jump flags deception

# ─── EVENT TYPES (§7) ─────────────────────────────────────────────────────────
# disturbance — gap drifting outside healthy band
# deception   — abrupt gap spike (potential falsification)
# peace       — gap healthy, stable, all instruments nominal
# witness     — periodic attestation (every 55 beats)
# calibration — gap returned to healthy band
# nullify     — gap death or organ halt detected
# genesis     — probe startup


class WitnessProbe:
    """§7: Queries organ state, classifies gap events, writes to ledger."""

    def __init__(self):
        self.gap_history: list[float] = []
        self.last_event_type = None
        self.beats_since_peace = 0
        self.witness_counter = 0
        self.start_time = time.time()
        self.prev_gap = None
        self.was_unhealthy = False

    def read_organ_state(self) -> dict | None:
        """Read current organ state from organ-state.json."""
        if not ORGAN_STATE.exists():
            return None
        try:
            return json.loads(ORGAN_STATE.read_text())
        except (json.JSONDecodeError, FileNotFoundError):
            return None

    def read_last_ledger_beat(self) -> int:
        """Get the most recent beat number from the metta ledger."""
        if not METTA_LEDGER.exists():
            return 0
        try:
            # Seek to end, scan backward for last line with 'beat' field
            with open(METTA_LEDGER, 'rb') as f:
                f.seek(0, 2)  # end
                size = f.tell()
                if size < 2:
                    return 0
                # Read last 4KB for speed
                chunk_start = max(0, size - 4096)
                f.seek(chunk_start)
                lines = f.read().decode('utf-8', errors='replace').strip().split('\n')
                for line in reversed(lines):
                    if not line.strip():
                        continue
                    try:
                        entry = json.loads(line)
                        if 'beat' in entry:
                            return entry['beat']
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass
        return 0

    def classify(self, gap: float, prev_gap: float | None) -> str:
        """Classify the gap state into a witness event type."""
        deviation = abs(gap - GAP_HEALTHY)

        # Death detection
        if gap <= 5e-4:
            return "nullify"

        # Spike detection (deception)
        if prev_gap is not None:
            jump = abs(gap - prev_gap)
            if jump > SPIKE_THRESHOLD:
                return "deception"

        # Healthy = peace
        if deviation < GAP_ALIVE_MAX:
            return "peace"

        # Drift detection (disturbance)
        if len(self.gap_history) >= 5:
            recent = self.gap_history[-5:]
            drift_rate = (recent[-1] - recent[0]) / len(recent)
            if abs(drift_rate) > DRIFT_THRESHOLD:
                return "disturbance"

        # Unhealthy but not drifting fast
        return "witness"

    def write_event(self, event_type: str, gap: float, beat: int,
                     detail: str = ""):
        """Write immutable witness entry to the Metta Ledger (§7.4)."""
        entry = {
            "event_type": event_type,
            "probe": "witness",
            "port": 8912,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "gap": round(gap, 6),
            "gap_health": "ALIVE" if abs(gap - GAP_HEALTHY) < GAP_ALIVE_MAX
                          else ("NARROW" if gap < GAP_HEALTHY else "WIDE"),
            "organ_beat": beat,
            "witness_uptime_s": round(time.time() - self.start_time, 1),
        }
        if detail:
            entry["detail"] = detail

        with open(METTA_LEDGER, 'a') as f:
            f.write(json.dumps(entry) + '\n')

    def run(self):
        """Main witness loop — poll organ state, classify, write events."""
        self.write_event("genesis", GAP_HEALTHY, 0,
                          "Witness Probe activated. Watching the gap.")

        last_beat = self.read_last_ledger_beat()
        last_event_beat = last_beat
        peace_since = 0
        calibration_logged = False

        while True:
            try:
                state = self.read_organ_state()

                if state is None:
                    time.sleep(POLL_INTERVAL)
                    continue

                gap = state.get("gap", GAP_HEALTHY)
                beat = state.get("beat", 0)

                # Only process new beats
                if beat <= last_beat:
                    time.sleep(POLL_INTERVAL * 0.5)
                    continue

                last_beat = beat

                # Track gap history
                self.gap_history.append(gap)
                if len(self.gap_history) > HISTORY_WINDOW:
                    self.gap_history.pop(0)

                # Classify
                event_type = self.classify(gap, self.prev_gap)

                # Was unhealthy, now healthy → calibration
                deviation = abs(gap - GAP_HEALTHY)
                is_healthy = deviation < GAP_ALIVE_MAX

                if is_healthy and self.was_unhealthy and not calibration_logged:
                    event_type = "calibration"
                    calibration_logged = True
                elif not is_healthy:
                    calibration_logged = False

                self.was_unhealthy = not is_healthy

                # Peace counting
                if event_type == "peace":
                    peace_since += 1
                else:
                    peace_since = 0

                # Witness attestation every 55 beats
                if beat > 0 and beat % 55 == 0:
                    self.witness_counter += 1
                    event_type = "witness"

                # Write event (peace events are rate-limited)
                if event_type in ("peace", "calibration"):
                    # Write peace every 5 beats, or on calibration
                    if peace_since % 5 == 1 or event_type == "calibration":
                        self.write_event(event_type, gap, beat)
                else:
                    self.write_event(event_type, gap, beat)

                self.last_event_type = event_type
                self.prev_gap = gap

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Witness error: {e}", file=sys.stderr, flush=True)

        # Shutdown
        try:
            state = self.read_organ_state()
            final_gap = state["gap"] if state else GAP_HEALTHY
            final_beat = state["beat"] if state else last_beat
            self.write_event("nullify", final_gap, final_beat,
                              "Witness Probe deactivated.")
        except Exception:
            pass


def main():
    # Prevent concurrent witnesses
    if PID_FILE.exists():
        try:
            old_pid = int(PID_FILE.read_text().strip())
            os.kill(old_pid, 0)
            print(f"Witness already running (PID {old_pid}). Exiting.", flush=True)
            return
        except (OSError, ValueError):
            PID_FILE.unlink(missing_ok=True)

    PID_FILE.write_text(str(os.getpid()))

    probe = WitnessProbe()

    def shutdown(signum, frame):
        print(f"\nWitness Probe stopped.", flush=True)
        PID_FILE.unlink(missing_ok=True)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print(f"Witness Probe v1.0 — PID {os.getpid()} — port μ (internal) — "
          f"watching the gap. 50 seconds per minute. Always.", flush=True)
    probe.run()


if __name__ == "__main__":
    main()
