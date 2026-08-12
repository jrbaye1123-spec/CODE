---
tags:
  - concept
  - CMI
  - mathematics
  - differential-geometry
aliases:
  - "nabla_self"
  - "self-referential connection"
---

# Self-Referential Differential Operator

> ∇self: a connection whose very definition depends on the section it acts upon.

## Contrast with Standard Operators

| Property | Standard ∇ | ∇self |
|---|---|---|
| Definition | Fixed on manifold | Depends on section (state) |
| Metric | Given a priori | Evolves with state |
| Curvature | Intrinsic to manifold | Depends on Fg |
| Linearity | Linear operator | Non-linear feedback |

## Mathematical Structure

∇self is a **connection on a fiber bundle** where:
- The base space is the material's configuration
- The fiber is the state space (ρ, u, Fg)
- The connection coefficients (Christoffel symbols) are functions of Fg
- The curvature measures the obstruction to parallel transport of the state

## Role in CMI

The self-reference creates a **feedback loop**:
1. Current state determines ∇self
2. ∇self determines the divergence Φ = ∇self · d
3. Φ determines state evolution
4. New state determines new ∇self

This is the mathematical expression of the Physical Monad.

## See Also

- [[CMI-Core-Equation]]
- [[Physical Monad]]
- [[Christoffel Symbols of Degradation]]
- [[A geometric theory of plasticity]] — Metric as internal variable
- [[Gauge theory of defects in continuous media]] — Gauge connections for defect dynamics
