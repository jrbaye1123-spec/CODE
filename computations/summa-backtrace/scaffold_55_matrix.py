#!/usr/bin/env python3
"""
The 55-Scaffold CMI Experiment (Summa Volume V, Applied Monad).

The GO/PLGA-PEG/HA scaffold is a physical monad — its state defines the operator
governing its own evolution. Degradation order parameter alpha (Ritger-Peppas
release exponent):

    alpha = 0.5    Fickian (pure diffusion)
    alpha > 0.5    self-referential / anomalous degradation

Summa specification: 55-scaffold sample matrix, five falsification criteria,
Micro-CT structural readout, Noether charge spectroscopy. ("No experiment yet
run" — this script implements the computational skeleton and the alpha/charge
readout; the wet-lab Micro-CT run remains pending.)

The 55-matrix: 5 GO loadings x 11 crosslink/HA-PEG formulations. The crosslink
density (beta) couples the scaffold state back to its own degradation rate,
raising alpha above the Fickian 0.5 baseline.
"""
import numpy as np
from scipy import optimize


def release_curve(t, alpha, k=1.0):
    """Fractional release R(t) = k t^alpha (short-time Ritger-Peppas law)."""
    return k * t ** alpha


def alpha_from_coupling(beta):
    """Fickian baseline 0.5, plus a self-referential correction from coupling."""
    return 0.5 + 0.9 * beta


def fit_alpha(t, R):
    """Recover alpha from R(t) = k t^alpha via log-log regression."""
    mask = R > 1e-6
    tt, rr = t[mask], R[mask]
    if len(tt) < 5:
        return None
    A = np.vstack([np.log(tt), np.ones_like(tt)]).T
    alpha, _ = np.linalg.lstsq(A, np.log(rr), rcond=None)[0]
    return float(alpha)


def noether_charge(beta, alpha):
    """Noether charge proxy: integrated self-coupling over the release window."""
    return float(beta * alpha)  # charge scales with coupling x order parameter


def main():
    print("=" * 60)
    print("55-SCAFFOLD CMI EXPERIMENT — computational skeleton")
    print("=" * 60)
    print("GO/PLGA-PEG/HA physical monad; alpha order parameter.")
    print()

    go_loadings = np.linspace(0.0, 1.0, 5)      # 5 GO loadings
    formulations = np.linspace(0.0, 0.5, 11)    # 11 crosslink densities (beta)
    t = np.linspace(0.05, 1.0, 50)
    rng = np.random.default_rng(0)

    results = []
    print(f"{'GO':>6} {'beta':>8} {'alpha':>8} {'Noether Q':>12}  regime")
    print("-" * 60)
    for go in go_loadings:
        for beta in formulations:
            # GO loading modulates the self-referential coupling strength
            coupling = beta * (0.5 + go)
            alpha_true = alpha_from_coupling(coupling)
            R = release_curve(t, alpha_true) + rng.normal(0, 0.004, t.size)
            a = fit_alpha(t, R)
            Q = noether_charge(coupling, a if a else alpha_true)
            regime = "Fickian" if coupling <= 1e-9 else "self-referential"
            results.append((go, beta, a, Q, regime))
            a_str = f"{a:.3f}" if a is not None else "  n/a"
            print(f"{go:>6.2f} {beta:>8.3f} {a_str:>8} {Q:>12.4e}  {regime}")

    n_fick = sum(1 for r in results if r[4] == "Fickian")
    n_self = sum(1 for r in results if r[4] == "self-referential")
    print("-" * 60)
    print(f"scaffolds with alpha = 0.5 (Fickian):        {n_fick}")
    print(f"scaffolds with alpha > 0.5 (self-referential): {n_self}")
    print()
    print("Five falsification criteria + Micro-CT + Noether spectroscopy:")
    print("  alpha/charge readout supplied here; wet-lab Micro-CT still pending.")
    print("  'No experiment yet run' (Summa) — this is the computation that runs.")


if __name__ == "__main__":
    main()
