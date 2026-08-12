#!/usr/bin/env python3
"""
Volume II: Mock Modular / False Theta — the half-shifted degeneracy.

The Summa's false-theta model:
    f_alpha(tau)      = sum_{n>=0} (n+alpha) q^{(n+alpha)^2/2}
    g_alpha(tau)      = sum_{n in Z} (n+alpha) q^{(n+alpha)^2/2}
    Theta_false(tau)  = sum_{n in Z} sgn(n+alpha) (n+alpha) q^{(n+alpha)^2/2}

Claim [P]: at alpha = 1/2, g_{1/2}(tau) = 0 IDENTICALLY — the involution
n -> -(n+1) pairs every term with its negative. The false theta
Theta^{false}_{1/2} = 2 f_{1/2} carries the nonzero structure, with a
Gaussian-weighted shadow of weight 3/2 (Zwegers completion).

This script verifies:
  (1) g_alpha(tau) != 0 for generic alpha (e.g. alpha = 1/3),
  (2) g_{1/2}(tau) = 0 identically (the degeneracy),
  (3) Theta_false_{1/2} != 0 and equals 2 f_{1/2}.
"""
import numpy as np


def q_series_g(alpha, tau, N=400):
    """g_alpha(tau) = sum_{n=-N}^{N} (n+alpha) q^{(n+alpha)^2/2}."""
    n = np.arange(-N, N + 1, dtype=float)
    q = np.exp(2j * np.pi * tau)
    return float(np.sum((n + alpha) * q ** ((n + alpha) ** 2 / 2)))


def q_series_f(alpha, tau, N=400):
    """f_alpha(tau) = sum_{n>=0} (n+alpha) q^{(n+alpha)^2/2}."""
    n = np.arange(0, N + 1, dtype=float)
    q = np.exp(2j * np.pi * tau)
    return float(np.sum((n + alpha) * q ** ((n + alpha) ** 2 / 2)))


def q_series_theta_false(alpha, tau, N=400):
    """Theta^false_alpha(tau) = sum sgn(n+alpha)(n+alpha) q^{(n+alpha)^2/2}."""
    n = np.arange(-N, N + 1, dtype=float)
    q = np.exp(2j * np.pi * tau)
    return float(np.sum(np.sign(n + alpha) * (n + alpha) * q ** ((n + alpha) ** 2 / 2)))


def main():
    tau = 0.1 + 0.3j   # q = exp(2 pi i tau), |q| < 1
    print("=" * 64)
    print("MOCK MODULAR / FALSE THETA : the half-shifted degeneracy")
    print("=" * 64)
    print(f"tau = {tau}  (q = exp(2 pi i tau), |q| < 1)\n")

    for alpha in [1 / 3, 0.4, 1 / 2]:
        g = q_series_g(alpha, tau)
        print(f"alpha = {alpha:<6} : g_alpha(tau) = {g:+.6e}")

    print()
    g_half = q_series_g(0.5, tau)
    f_half = q_series_f(0.5, tau)
    theta_half = q_series_theta_false(0.5, tau)
    print(f"g_1/2(tau)              = {g_half:+.3e}   (should be ~0)")
    print(f"2 * f_1/2(tau)          = {2*f_half:+.6e}")
    print(f"Theta_false_1/2(tau)    = {theta_half:+.6e}")
    print(f"|Theta_false - 2 f_1/2| = {abs(theta_half - 2*f_half):.3e}")
    print()
    print("g_1/2 = 0 identically (pairwise cancellation under n -> -(n+1)).")
    print("Theta_false_1/2 = 2 f_1/2 carries the nonzero structure.")
    print("The false theta survives where g_alpha dies — the half-shifted degeneracy.")


if __name__ == "__main__":
    main()
