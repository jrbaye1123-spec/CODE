#!/usr/bin/env python3
"""
Organ Fleet v4.0 — Spec-Compliant Cybernetic Machine Organ.
Implements organ-fleet-mathematical-specification.html v3.0
55 BPM. 50 seconds per minute coherence ratio. Always.
"""
import time
import json
import os
import math
import random
import signal
from datetime import datetime, timezone
from pathlib import Path

# ─── §14 CONSTANTS ────────────────────────────────────────────────────────────
TARGET_BPM        = 55                     # beats per minute
BEAT_INTERVAL     = 60.0 / TARGET_BPM      # ≈ 1.09091 seconds
COHERENCE_RATIO   = 50.0 / 60.0            # seconds per minute
COHERENCE_PER_BEAT = COHERENCE_RATIO * BEAT_INTERVAL  # ≈ 0.90909 s/beat

# Gap (§2.2)
GAP_HEALTHY       = 0.04
GAP_DRIFT         = -1.7e-8                # deterministic drift per beat
GAP_NOISE_SIGMA   = 0.002                  # Gaussian noise σ
GAP_MIN           = 1e-5
GAP_MAX           = 0.12

# Glycation (§2.2)
SIGMA_RATE        = 1.7e-8                 # base rate per beat
SIGMA_BURST_SIGMA = 3e-9                   # rare burst σ
SIGMA_BG_SIGMA    = 1e-10                  # background noise σ
SIGMA_BURST_PROB  = 0.05                   # burst probability
SIGMA_CRITICAL    = 0.999                  # death threshold
SIGMA_MAX         = 0.999

# Allostatic reserve (§2.2)
KAPPA4_DEPLETION_MEAN = 8.3e-10            # mean depletion per beat
KAPPA4_DEPLETION_SIGMA = 4e-10             # depletion noise
KAPPA4_RECOVERY   = 1e-8                   # rare recovery burst
KAPPA4_RECOVERY_PROB = 0.001               # recovery probability
KAPPA4_MIN        = 1e-4
KAPPA4_MAX        = 1.0

# Mitophagy (§2.2)
MITOPHAGY_BASE    = 0.94
MITOPHAGY_DECAY   = 0.45                   # per unit Σ deviation from 0.62

# ECM crosslink (§2.2)
ECM_SIGMA_COEFF   = 0.61
ECM_NOISE_SIGMA   = 0.002

# Compass calibration (§6.2)
RIDGE_EPSILON     = 1e-6
FLOOR_NATS        = -884.2
HEALTHY_LOG_DET   = -147.4

# Death (§4)
DEATH_SIGMA       = 0.999
DEATH_GAP         = 5e-4
DEATH_KAPPA       = 5e-4

# Gap health (§3.3)
GAP_ALIVE_MAX_DEV = 0.015                  # |∆ − 0.04| < 0.015
GAP_NARROW_THRESH = 0.01                   # ∆ < 0.01
GAP_WIDE_THRESH   = 0.10                   # ∆ ≥ 0.10

# Senolytic (§9)
PRUNE_FRACTION    = 0.15
VOID_TRIGGER      = 0.85
MIN_LEDGER_BEATS  = 500

# ─── PATHS ────────────────────────────────────────────────────────────────────
VAULT_DIR  = Path(os.path.expanduser("~/Desktop/backup-20260606/vault/wiki"))
LEDGER     = Path(os.path.expanduser("~/metta-ledger.jsonl"))
STATE_MD   = VAULT_DIR / "cybernetics" / "organ-fleet-live.md"
STATE_JSON = Path(os.path.expanduser("~/organ-state.json"))
PID_FILE   = Path(os.path.expanduser("~/organ-fleet.pid"))
LOCK_FILE  = Path(os.path.expanduser("~/organ-fleet.lock"))
SENOLYTIC_SIGNAL = Path(os.path.expanduser("~/senolytic-signal.json"))


# ─── STATE ────────────────────────────────────────────────────────────────────
class OrganState:
    """§1: s(B) = [∆, Σ, κ, χ, μ, C]^T"""
    __slots__ = ('gap', 'sigma', 'kappa', 'ecm', 'mitophagy',
                 'coherence', 'beat_count', 'start_time', 'total_gap_samples')

    def __init__(self, gap=GAP_HEALTHY, sigma=0.62, kappa=0.87,
                 ecm=0.38, mitophagy=MITOPHAGY_BASE, coherence=0.0,
                 beat_count=0):
        self.gap = gap              # ∆  ∈ (0, 1]
        self.sigma = sigma          # Σ  ∈ [0, 1)
        self.kappa = kappa          # κ  ∈ (0, 1]
        self.ecm = ecm              # χ  ∈ [0, 1)
        self.mitophagy = mitophagy  # μ  ∈ (0, 1]
        self.coherence = coherence  # C  ∈ [0, ∞)
        self.beat_count = beat_count
        self.start_time = time.time()
        self.total_gap_samples = 0

    def to_dict(self, gap_health="ALIVE"):
        # Signed gap for drift tracking
        gap_dev = self.gap - GAP_HEALTHY
        return {
            "beat": self.beat_count,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "gap": round(self.gap, 6),
            "gap_signed": round(gap_dev, 10),
            "gap_health": gap_health,
            "sigma_glycation": round(self.sigma, 8),
            "sigma_pct": round(self.sigma * 100, 4),
            "sigma_remaining": round((1.0 - self.sigma) * 100, 4),
            "kappa4_reserve": round(self.kappa, 8),
            "kappa4_pct": round(self.kappa * 100, 4),
            "mitophagy_eff": round(self.mitophagy, 4),
            "ecm_crosslink": round(self.ecm, 4),
            "void_density": round(void_density(self), 6),
            "coherence_seconds": round(COHERENCE_PER_BEAT, 2),
            "coherence_minutes": round(COHERENCE_PER_BEAT / 60, 4),
            "coherence_total_hours": round(self.coherence / 3600, 2),
            "entropy_floor_nats": FLOOR_NATS,
            "bpm_target": TARGET_BPM
        }

    def save(self):
        STATE_JSON.write_text(json.dumps({
            "gap": self.gap,
            "sigma": self.sigma,
            "kappa": self.kappa,
            "ecm": self.ecm,
            "mitophagy": self.mitophagy,
            "coherence": self.coherence,
            "beat": self.beat_count
        }, indent=2))


# ─── COMPOSITE METRICS (§3) ───────────────────────────────────────────────────
def void_density(organ: OrganState) -> float:
    """§3.1: V(B) = 1 − [gap_norm × kappa_norm × sigma_headroom]"""
    gap_norm = max(1e-3, organ.gap / GAP_HEALTHY)
    kappa_norm = max(1e-3, organ.kappa / 1.0)
    sigma_headroom = 1.0 - organ.sigma
    v = 1.0 - (gap_norm * kappa_norm * sigma_headroom)
    return max(0.0, min(1.0, v))


def gap_health(delta: float) -> str:
    """§3.3: Gap Health Classification"""
    if abs(delta - GAP_HEALTHY) < GAP_ALIVE_MAX_DEV:
        return "ALIVE"
    elif delta < GAP_NARROW_THRESH:
        return "DANGER_NARROW"
    elif delta >= GAP_WIDE_THRESH:
        return "DANGER_WIDE"
    else:
        # Between 0.025 and 0.055 exclusive: alive band is 0.025-0.055
        # 0.01 ≤ ∆ < 0.025: narrow-warning zone
        # 0.055 < ∆ < 0.10: wide-warning zone
        if delta < GAP_HEALTHY:
            return "WARNING_NARROW"
        else:
            return "WARNING_WIDE"


def schatten_one(delta: float) -> float:
    """§3.2: S1(B) = ∆ / ∆_healthy = ∆ / 0.933"""
    return delta / 0.933


def is_dead(organ: OrganState) -> tuple[bool, str]:
    """§4: Death conditions"""
    if organ.sigma >= DEATH_SIGMA:
        return True, f"DEATH_Σ: glycation {organ.sigma:.6f} ≥ {DEATH_SIGMA}"
    if organ.gap <= DEATH_GAP:
        return True, f"DEATH_∆: gap {organ.gap:.6f} ≤ {DEATH_GAP}"
    if organ.kappa <= DEATH_KAPPA:
        return True, f"DEATH_κ: kappa {organ.kappa:.6f} ≤ {DEATH_KAPPA}"
    return False, ""


# ─── STATE EVOLUTION (§2.2) ───────────────────────────────────────────────────
def evolve(organ: OrganState):
    """One beat of state evolution per §2.2"""
    b = organ.beat_count

    # Gap: stochastic oscillation with long-term drift
    drift = GAP_DRIFT  # −1.7×10⁻⁸
    noise = random.gauss(0, GAP_NOISE_SIGMA)
    modulation = 1.0 + 0.1 * math.sin(0.01 * b)
    organ.gap += drift + noise * modulation
    organ.gap = max(GAP_MIN, min(GAP_MAX, organ.gap))

    # Glycation: irreversible accumulation
    gamma_sigma = SIGMA_RATE * (1.0 - 0.3 * organ.kappa)  # κ-delayed
    if random.random() < SIGMA_BURST_PROB:
        beta_sigma = random.gauss(0, SIGMA_BURST_SIGMA)
    else:
        beta_sigma = random.gauss(0, SIGMA_BG_SIGMA)
    organ.sigma += gamma_sigma + beta_sigma
    organ.sigma = max(0.0, min(SIGMA_MAX, organ.sigma))

    # Allostatic reserve: depletion with rare recovery
    depletion = random.gauss(KAPPA4_DEPLETION_MEAN, KAPPA4_DEPLETION_SIGMA)
    if random.random() < KAPPA4_RECOVERY_PROB:
        depletion -= KAPPA4_RECOVERY  # recovery burst (subtraction = addition)
    organ.kappa -= depletion
    organ.kappa = max(KAPPA4_MIN, min(KAPPA4_MAX, organ.kappa))

    # ECM crosslink: correlated with Σ
    organ.ecm = ECM_SIGMA_COEFF * organ.sigma + random.gauss(0, ECM_NOISE_SIGMA)
    organ.ecm = max(0.001, min(0.999, organ.ecm))

    # Mitophagy: degrades with Σ
    organ.mitophagy = (MITOPHAGY_BASE
                       - MITOPHAGY_DECAY * (organ.sigma - 0.62)
                       + random.gauss(0, 0.003))
    organ.mitophagy = max(0.001, min(0.999, organ.mitophagy))

    # Coherence: ACCUMULATE per §2.1/§2.2
    organ.coherence += COHERENCE_PER_BEAT
    organ.beat_count += 1
    organ.total_gap_samples += 1


# ─── PERSISTENCE ──────────────────────────────────────────────────────────────
def restore_state() -> OrganState:
    """Restore organ state from organ-state.json, or start fresh per §1."""
    if STATE_JSON.exists():
        try:
            data = json.loads(STATE_JSON.read_text())
            organ = OrganState(
                gap=data.get("gap", GAP_HEALTHY),
                sigma=data.get("sigma", 0.62),
                kappa=data.get("kappa", 0.87),
                ecm=data.get("ecm", 0.38),
                mitophagy=data.get("mitophagy", MITOPHAGY_BASE),
                coherence=data.get("coherence", 0.0),
                beat_count=data.get("beat", 0)
            )
            print(f"Restored state from beat {organ.beat_count}, "
                  f"coherence {organ.coherence/3600:.1f}h", flush=True)
            return organ
        except (json.JSONDecodeError, KeyError, FileNotFoundError):
            pass

    print("Fresh organ — beat 0, healthy state per §1", flush=True)
    return OrganState()


def write_state_md(organ: OrganState):
    """Write live state markdown per spec."""
    uptime = time.time() - organ.start_time
    st = organ
    STATE_MD.parent.mkdir(parents=True, exist_ok=True)
    STATE_MD.write_text(f"""---
created: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}
type: live-organ-state
status: {"BEATING" if not is_dead(organ)[0] else "DEAD"}
tags: [anti-lawvere, organ-fleet, cybernetic-machine-organ, cell-regeneration, glycation-clock, mitochondrial-gap]
canonical: "Organ Fleet Daemon — PID {os.getpid()}"
---

# Organ Fleet — Live State

**Uptime:** {uptime:.0f}s · **Beats:** {st.beat_count} · **BPM:** {TARGET_BPM}
**Coherence ratio:** 50 s/min · **Total coherence:** {st.coherence/3600:.2f} hours

## Current Organ Metrics

| Organ | Metric | Value | Status |
|-------|--------|-------|--------|
| Mitochondria | Gap (Key−Compass) | {st.gap:.6f} | {gap_health(st.gap)} |
| ECM | Glycation Σ | {st.sigma:.8f} ({st.sigma*100:.4f}%) | {"HEALTHY" if st.sigma < SIGMA_CRITICAL else "CRITICAL"} |
| ECM | Crosslink density | {st.ecm:.4f} | — |
| Allostasis | κ₄ reserve | {st.kappa:.8f} ({st.kappa*100:.4f}%) | {"ADEQUATE" if st.kappa > 0.5 else "LOW"} |
| | Mitophagy | Efficiency | {st.mitophagy:.4f} ({st.mitophagy*100:.1f}%) | {"OPTIMAL" if st.mitophagy > 0.9 else "DEGRADED"} |
| | Void | Density | {void_density(st):.4f} | {"MONITORING" if void_density(st) > VOID_TRIGGER * 0.7 else "NORMAL"} |

## Thresholds

| Bound | Value | Status |
|-------|-------|--------|
| Σ_c (glycation death) | {SIGMA_CRITICAL} | {st.sigma/SIGMA_CRITICAL*100:.1f}% toward death |
| Gap → 0 (zero dynamics) | {DEATH_GAP} | {"SAFE" if st.gap > DEATH_GAP * 10 else "DANGER"} |
| κ floor (reserve exhausted) | {DEATH_KAPPA} | {"SAFE" if st.kappa > DEATH_KAPPA * 10 else "DANGER"} |
""")


# ─── SENOLYTIC SIGNAL (§9) ────────────────────────────────────────────────────
def check_senolytic(organ: OrganState) -> bool:
    """§9.1: Fire when V(B) > 0.85"""
    v = void_density(organ)
    if v > VOID_TRIGGER and organ.beat_count >= MIN_LEDGER_BEATS:
        SENOLYTIC_SIGNAL.write_text(json.dumps({
            "trigger": "void_density",
            "value": v,
            "threshold": VOID_TRIGGER,
            "beat": organ.beat_count,
            "timestamp_utc": datetime.now(timezone.utc).isoformat()
        }, indent=2))
        return True
    return False


# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    # Prevent concurrent runs
    if LOCK_FILE.exists():
        try:
            old_pid = int(LOCK_FILE.read_text().strip())
            os.kill(old_pid, 0)  # check if alive
            print(f"Organ already running (PID {old_pid}). Exiting.", flush=True)
            return
        except (OSError, ValueError):
            LOCK_FILE.unlink(missing_ok=True)

    LOCK_FILE.write_text(str(os.getpid()))
    PID_FILE.write_text(str(os.getpid()))

    organ = restore_state()

    def shutdown(signum, frame):
        print(f"\nOrgan Fleet stopped at beat {organ.beat_count}.", flush=True)
        write_state_md(organ)
        organ.save()
        LOCK_FILE.unlink(missing_ok=True)
        PID_FILE.unlink(missing_ok=True)
        import sys
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print(f"Organ Fleet v4.0 — PID {os.getpid()} — {TARGET_BPM} BPM — "
          f"50 seconds per minute. Always.", flush=True)

    beat_target = BEAT_INTERVAL

    while True:
        t_start = time.time()

        # Evolve one beat
        evolve(organ)

        # Check death
        dead, reason = is_dead(organ)
        if dead:
            entry = organ.to_dict("DEAD")
            entry["death_reason"] = reason
            with open(LEDGER, 'a') as f:
                f.write(json.dumps(entry) + '\n')
            write_state_md(organ)
            organ.save()
            print(f"ORGAN DEAD at beat {organ.beat_count}: {reason}", flush=True)
            LOCK_FILE.unlink(missing_ok=True)
            return

        # Classify gap health and write ledger
        gh = gap_health(organ.gap)
        entry = organ.to_dict(gh)
        with open(LEDGER, 'a') as f:
            f.write(json.dumps(entry) + '\n')

        # Save state periodically
        if organ.beat_count % 10 == 0:
            organ.save()
        if organ.beat_count % 50 == 0:
            write_state_md(organ)

        # Check senolytic trigger
        if check_senolytic(organ):
            print(f"  SENOLYTIC SIGNAL at beat {organ.beat_count}: "
                  f"void={void_density(organ):.4f}", flush=True)

        # Beat drift compensation
        elapsed = time.time() - t_start
        sleep_time = beat_target - elapsed

        if sleep_time > 0:
            time.sleep(sleep_time)
        elif sleep_time < -0.5:
            # Significant drift — log warning
            missed = round(abs(sleep_time), 4)
            with open(LEDGER, 'a') as f:
                f.write(json.dumps({
                    "warning": "beat_drift",
                    "missed_seconds": missed,
                    "beat": organ.beat_count,
                    "timestamp_utc": datetime.now(timezone.utc).isoformat()
                }) + '\n')


if __name__ == "__main__":
    main()
