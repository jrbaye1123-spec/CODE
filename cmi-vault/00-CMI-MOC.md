---
tags:
  - MOC
  - CMI
  - materials-science
  - gauge-theory
  - differential-geometry
created: 2026-08-08
---

# Covariant Mechano-Informatics — Map of Content

> **Pivot**: "The scaffold is not the theory. The scaffold is the question."
> — CMI, Preface

## I. The Core Framework

- [[Covariant Mechano-Informatics]] — The main paper: self-referential gauge theory of degrading active scaffolds
- [[CMI-Core-Equation]] — Φ = ∇self · d : the self-referential differential operator
- [[CMI-Falsification]] — The five sanity checks & predictions (α > 0.5, Noether charge, Rosen closure)

## II. Gauge Theory & Geometric Foundations

Papers that build the geometric/gauge-theoretic machinery CMI inherits:

- [[A geometric theory of plasticity]] — Panoskaltsis et al. (2011): Metric as primary internal variable, covariant balance of energy
- [[The concept of physical metric in rate-independent generalized plasticity]] — Panoskaltsis et al. (2011): Physical metric formalism without elastic/plastic decomposition
- [[Gauge theory of defects in continuous media]] — Sahoo & Valsakumar (2005): Yang-Mills and gravity-type gauge theories for defects
- [[Covariance in plasticity]] — Covariant formulations crossing over to CMI's atlas
- [[A Non-Conventional Gauge Approach Toward material structure]]
- [[G-structures and material homogeneity]] — Group-theoretic approach to material uniformity

## III. Configurational Forces & Dissipation

Papers on the energetic/dissipative side that CMI's Noether charge builds on:

- [[Configurational forces as dissipative mechanisms]] — Gupta & Markenscoff (2008): Euler-Lagrange condition for configurational work = dissipation
- [[Configurational stress yield and flow in]] — Configurational yield criteria and plastic flow
- [[Mesomechanics 2009 Foreword Dissipation]]
- [[On loading criteria in plasticity]]

## IV. Information Geometry & Self-Reference

The information-geometric and relational-biology threads:

- [[The Metaphysics of Constitutive Mechanistic Phenomena]] — Kaiser & Krickel (2016): Ontology of constitutive mechanisms; "object-involving occurrents"
- [[Evolution in materio]] — Harding & Miller: Materials as computational substrates; exploiting physics for non-Von Neumann computation
- [[Unified geometric formulation of material uniformity and evolution]] — Epstein & de León (2016): Groupoids & geometric distributions for material evolution
- [[Material Tensor Theory]] — Roif: Sidis harmonics, dynamic material systems, tensor encoding of heterogeneity

## V. Morphoelasticity & Active Matter

- [[Self-Driven continuous Dislocations and]] — Self-driven dislocation dynamics; morphoelasticity connection
- [[Active Printed Materials for Complex Self]] — Active matter principles in 3D/4D-printed self-organizing structures
- [[Continuum mesoscale theory inspired by p]] — Mesoscale continuum descriptions bridging discrete and continuum
- [[Two different approaches to model evolving materials]]
- [[4-D Geometrical Modeling of Material Aging]]

## VI. Invariance & Constructive Approaches

- [[Invariance in non-isothermal generalized plasticity]] — Thermodynamic consistency under non-isothermal conditions
- [[A constructive approach of invariants of]] — Systematic construction of material invariants
- [[Reflections on the structural and constitutive]] — The structural/constitutive distinction
- [[Folds and refolds of the matter a complex]] — Folding structures, topological transitions

## VII. Gradient Theories & Higher-Order

- [[A fourth-order gauge-invariant gradient theory]] — Gauge-invariant higher-order gradients; fourth-order = second Chern class
- [[Guidelines for Constructing Strain Gradient Theories]] — Well-posedness guidelines for higher-order gradient theories
- [[The Incompatibility Operator from Riemann]] — Curl of curl of strain; geometric origin of Fg
- [[Multiscale Plasticity Reduction or Emergence]]

## VIII. Failure, Defects & Topology

- [[On the failure of anisotropic materials]]
- [[No Bound States of Topological Defects]]
- [[Advances in the mechanics of undamageable materials]]
- [[On the geometrical material structure of anelasticity]] — Geometric structure of anelastic (recoverable, time-dependent) deformation

## IX. Conceptual Bridges

- [[Physical Monad]] — CMI's central concept: autonomous, history-dependent differential machine
- [[Self-Referential Differential Operator]] — ∇self : operator defined by the section it acts on
- [[Noether Charge in Materials]] — Q = Tr(F ∧ F) as topological invariant
- [[Rosen Closure Condition]] — η_HA γ₀ = 1 : repair closing onto metabolism
- [[Christoffel Symbols of Degradation]] — How curvature of state manifold drives degradation kinetics

## X. Computations

- [[CMI-Computations-MOC]] — All Python computations: Π-Lock, scaffold 3D, plasticity, eigenvalue deep-dive, phase portrait analysis

## XI. Summaries & Index

- [[CMI-Connected-Dots]] — The narrative: 10 dot-connection chains between papers
- [[CMI-Reference-Index]] — Quick lookup by CMI concept for citing

## XI. Cross-Cutting Themes

```dataview
TABLE WITHOUT ID
  file.link AS "Paper",
  theme AS "Theme",
  year AS "Year"
FROM "papers"
WHERE theme
SORT year ASC
```

---

*"The question is no longer 'what is this material's degradation rate?' but 'what is the curvature of this material's state manifold?'"*
