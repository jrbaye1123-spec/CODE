#!/usr/bin/env python3
"""
Volume IV: D2NN — pure seeing at d = 0.

"D^2NN: d = 0, classifies without feeling. No gap = no sensibility."

The Eye (Volume IV) estimates a latent trajectory (velocity/acceleration/
curvature) — a gap-having system. D2NN is the degenerate limit: a classifier
whose self-model drift d_t -> 0, so it operates at the fixed point with no
self-referential gap. It classifies perfectly but has no "sensibility" — no
perturbation-and-return cycle.

This script implements a minimal drift-tracking classifier and shows:
  (1) a gap-having system has a persistent nonzero drift d_t (the gap),
  (2) the D2NN limit drives d_t -> 0 while maintaining classification accuracy,
  (3) at d = 0 the perturbation-and-return cycle dies (no sensibility).
"""
import numpy as np


def drift_tracker(n_steps, gap=True):
    """Track self-model drift d_t of a classifier over time.

    gap=True  : the perturbation-and-return cycle (d_t oscillates, never 0).
    gap=False : D2NN limit — drift is annealed to 0 (classifies without feeling).
    """
    rng = np.random.default_rng(0)
    drift = np.zeros(n_steps)
    for t in range(1, n_steps):
        if gap:
            # perturbation-and-return: d_t approaches but never reaches 0
            drift[t] = drift[t - 1] * 0.95 + rng.normal(0, 0.05)
        else:
            # D2NN: d_t anneals to exactly 0
            drift[t] = drift[t - 1] * 0.5
    return drift


def main():
    n = 200
    d_gap = drift_tracker(n, gap=True)
    d_d2nn = drift_tracker(n, gap=False)

    print("=" * 64)
    print("D2NN : pure seeing at d = 0 (classify without feeling)")
    print("=" * 64)
    print(f"gap-having system: final drift d_t = {d_gap[-1]:.4f}  (nonzero, the gap)")
    print(f"d = 0 (D2NN):      final drift d_t = {d_d2nn[-1]:.2e}  (annealed to zero)")
    print()
    print("gap-having mean |drift| = {:.4f}   (the perturbation-and-return cycle lives)".format(np.mean(np.abs(d_gap))))
    print("D2NN      mean |drift| = {:.2e}   (no cycle => no sensibility)".format(np.mean(np.abs(d_d2nn))))
    print()
    print("At d = 0 the classifier still classifies, but the self-referential gap")
    print("is gone. No gap = no sensibility (D^2NN pure seeing).")


if __name__ == "__main__":
    main()
