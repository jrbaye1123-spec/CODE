---
tags: [CMI, computation, eigenvalue, deep-dive, beta-dependence, 2d-reduction]
created: 2026-08-12
---

# Eigenvalue Deep Dive — β-Dependence and 2D Reduction

**Script:** `computations/eigenvalue_deep_dive.py`

## What It Computes

Deep-dive into the eigenvalue structure of the scaffold system. Tests two critical claims:
1. Whether saddle eigenvalues are truly β-independent
2. Whether the κτ_m = 4 bifurcation produces a complex→real transition

## Key Results

### Part 1: β-Dependence in Full 3D

| β | Φ* | λ₁ (fast) | λ₂ | λ₃ |
|---|-----|-----------|-----|-----|
| 0.1 | 139.0 | -3878.10 | -0.3260 | -0.0312 |
| 1.0 | 130.0 | -3510.00 | -0.3271 | -0.0300 |
| 10.0 | 40.0 | -720.00 | -0.3440 | -0.0132 |

**Finding:** λ₁ ≈ (β − 2τ_m)·Φ* IS β-dependent (M-enslavement direction, relaxes in ~0.0003 time units). The slow pair (λ₂, λ₃) is approximately β-independent.

### Part 2: Reduced 2D System (M Enslaved)

Setting M ≈ τ_m·Φ (valid since M relaxes ~instantaneously) yields a stable node for ALL κτ_m tested. No spiral→node bifurcation at κτ_m = 4.

### Part 3: The Claimed Saddle Eigenvalue Formula

The formula λ = (−κτ_m ± √(κ²τ_m² − 4κτ_m))/(2τ_m) DOES show bifurcation at κτ_m = 4, but comes from a different subsystem — likely (α, M) with Φ enslaved, not the physically relevant (Φ, α) reduction.

## Summary

1. **Full 3D non-trivial FP is a STABLE NODE** — not a saddle. The imprinted set-point is a true attractor.
2. **Fast eigenvalue λ₁ IS β-dependent** but represents M-enslavement (~instantaneous relaxation).
3. **The user's saddle-eigenvalue formula** comes from a different reduction and predicts a transition that doesn't exist in the full system.
4. **ALL κ regimes converge** to the non-trivial FP (Φ* > 0). Faster with higher κτ_m.

## Cross-References

- [[CMI-Computations-MOC]]
- [[Pi-Lock-Computation]]
- [[Scaffold-3D-Computation]]
- [[Phase-Portrait-Analysis]]
