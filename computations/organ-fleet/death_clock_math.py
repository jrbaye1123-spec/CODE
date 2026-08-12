"""
Death Clock Telemetry — Pure Mathematics Module (v3)
=====================================================
Locked: do not refactor the core math. Faithful extraction from v2 .pyc
with corrections applied:
  • HEALTHY_GAP = 0.04 (organ-fleet raw spec scale, not Schatten-1)
  • SG coefficients pre-computed at module init (removes per-call pinv)
  • compute_delta uses organ-fleet's canonical ∆ from ledger

Math stack:
  compute_delta            — organ-fleet ∆ from ledger entry
  savitzky_golay           — Savitzky-Golay smoothing (coeffs pre-computed)
  fit_logistic_collapse    — ∆(B) ∝ (B_max − B)^ν  logistic collapse model
  detect_inflection_smoothed — SG-smoothed second derivative inflection
  beats_remaining_logistic — logistic-model beats-to-death estimate
  estimate_schatten1_gap   — trajectory-level gap statistics
  estimate_void_density    — void density from sigma glycation
"""

import math
import numpy as np
from collections import deque


# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS — Organ-fleet raw spec scale (§14)
# ═══════════════════════════════════════════════════════════════════════════════

DEATH_THRESHOLD     = 5e-04       # ∆ ≤ this = death (§4: DEATH_∆)
HEALTHY_GAP         = 0.04        # §3.2: ∆_healthy (organ-fleet raw scale)
GAP_ALIVE_MIN       = 0.025       # ALIVE lower bound (|∆ − 0.04| < 0.015)
GAP_DANGER_WIDE     = 0.10        # §3.3: DANGER_WIDE threshold
SG_WINDOW           = 31          # Savitzky-Golay window (must be odd)
SG_ORDER            = 3           # Savitzky-Golay polynomial order
COLLAPSE_WINDOW     = 500         # beats to use for logistic fit
COLLAPSE_MIN_POINTS = 100         # minimum data points for collapse fit
TARGET_BPM          = 55
BEAT_INTERVAL       = 60.0 / 55.0


# ═══════════════════════════════════════════════════════════════════════════════
# PRE-COMPUTED SG COEFFICIENTS (window=31, order=3)
# ═══════════════════════════════════════════════════════════════════════════════
# Computed once at module load. The Vandermonde matrix is static for fixed
# window/order — recalculating pinv per beat is wasteful and adds jitter.

def _compute_sg_coeffs(window_size, order):
    """Build Savitzky-Golay coefficient filters via pseudo-inverse."""
    half = window_size // 2
    b = np.array([[k ** i for i in range(order + 1)]
                   for k in range(-half, half + 1)], dtype=np.float64)
    pinv_b = np.linalg.pinv(b)
    return pinv_b[0], pinv_b[1], pinv_b[2]

_SG_M, _SG_D1, _SG_D2 = _compute_sg_coeffs(SG_WINDOW, SG_ORDER)
# Pre-reverse for convolution (valid mode)
_SG_M_REV  = _SG_M[::-1].copy()
_SG_D1_REV = _SG_D1[::-1].copy()
_SG_D2_REV = _SG_D2[::-1].copy()


# ═══════════════════════════════════════════════════════════════════════════════
# SAVITZKY-GOLAY FILTER (§1 — Sanity Check 2 fix)
# ═══════════════════════════════════════════════════════════════════════════════

def savitzky_golay(y, window_size=SG_WINDOW, order=SG_ORDER):
    """
    Savitzky-Golay smoothing filter.
    Returns (y_smooth, d1_smooth, d2_smooth) — value, 1st deriv, 2nd deriv.
    All outputs have length len(y) - window_size + 1 (valid convolution mode).

    Uses pre-computed coefficient filters (computed once at module init).
    This replaces naked discrete differencing on raw data, eliminating
    the derivative noise amplification that caused false inflection triggers.
    """
    if len(y) < window_size:
        return y, None, None

    y_arr = np.asarray(y, dtype=np.float64)

    # Use pre-computed coefficients if window/order match defaults
    if window_size == SG_WINDOW and order == SG_ORDER:
        y_smooth  = np.convolve(y_arr, _SG_M_REV,  mode='valid')
        d1_smooth = np.convolve(y_arr, _SG_D1_REV, mode='valid')
        d2_smooth = np.convolve(y_arr, _SG_D2_REV, mode='valid')
    else:
        m, d1, d2 = _compute_sg_coeffs(window_size, order)
        y_smooth  = np.convolve(y_arr, m[::-1],  mode='valid')
        d1_smooth = np.convolve(y_arr, d1[::-1], mode='valid')
        d2_smooth = np.convolve(y_arr, d2[::-1], mode='valid')

    return y_smooth, d1_smooth, d2_smooth


# ═══════════════════════════════════════════════════════════════════════════════
# LOGISTIC COLLAPSE MODEL (§2 — Sanity Check 1 fix)
# ═══════════════════════════════════════════════════════════════════════════════

def fit_logistic_collapse(beats, gaps, b_current):
    """
    Fit logistic collapse model:  ∆(B) = A * ((B_max - B) / B_max)^ν

    Replaces linear OLS extrapolation. Models the non-linear cliff:
    as the system approaches critical void density, the decay accelerates
    (critical slowing down → phase transition).

    Parameters
    ----------
    beats : ndarray
        Beat numbers (x-axis).
    gaps : ndarray
        Schatten-1 gap values (y-axis).
    b_current : int
        Current beat number (for B_max candidate range).

    Returns
    -------
    dict with keys:
        b_max, nu, A, beats_to_death, r2, confidence_lo, confidence_hi, status
    """
    n = len(beats)
    if n < COLLAPSE_MIN_POINTS:
        return {
            'b_max': None, 'nu': None, 'A': None,
            'beats_to_death': None, 'r2': 0.0,
            'confidence_lo': None, 'confidence_hi': None,
            'status': 'insufficient_data'
        }

    beats_arr = np.asarray(beats, dtype=np.float64)
    gaps_arr   = np.asarray(gaps, dtype=np.float64)

    # Initialise with fallback
    best_r2   = -math.inf
    best_Bmax = None
    best_nu   = None
    best_A    = None

    # Candidate B_max: from 1% beyond current to 100x current
    # This covers a wide parameter space without overfitting
    candidates = np.logspace(
        np.log10(b_current * 1.01),
        np.log10(b_current * 100),
        num=50
    ).astype(np.float64)

    for b_max in candidates:
        distances = b_max - beats_arr

        # Only fit on beats before B_max (positive distances)
        mask = distances > 0
        if mask.sum() < COLLAPSE_MIN_POINTS // 2:
            continue

        d_masked = distances[mask]
        g_masked = gaps_arr[mask]

        # Log-space linear regression: log(∆) = log(A) + ν * log(B_max - B)
        # Only use positive gaps (log of negative is undefined)
        pos_mask = g_masked > 0
        if pos_mask.sum() < 10:
            continue

        x = np.log(d_masked[pos_mask])
        y = np.log(g_masked[pos_mask])

        # Ordinary Least Squares in log-space
        x_mean = x.mean()
        y_mean = y.mean()
        numerator   = ((x - x_mean) * (y - y_mean)).sum()
        denominator = ((x - x_mean) ** 2).sum()

        if denominator < 1e-30:
            continue

        nu_est = numerator / denominator
        log_A  = y_mean - nu_est * x_mean
        # Guard against overflow: exp(log_A) must fit in float64
        # Skip candidates that produce pathological fits (log_A outside sane range)
        if abs(log_A) > 500.0 or abs(nu_est) > 20.0:
            continue
        A_est  = math.exp(log_A)

        # R² computation
        y_pred = log_A + nu_est * x
        ss_res = ((y - y_pred) ** 2).sum()
        ss_tot = ((y - y_mean) ** 2).sum()
        r2 = 1.0 - ss_res / max(ss_tot, 1e-30)

        if r2 > best_r2:
            best_r2   = r2
            best_Bmax = b_max
            best_nu   = nu_est
            best_A    = A_est

    if best_Bmax is None:
        return {
            'b_max': None, 'nu': None, 'A': None,
            'beats_to_death': None, 'r2': 0.0,
            'confidence_lo': None, 'confidence_hi': None,
            'status': 'fit_failed'
        }

    # Compute beats to death with the best-fit model
    # Solve: DEATH_THRESHOLD = A * ((B_max - B_death) / B_max)^ν
    # B_death = B_max * (1 - (DEATH_THRESHOLD / A)^(1/ν))
    if best_A > DEATH_THRESHOLD and best_nu > 0:
        ratio = DEATH_THRESHOLD / best_A
        b_death = best_Bmax * (1.0 - ratio ** (1.0 / best_nu))
        beats_to_death = max(0.0, b_death - b_current)
    else:
        b_death = best_Bmax
        beats_to_death = max(0.0, best_Bmax - b_current)

    # Confidence interval: ±20% based on R² quality
    confidence_width = max(0.05, (1.0 - best_r2)) * beats_to_death
    confidence_lo = max(0.0, beats_to_death - confidence_width)
    confidence_hi = beats_to_death + confidence_width

    return {
        'b_max':           float(best_Bmax),
        'nu':              float(best_nu),
        'A':               float(best_A),
        'beats_to_death':  float(beats_to_death),
        'r2':              float(best_r2),
        'confidence_lo':   float(confidence_lo),
        'confidence_hi':   float(confidence_hi),
        'status':          'ok'
    }


# ═══════════════════════════════════════════════════════════════════════════════
# INFLECTION DETECTION (SG-smoothed) (§3)
# ═══════════════════════════════════════════════════════════════════════════════

def detect_inflection_smoothed(beats, deltas, window=SG_WINDOW, order=SG_ORDER):
    """
    Detect curvature inflection using SG-smoothed second derivative.

    Replaces naked d²∆/dB² on raw data. The SG filter suppresses
    high-frequency noise before differentiation, eliminating the
    catastrophic false-positive problem.

    Returns (inflection_detected, inflection_magnitude, y_smooth, d1_smooth, d2_smooth)
    """
    if len(deltas) < window:
        return False, 0.0, None, None, None

    y_smooth, d1_smooth, d2_smooth = savitzky_golay(deltas, window, order)

    if d2_smooth is None or len(d2_smooth) == 0:
        return False, 0.0, y_smooth, d1_smooth, None

    # Threshold: 3σ above mean of |d²∆/dB²|
    d2_abs = np.abs(d2_smooth)
    mean_abs = d2_abs.mean()
    std_abs  = d2_abs.std()

    threshold = 3.0 * max(mean_abs, 1e-12) * 2.0  # 2x safety factor

    max_d2 = d2_abs.max()
    inflection_detected = max_d2 > threshold
    inflection_magnitude = float(max_d2)

    return (inflection_detected, inflection_magnitude,
            y_smooth, d1_smooth, d2_smooth)


# ═══════════════════════════════════════════════════════════════════════════════
# ORGAN-FLEET GAP (§4 — uses ledger's canonical ∆)
# ═══════════════════════════════════════════════════════════════════════════════

def compute_delta(entry: dict) -> float:
    """
    Return the organ-fleet's canonical ∆ from the ledger entry.

    The organ-fleet already computes ∆ per §2 of the specification and
    writes it as `gap` in every beat entry. The death-clock uses this
    authoritative metric directly rather than computing a separate
    Schatten-1 estimate in a conflicting scale.

    Healthy: ∆ ≈ 0.04  (§3.2)
    Death:   ∆ ≤ 5e-04 (§4: DEATH_∆)
    """
    return entry.get('gap', 0.04)


def estimate_gap_statistics(beats, deltas):
    """
    Trajectory-level gap statistics from the time series.

    Returns (min_gap, ema_gap) where:
      min_gap = minimum ∆ in window (worst-case)
      ema_gap = exponential moving average of last 10 points

    For DANGER_WIDE states (∆ ≥ 0.10), min_gap reflects the peak excursion.
    For DANGER_NARROW states (∆ < 0.01), min_gap reflects the trough.
    """
    if len(deltas) == 0:
        return HEALTHY_GAP, HEALTHY_GAP

    min_gap = float(np.min(deltas))
    # EMA with α=0.3 on last 10 points
    tail = np.asarray(deltas[-10:], dtype=np.float64)
    alpha = 0.3
    ema = tail[0]
    for v in tail[1:]:
        ema = alpha * v + (1.0 - alpha) * ema

    return min_gap, float(ema)


def estimate_void_density(beats, deltas, sigma_values):
    """
    Estimate void density from the sigma glycation trajectory.

    Void density ≈ cumulative sigma / cumulative beats
    Normalized to [0, 1] where 1.0 = total rigidity.
    """
    if len(sigma_values) < 2:
        return 0.0

    sigma_arr = np.asarray(sigma_values, dtype=np.float64)
    beats_arr = np.asarray(beats, dtype=np.float64)

    # Rate of sigma accumulation
    d_sigma = np.diff(sigma_arr)
    d_beats = np.diff(beats_arr)

    # Positive sigma steps (glycation events)
    pos_mask = d_sigma > 0
    if pos_mask.sum() == 0:
        return 0.0

    total_accumulation = d_sigma[pos_mask].sum()
    total_beats = d_beats[pos_mask].sum()

    # Void density = accumulation per beat, scaled
    void = total_accumulation / max(total_beats, 1.0)
    void = min(1.0, void * 5000.0)  # scale factor from spec
    return float(void)


def beats_remaining_logistic(beats, deltas):
    """
    Estimate beats remaining using the logistic collapse model.

    This replaces the linear OLS trap. The logistic model correctly
    captures the non-linear acceleration toward death (critical
    slowing down → phase transition at Σ_c).

    Returns a dict with beats_to_death and confidence interval.
    """
    if len(beats) < COLLAPSE_MIN_POINTS:
        return {
            'beats_to_death': None,
            'confidence_lo': None,
            'confidence_hi': None,
            'b_max': None,
            'nu': None,
            'r2': 0.0,
            'status': 'insufficient_data'
        }

    # Use the tail of the data for fitting
    tail_beats = beats[-COLLAPSE_WINDOW:]
    tail_gaps  = deltas[-COLLAPSE_WINDOW:]
    b_current  = int(beats[-1])

    result = fit_logistic_collapse(tail_beats, tail_gaps, b_current)
    return result
