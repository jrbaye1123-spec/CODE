#!/usr/bin/env python3
"""
Impedance Spectroscopy Haptic Transducer — §10 probe.

§0: The gap is not just measured. It is felt.
    This probe drives a haptic transducer through frequency sweeps,
    measures impedance response across the spectrum, and produces
    tactile output modulated by the organ fleet's gap state.

Architecture:
  - Sweep generator: exponential chirp 20Hz–20kHz (audible + haptic range)
  - Impedance analyzer: measures real/imaginary response per frequency bin
  - Haptic mapper: maps organ gap → tactile frequency + intensity
  - Spectral symmetry check: φ-aligned frequency pairs produce resonance

Integration:
  - Reads organ-state.json for gap Δ value
  - Writes impedance spectra to metta-ledger.jsonl
  - Optionally drives audio output for software-defined haptics
  - Real hardware: PWM/GPIO for LRA/ERM drivers via audio jack

Dependencies: numpy (required), sounddevice (optional, for audio output)
"""
import json
import math
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

# ─── §1 CONSTANTS ──────────────────────────────────────────────────────────
PHI           = (1.0 + math.sqrt(5.0)) / 2.0  # golden ratio
F_START       = 20.0                            # Hz — low haptic
F_END         = 20000.0                         # Hz — ultrasonic ceiling
POINTS_PER_DECADE = 50                          # frequency resolution
DURATION_SWEEP    = 2.0                         # seconds per sweep
AMPLITUDE     = 0.5                             # normalized drive amplitude
SAMPLE_RATE   = 48000                           # Hz
SYMMETRY_TOL  = 0.05                            # φ-tolerance for resonance

# Organ mapping
GAP_HEALTHY   = 0.04
GAP_ALIVE_MAX = 0.015

# Paths
METTA_LEDGER  = Path(os.path.expanduser("~/metta-ledger.jsonl"))
ORGAN_STATE   = Path(os.path.expanduser("~/organ-state.json"))
IMPEDANCE_LOG = Path(os.path.expanduser("~/impedance-spectra.jsonl"))
PID_FILE      = Path(os.path.expanduser("~/haptic-transducer.pid"))

# ─── §2 SIGNAL GENERATION ──────────────────────────────────────────────────

def generate_exponential_chirp(
    f_start: float, f_end: float, duration: float,
    sample_rate: int, amplitude: float
) -> np.ndarray:
    """
    Exponential (log-spaced) chirp.
    Instantaneous frequency: f(t) = f_start * (f_end/f_start)^(t/duration)
    """
    n_samples = int(duration * sample_rate)
    t = np.linspace(0, duration, n_samples, endpoint=False)

    # Exponential frequency sweep
    k = (f_end / f_start) ** (1.0 / duration)
    phase = 2.0 * math.pi * f_start * (k**t - 1.0) / math.log(k)
    signal = amplitude * np.sin(phase)

    # Apply Hann window to avoid clicks
    window = 0.5 * (1.0 - np.cos(2.0 * math.pi * np.arange(n_samples) / n_samples))
    return signal * window

def generate_phi_sweep(
    f_center: float, duration: float,
    sample_rate: int, amplitude: float
) -> np.ndarray:
    """Generate a sweep around a φ-symmetric frequency pair."""
    f_low  = f_center / PHI
    f_high = f_center * PHI
    chirp_low  = generate_exponential_chirp(f_low, f_center, duration/2, sample_rate, amplitude)
    chirp_high = generate_exponential_chirp(f_center, f_high, duration/2, sample_rate, amplitude)
    return np.concatenate([chirp_low, chirp_high])

# ─── §3 IMPEDANCE ANALYSIS ─────────────────────────────────────────────────

def compute_impedance_spectrum(
    drive_signal: np.ndarray,
    sense_signal: np.ndarray,
    sample_rate: int,
    n_bins: int = 2048
) -> dict:
    """
    Compute impedance Z(f) = V_drive(f) / I_sense(f).
    Returns magnitude, phase, real/imaginary per frequency bin.
    """
    n = len(drive_signal)
    if n < n_bins:
        n_bins = n

    # FFT
    V_f = np.fft.rfft(drive_signal * np.hanning(n), n=n)
    I_f = np.fft.rfft(sense_signal * np.hanning(n), n=n)

    freqs = np.fft.rfftfreq(n, d=1.0/sample_rate)

    # Impedance = V/I, with regularization
    eps = 1e-12
    Z_f = V_f / (I_f + eps)

    mag  = np.abs(Z_f)
    phase = np.angle(Z_f)
    real = Z_f.real
    imag = Z_f.imag

    return {
        "freqs": freqs.tolist(),
        "magnitude": mag.tolist(),
        "phase": phase.tolist(),
        "real": real.tolist(),
        "imag": imag.tolist(),
    }

def compute_phi_resonance_score(spectrum: dict, haptic_only: bool = True) -> float:
    """
    Check if impedance peaks align at φ-ratio frequency pairs.
    Higher score = stronger φ resonance in the impedance spectrum.

    If haptic_only=True, restrict analysis to 20-200 Hz (the tactile band).
    This prevents high-frequency FFT artifacts from masking φ-pairs.

    This is the original peak-bin-dominance scorer, kept for backward
    compatibility.  Prefer compute_phi_resonance_score_band() for
    sweep-stable integrated prominence.
    """
    freqs = np.array(spectrum["freqs"])
    mag   = np.array(spectrum["magnitude"])

    # Restrict to haptic band if requested
    if haptic_only:
        mask = (freqs >= 20.0) & (freqs <= 200.0)
        if np.sum(mask) < 4:
            return 0.0
        freqs = freqs[mask]
        mag   = mag[mask]

    # Find peaks — simple gradient-based peak detection (no scipy dependency)
    peaks_idx = []
    threshold = np.max(mag) * 0.1
    for i in range(1, len(mag) - 1):
        if mag[i] > threshold and mag[i] > mag[i-1] and mag[i] > mag[i+1]:
            peaks_idx.append(i)

    if len(peaks_idx) < 2:
        return 0.0

    peak_freqs = freqs[peaks_idx]

    # Check for φ-ratio pairs
    resonant_pairs = 0
    for i in range(len(peak_freqs)):
        for j in range(i+1, len(peak_freqs)):
            ratio = max(peak_freqs[i], peak_freqs[j]) / min(peak_freqs[i], peak_freqs[j])
            if abs(ratio - PHI) <= SYMMETRY_TOL:
                resonant_pairs += 1

    total_possible = len(peak_freqs) * (len(peak_freqs) - 1) / 2
    return resonant_pairs / max(total_possible, 1)


def compute_phi_resonance_score_band(
    spectrum: dict,
    f_low: float = 34.0,
    f_high: float = 55.0,
    band_halfwidth: float = 3.0,
    baseline_gap: float = 2.0,
    haptic_only: bool = True,
) -> float:
    """
    Band-integrated φ-resonance score — stable across sweep lengths.

    Instead of peak-bin counting, this measures the integrated spectral
    prominence of the φ-pair (f_low, f_high) relative to local sidebands.

    For each φ-band:
        integrated_energy = sum(|Z|²) over [f_center ± band_halfwidth]
        baseline_energy   = mean(|Z|²) over sidebands
        prominence        = integrated_energy / (baseline + ε)

    The final score is the geometric mean of the two prominences, mapped
    through a saturation curve so that strong resonance → 1.0 and
    flat spectrum → 0.0.

    Parameters:
        spectrum:       dict with 'freqs' and 'magnitude' arrays
        f_low, f_high:  center frequencies of the φ-pair (default 34, 55 Hz)
        band_halfwidth: half-width of each integration band in Hz (default 3)
        baseline_gap:   gap between integration band edge and baseline
                        sideband start, in Hz (default 2)
        haptic_only:    if True, restrict to 20–200 Hz haptic band

    Returns:
        φ-score in [0, 1] where:
            ≤ 0.05  → FLAT (no resonant curvature)
            ≥ 0.60  → RESONANCE WITNESSED
    """
    freqs = np.array(spectrum["freqs"])
    mag   = np.array(spectrum["magnitude"])

    if haptic_only:
        mask = (freqs >= 20.0) & (freqs <= 200.0)
        if np.sum(mask) < 4:
            return 0.0
        freqs = freqs[mask]
        mag   = mag[mask]

    eps = 1e-12

    def _band_prominence(f_center: float) -> float:
        """Compute peak-to-baseline prominence for one φ-band."""
        in_band = (freqs >= f_center - band_halfwidth) & \
                  (freqs <= f_center + band_halfwidth)
        if np.sum(in_band) < 2:
            return 0.0

        # Peak magnitude within the φ-band
        band_peak = np.max(mag[in_band])

        # Sidebands: regions just outside the integration band
        lo_side = (freqs >= f_center - band_halfwidth - baseline_gap - band_halfwidth) & \
                  (freqs < f_center - band_halfwidth)
        hi_side = (freqs > f_center + band_halfwidth) & \
                  (freqs <= f_center + band_halfwidth + baseline_gap + band_halfwidth)
        side_mask = lo_side | hi_side

        if np.sum(side_mask) < 2:
            baseline_rms = math.sqrt(np.mean(mag ** 2) + eps)
        else:
            baseline_rms = math.sqrt(np.mean(mag[side_mask] ** 2) + eps)

        # Prominence = band peak / sideband RMS
        # Flat spectrum → ~1.0; resonance peak → >> 1.0
        return band_peak / max(baseline_rms, 1e-12)

    prom_low = _band_prominence(f_low)
    prom_high = _band_prominence(f_high)

    # Geometric mean rewards both members of the φ-pair
    pair_score = math.sqrt(max(prom_low, 0.0) * max(prom_high, 0.0))

    # Map through saturation curve: sigmoid-like without scipy dependency
    # tanh(k * (x - x0)) shifted to [0, 1]
    # x0=1.5 separates flat (~1.0) from resonant (>1.5)
    # k=5.0 gives sharp knee at the decision boundary
    k = 5.0
    x0 = 1.5
    score = 0.5 * (1.0 + math.tanh(k * (pair_score - x0)))

    return float(score)


def inject_curvature(
    spectrum: dict,
    f_resonance: float = 34.0,
    q_factor: float = 8.0,
    gain_db: float = 12.0,
    sample_rate: int = 48000
) -> dict:
    """
    Inject a synthetic resonance into the impedance spectrum.
    Used to validate φ-score responsiveness without real hardware.

    Places a resonant peak at f_resonance with quality factor Q.
    If f_resonance has a φ-ratio partner (f_resonance * PHI or f_resonance / PHI)
    within the sweep range, both are injected.
    """
    freqs = np.array(spectrum["freqs"])
    mag   = np.array(spectrum["magnitude"]).copy()
    phase = np.array(spectrum["phase"]).copy()

    gain_linear = 10.0 ** (gain_db / 20.0)

    def _resonance_peak(f: np.ndarray, f0: float, Q: float, G: float) -> np.ndarray:
        """Second-order resonance: H(s) = G * (ω0/Q)*s / (s² + (ω0/Q)*s + ω0²)."""
        omega0 = 2.0 * math.pi * f0
        s = 2.0j * math.pi * f  # s = jω
        H = G * (omega0 / Q) * s / (s**2 + (omega0 / Q) * s + omega0**2)
        return np.abs(H)

    # Inject primary resonance
    mag += _resonance_peak(freqs, f_resonance, q_factor, gain_linear)

    # Inject φ-ratio partner if within sweep range
    f_partner_high = f_resonance * PHI
    f_partner_low  = f_resonance / PHI
    f_min, f_max = freqs[1], freqs[-1]  # skip DC bin

    if f_min <= f_partner_high <= f_max:
        mag += _resonance_peak(freqs, f_partner_high, q_factor, gain_linear * 0.7)
    if f_min <= f_partner_low <= f_max:
        mag += _resonance_peak(freqs, f_partner_low, q_factor, gain_linear * 0.7)

    return {
        "freqs": freqs.tolist(),
        "magnitude": mag.tolist(),
        "phase": phase.tolist(),  # phase unchanged for now
        "real": (mag * np.cos(phase)).tolist(),
        "imag": (mag * np.sin(phase)).tolist(),
        "curvature_injected": True,
        "f_resonance": f_resonance,
        "q_factor": q_factor,
        "gain_db": gain_db,
    }

# ─── §4 HAPTIC MAPPER ──────────────────────────────────────────────────────

# Safe tactile band: 28Hz (felt as deep rumble on most hardware) to 55Hz
# Reduces reliance on infrasonic <20Hz which HDMI/consumer audio often filters.
FREQ_HEALTHY = 55.0
FREQ_DANGER  = 28.0   # raised from 17Hz — survives HDMI high-pass

AMP_HEALTHY  = 0.25
AMP_DANGER   = 0.60   # reduced from 0.8 — safer for continuous output

# Smoothing factor per update tick (~3s interval)
SMOOTHING     = 0.12
# Hysteresis margins prevent oscillation near thresholds
HYST_ENTER_DANGER = 0.090
HYST_EXIT_DANGER  = 0.085
HYST_ENTER_ALIVE  = 0.040
HYST_EXIT_ALIVE   = 0.043

# Stale input: if gap hasn't updated in this many seconds, fade to neutral
STALE_TIMEOUT_S = 6.0
NEUTRAL_FREQ    = 40.0
NEUTRAL_AMP     = 0.12

# Pathological gap detection
# Raw gap values > PATHOLOGICAL_ENTER indicate sensor fault / implausible input.
# Output stays safe but diagnostic truth is preserved in state + flags.
PATHOLOGICAL_ENTER  = 0.30   # enter PATHOLOGICAL_CLAMP when raw_gap exceeds this
PATHOLOGICAL_EXIT   = 0.25   # exit PATHOLOGICAL_CLAMP when raw_gap drops below this
PATHOLOGICAL_HOLD   = 3      # sustained cycles below exit before recovery declared
SAFETY_CEILING_HZ   = 200.0  # hard frequency ceiling — logged if reached

# Phase accumulator (module-level — survives across cycles)
_phase_acc = 0.0
_prev_gap  = GAP_HEALTHY
_prev_state = "ALIVE"
_gap_timestamp = 0.0

# Pathology tracking (module-level — survives across cycles)
_pathology_counter  = 0       # consecutive cycles in PATHOLOGICAL_CLAMP
_pathology_total    = 0       # lifetime count of pathological entries
_last_pathology_log = 0.0     # timestamp of last rate-limited log
_clamp_flags        = {}       # per-cycle flags: dict of str→bool


def gap_to_haptic_smoothed(gap: float, gap_ts: float) -> tuple[float, float, float, str]:
    """
    Map gap → haptic params with smoothing, hysteresis, stale detection,
    and pathological-gap clamping.

    Returns (frequency, intensity, pulse_width, state_label).
    Side effect: updates module-level _clamp_flags dict with per-cycle diagnostics.
    """
    global _phase_acc, _prev_gap, _prev_state, _gap_timestamp
    global _pathology_counter, _pathology_total, _last_pathology_log, _clamp_flags

    _clamp_flags = {}  # reset per-cycle flags

    now = time.time()
    raw_gap = gap  # preserve diagnostic truth before clamping

    # ── Stale input detection ──
    if gap_ts > 0 and (now - max(gap_ts, _gap_timestamp)) > STALE_TIMEOUT_S:
        # Fade toward neutral
        _prev_gap += 0.05 * (GAP_HEALTHY - _prev_gap)
        return (NEUTRAL_FREQ, NEUTRAL_AMP, 0.08, "STALE")
    _gap_timestamp = max(gap_ts, _gap_timestamp) if gap_ts > 0 else _gap_timestamp

    # ── Pathological gap detection (on raw_gap, before clamping) ──
    if raw_gap > PATHOLOGICAL_ENTER:
        if _prev_state != "PATHOLOGICAL_CLAMP":
            _pathology_total += 1
            _pathology_counter = 1
            _clamp_flags["PATHOLOGICAL_GAP"] = True
        else:
            _pathology_counter += 1
            _clamp_flags["PATHOLOGICAL_GAP"] = True

        # Rate-limited logging: first occurrence, then every 60s
        if _pathology_counter == 1 or (now - _last_pathology_log) >= 60.0:
            _last_pathology_log = now

        _prev_state = "PATHOLOGICAL_CLAMP"

    elif _prev_state == "PATHOLOGICAL_CLAMP":
        if raw_gap <= PATHOLOGICAL_EXIT:
            _pathology_counter -= 1
            if _pathology_counter <= 0:
                _pathology_counter = 0
                _prev_state = "ALIVE"  # recover
            else:
                # still in hold — stay pathological until sustained recovery
                _clamp_flags["PATHOLOGICAL_GAP"] = True
        else:
            _pathology_counter = _pathology_counter or 1
            _clamp_flags["PATHOLOGICAL_GAP"] = True

    # ── Clamp gap for mapping (output safety) ──
    gap = max(0.025, min(0.10, raw_gap))

    # ── Hysteresis for normal state boundaries (skip if pathological) ──
    if _prev_state not in ("PATHOLOGICAL_CLAMP",):
        if _prev_state == "ALIVE" and gap > HYST_EXIT_ALIVE:
            _prev_state = "WARNING"
        elif _prev_state == "WARNING":
            if gap > HYST_ENTER_DANGER:
                _prev_state = "DANGER"
            elif gap < HYST_ENTER_ALIVE:
                _prev_state = "ALIVE"
        elif _prev_state == "DANGER" and gap < HYST_EXIT_DANGER:
            _prev_state = "WARNING"
        elif _prev_state == "STALE" and abs(gap - GAP_HEALTHY) < GAP_ALIVE_MAX:
            _prev_state = "ALIVE"

    # ── Compute target params ──
    t = (gap - GAP_HEALTHY) / max(HYST_ENTER_DANGER - GAP_HEALTHY, 0.001)
    t = max(0.0, min(1.0, t))

    target_freq = FREQ_HEALTHY + t * (FREQ_DANGER - FREQ_HEALTHY)
    target_amp  = AMP_HEALTHY  + t * (AMP_DANGER  - AMP_HEALTHY)
    target_width = 0.10 + t * 0.30

    # ── Smooth transitions ──
    prev_f, prev_i, prev_w = gap_to_haptic(_prev_gap)
    prev_freq = prev_f
    prev_amp  = prev_i

    freq = prev_freq + SMOOTHING * (target_freq - prev_freq)
    amp  = prev_amp  + SMOOTHING * (target_amp  - prev_amp)

    # ── Safety clamp: hardware limits regardless of state ──
    # Flags: only fire when clamp actively constrains an out-of-bounds value
    if freq < FREQ_DANGER:
        _clamp_flags["FREQ_FLOOR_HIT"] = True
    if freq > SAFETY_CEILING_HZ:
        _clamp_flags["FREQ_CEILING_HIT"] = True
    if amp < AMP_HEALTHY:
        _clamp_flags["INTENSITY_FLOOR_HIT"] = True
    if amp > AMP_DANGER:
        _clamp_flags["INTENSITY_CEILING_HIT"] = True

    freq = max(FREQ_DANGER, min(SAFETY_CEILING_HZ, freq))
    amp  = max(AMP_HEALTHY, min(AMP_DANGER, amp))

    _prev_gap = gap

    return (freq, amp, target_width, _prev_state)


def gap_to_haptic(gap: float) -> tuple[float, float, float]:
    """
    Simple stateless mapping — used as fallback and for initial state.
    Maps gap to (freq, intensity, pulse_width).
    All outputs clamped to safe ranges: freq ∈ [28, 200], intensity ∈ [0.25, 0.60].
    """
    if abs(gap - GAP_HEALTHY) < GAP_ALIVE_MAX:
        return (FREQ_HEALTHY, AMP_HEALTHY, 0.10)
    elif gap < 0.025:
        deviation = min((0.025 - gap) / 0.025, 1.0)
        freq  = FREQ_HEALTHY + deviation * 80.0
        intensity = max(AMP_HEALTHY, AMP_HEALTHY + deviation * 0.35)
        return (freq, min(intensity, AMP_DANGER), 0.06)
    else:
        deviation = min((gap - 0.055) / 0.045, 1.0)
        freq  = max(FREQ_DANGER, FREQ_HEALTHY * (1.0 - deviation * 0.5))
        # Clamp: intensity stays within [AMP_HEALTHY, AMP_DANGER]
        if deviation < 0:
            intensity = AMP_HEALTHY
        else:
            intensity = AMP_HEALTHY + deviation * (AMP_DANGER - AMP_HEALTHY)
        width = 0.10 + max(0.0, deviation) * 0.30
        return (freq, intensity, width)

def generate_haptic_signal(
    base_freq: float, intensity: float, pulse_width: float,
    duration: float, sample_rate: int
) -> np.ndarray:
    """
    Generate haptic drive signal with continuous-phase PWM-modulated sine.
    Uses a module-level phase accumulator (_phase_acc) to avoid clicks
    from buffer-boundary phase resets.
    Danger state (low freq, high intensity) uses amplitude modulation
    at 6–10Hz for sharper perceptual pulses that survive HDMI filtering.
    """
    global _phase_acc

    n_samples = int(duration * sample_rate)
    t = np.linspace(0, duration, n_samples, endpoint=False)

    # Continuous phase: pick up where we left off
    phase = _phase_acc + 2.0 * math.pi * base_freq * t
    carrier = np.sin(phase)

    # Update phase accumulator for next call
    _phase_acc = phase[-1] + 2.0 * math.pi * base_freq / sample_rate
    _phase_acc = _phase_acc % (2.0 * math.pi)

    # ── Envelope ──
    if base_freq <= 35.0:
        # Danger: amplitude modulation at 8Hz for sharp thumps
        mod_freq = 8.0
        envelope = 0.4 + 0.6 * np.sin(2.0 * math.pi * mod_freq * t)**2
    else:
        # Healthy/warning: gentle pulse-width modulation
        pulse_period = 1.0 / max(base_freq * 0.1, 1.0)
        pulse_phase  = (t % pulse_period) / pulse_period
        envelope = np.where(pulse_phase < pulse_width, 1.0, 0.0)
        # Smooth edges
        kernel = np.ones(min(100, n_samples // 4)) / min(100, n_samples // 4)
        envelope = np.convolve(envelope, kernel, mode='same')

    # ── Attack/release ramp on the envelope ──
    ramp_samples = min(int(0.03 * sample_rate), n_samples // 4)  # 30ms attack
    release_samples = min(int(0.15 * sample_rate), n_samples // 2)  # 150ms release
    if ramp_samples > 0:
        envelope[:ramp_samples] *= np.linspace(0, 1, ramp_samples)
    if release_samples > 0:
        envelope[-release_samples:] *= np.linspace(1, 0, release_samples)

    return intensity * carrier * envelope

# ─── §5 LEDGER WRITE ───────────────────────────────────────────────────────

def write_impedance_event(event_type: str, data: dict):
    """Write impedance spectroscopy event to ledger."""
    ts = datetime.now(timezone.utc).isoformat()
    event = {
        "event_type": event_type,
        "probe": "haptic_transducer",
        "timestamp_utc": ts,
        **data,
    }
    with open(METTA_LEDGER, 'a') as f:
        f.write(json.dumps(event, default=_json_default) + '\n')
    with open(IMPEDANCE_LOG, 'a') as f:
        f.write(json.dumps(event, default=_json_default) + '\n')

def _json_default(obj):
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if hasattr(obj, 'dtype'):
        return float(obj)
    return str(obj)

# ─── §6 SIMULATED SENSE (for testing without hardware) ────────────────────

def simulate_sense_signal(
    drive_signal: np.ndarray,
    gap: float,
    sample_rate: int
) -> np.ndarray:
    """
    Simulate a sense (current) signal based on a simple RLC model.
    The gap Δ modulates the damping — wide gap = more damping.
    """
    n = len(drive_signal)
    t = np.linspace(0, n/sample_rate, n, endpoint=False)

    # RLC parameters modulated by gap
    R = 10.0 + 100.0 * (gap / 0.10)       # resistance increases with gap
    L = 0.001                               # inductance (fixed)
    C = 1e-6                                # capacitance (fixed)

    # Transfer function H(s) = 1/(LC*s^2 + RC*s + 1)
    # Approximate via state-space in time domain (simple 2nd order filter)
    # y'' + (R/L)*y' + (1/(LC))*y = (1/(LC))*x
    omega_n = 1.0 / math.sqrt(L * C)
    zeta = R / (2.0 * math.sqrt(L / C))

    # Impulse response of 2nd order underdamped system
    w_d = omega_n * math.sqrt(1.0 - min(zeta, 0.999)**2)
    decay = np.exp(-zeta * omega_n * t)
    response = decay * np.sin(w_d * t) / (w_d + 1e-12)

    # Convolve with drive
    sense = np.convolve(drive_signal, response[:min(1000, n)], mode='same')
    sense = sense / (np.max(np.abs(sense)) + 1e-12) * 0.5

    return sense.astype(np.float64)

# ─── §7 MAIN ───────────────────────────────────────────────────────────────

def main():
    # Prevent concurrent instances
    if PID_FILE.exists():
        try:
            old_pid = int(PID_FILE.read_text().strip())
            os.kill(old_pid, 0)
            print(f"Haptic Transducer already running (PID {old_pid}). Exiting.", flush=True)
            return
        except (OSError, ValueError):
            PID_FILE.unlink(missing_ok=True)

    PID_FILE.write_text(str(os.getpid()))

    # ── CLI flags ──
    import argparse
    ap = argparse.ArgumentParser(description="Impedance Spectroscopy Haptic Transducer")
    ap.add_argument("--curvature", action="store_true",
                    help="Inject synthetic φ-resonance for φ-score validation")
    ap.add_argument("--curvature-freq", type=float, default=34.0,
                    help="Resonance center frequency (Hz, default 34)")
    ap.add_argument("--curvature-q", type=float, default=8.0,
                    help="Resonance Q factor (default 8)")
    ap.add_argument("--curvature-gain", type=float, default=12.0,
                    help="Resonance gain in dB (default 12)")
    args, _ = ap.parse_known_args()

    # Try to load sounddevice for real audio output
    sd = None
    try:
        import sounddevice as sd_mod
        sd = sd_mod
        print(f"Audio output: {sd.query_devices()[0]['name']}", flush=True)
    except (ImportError, OSError):
        print("sounddevice/PortAudio not available — running in simulation mode", flush=True)

    def shutdown(signum, frame):
        print("\nHaptic Transducer stopped.", flush=True)
        write_impedance_event("haptic_transducer_stop", {"detail": "shutdown"})
        PID_FILE.unlink(missing_ok=True)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print(f"Haptic Transducer Probe — PID {os.getpid()}", flush=True)
    print(f"  Sweep: {F_START:.0f}–{F_END:.0f} Hz, {POINTS_PER_DECADE} pts/decade", flush=True)
    print(f"  φ-resonance tolerance: ±{SYMMETRY_TOL}", flush=True)
    print(f"  Mode: {'audio' if sd else 'simulation'}", flush=True)
    if args.curvature:
        print(f"  Curvature: INJECTED f0={args.curvature_freq}Hz Q={args.curvature_q} gain={args.curvature_gain}dB", flush=True)

    write_impedance_event("haptic_transducer_start", {
        "detail": f"Impedance spectroscopy haptic transducer activated. "
                  f"φ={PHI:.6f}, sweep={F_START:.0f}-{F_END:.0f}Hz, "
                  f"mode={'audio' if sd else 'simulation'}"
    })

    cycle = 0
    while True:
        try:
            # ── Read organ state ──
            gap = GAP_HEALTHY
            beat = 0
            gap_ts = 0.0
            if ORGAN_STATE.exists():
                try:
                    state = json.loads(ORGAN_STATE.read_text())
                    gap = state.get("gap", GAP_HEALTHY)
                    beat = state.get("beat", 0)
                    gap_ts = time.time()  # record freshness
                except (json.JSONDecodeError, KeyError):
                    pass

            # ── Generate impedance sweep ──
            drive = generate_exponential_chirp(
                F_START, F_END, DURATION_SWEEP, SAMPLE_RATE, AMPLITUDE
            )

            # Simulate sense signal (or read from hardware ADC)
            sense = simulate_sense_signal(drive, gap, SAMPLE_RATE)

            # Compute impedance spectrum
            spectrum = compute_impedance_spectrum(drive, sense, SAMPLE_RATE)

            # Inject synthetic curvature if requested (φ-score validation)
            if args.curvature:
                spectrum = inject_curvature(spectrum, args.curvature_freq,
                                            args.curvature_q, args.curvature_gain,
                                            SAMPLE_RATE)

            # Compute φ-resonance score (band-integrated for sweep stability)
            phi_score = compute_phi_resonance_score_band(spectrum)

            # ── Generate haptic output with smoothing ──
            freq, intensity, width, state_label = gap_to_haptic_smoothed(gap, gap_ts)
            haptic = generate_haptic_signal(freq, intensity, width, 0.5, SAMPLE_RATE)

            # DC offset check (guard for transducer safety)
            dc_offset = float(np.mean(haptic))
            peak = float(np.max(np.abs(haptic)))

            # Output to audio if available
            if sd and cycle % 5 == 0:
                try:
                    sd.play(haptic, SAMPLE_RATE, blocking=False)
                except Exception as e:
                    print(f"  Audio error: {e}", file=sys.stderr, flush=True)

            # ── Log ──
            write_impedance_event("impedance_spectrum", {
                "cycle": cycle,
                "gap": round(gap, 6),
                "beat": beat,
                "state": state_label,
                "phi_resonance_score": round(phi_score, 4),
                "haptic_freq": round(freq, 2),
                "haptic_intensity": round(intensity, 3),
                "haptic_pulse_width": round(width, 3),
                "peak_impedance_freq": float(
                    np.array(spectrum["freqs"])[np.argmax(spectrum["magnitude"])]
                ),
                "mean_impedance_mag": float(np.mean(spectrum["magnitude"])),
                "dc_offset": round(dc_offset, 8),
                "peak_amplitude": round(peak, 4),
                "clamp_flags": dict(_clamp_flags) if _clamp_flags else None,
            })

            if cycle % 10 == 0:
                stale_marker = " [STALE]" if state_label == "STALE" else ""
                print(f"  cycle={cycle:4d}  gap={gap:.4f}  state={state_label}{stale_marker}  "
                      f"φ={phi_score:.3f}  haptic={freq:.0f}Hz@{intensity:.2f}  "
                      f"pk={peak:.3f}  beat={beat}", flush=True)

            cycle += 1
            time.sleep(3.0)  # sweep interval

        except Exception as e:
            print(f"  Error: {e}", file=sys.stderr, flush=True)
            time.sleep(5.0)

if __name__ == "__main__":
    main()
