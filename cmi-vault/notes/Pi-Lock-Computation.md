---
tags: [CMI, computation, pi-lock, scaffold, eigenvalue, Lyapunov]
created: 2026-08-12
---

# Π-Lock Computation — Stripped to the Iron

**Script:** `computations/pi_lock_final.py`
**Results:** `computations/results/pi_lock_final.json`, `computations/results/figure1_convergence.png`

## What It Computes

The definitive Π-lock simulation. No bifurcations. No critical damping. No poetic artifacts.

### Core System

```
Φ̇  = α·Φ − β·Φ² − γ·Φ³
Ṁ  = Φ − M/τ_m
α̇  = κ(M − α)
```

### Parameters (Empirically Anchored)

| Parameter | Value | Source |
|-----------|-------|--------|
| α₀ | 7.68 | Universal spectral invariant (14 datasets) |
| τ_m | 12.0 | ECM memory (pre-implant HRV test) |
| β | 1.0 | Intrinsic ganglionic decay rate |
| γ | 17.1875 | Derived: τ_m(τ_m − β)/α₀ |

### Fixed Point

- Φ* = 0.6400 (homeostatic set-point)
- M* = 7.6800
- α* = 7.6800 ≡ α₀ ✓

## Key Results

### Part 1: Cubic Discriminant Analysis — No Bifurcation

The cubic discriminant Δ > 0 for ALL κ > 0, τ_m > β. All eigenvalues are real and negative. This is always an **overdamped stable node**. No Hopf bifurcation. No spiral. No threshold.

### Part 2: Time-Domain Convergence

κ only controls convergence speed monotonically:
- κτ_m = 0.5 → T₁% ≈ ∞ (very slow)
- κτ_m = 1.0 → T₁% ≈ 165.0 days
- κτ_m = 2.0 → T₁% ≈ 137.6 days
- κτ_m = 4.0 → T₁% ≈ 124.6 days (recommended)

The lock is **τ_m > β**, not κ. Even κτ_m = 0.2 eventually converges.

### Part 3: Engineering Protocol

1. **Measure τ_m** — Pre-implant HRV perturbation-recovery test (5 min)
2. **Set γ** — γ = τ_m(τ_m − β)/α₀, controlled via PEG crosslinking density
3. **Set κ** — κ = 4/τ_m (practical), controlled via GO concentration + pore size
4. **Implant** — Φ(t) → Φ* monotonically. No overshoot. No oscillation.

### The True Lock

```
τ_m > β  ⇒  guaranteed imprint  (biologically guaranteed)
γ = τ_m(τ_m − β)/α₀  ⇒  spectral matching  (empirically anchored)
κ  ⇒  speed dial  (manufacturing tolerance: ±50% still works)
```

## Outputs

- `pi_lock_final.json` — Full trajectory data for all κ regimes
- `figure1_convergence.png` — Monotonic convergence plot with asymptote zoom

## Cross-References

- [[CMI-Computations-MOC]]
- [[CMI-Core-Equation]]
- [[Scaffold-3D-Computation]]
- [[Eigenvalue-Deep-Dive]]
