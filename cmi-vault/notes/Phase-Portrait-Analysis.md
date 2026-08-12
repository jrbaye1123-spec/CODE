---
tags: [CMI, computation, phase-portrait, saddle, fixed-point, stability]
created: 2026-08-12
---

# Phase Portrait Analysis — Fixed Point Structure

**Script:** `computations/phase_analysis.py`

## What It Computes

Phase portrait analysis of the scaffold integro-differential equation. Reveals the saddle structure at Φ* = −α/(βτ_m) and demonstrates the stable manifold geometry.

## Key Results

### Fixed Point Classification

The non-zero FP is **always a saddle** regardless of βτ_m:
- λ₁ = +0.084 (unstable direction)
- λ₂ = −0.155 (stable direction)

The zero FP is **always a stable node**.

All generic initial conditions → Φ = 0, I = 0.

### The Saddle Problem

For the saddle to be reached, the initial condition must lie EXACTLY on its 1D stable manifold. Generic Φ₀ > 0 misses it entirely.

**Demonstration:**
- Starting ON the stable manifold → converges to zero (not the saddle!)
- Starting OFF the manifold → also converges to zero
- The saddle cannot be reached from generic initial conditions

## Three Resolutions

1. **α(t) DRIFT is essential.** If α evolves with the memory integral (α → α₀ − κ·I), the fixed point structure changes qualitatively. This is what "α does not decay, it drifts" might encode.

2. **The equation needs a DRIVING TERM.** The scaffold doesn't just passively relax; it actively injects the encoded HRV profile: Φ̇ = −(α/τ)Φ − (β/τ)Φ·I + D(t).

3. **SIGN CONVENTION.** If Φ represents deviation FROM the trained set-point (not from baseline), then convergence to Φ = 0 IS the imprint. But then βτ_m changes the damping of the return, not the destination.

## Resolution in Full 3D System

The full 3D autonomous system (`scaffold_3d.py`) resolves this elegantly: with α(t) drift, the non-trivial FP becomes a STABLE NODE — a true attractor reachable from generic initial conditions.

## Cross-References

- [[CMI-Computations-MOC]]
- [[Scaffold-3D-Computation]]
- [[Scaffold-Plasticity-Computation]]
- [[Eigenvalue-Deep-Dive]]
