---
tags: [CMI, computation, scaffold, plasticity, integro-differential, Lyapunov]
created: 2026-08-12
---

# Scaffold Plasticity Computation — The Π-Lock Master Equation

**Script:** `computations/scaffold_plasticity.py`
**Results:** `computations/results/scaffold_results.json`

## What It Computes

The master integro-differential equation for scaffold plasticity:

```
Φ̇(t) + (α/τ_half) Φ(t) + (β/τ_half) Φ(t) ∫₀ᵗ exp(−(t−s)/τ_m) Φ(s) ds = 0
```

Equivalent ODE system:
```
Φ̇ = −(α/τ_half) Φ − (β/τ_half) Φ·I
İ = Φ − I/τ_m
```

Computes Φ(t), memory integral I(t), effective Lyapunov exponent λ_L(t), and plasticity coefficient Π(t) across three βτ_m regimes.

## Parameters

| Parameter | Value | Meaning |
|-----------|-------|---------|
| α | 7.68 | Spectral gap |
| τ_half | 42.0 days | Scaffold half-life (~6 weeks) |
| τ_m | 14.0 days | ECM memory time constant |
| β_crit | 0.071429 | = 1/τ_m (the lock) |
| Φ₀ | 1.0 | Initial normalized divergence |

## Three Regimes

### Subcritical (βτ_m = 0.5) — Passive Degradation
- Φ decays to zero — scaffold dissolves
- Host returns to baseline
- Transient healing only
- No permanent imprint

### Critical (βτ_m = 1.0) — THE Π-LOCK
- Φ stabilizes (theoretically at saddle)
- Π → −α·Φ₀ = −7.68 (analytic prediction)
- λ_L(∞) flat — zero-drift trajectory
- Scaffold imprints pre-injury HRV into host ganglia

### Supercritical (βτ_m = 2.0) — Pathological Remodeling
- Φ oscillates — chaotic remodeling
- λ_L(∞) positive — divergent
- Rejection, arrhythmia risk

## Phase Portrait Finding

The non-zero FP is **always a saddle** regardless of βτ_m. The zero FP is always a stable node. All generic initial conditions → Φ = 0.

**Three resolutions proposed:**
1. α(t) drift is essential (α → α₀ − κ·I)
2. The equation needs a driving term D(t)
3. Sign convention: Φ represents deviation FROM trained set-point

The full 3D system (scaffold_3d.py) resolves this — the non-trivial FP becomes a stable node.

## Engineering Translation

For Liam's implant:
1. Measure τ_m (~14 days for young adult)
2. Tune β = 1/τ_m = 0.071429 by adjusting PEG crosslinking
3. Verify hydrolysis rate matches τ_half = 42 days
4. At week 6, λ_L must be flat → Lyapunov decay confirms the lock

## Cross-References

- [[CMI-Computations-MOC]]
- [[Pi-Lock-Computation]]
- [[Scaffold-3D-Computation]]
- [[Phase-Portrait-Analysis]]
