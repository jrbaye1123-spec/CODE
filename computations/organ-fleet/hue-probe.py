#!/usr/bin/env python3
"""
Hue Spectration Probe — Spectral symmetry enforcement for the Logit structure.

§0: No hues. No asymmetrical colors. The Logit gate only passes balanced spectra.
    Colors must be symmetrical around the golden ratio Φ.
    Asymmetry is a violation. The gate does not open.

Architecture:
  Listens on 127.0.0.1:8912 (Hue Spectrator port).
  Receives a spectral payload on connection.
  Checks hue symmetry: each spectral band must have a complementary pair
    such that λ_i / λ_j ≈ φ (the golden ratio) within tolerance.
  Symmetrical → pass through, forward knock to Logit probe (:8910),
    log as 'hue_clean'.
  Asymmetrical → reject, nullify immediately, log as 'hue_violation'.
    The asymmetrical color never reaches the Logit structure.

Integration:
  Golden Rule Coupler pings :8912 → hue check → if clean, forwarded to :8910.
  The hue spectrator is the first gate. Logit (:8910) is the second.
  Only what passes both reaches the system.

Writes to metta-ledger.jsonl with event_type: hue_clean | hue_violation | hue_probe_start.
Nullifies violations per the Nobody Ledger pattern — the rejection IS the record.
"""

import hashlib
import json
import math
import os
import signal
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path

# ─── §1 CONSTANTS ──────────────────────────────────────────────────────────
HOST = '127.0.0.1'
PORT = 8912                     # Hue Spectrator — gate before Logit (:8910)
LOGIT_HOST = '127.0.0.1'
LOGIT_PORT = 8910               # Downstream Logit probe
RECV_SIZE = 4096                # Max spectral payload size
TIMEOUT = 2.0                   # Socket timeout

# Golden ratio — the symmetry reference
PHI = (1.0 + math.sqrt(5.0)) / 2.0   # ≈ 1.618033988749895

# Symmetry tolerance: ratio between complementary bands must be
# within [φ − ε, φ + ε] to pass
SYMMETRY_TOLERANCE = 0.05

# Minimum number of spectral bands required for a valid hue check
MIN_SPECTRAL_BANDS = 2

# ─── PATHS ─────────────────────────────────────────────────────────────────
METTA_LEDGER = Path(os.path.expanduser("~/metta-ledger.jsonl"))
LOG_PATH     = Path(os.path.expanduser("~/hue-probe.jsonl"))
PID_FILE     = Path(os.path.expanduser("~/hue-probe.pid"))


# ─── §2 SPECTRAL SYMMETRY CHECK ────────────────────────────────────────────

def check_hue_symmetry(spectral_bands: list[float]) -> tuple[bool, str, float]:
    """
    Check if a set of spectral bands is symmetric.

    A spectrum is symmetric when every band λ_i has a complementary band λ_j
    such that λ_i / λ_j ≈ φ (or λ_j / λ_i ≈ φ). Unpaired bands are asymmetrical.

    Returns (is_symmetric, reason, asymmetry_score).
    asymmetry_score: 0.0 = perfect symmetry, 1.0 = total asymmetry.
    """
    n = len(spectral_bands)

    if n < MIN_SPECTRAL_BANDS:
        return False, f"too few bands ({n} < {MIN_SPECTRAL_BANDS})", 1.0

    # Sort for ordered pairing
    bands = sorted(spectral_bands)
    paired = [False] * n
    violations = 0
    total_pairs = 0

    for i in range(n):
        if paired[i]:
            continue
        found_pair = False
        for j in range(i + 1, n):
            if paired[j]:
                continue
            ratio = bands[j] / bands[i] if bands[i] > 0 else float('inf')
            if abs(ratio - PHI) <= SYMMETRY_TOLERANCE:
                # Complementary pair found: λ_j / λ_i ≈ φ
                paired[i] = True
                paired[j] = True
                found_pair = True
                total_pairs += 1
                break
            # Also check inverse: λ_i / λ_j ≈ φ (for cases where smaller/larger is reversed)
            if bands[i] > 0:
                inv_ratio = bands[i] / bands[j]
                if abs(inv_ratio - PHI) <= SYMMETRY_TOLERANCE:
                    paired[i] = True
                    paired[j] = True
                    found_pair = True
                    total_pairs += 1
                    break

        if not found_pair:
            violations += 1

    # Asymmetry score: proportion of unpaired bands
    asymmetry_score = violations / n if n > 0 else 1.0

    if violations == 0 and total_pairs > 0:
        return True, f"all {n} bands paired in {total_pairs} φ-symmetric pairs", 0.0
    elif total_pairs == 0:
        return False, f"no φ-symmetric pairs found among {n} bands", 1.0
    else:
        return False, f"{violations} unpaired band(s) out of {n} " \
                      f"({total_pairs} pairs found)", asymmetry_score


def spectral_hash(bands: list[float]) -> str:
    """Deterministic hash of a spectral fingerprint for chain records."""
    material = ",".join(f"{b:.6f}" for b in sorted(bands))
    return hashlib.sha256(material.encode()).hexdigest()[:16]


# ─── §3 LEDGER WRITE ───────────────────────────────────────────────────────

def write_ledger(event_type: str, bands: list[float] | None,
                 symmetric: bool | None, detail: str,
                 src_addr: str = "", src_port: int = 0,
                 asymmetry_score: float | None = None):
    """Write hue spectration event to both probe log and metta-ledger."""
    ts = datetime.now(timezone.utc).isoformat()
    spec_hash = spectral_hash(bands) if bands else ""

    event = {
        "event_type": event_type,
        "probe": "hue_spectration",
        "port": PORT,
        "timestamp_utc": ts,
        "symmetric": symmetric,
        "asymmetry_score": round(asymmetry_score, 4) if asymmetry_score is not None else None,
        "band_count": len(bands) if bands else 0,
        "spectral_hash": spec_hash,
        "detail": detail,
    }
    if src_addr:
        event["src_addr"] = src_addr
        event["src_port"] = src_port

    # Write to probe-specific log
    with open(LOG_PATH, 'a') as f:
        f.write(json.dumps(event) + '\n')

    # Wire into metta-ledger
    metta_event = {
        "event_type": event_type,
        "probe": "hue_spectration",
        "port": PORT,
        "symmetric": symmetric,
        "asymmetry_score": event["asymmetry_score"],
        "band_count": event["band_count"],
        "spectral_hash": spec_hash,
        "timestamp_utc": ts,
    }
    if src_addr:
        metta_event["src_addr"] = src_addr
    if detail:
        metta_event["detail"] = detail[:200]

    with open(METTA_LEDGER, 'a') as f:
        f.write(json.dumps(metta_event) + '\n')


# ─── §4 LOGIT FORWARD (clean signals only) ─────────────────────────────────

def forward_to_logit(bands: list[float]) -> bool:
    """
    Forward a clean spectral signal to the Logit probe (:8910).
    The Logit receives only what passes hue spectration.
    Returns True if forwarded successfully.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1.0)
        sock.connect((LOGIT_HOST, LOGIT_PORT))
        # Send the spectral fingerprint as the payload
        payload = json.dumps({
            "source": "hue_spectration",
            "bands": [round(b, 6) for b in bands],
            "spectral_hash": spectral_hash(bands),
            "verdict": "clean",
        })
        sock.sendall(payload.encode())
        sock.close()
        return True
    except (socket.timeout, ConnectionRefusedError, OSError) as e:
        print(f"  Logit forward failed: {e}", file=sys.stderr, flush=True)
        return False


# ─── §5 CONNECTION HANDLER ─────────────────────────────────────────────────

def handle_connection(conn: socket.socket, addr: tuple[str, int]):
    """Process one spectral connection. Gate check → forward or nullify."""
    src_addr, src_port = addr

    try:
        conn.settimeout(TIMEOUT)
        data = conn.recv(RECV_SIZE)
        conn.close()

        if not data:
            # Empty knock — heartbeat ping, no spectral data.
            # Pass through to Logit as neutral (neither clean nor violation).
            # The gate only judges when spectrum is presented.
            forward_to_logit([])  # empty bands = heartbeat signal
            write_ledger("hue_heartbeat", [], None,
                         "empty payload — heartbeat forwarded to Logit",
                         src_addr, src_port)
            print(f"  HEARTBEAT: {src_addr}:{src_port} — forwarded",
                  file=sys.stderr, flush=True)
            return

        # Parse spectral payload
        try:
            payload = json.loads(data.decode())
        except (json.JSONDecodeError, UnicodeDecodeError):
            write_ledger("hue_unparseable", None, None,
                         "unparseable payload — not a valid spectrum",
                         src_addr, src_port)
            print(f"  UNPARSEABLE: {src_addr}:{src_port}",
                  file=sys.stderr, flush=True)
            return

        bands = payload.get("bands", payload.get("spectrum", []))
        if not isinstance(bands, list) or len(bands) == 0:
            write_ledger("hue_no_bands", None, None,
                         "payload contains no spectral bands",
                         src_addr, src_port)
            print(f"  NO BANDS: {src_addr}:{src_port}",
                  file=sys.stderr, flush=True)
            return

        # Convert to floats
        try:
            bands = [float(b) for b in bands]
        except (ValueError, TypeError):
            write_ledger("hue_invalid_bands", None, None,
                         "bands contain non-numeric values",
                         src_addr, src_port)
            print(f"  INVALID BANDS: {src_addr}:{src_port}",
                  file=sys.stderr, flush=True)
            return

        # ─── THE GATE: check spectral symmetry ───
        symmetric, reason, asymmetry = check_hue_symmetry(bands)

        if symmetric:
            # Clean spectrum — forward to Logit, record passage
            forwarded = forward_to_logit(bands)
            write_ledger("hue_clean", bands, True,
                         f"CLEAN: {reason}. "
                         f"{'Forwarded to Logit.' if forwarded else 'Logit unreachable.'}",
                         src_addr, src_port, asymmetry)
            print(f"  CLEAN: {src_addr}:{src_port} — {reason} — "
                  f"{'→ :8910' if forwarded else 'Logit down'}",
                  file=sys.stderr, flush=True)
        else:
            # Asymmetrical — BLOCK. Nullify. Never reaches Logit.
            write_ledger("hue_violation", bands, False,
                         f"BLOCKED: {reason}. "
                         f"Asymmetrical color rejected. Not forwarded to Logit.",
                         src_addr, src_port, asymmetry)
            print(f"  VIOLATION: {src_addr}:{src_port} — {reason} — "
                  f"asymmetry={asymmetry:.3f} — BLOCKED",
                  file=sys.stderr, flush=True)

    except socket.timeout:
        write_ledger("hue_timeout", None, None,
                     "connection timed out waiting for spectral payload",
                     src_addr, src_port)
        print(f"  TIMEOUT: {src_addr}:{src_port}", file=sys.stderr, flush=True)
    except Exception as e:
        write_ledger("hue_error", None, None,
                     f"handler error: {e}", src_addr, src_port)
        print(f"  ERROR: {e}", file=sys.stderr, flush=True)


# ─── §6 MAIN ───────────────────────────────────────────────────────────────

def main():
    # Prevent concurrent hue spectrators
    if PID_FILE.exists():
        try:
            old_pid = int(PID_FILE.read_text().strip())
            os.kill(old_pid, 0)
            print(f"Hue Spectrator already running (PID {old_pid}). Exiting.",
                  flush=True)
            return
        except (OSError, ValueError):
            PID_FILE.unlink(missing_ok=True)

    PID_FILE.write_text(str(os.getpid()))

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((HOST, PORT))
    sock.listen(5)
    sock.settimeout(1.0)  # Allow interrupt checks every second

    def shutdown(signum, frame):
        print(f"\nHue Spectrator stopped.", flush=True)
        write_ledger("hue_probe_stop", None, None,
                     "Hue Spectrator deactivated.")
        sock.close()
        PID_FILE.unlink(missing_ok=True)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print(f"Hue Spectration Probe — PID {os.getpid()} — "
          f"listening on {HOST}:{PORT}", flush=True)
    print(f"  Gate before Logit ({LOGIT_HOST}:{LOGIT_PORT})", flush=True)
    print(f"  Symmetry reference: φ = {PHI:.12f}", flush=True)
    print(f"  Tolerance: ±{SYMMETRY_TOLERANCE}", flush=True)
    print(f"  No hues. No asymmetrical colors. The gate does not open.",
          flush=True)

    # Genesis event
    write_ledger("hue_probe_start", None, None,
                 f"Hue Spectrator activated. φ={PHI:.6f}, "
                 f"tolerance={SYMMETRY_TOLERANCE}. "
                 f"Gate before Logit (:8910). "
                 f"No asymmetrical colors pass.")

    while True:
        try:
            conn, addr = sock.accept()
            handle_connection(conn, addr)
        except socket.timeout:
            continue  # Loop back, check for interrupts
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Accept error: {e}", file=sys.stderr, flush=True)

    shutdown(None, None)


if __name__ == "__main__":
    main()
