---
tags: [MOC, CMI, computations, scaffold, pi-lock]
created: 2026-08-12
---

# CMI Computations — Map of Content

> "The scaffold is the question." All Python computations that verify, test, and extend the CMI framework.

## I. The Π-Lock Series

Core computational verification of the scaffold imprinting mechanism.

### Primary Computations

| Script | What It Does | Output | Key Finding |
|--------|-------------|--------|-------------|
| [[Pi-Lock-Computation]] | π_lock_final.py — Stripped-down Π-lock with empirical anchors (α₀=7.68) | pi_lock_final.json, figure1_convergence.png/.pdf | No bifurcation. Stable node for all κ>0. Lock = τ_m > β |
| [[Scaffold-3D-Computation]] | scaffold_3d.py — Full 3D autonomous system (Φ, M, α) | scaffold_3d_results.json | Non-trivial FP is stable node (not saddle). β-drops out of saddle eigenvalues |
| [[Scaffold-Plasticity-Computation]] | scaffold_plasticity.py — Integro-differential master equation | scaffold_results.json | Three regimes: subcritical (decay), critical (lock), supercritical (pathological) |

### Diagnostic Computations

| Script | What It Does | Key Finding |
|--------|-------------|-------------|
| [[Eigenvalue-Deep-Dive]] | eigenvalue_deep_dive.py — β-dependence, 2D reduction | Fast eigenvalue λ₁ IS β-dependent (M-enslavement). Slow pair ≈β-independent |
| [[Phase-Portrait-Analysis]] | phase_analysis.py — Fixed point classification | Non-zero FP always a saddle. 3 resolutions proposed for Π-lock viability |

## II. Parameter Map

```
τ_m  = ECM memory time constant (10-18 days, young adult)
β    = intrinsic ganglionic learning rate (material property)
γ    = cubic saturation coefficient (derived from α₀)
κ    = coupling rate (tuned via PEG crosslinking + GO concentration)
α₀   = universal spectral invariant (7.68, from 14 datasets)
Φ    = autonomic state divergence
M    = ECM memory integral
```

## III. Key Results

1. **No bifurcation exists.** All eigenvalues real and negative for all κ > 0, τ_m > β. The lock is not a critical point — it's a guaranteed attractor.

2. **β-independence of slow dynamics.** β only scales the fast M-enslavement eigenvalue. The slow pair (λ₂, λ₃) governing convergence is approximately β-independent.

3. **Phase portrait shows saddle structure.** The 2D integro-differential form has saddle FP. Resolution: α(t) drift (α → α₀ − κ·I) changes FP structure. This is encoded in the full 3D system.

4. **Engineering protocol validated.** κ = 4/τ_m is a practical speed recommendation, not a mathematical requirement. ±50% tolerance still converges.

## IV. Files

All scripts in: `computations/`
All results in: `computations/results/`

- `computations/pi_lock_final.py`
- `computations/scaffold_3d.py`
- `computations/scaffold_plasticity.py`
- `computations/eigenvalue_deep_dive.py`
- `computations/phase_analysis.py`

## V. Cross-References

- [[CMI-Core-Equation]] — Φ = ∇self · d
- [[CMI-Falsification]] — The five sanity checks
- [[Self-Referential Differential Operator]] — ∇self
- [[Noether Charge in Materials]] — Q = Tr(F ∧ F)
- [[Rosen Closure Condition]] — η_HA γ₀ = 1

---

*"The question is no longer 'what is this material's degradation rate?' but 'what is the curvature of this material's state manifold?'"*
