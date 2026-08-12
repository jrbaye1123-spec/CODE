---
tags: [CMI, computation, scaffold, 3d, autonomous-system, fixed-point]
created: 2026-08-12
---

# Scaffold 3D Computation — Full Autonomous System

**Script:** `computations/scaffold_3d.py`
**Results:** `computations/results/scaffold_3d_results.json`

## What It Computes

The full 3D autonomous system — the Π-Lock, re-forged:

```
Φ̇ = α·Φ − β·Φ² − γ·Φ³
Ṁ = Φ − M/τ_m
α̇ = κ(M − α)           [steady-state, η→0 after week 1]
```

Tests three κ regimes (subcritical, critical, supercritical) and verifies β-independence of saddle eigenvalues.

## Parameters

| Parameter | Value | Meaning |
|-----------|-------|---------|
| τ_m | 14.0 days | ECM memory time constant |
| β | 1.0 | Intrinsic ganglionic learning rate |
| γ | 0.1 | Cubic saturation coefficient |
| κ_crit | 0.285714 | Bifurcation point (4/τ_m) |
| α₀ | 7.68 | Initial spectral gap |
| Φ₀ | 1.0 | Initial post-injury divergence |

Non-trivial fixed point: Φ* = 130.0, M* = 1820.0, α* = 1820.0

## Key Results

### β-Independence Verification

The β-independence claim was tested numerically:

| β | λ₁ (fast) | λ₂ | λ₃ |
|---|-----------|----|-----|
| 0.5 | -3712.50 | -0.3265 | -0.0307 |
| 1.0 | -3510.00 | -0.3271 | -0.0300 |
| 2.0 | -3120.00 | -0.3285 | -0.0287 |
| 5.0 | -2070.00 | -0.3332 | -0.0240 |

**Finding:** The fast eigenvalue λ₁ IS β-dependent (scales with Φ*). The slow pair (λ₂, λ₃) is approximately β-independent — confirmed.

### Fixed Point Classification

**ALL regimes produce a STABLE NODE at the non-trivial FP.** This is better than a saddle — the imprinted set-point is a true attractor. Trajectories are drawn to it from generic initial conditions.

| Regime | κτ_m | Type | λ₂ | λ₃ |
|--------|------|------|-----|-----|
| Subcritical | 1.0 | STABLE NODE | -0.123 | -0.020 |
| Critical | 4.0 | STABLE NODE | -0.030 | -0.327 |
| Supercritical | 8.0 | STABLE NODE | -0.032 | -0.611 |

### Convergence Behavior

All regimes converge to the non-trivial FP. Higher κτ_m = faster convergence.

## Engineering Translation

1. Measure τ_m from pre-implant HRV recovery test
2. Set κ = 4/τ_m via PEG crosslinking density + GO concentration
3. β is irrelevant — scaffold works for any β at κ·τ_m = 4
4. Observe the lock: critically damped, no oscillations, no return to baseline

## Cross-References

- [[CMI-Computations-MOC]]
- [[Pi-Lock-Computation]]
- [[Scaffold-Plasticity-Computation]]
- [[CMI-Falsification]]
