---
tags:
  - concept
  - CMI
  - differential-geometry
  - degradation
---

# Christoffel Symbols of Degradation

> The degradation rate is the Ricci scalar of the material's self-awareness.

## From Geometry to Kinetics

In general relativity:
- Christoffel symbols Γ^k_ij encode how basis vectors change from point to point
- The Ricci scalar R = g^ij R_ij measures the curvature of spacetime

In CMI:
- Christoffel symbols Γ^k_ij(Fg) are functions of the plastic strain Fg
- The connection ∇self is built from these Christoffel symbols
- The divergence Φ = ∇self · d produces a "force" driving degradation
- The effective degradation rate α is proportional to the **Ricci scalar** of the state manifold

## Why α > 0.5

Classical Fickian diffusion (α = 0.5) corresponds to a **flat** state manifold — no curvature, no feedback.

CMI predicts α > 0.5 because:
- The state manifold has intrinsic curvature from Fg
- This curvature **accelerates** the degradation front
- α - 0.5 is a direct measure of state-manifold curvature

## Connection to Other Frameworks

- [[A geometric theory of plasticity]] — Metric as internal variable, Christoffel symbols from metric
- [[The concept of physical metric in rate-independent generalized plasticity]] — Physical metric formalism
- [[Unified geometric formulation of material uniformity and evolution]] — Geometric distributions for material evolution

## See Also

- [[CMI-Core-Equation]]
- [[Self-Referential Differential Operator]]
- [[CMI-Falsification]]
