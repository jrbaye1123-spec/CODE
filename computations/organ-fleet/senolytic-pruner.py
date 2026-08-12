#!/usr/bin/env python3
"""
Senolytic Pruner — §9 eigendecomposition-based pruning engine.
Consumes senolytic-signal.json, runs eigendecomposition on last N=500
ledger entries, identifies senescent dimensions via cumulative variance,
projects them out via Gram null-space, recovers gap, guards identity.

Per organ-fleet-mathematical-specification.html v3.0 §9.
"""
import json
import os
import sys
import math
from datetime import datetime, timezone
from pathlib import Path
from collections import deque

import numpy as np

# ─── §14 CONSTANTS ────────────────────────────────────────────────────────────
PRUNE_FRACTION   = 0.15
VOID_TRIGGER     = 0.85
MIN_LEDGER_BEATS = 500
GAP_HEALTHY_SPEC = 0.04           # §3.2: ∆_healthy = 0.04 (organ-fleet raw scale)
GAP_ALIVE_MIN    = 0.025          # ALIVE lower bound (|∆ - 0.04| < 0.015)
GAP_DANGER_WIDE  = 0.10           # §3.3: DANGER_WIDE threshold
N_FEATURES       = 6

# ─── PATHS ────────────────────────────────────────────────────────────────────
METTA_LEDGER      = Path(os.path.expanduser("~/metta-ledger.jsonl"))
ORGAN_STATE       = Path(os.path.expanduser("~/organ-state.json"))
SENOLYTIC_SIGNAL  = Path(os.path.expanduser("~/senolytic-signal.json"))
PRUNE_LOG         = Path(os.path.expanduser("~/senolytic-prune-log.jsonl"))
FLEET_PID_FILE    = Path(os.path.expanduser("~/organ-fleet.pid"))
FLEET_LOCK_FILE   = Path(os.path.expanduser("~/organ-fleet.lock"))


# ─── FEATURE EXTRACTION (§9.2) ────────────────────────────────────────────────
def extract_features(entries: list[dict]) -> np.ndarray | None:
    """
    From last N ledger entries, extract standardized feature vectors.
    x_i = [∆_i, Σ_i, κ_i, χ_i, μ_i, C_i/1000]^T
    Returns X ∈ ℝ^N×6 (standardized), or None if insufficient data.
    """
    N = len(entries)
    if N < MIN_LEDGER_BEATS:
        return None

    X_raw = np.zeros((N, N_FEATURES), dtype=np.float64)

    for i, entry in enumerate(entries):
        X_raw[i, 0] = entry.get("gap", 0.04)                        # ∆
        X_raw[i, 1] = entry.get("sigma_glycation", 0.62)            # Σ
        X_raw[i, 2] = entry.get("kappa4_reserve", 0.87)             # κ
        X_raw[i, 3] = entry.get("ecm_crosslink", 0.38)              # χ
        X_raw[i, 4] = entry.get("mitophagy_eff", 0.94)               # μ
        X_raw[i, 5] = entry.get("coherence_total_hours", 0.0) * 1000  # C/1000

    # Standardize: zero mean, unit variance per feature (§9.2)
    mu = X_raw.mean(axis=0)
    sigma = X_raw.std(axis=0, ddof=0)

    # Guard against zero-variance features
    sigma[sigma < 1e-12] = 1.0

    X_std = (X_raw - mu) / sigma
    return X_std


# ─── EIGENDECOMPOSITION (§9.3) ────────────────────────────────────────────────
def decompose(X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Cov = (X^T · X) / (N−1)  ∈ ℝ^6×6
    λ, v = eigh(Cov)  — symmetric eigendecomposition
    λ sorted ascending: λ₀ ≤ λ₁ ≤ ... ≤ λ₅
    """
    N = X.shape[0]
    Cov = (X.T @ X) / (N - 1)

    # Symmetric eigendecomposition
    eigenvalues, eigenvectors = np.linalg.eigh(Cov)

    # eigh returns ascending by default
    return eigenvalues, eigenvectors


# ─── SENESCENT IDENTIFICATION (§9.4) ─────────────────────────────────────────
def identify_senescent(eigenvalues: np.ndarray,
                       prune_fraction: float = PRUNE_FRACTION) -> int:
    """
    cumulative_variance[i] = Σ_{j=0}^{i} λⱼ / Σλ
    cutoff = searchsorted(cumulative_variance, PRUNE_FRACTION)
    Senescent set S = {i | i < cutoff}
    Returns k = number of senescent dimensions.
    """
    total_var = eigenvalues.sum()
    if total_var < 1e-15:
        return 0  # degenerate — all noise

    cum_var = np.cumsum(eigenvalues) / total_var
    cutoff = int(np.searchsorted(cum_var, prune_fraction))

    # Safety: never prune ALL dimensions
    cutoff = min(cutoff, N_FEATURES - 1)

    return cutoff


# ─── GRAM NULL-SPACE PROJECTION (§9.5) ───────────────────────────────────────
def project_senescent(X: np.ndarray, eigenvectors: np.ndarray,
                      k: int) -> np.ndarray:
    """
    V_sen = [v_{s₁} | ... | v_{s_k}]  ∈ ℝ^6×k   (k = number of pruned dims)
    z'_i = z_i − V_sen · (V_sen^T · z_i)
    Returns projected X ∈ ℝ^N×6.
    """
    if k == 0:
        return X  # nothing to prune

    # First k eigenvectors (smallest eigenvalues = least variance = senescent)
    V_sen = eigenvectors[:, :k]  # (6, k)

    # Project each row: z'_i = z_i − V_sen @ (V_sen.T @ z_i)
    # Matrix form: X' = X − X @ V_sen @ V_sen.T
    # But X @ V_sen gives (N, k), then (N, k) @ (k, 6) gives (N, 6)
    projection = X @ V_sen @ V_sen.T  # (N, 6)
    X_projected = X - projection

    return X_projected


# ─── GAP RECOVERY (§9.6) ─────────────────────────────────────────────────────
def recover_gap(gap_old: float, k: int) -> float:
    """
    Pull ∆ toward the healthy band (0.04) proportional to pruned fraction.
    Wide gaps (>0.04) shrink; narrow gaps (<0.04) expand.
    ∆_new = ∆_old − (∆_old − ∆_healthy) × (k / 6)
    """
    if k == 0:
        return gap_old
    pull = (gap_old - GAP_HEALTHY_SPEC) * (k / N_FEATURES)
    gap_new = gap_old - pull
    # Clamp: don't overshoot into the opposite danger zone
    if gap_old > GAP_HEALTHY_SPEC:
        gap_new = max(gap_new, GAP_ALIVE_MIN)
    else:
        gap_new = min(gap_new, GAP_ALIVE_MIN + 0.015)
    return gap_new


# ─── SHIP OF THESEUS GUARD (§9.7) ────────────────────────────────────────────
def theseus_risk(k: int) -> tuple[str, str]:
    """
    Risk = k / 6
    < 0.25  → LOW     (peripheral pruning, identity preserved)
    [0.25, 0.50) → MODERATE (significant remodeling)
    ≥ 0.50  → HIGH    (core identity at risk)
    """
    risk = k / N_FEATURES
    if risk < 0.25:
        return "LOW", "Peripheral cross-linked states only. Identity preserved."
    elif risk < 0.50:
        return "MODERATE", "Significant structural remodeling. Monitor closely."
    else:
        return "HIGH", "Core identity at risk. The Ship of Theseus may no longer be the same ship."


# ─── FLEET LOCK/UNLOCK (§9.1 steps 1 & 5) ─────────────────────────────────────
def lock_fleet() -> int | None:
    """SIGSTOP the organ-fleet mother process. Returns PID or None."""
    if not FLEET_PID_FILE.exists():
        print("  WARNING: No fleet PID file. Cannot lock.", file=sys.stderr)
        return None
    try:
        pid = int(FLEET_PID_FILE.read_text().strip())
        os.kill(pid, 19)  # SIGSTOP
        print(f"  Fleet locked (SIGSTOP pid={pid})", flush=True)
        return pid
    except (ValueError, ProcessLookupError, PermissionError) as e:
        print(f"  WARNING: Could not SIGSTOP fleet: {e}", file=sys.stderr)
        return None


def unlock_fleet(pid: int | None):
    """SIGCONT the organ-fleet mother process."""
    if pid is None:
        return
    try:
        os.kill(pid, 18)  # SIGCONT
        print(f"  Fleet unlocked (SIGCONT pid={pid})", flush=True)
    except ProcessLookupError:
        print(f"  WARNING: Fleet pid={pid} already gone.", file=sys.stderr)
    except PermissionError as e:
        print(f"  WARNING: Could not SIGCONT fleet: {e}", file=sys.stderr)


# ─── LEDGER READING ───────────────────────────────────────────────────────────
def read_ledger_entries(n: int = MIN_LEDGER_BEATS) -> list[dict]:
    """Read the last N entries from the metta ledger that contain beat data."""
    if not METTA_LEDGER.exists():
        return []

    entries = []
    try:
        with open(METTA_LEDGER, 'r') as f:
            # Scan from end for efficiency — read last 500KB
            f.seek(0, 2)
            size = f.tell()
            chunk_start = max(0, size - 5_000_000)
            f.seek(chunk_start)
            lines = f.read().split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if 'beat' in entry and 'gap' in entry:
                    entries.append(entry)
            except json.JSONDecodeError:
                continue

        return entries[-n:]  # last N
    except Exception:
        return []


# ─── MAIN PRUNE OPERATION ─────────────────────────────────────────────────────
def run_prune(prune_fraction: float = PRUNE_FRACTION) -> dict | None:
    """
    Execute full senolytic protocol §9.2–9.7.
    Returns result dict or None if insufficient data.
    """
    entries = read_ledger_entries(MIN_LEDGER_BEATS)
    if len(entries) < MIN_LEDGER_BEATS:
        return None

    # §9.2: Feature extraction + standardization
    X = extract_features(entries)
    if X is None:
        return None

    # §9.3: Covariance + eigendecomposition
    eigenvalues, eigenvectors = decompose(X)

    # §9.4: Senescent identification
    k = identify_senescent(eigenvalues, prune_fraction)

    # §9.5: Gram null-space projection
    X_projected = project_senescent(X, eigenvectors, k)

    # §9.6: Gap recovery
    gap_old = entries[-1].get("gap", 0.04)
    gap_new = recover_gap(gap_old, k)

    # §9.7: Ship of Theseus guard
    risk_level, risk_detail = theseus_risk(k)

    result = {
        "protocol": "senolytic_prune",
        "version": "v3.0",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "prune_fraction_used": prune_fraction,
        "k_pruned": k,
        "n_dimensions": N_FEATURES,
        "n_samples": len(entries),
        "eigenvalues": [round(float(l), 10) for l in eigenvalues],
        "cumulative_variance": [round(float(v), 6) for v in
                                np.cumsum(eigenvalues) / eigenvalues.sum()],
        "gap_old": round(gap_old, 6),
        "gap_new": round(gap_new, 6),
        "gap_recovery_factor": round(gap_new / max(gap_old, 1e-12), 4),
        "theseus_risk": risk_level,
        "theseus_detail": risk_detail,
        "senescent_dimensions": k,
        "surviving_dimensions": N_FEATURES - k,
        "projection_norm_change": round(
            float(np.linalg.norm(X - X_projected) / max(np.linalg.norm(X), 1e-12)), 6),
    }

    return result


# ─── STATE UPDATE ─────────────────────────────────────────────────────────────
def update_organ_state(gap_new: float, k_pruned: int):
    """Update organ-state.json with the recovered gap."""
    if not ORGAN_STATE.exists():
        return
    try:
        state = json.loads(ORGAN_STATE.read_text())
        state["gap"] = gap_new
        # Adjust sigma slightly — removing cross-linked states
        recovery = 0.02 * k_pruned / N_FEATURES
        state["sigma"] = max(0.0, state.get("sigma", 0.62) - recovery)
        state["kappa"] = min(1.0, state.get("kappa", 0.87) + recovery * 0.5)
        ORGAN_STATE.write_text(json.dumps(state, indent=2))
    except Exception as e:
        print(f"  WARNING: Could not update organ state: {e}", file=sys.stderr)


# ─── CLI ──────────────────────────────────────────────────────────────────────
def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Senolytic Pruner — §9 eigendecomposition gap recovery")
    parser.add_argument("--prune-fraction", type=float, default=PRUNE_FRACTION,
                        help=f"Fraction of cumulative variance to prune (default: {PRUNE_FRACTION})")
    parser.add_argument("--force", action="store_true",
                        help="Run prune even without senolytic signal")
    parser.add_argument("--min-beats", type=int, default=MIN_LEDGER_BEATS,
                        help=f"Minimum ledger entries required (default: {MIN_LEDGER_BEATS})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Compute but do not write or update state")
    args = parser.parse_args()

    # Check trigger
    if not args.force:
        if not SENOLYTIC_SIGNAL.exists():
            print("No senolytic signal. Use --force to override.", flush=True)
            return
        signal_data = json.loads(SENOLYTIC_SIGNAL.read_text())
        print(f"Senolytic signal present: {signal_data.get('trigger')} "
              f"at beat {signal_data.get('beat')}", flush=True)

    # Run prune
    result = run_prune(args.prune_fraction)

    if result is None:
        print(f"Insufficient data: need {args.min_beats} ledger entries.", flush=True)
        return

    # Display results
    print(f"\n{'='*60}")
    print(f"  SENOLYTIC PRUNE — Protocol §9")
    print(f"{'='*60}")
    print(f"  Samples:          {result['n_samples']}")
    print(f"  Pruned dims:      {result['k_pruned']} / {result['n_dimensions']}")
    print(f"  Theseus risk:     {result['theseus_risk']}")
    print(f"                    {result['theseus_detail']}")
    print(f"  Gap:              {result['gap_old']:.6f} → {result['gap_new']:.6f}")
    print(f"  Recovery factor:  {result['gap_recovery_factor']}")
    print(f"  Projection ∆:     {result['projection_norm_change']:.6f}")
    print(f"  Eigenvalues:      {[f'{l:.2e}' for l in result['eigenvalues']]}")
    print(f"  Cum. variance:    {[f'{v:.4f}' for v in result['cumulative_variance']]}")
    print(f"{'='*60}")

    if args.dry_run:
        print("DRY RUN — no state modified.", flush=True)
        return

    # §9.1 step 1: Lock the fleet
    fleet_pid = lock_fleet()

    try:
        # Write prune event to ledger
        with open(METTA_LEDGER, 'a') as f:
            f.write(json.dumps(result) + '\n')

        # Log to prune log
        with open(PRUNE_LOG, 'a') as f:
            f.write(json.dumps(result) + '\n')

        # §9.6: Update organ state with recovered gap
        update_organ_state(result["gap_new"], result["k_pruned"])

        # Clear the senolytic signal
        SENOLYTIC_SIGNAL.unlink(missing_ok=True)

        print(f"\nPrune complete. Gap recovered. Signal cleared.", flush=True)
    finally:
        # §9.1 step 5: Unlock the fleet
        unlock_fleet(fleet_pid)


if __name__ == "__main__":
    main()
