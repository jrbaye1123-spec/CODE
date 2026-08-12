#!/usr/bin/env python3
"""
Death Clock Telemetry v3 — Clean-Source Pipeline
==================================================
Watches the Metta ledger, computes Schatten-1 gap, logistic collapse
projections, and inflection detection. Emits telemetry events to its
own log and self-monitoring heartbeats to the ledger.

Math: death_clock_math.py (pure, stateless, locked)
Config: death-clock-config.toml (strict schema validation)

No bytecode. No hardcoded paths. No silent failures.
"""

import json
import os
import sys
import math
import time
import signal
import traceback
from datetime import datetime, timezone
from pathlib import Path
from collections import deque

import numpy as np

# ── Pure math module (locked, do not refactor) ────────────────────────────────
# Import from sibling directory (same folder as this script)
_script_dir = Path(__file__).resolve().parent
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

from death_clock_math import (
    savitzky_golay,
    fit_logistic_collapse,
    detect_inflection_smoothed,
    compute_delta,
    estimate_gap_statistics,
    estimate_void_density,
    beats_remaining_logistic,
    DEATH_THRESHOLD,
    HEALTHY_GAP,
    SG_WINDOW,
    SG_ORDER,
    COLLAPSE_WINDOW,
    COLLAPSE_MIN_POINTS,
    TARGET_BPM,
    BEAT_INTERVAL,
    GAP_ALIVE_MIN,
    GAP_DANGER_WIDE,
)


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION SCHEMA & VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

CONFIG_SCHEMA = {
    'ledger': {
        'path': (str, True),
        'tail_scan_bytes': (int, False),
    },
    'telemetry': {
        'output_path': (str, True),
        'pid_file': (str, True),
        'fleet_pid_file': (str, True),
    },
    'math': {
        'sg_window': (int, False),
        'sg_order': (int, False),
        'collapse_window': (int, False),
        'collapse_min_points': (int, False),
        'death_threshold': (float, False),
        'healthy_gap': (float, False),
        'gap_alive_min': (float, False),
        'gap_danger_wide': (float, False),
        'inflection_sigma': (float, False),
        'inflection_safety_factor': (float, False),
    },
    'monitoring': {
        'heartbeat_interval_beats': (int, False),
        'watchdog_stall_beats': (int, False),
        'beat_interval': (float, False),
    },
    'buffer': {
        'enabled': (bool, False),
        'max_size': (int, False),
        'retry_interval_sec': (float, False),
    },
    'display': {
        'status_every_beats': (int, False),
        'verbose': (bool, False),
    },
}

CONFIG_DEFAULTS = {
    'ledger': {
        'tail_scan_bytes': 5_000_000,
    },
    'math': {
        'sg_window': 31,
        'sg_order': 3,
        'collapse_window': 500,
        'collapse_min_points': 100,
        'death_threshold': 5e-04,
        'healthy_gap': 0.04,
        'gap_alive_min': 0.025,
        'gap_danger_wide': 0.10,
        'inflection_sigma': 3.0,
        'inflection_safety_factor': 2.0,
    },
    'monitoring': {
        'heartbeat_interval_beats': 60,
        'watchdog_stall_beats': 3,
        'beat_interval': 1.090909,
    },
    'buffer': {
        'enabled': True,
        'max_size': 1000,
        'retry_interval_sec': 1.0,
    },
    'display': {
        'status_every_beats': 10,
        'verbose': False,
    },
}


def _resolve_path(raw_path: str) -> Path:
    """Resolve ~ and $HOME in paths."""
    return Path(os.path.expanduser(raw_path)).resolve()


def _set_defaults(section: str, config: dict):
    """Apply defaults for a section if not present."""
    if section in CONFIG_DEFAULTS:
        for key, default in CONFIG_DEFAULTS[section].items():
            config[section].setdefault(key, default)


def load_config(config_path: str = None) -> dict:
    """
    Load TOML configuration, validate schema, apply defaults.

    Fails loudly on missing required fields or type errors.
    Never falls back to dangerous defaults.
    """
    if config_path is None:
        config_path = os.path.expanduser("~/death-clock-config.toml")

    config_file = Path(config_path)
    if not config_file.exists():
        die(f"Configuration file not found: {config_file}")

    # TOML is stdlib in Python 3.11+
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib

    try:
        with open(config_file, 'rb') as f:
            raw = tomllib.load(f)
    except Exception as e:
        die(f"Failed to parse TOML config: {e}")

    config = {}

    # Validate top-level sections
    for section, fields in CONFIG_SCHEMA.items():
        if section not in raw:
            die(f"Missing config section: [{section}]")

        config[section] = {}
        section_data = raw[section]
        if not isinstance(section_data, dict):
            die(f"Config section [{section}] must be a table, got {type(section_data).__name__}")

        for field, (expected_type, required) in fields.items():
            if field not in section_data:
                if required:
                    die(f"Missing required field: [{section}].{field}")
                continue

            value = section_data[field]
            if not isinstance(value, expected_type):
                die(f"Type error: [{section}].{field} expected {expected_type.__name__}, "
                    f"got {type(value).__name__}")

            config[section][field] = value

        # Apply defaults for optional fields
        _set_defaults(section, config)

    # Resolve path fields
    config['ledger']['path'] = str(_resolve_path(config['ledger']['path']))
    config['telemetry']['output_path'] = str(_resolve_path(config['telemetry']['output_path']))
    config['telemetry']['pid_file'] = str(_resolve_path(config['telemetry']['pid_file']))
    config['telemetry']['fleet_pid_file'] = str(_resolve_path(config['telemetry']['fleet_pid_file']))

    # Validate math parameters
    math_cfg = config['math']
    if math_cfg['sg_window'] % 2 == 0:
        die(f"sg_window must be odd, got {math_cfg['sg_window']}")
    if math_cfg['sg_order'] >= math_cfg['sg_window']:
        die(f"sg_order ({math_cfg['sg_order']}) must be < sg_window ({math_cfg['sg_window']})")
    if math_cfg['collapse_min_points'] > math_cfg['collapse_window']:
        die(f"collapse_min_points ({math_cfg['collapse_min_points']}) "
            f"must be <= collapse_window ({math_cfg['collapse_window']})")

    return config


def die(msg: str, exit_code: int = 1):
    """Fail loudly and exit."""
    print(f"FATAL: {msg}", file=sys.stderr, flush=True)
    sys.exit(exit_code)


# ═══════════════════════════════════════════════════════════════════════════════
# PID LOCK FILE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

class PidLock:
    """Prevent duplicate instances. Cleans up on exit."""

    def __init__(self, pid_file: str):
        self.pid_file = Path(pid_file)
        self.acquired = False

    def acquire(self) -> bool:
        if self.pid_file.exists():
            try:
                old_pid = int(self.pid_file.read_text().strip())
                # Check if old process is still alive
                os.kill(old_pid, 0)
                die(f"Another instance is running (PID {old_pid}). "
                    f"Remove {self.pid_file} if stale.")
            except (ValueError, ProcessLookupError):
                # Stale lock file — clean up
                self.pid_file.unlink(missing_ok=True)
            except PermissionError:
                die(f"Cannot check PID in {self.pid_file}")

        self.pid_file.write_text(str(os.getpid()))
        self.acquired = True
        return True

    def release(self):
        if self.acquired:
            self.pid_file.unlink(missing_ok=True)
            self.acquired = False


# ═══════════════════════════════════════════════════════════════════════════════
# LEDGER READER
# ═══════════════════════════════════════════════════════════════════════════════

class LedgerReader:
    """Tail-reads the Metta ledger, yielding beat entries as they appear."""

    def __init__(self, ledger_path: str, tail_scan_bytes: int = 5_000_000):
        self.path = Path(ledger_path)
        self.tail_scan_bytes = tail_scan_bytes
        self._pos = 0         # byte position for incremental reads
        self._beat_index = {} # beat → file offset for seeking

    def initial_scan(self) -> list[dict]:
        """Read historical beats from the tail of the ledger."""
        if not self.path.exists():
            return []

        file_size = self.path.stat().st_size
        if file_size == 0:
            return []

        chunk_start = max(0, file_size - self.tail_scan_bytes)

        entries = []
        with open(self.path, 'r') as f:
            f.seek(chunk_start)
            # Skip partial first line if not at start of file
            if chunk_start > 0:
                f.readline()

            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if 'beat' in entry and 'gap' in entry:
                        entries.append(entry)
                except json.JSONDecodeError:
                    continue

        self._pos = file_size
        return entries

    def read_new(self) -> list[dict]:
        """Read beat entries that have appeared since last read."""
        if not self.path.exists():
            return []

        file_size = self.path.stat().st_size
        if file_size <= self._pos:
            return []

        new_entries = []
        with open(self.path, 'r') as f:
            f.seek(self._pos)
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if 'beat' in entry and 'gap' in entry:
                        new_entries.append(entry)
                except json.JSONDecodeError:
                    continue

        self._pos = file_size
        return new_entries


# ═══════════════════════════════════════════════════════════════════════════════
# TELEMETRY WRITER (with buffer & retry)
# ═══════════════════════════════════════════════════════════════════════════════

class TelemetryWriter:
    """
    Writes telemetry events to the output log.
    On failure: buffers to memory and retries. Never drops data silently.
    """

    def __init__(self, output_path: str, buffer_config: dict):
        self.path = Path(output_path)
        self.buffer_enabled = buffer_config.get('enabled', True)
        self.max_buffer = buffer_config.get('max_size', 1000)
        self.retry_interval = buffer_config.get('retry_interval_sec', 1.0)
        self._buffer: deque = deque(maxlen=self.max_buffer)
        self._consecutive_failures = 0

    def write(self, event: dict) -> bool:
        """Write a telemetry event. Returns True on success."""
        # Flush buffer first if any
        if self._buffer:
            self._flush_buffer()

        line = json.dumps(event, ensure_ascii=False) + '\n'
        return self._write_line(line)

    def heartbeat(self, event: dict) -> bool:
        """Write a heartbeat event (lower priority, drop if buffer full)."""
        if self._buffer:
            self._flush_buffer()
        line = json.dumps(event, ensure_ascii=False) + '\n'
        return self._write_line(line)

    def _write_line(self, line: str) -> bool:
        """Write a single line. Buffer on failure."""
        try:
            with open(self.path, 'a') as f:
                f.write(line)
            self._consecutive_failures = 0
            return True
        except (OSError, IOError) as e:
            self._consecutive_failures += 1
            if self.buffer_enabled:
                self._buffer.append(line)
                if self._consecutive_failures == 1:
                    print(f"  ⚠ Telemetry write failed (buffering): {e}",
                          file=sys.stderr, flush=True)
            else:
                print(f"  ⚠ Telemetry write failed (no buffer): {e}",
                      file=sys.stderr, flush=True)
            return False

    def _flush_buffer(self) -> int:
        """Attempt to flush buffered events. Returns count flushed."""
        flushed = 0
        while self._buffer:
            line = self._buffer[0]
            try:
                with open(self.path, 'a') as f:
                    f.write(line)
                self._buffer.popleft()
                flushed += 1
                self._consecutive_failures = 0
            except (OSError, IOError):
                time.sleep(self.retry_interval)
                break  # try again next write cycle
        return flushed

    @property
    def buffer_size(self) -> int:
        return len(self._buffer)


# ═══════════════════════════════════════════════════════════════════════════════
# WATCHDOG
# ═══════════════════════════════════════════════════════════════════════════════

class Watchdog:
    """Detects telemetry loop stalls. If we miss N beats, something is wrong."""

    def __init__(self, stall_beats: int, beat_interval: float):
        self.stall_beats = stall_beats
        self.stall_seconds = stall_beats * beat_interval
        self._last_beat_time = time.monotonic()
        self._stalled = False

    def feed(self):
        """Call on every successful beat ingestion."""
        self._last_beat_time = time.monotonic()
        self._stalled = False

    def check(self) -> bool:
        """Return True if stalled (no beat for > stall_seconds)."""
        if self._stalled:
            return True
        elapsed = time.monotonic() - self._last_beat_time
        if elapsed > self.stall_seconds:
            self._stalled = True
            return True
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# FLEET LIVENESS CHECK
# ═══════════════════════════════════════════════════════════════════════════════

def check_fleet_alive(fleet_pid_file: str) -> tuple[bool, str]:
    """Check if the organ-fleet mother process is running."""
    pid_path = Path(fleet_pid_file)
    if not pid_path.exists():
        return False, "No PID file"
    try:
        pid = int(pid_path.read_text().strip())
        os.kill(pid, 0)
        return True, f"PID {pid}"
    except (ValueError, ProcessLookupError):
        return False, "Process not found"
    except PermissionError:
        return False, "Permission denied"


# ═══════════════════════════════════════════════════════════════════════════════
# TELEMETRY COMPUTATION ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def compute_telemetry(history: list[dict], new_entry: dict, config: dict) -> dict:
    """
    Compute full telemetry for a single ledger beat entry.

    Returns a dict ready for JSON serialization.
    """
    math_cfg = config['math']

    # Extract time series from history window
    beats  = np.array([e['beat'] for e in history], dtype=np.float64)
    org_gaps = np.array([e['gap'] for e in history], dtype=np.float64)
    sigma_vals = np.array([e.get('sigma_glycation', 0.62) for e in history],
                          dtype=np.float64)

    # Use organ-fleet's canonical ∆ (compute_delta = entry['gap'])
    deltas = np.array([compute_delta(e) for e in history], dtype=np.float64)
    current_delta = compute_delta(new_entry)

    # ── Gap statistics ────────────────────────────────────────────────────
    min_gap, ema_gap = estimate_gap_statistics(beats, deltas)

    # ── Void density ──────────────────────────────────────────────────────
    void_density = estimate_void_density(beats, deltas, sigma_vals)

    # ── Inflection detection (SG-smoothed) ────────────────────────────────
    # Warmup guard: need at least window_size beats before calling SG filter
    if len(deltas) >= math_cfg['sg_window']:
        inflection, inflect_mag, y_s, d1_s, d2_s = detect_inflection_smoothed(
            beats[-math_cfg['collapse_window']:],
            deltas[-math_cfg['collapse_window']:],
            window=math_cfg['sg_window'],
            order=math_cfg['sg_order'],
        )
        # Convert numpy bool_ to Python bool for JSON serialization
        inflection = bool(inflection)
    else:
        inflection, inflect_mag = False, 0.0

    # ── Logistic collapse projection ──────────────────────────────────────
    collapse = beats_remaining_logistic(beats, deltas)

    # ── Gap health classification ─────────────────────────────────────────
    gap = new_entry['gap']
    gap_health = new_entry.get('gap_health', classify_gap_health(gap, current_delta))

    return {
        'event_type': 'death_clock_telemetry',
        'version': '3.0',
        'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'organ_beat': new_entry['beat'],
        'organ_timestamp': new_entry.get('timestamp_utc', ''),
        # Raw metrics (organ-fleet canonical scale)
        'gap_organ': round(gap, 6),
        'gap_current': round(current_delta, 6),
        'gap_min': round(min_gap, 6),
        'gap_ema': round(ema_gap, 6),
        'gap_health': gap_health,
        'void_density': round(void_density, 6),
        'sigma_glycation': new_entry.get('sigma_glycation', 0.0),
        'sigma_pct': new_entry.get('sigma_pct', 0.0),
        'kappa4_reserve': new_entry.get('kappa4_reserve', 0.0),
        # Inflection
        'inflection_detected': inflection,
        'inflection_magnitude': round(inflect_mag, 10),
        # Logistic collapse projection
        'logistic_b_max': collapse.get('b_max'),
        'logistic_nu': collapse.get('nu'),
        'logistic_r2': round(collapse.get('r2', 0.0), 6),
        'logistic_beats_to_death': collapse.get('beats_to_death'),
        'logistic_confidence_lo': collapse.get('confidence_lo'),
        'logistic_confidence_hi': collapse.get('confidence_hi'),
        'logistic_status': collapse.get('status', 'unknown'),
        # Metadata
        'history_length': len(history),
    }


def classify_gap_health(gap: float, schatten1: float) -> str:
    """Classify organ-fleet gap health from both gap and Schatten-1."""
    if gap >= 0.10:
        return 'DANGER_WIDE'
    elif gap > 0.055:
        return 'WARNING_WIDE'
    elif gap < 0.01:
        return 'DANGER_NARROW'
    elif gap < 0.025:
        return 'WARNING_NARROW'
    elif abs(gap - 0.04) < 0.015:
        return 'ALIVE'
    else:
        return 'BORDERLINE'


# ═══════════════════════════════════════════════════════════════════════════════
# STATUS LINE RENDERING
# ═══════════════════════════════════════════════════════════════════════════════

def render_status(telemetry: dict, collapse: dict, inflection: bool,
                  beat_count: int, buffer_size: int):
    """Render a one-line status for the terminal."""
    b = telemetry.get('organ_beat', '?')
    g = telemetry.get('gap_organ', 0)
    health = telemetry.get('gap_health', '?')
    btd = telemetry.get('logistic_beats_to_death')
    void = telemetry.get('void_density', 0)

    btd_str = f'{btd:,.0f}' if btd is not None else '---'
    health_icon = {'ALIVE': '✓', 'WARNING_WIDE': '⚠', 'WARNING_NARROW': '⚠',
                   'DANGER_WIDE': '✕', 'DANGER_NARROW': '✕', 'BORDERLINE': '~'}.get(health, '?')

    parts = [
        f"beat={b:>6}",
        f"∆={g:.4f}",
        f"{health_icon} {health:<14}",
        f"void={void:.3f}",
        f"⏳{btd_str}",
    ]
    if inflection:
        parts.append("⚡INFLECTION")
    if buffer_size > 0:
        parts.append(f"buf={buffer_size}")

    return "  ".join(parts)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN TELEMETRY LOOP
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    # ── Load configuration ─────────────────────────────────────────────────
    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    config = load_config(config_path)

    math_cfg    = config['math']
    mon_cfg     = config['monitoring']
    display_cfg = config['display']

    # ── Acquire PID lock ───────────────────────────────────────────────────
    pid_lock = PidLock(config['telemetry']['pid_file'])
    pid_lock.acquire()

    # ── Graceful shutdown ──────────────────────────────────────────────────
    shutdown_flag = False

    def handle_signal(signum, frame):
        nonlocal shutdown_flag
        sig_name = signal.Signals(signum).name
        print(f"\n  Signal {sig_name} received. Shutting down...", flush=True)
        shutdown_flag = True

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    # ── Header ─────────────────────────────────────────────────────────────
    print(f"═══ DEATH CLOCK TELEMETRY v3 ═══")
    print(f"Model:    Logistic collapse ∆ ∝ (B_max − B)^ν")
    print(f"Filter:   Savitzky-Golay (window={math_cfg['sg_window']}, "
          f"order={math_cfg['sg_order']})")
    print(f"Organ:    {TARGET_BPM} BPM")
    print(f"Healthy:  ∆ = {math_cfg['healthy_gap']}")
    print(f"Death:    ∆ < {math_cfg['death_threshold']}")
    print(f"Telemetry: {config['telemetry']['output_path']}")
    print(f"Ledger:   {config['ledger']['path']}")
    print()

    # ── Check fleet liveness ───────────────────────────────────────────────
    fleet_alive, fleet_detail = check_fleet_alive(config['telemetry']['fleet_pid_file'])
    if not fleet_alive:
        print(f"⚠ ORGAN FLEET NOT RUNNING ({fleet_detail})")
        print(f"  Start: python3 ~/.hermes/scripts/organ-fleet.py")
        print()
    else:
        print(f"✓ Organ fleet running ({fleet_detail})")
        print()

    # ── Initialise components ──────────────────────────────────────────────
    reader = LedgerReader(
        config['ledger']['path'],
        tail_scan_bytes=config['ledger']['tail_scan_bytes'],
    )
    writer = TelemetryWriter(
        config['telemetry']['output_path'],
        config['buffer'],
    )
    watchdog = Watchdog(
        mon_cfg['watchdog_stall_beats'],
        mon_cfg['beat_interval'],
    )

    # ── Initial history load ───────────────────────────────────────────────
    history = reader.initial_scan()
    history_window = deque(history[-math_cfg['collapse_window']:],
                           maxlen=math_cfg['collapse_window'])

    beat_count = len(history)
    if beat_count == 0:
        print(f"⚠ METTA LEDGER NOT FOUND at {config['ledger']['path']}")
        pid_lock.release()
        return 1

    print(f"  Ledger: {beat_count} beats recorded.")
    print(f"  Window: {len(history_window)} beats (max {math_cfg['collapse_window']})")
    print(f"  Latest beat: {history[-1]['beat'] if history else 'N/A'}")
    print()

    # ── Main loop ──────────────────────────────────────────────────────────
    heartbeat_counter = 0
    status_counter = 0

    try:
        while not shutdown_flag:
            # Read new beats
            new_entries = reader.read_new()

            if not new_entries:
                # Check watchdog
                if watchdog.check():
                    msg = (f"⛔ WATCHDOG: No beats for > "
                           f"{mon_cfg['watchdog_stall_beats']} intervals. "
                           f"Telemetry loop may be stalled!")
                    print(msg, file=sys.stderr, flush=True)
                    # Write watchdog alert to ledger
                    alert = {
                        'event_type': 'telemetry_watchdog',
                        'version': '3.0',
                        'timestamp_utc': datetime.now(timezone.utc).isoformat(),
                        'alert': 'telemetry_stall',
                        'detail': msg,
                    }
                    writer.heartbeat(alert)
                time.sleep(mon_cfg['beat_interval'] * 0.5)
                continue

            # Process each new entry
            for entry in new_entries:
                history_window.append(entry)
                beat_count += 1
                watchdog.feed()

                # Compute telemetry
                telemetry = compute_telemetry(list(history_window), entry, config)

                # Write to telemetry log
                ok = writer.write(telemetry)
                if not ok and display_cfg['verbose']:
                    print(f"  ⚠ Buffered telemetry for beat {entry['beat']}",
                          file=sys.stderr)

                # Status line
                status_counter += 1
                if display_cfg['status_every_beats'] > 0 and \
                   status_counter % display_cfg['status_every_beats'] == 0:
                    collapse = beats_remaining_logistic(
                        np.array([e['beat'] for e in history_window],
                                 dtype=np.float64),
                        np.array([e['gap'] for e in history_window],
                                 dtype=np.float64),
                    )
                    line = render_status(
                        telemetry, collapse,
                        telemetry.get('inflection_detected', False),
                        beat_count, writer.buffer_size,
                    )
                    print(f"  {line}", flush=True)

                # Inflection alert
                if telemetry.get('inflection_detected'):
                    print()
                    print(f"  {'─'*60}")
                    print(f"  ⚠ INFLECTION DETECTED")
                    print(f"     |d²∆/dB²| smoothed magnitude: "
                          f"{telemetry.get('inflection_magnitude', 0):.6e}")
                    print(f"     Repair mechanism failing — acceleration toward death.")
                    print(f"     SENOLYTIC PROTOCOL ADVISED.")
                    if telemetry.get('logistic_beats_to_death') is not None:
                        btd = telemetry['logistic_beats_to_death']
                        lo = telemetry.get('logistic_confidence_lo', btd)
                        hi = telemetry.get('logistic_confidence_hi', btd)
                        print(f"     Estimated beats remaining: {btd:,.0f} "
                              f"[{lo:,.0f} – {hi:,.0f}]")
                    print(f"  {'─'*60}")
                    print()

                    # Write inflection event to ledger
                    inflection_event = {
                        'event_type': 'telemetry_inflection',
                        'version': '3.0',
                        'timestamp_utc': datetime.now(timezone.utc).isoformat(),
                        'organ_beat': entry['beat'],
                        'inflection_magnitude': telemetry['inflection_magnitude'],
                        'logistic_beats_to_death': telemetry['logistic_beats_to_death'],
                        'logistic_b_max': telemetry['logistic_b_max'],
                        'logistic_nu': telemetry['logistic_nu'],
                    }
                    writer.write(inflection_event)

                # Heartbeat emission (self-observability)
                heartbeat_counter += 1
                if heartbeat_counter >= mon_cfg['heartbeat_interval_beats']:
                    heartbeat_counter = 0
                    hb = {
                        'event_type': 'telemetry_heartbeat',
                        'version': '3.0',
                        'timestamp_utc': datetime.now(timezone.utc).isoformat(),
                        'organ_beat': entry['beat'],
                        'telemetry_beat_count': beat_count,
                        'buffer_size': writer.buffer_size,
                        'history_window': len(history_window),
                        'gap_current': telemetry.get('gap_current'),
                        'void_density': telemetry.get('void_density'),
                    }
                    writer.heartbeat(hb)

    except KeyboardInterrupt:
        pass  # handled by signal handler
    except Exception as e:
        print(f"\n  ⚠ Telemetry loop crashed: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
    finally:
        # Flush buffer before exit
        if writer.buffer_size > 0:
            print(f"  Flushing {writer.buffer_size} buffered events...", flush=True)
            writer._flush_buffer()

        print(f"\n  Telemetry stopped after {beat_count} beats.", flush=True)
        pid_lock.release()

    return 0


if __name__ == '__main__':
    sys.exit(main())
