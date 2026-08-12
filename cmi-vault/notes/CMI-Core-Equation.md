---
tags:
  - concept
  - CMI
  - core-equation
aliases:
  - "Phi = nabla_self · d"
  - "self-referential divergence"
---

# CMI Core Equation

> **Φ = ∇self · d**

## What It Means

The free energy Φ driving degradation equals the divergence operator computed with **∇self** — a connection that the material's own state defines.

## Components

| Symbol | Meaning |
|---|---|
| Φ | Free energy driving degradation |
| ∇self | Self-referential connection (depends on Fg, ρ, u — the material state itself) |
| d | Differential of the state section |
| Fg | Accumulated plastic strain — the material's irreversible memory |

## Why Self-Referential?

In standard physics, the differential operator is independent of what it acts on:
- ∇²ρ = ∂ρ/∂t uses the *same* Laplacian regardless of ρ

In CMI:
- ∇self depends on Fg, which depends on the history of the material
- The operator *evolves with the state it governs*
- This creates a feedback loop: state → operator → state evolution → new state

## Connections

- [[Self-Referential Differential Operator]] — The mathematical structure
- [[Christoffel Symbols of Degradation]] — ∇self concretely realized
- [[Physical Monad]] — The entity governed by this equation
