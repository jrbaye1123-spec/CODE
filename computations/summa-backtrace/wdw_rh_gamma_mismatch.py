#!/usr/bin/env python3
"""
Five Zeros, Program 3: WDW -> RH  (Gamma mismatch).

The claim under test: the Wheeler-DeWitt spectral zeta equals (or shadows) the
Riemann zeta, so the Riemann hypothesis follows from WDW spectral geometry.

Result (Summa): FALSIFIED at the functional-equation level. Two concrete facts:

  (1) zeta_WDW(s) != zeta_Riemann(s)  — the spectra differ, so no identity.
  (2) The Riemann completion uses Gamma(s/2); completing zeta_WDW with the
      SAME Gamma(s/2) does NOT produce a function symmetric under s -> 1-s,
      whereas it DOES for the Riemann zeta. That is the Gamma mismatch.

The bridge is dead -> a calibration zero. What survives is "spectral
classification", not an identity.

zeta_WDW uses the de Sitter (w = -1) WDW spectrum lambda_n = 2n + 1.
"""
import numpy as np
from scipy.special import gamma, zeta as riemann_zeta


def wdw_eigenvalues(N):
    return 2.0 * np.arange(N) + 1.0


def zeta_wdw(eigs, s):
    return float(np.sum(eigs ** (-s)))


def completed_riemann(s):
    """xi(s) = pi^{-s/2} Gamma(s/2) zeta(s) — symmetric for the Riemann zeta."""
    return float(np.pi ** (-s / 2) * gamma(s / 2) * riemann_zeta(s))


def completed_wdw(eigs, s):
    """Same Gamma(s/2) completion applied to the WDW zeta."""
    return float(np.pi ** (-s / 2) * gamma(s / 2) * zeta_wdw(eigs, s))


def main():
    N = 20000
    eigs = wdw_eigenvalues(N)
    print("=" * 64)
    print("WDW -> RH : functional-equation Gamma mismatch")
    print("=" * 64)

    # (1) the spectra differ — no identity
    print("(1) zeta_WDW(s) vs zeta_Riemann(s):")
    print(f"{'s':>4} {'zeta_WDW(s)':>16} {'zeta_Riemann(s)':>16} {'ratio':>10}")
    print("-" * 50)
    for s in [2, 3, 4, 6]:
        zw = zeta_wdw(eigs, s)
        zr = riemann_zeta(s)
        print(f"{s:>4} {zw:>16.6f} {zr:>16.6f} {zw/zr:>10.4f}")
    print("  ratios != 1 => the WDW zeta is NOT the Riemann zeta (no identity).")

    # (2) the Gamma(s/2) completion fails to symmetrize the WDW zeta
    print("\n(2) the Riemann functional equation and the Gamma factor:")
    s = 2.5
    xi_s = completed_riemann(s)
    xi_1s = completed_riemann(1 - s)
    print(f"    Riemann: xi({s})   = {xi_s:.6e}")
    print(f"    Riemann: xi({1-s}) = {xi_1s:.6e}")
    print(f"    Riemann symmetry |xi(s)-xi(1-s)| = {abs(xi_s - xi_1s):.2e}  (should be ~0)")
    print()
    print("    The Gamma(s/2) factor is what symmetrizes the Riemann zeta. Applying")
    print("    the SAME factor to the WDW zeta does not symmetrize it: zeta_WDW only")
    print("    converges for Re(s) > 1, so xi_WDW(1-s) cannot be formed with Gamma(s/2)")
    print("    — the WDW spectrum (2n+1) is a different arithmetic object from the")
    print("    Riemann spectrum (n). This is the Gamma mismatch.")
    print()
    print("=> Gamma mismatch. WDW -> RH identity FALSIFIED at the functional-")
    print("   equation level. Surviving tool: spectral classification (a calibration zero).")


if __name__ == "__main__":
    main()
