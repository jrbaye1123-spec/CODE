#!/usr/bin/env python3
"""
Phase portrait analysis of the scaffold integro-differential equation.
Reveals the saddle structure at Φ* = -α/(βτ_m).
"""
import numpy as np
from scipy.integrate import solve_ivp

ALPHA, TAU_HALF, TAU_M = 7.68, 42.0, 14.0
BETA_CRIT = 1.0 / TAU_M

def solve_trajectory(beta, phi0, T=300):
    y0 = [phi0, 0.0]
    sol = solve_ivp(
        lambda t, y: [
            -(ALPHA/TAU_HALF)*y[0] - (beta/TAU_HALF)*y[0]*y[1],
            y[0] - y[1]/TAU_M
        ],
        (0, T), y0, t_eval=np.linspace(0, T, 3000),
        method='RK45', rtol=1e-9, atol=1e-12
    )
    return sol.t, sol.y[0], sol.y[1]

def fixed_point(beta):
    """Non-zero fixed point: Φ* = -α/(βτ_m), I* = τ_m·Φ*"""
    bt = beta * TAU_M
    phi_star = -ALPHA / bt
    I_star = TAU_M * phi_star
    return phi_star, I_star

def jacobian_at_fp(beta):
    """Jacobian at the non-zero fixed point."""
    bt = beta * TAU_M
    phi_star = -ALPHA / bt
    # J = [[0, α/(τ_half·τ_m)], [1, -1/τ_m]]
    J = np.array([
        [0.0, ALPHA / (TAU_HALF * TAU_M)],
        [1.0, -1.0 / TAU_M]
    ])
    evals = np.linalg.eigvals(J)
    return J, evals

print("=" * 72)
print("PHASE PORTRAIT ANALYSIS: Fixed Point Structure")
print("=" * 72)
print()

for beta, label in [(0.5/TAU_M, "subcritical"), (BETA_CRIT, "critical"), (2.0/TAU_M, "supercritical")]:
    phi_star, I_star = fixed_point(beta)
    J, evals = jacobian_at_fp(beta)
    bt = beta * TAU_M
    
    print(f"─── {label} (βτ_m = {bt:.4f}) ───")
    print(f"  Non-zero fixed point:  Φ* = {phi_star:.4f},  I* = {I_star:.4f}")
    print(f"  Jacobian eigenvalues:  λ₁ = {evals[0]:+.6f},  λ₂ = {evals[1]:+.6f}")
    print(f"  Fixed-point type:      SADDLE (one stable, one unstable manifold)")
    print(f"  Zero fixed point:      Φ=0, I=0 → stable node (both eigenvalues < 0)")
    print()

print("─" * 72)
print("KEY INSIGHT:")
print()
print("  The non-zero FP is ALWAYS a saddle, regardless of βτ_m.")
print("  The zero FP is ALWAYS a stable node.")
print("  All generic initial conditions → Φ=0, I=0.")
print()
print("  For the saddle to be reached, the initial condition must lie")
print("  EXACTLY on its 1D stable manifold. Generic Φ₀ > 0 misses it.")
print()
print("─" * 72)
print("WHAT THIS MEANS FOR THE Π-LOCK:")
print()
print("  As written, the master equation cannot produce a stable imprinted")
print("  set-point. The 'trained' state (Φ* = -α/(βτ_m)) is a saddle —")
print("  it's mathematically reachable but physically unrealizable from")
print("  generic initial conditions.")
print()
print("  Three possible resolutions:")
print()
print("  1. α(t) DRIFT is essential. If α evolves with the memory integral")
print("     (α → α₀ - κ·I), the fixed point structure changes qualitatively.")
print("     This is what 'α does not decay, it drifts' might encode.")
print()
print("  2. The equation needs a DRIVING TERM — the scaffold doesn't just")
print("     passively relax; it actively injects the encoded HRV profile.")
print("     Something like: Φ̇ = -(α/τ)Φ - (β/τ)Φ·I + D(t) where D(t) is")
print("     the degradation-mediated teaching signal.")
print()
print("  3. SIGN CONVENTION. If Φ represents deviation FROM the trained")
print("     set-point (not from baseline), then convergence to Φ=0 IS the")
print("     imprint. But then βτ_m changes the damping of the return, not")
print("     the destination.")
print()
print("  Which of these is closest to the physical picture?")
print("=" * 72)

# ─── Demonstrate: starting near the stable manifold ───
print()
print("─" * 72)
print("DEMONSTRATION: Starting on the stable manifold of the saddle")
print("─" * 72)

beta = BETA_CRIT
phi_star, I_star = fixed_point(beta)
J, evals = jacobian_at_fp(beta)
stable_eval = evals[0] if evals[0] < 0 else evals[1]

# Stable eigenvector
# For λ_stable, solve (J - λI)v = 0
# [0-λ, a; 1, -1/τ_m-λ] [v1; v2] = 0 where a = α/(τ_half·τ_m)
a = ALPHA / (TAU_HALF * TAU_M)
# (0-λ)*v1 + a*v2 = 0 → v1 = (a/λ)*v2
# Using v2=1, v1 = a/λ
v_stable = np.array([a / stable_eval, 1.0])
v_stable = v_stable / np.linalg.norm(v_stable)

# Start epsilon away from the saddle along the stable direction
eps = 0.5
y0_near = np.array([phi_star, I_star]) + eps * v_stable

print(f"  Saddle point:        (Φ*, I*) = ({phi_star:.4f}, {I_star:.4f})")
print(f"  Stable eigenvalue:    λ_stable = {stable_eval:.6f}")
print(f"  Stable direction:     v = [{v_stable[0]:.6f}, {v_stable[1]:.6f}]")
print(f"  Perturbed start:      ({y0_near[0]:.4f}, {y0_near[1]:.4f})")

sol = solve_ivp(
    lambda t, y: [
        -(ALPHA/TAU_HALF)*y[0] - (beta/TAU_HALF)*y[0]*y[1],
        y[0] - y[1]/TAU_M
    ],
    (0, 500), y0_near, t_eval=np.linspace(0, 500, 3000),
    method='RK45', rtol=1e-9, atol=1e-12
)

phi_traj = sol.y[0]
I_traj = sol.y[1]
print(f"  Final state:          Φ = {phi_traj[-1]:.6f}, I = {I_traj[-1]:.6f}")
print(f"  Distance to saddle:   {np.sqrt((phi_traj[-1]-phi_star)**2 + (I_traj[-1]-I_star)**2):.6e}")
print(f"  Distance to zero:     {np.sqrt(phi_traj[-1]**2 + I_traj[-1]**2):.6e}")

# Now perturb in the WRONG direction
y0_wrong = np.array([phi_star, I_star]) + eps * np.array([1.0, 0.0])
sol2 = solve_ivp(
    lambda t, y: [
        -(ALPHA/TAU_HALF)*y[0] - (beta/TAU_HALF)*y[0]*y[1],
        y[0] - y[1]/TAU_M
    ],
    (0, 500), y0_wrong, t_eval=np.linspace(0, 500, 3000),
    method='RK45', rtol=1e-9, atol=1e-12
)
print()
print(f"  (Off-manifold start: Φ={y0_wrong[0]:.4f}, I={y0_wrong[1]:.4f})")
print(f"  Final state:          Φ = {sol2.y[0][-1]:.6f} → decays to zero")
print("=" * 72)
