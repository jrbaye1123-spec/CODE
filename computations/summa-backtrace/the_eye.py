#!/usr/bin/env python3
"""
The Eye (Summa Volume IV): latent information trajectory estimator.

"The Eye estimates the latent information trajectory from noisy text
 observations. It measures latent dynamics (velocity, acceleration, curvature),
 not raw text. The state estimate IS the measurement. The Eye does not
 classify. It tracks the trajectory."

This is a Kalman-filter-style estimator over a latent state (position, velocity,
acceleration) driven by noisy text-derived observations. It recovers the smooth
latent trajectory (velocity/acceleration/curvature) from observations where the
raw signal is dominated by noise — the "pure seeing" of d2nn.

Build Instruction: "Test the Eye on n >= 100 humans."
"""
import numpy as np
from scipy import linalg


class Eye:
    """Constant-acceleration Kalman filter estimating latent dynamics."""

    def __init__(self, dt=1.0, obs_noise=1.0, process_noise=0.05):
        self.dt = dt
        self.R = np.eye(1) * obs_noise
        # state = [position, velocity, acceleration]
        self.F = np.array([
            [1, dt, 0.5 * dt ** 2],
            [0, 1, dt],
            [0, 0, 1],
        ])
        self.H = np.array([[1.0, 0.0, 0.0]])
        self.Q = np.eye(3) * process_noise
        self.x = np.zeros((3, 1))
        self.P = np.eye(3) * 10.0

    def update(self, z):
        # predict
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q
        # update
        y = z - self.H @ self.x
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ linalg.inv(S)
        self.x = self.x + K @ y
        self.P = (np.eye(3) - K @ self.H) @ self.P
        return self.x.flatten().copy()

    def curvature(self):
        v, a = self.x[1, 0], self.x[2, 0]
        speed = abs(v) + 1e-9
        return a / (speed ** 2)


def simulate_latent_human(n_steps=200, dt=0.1, seed=0):
    """Generate a latent trajectory (position/velocity/acceleration) + noisy obs."""
    rng = np.random.default_rng(seed)
    pos = np.zeros(n_steps)
    vel = np.zeros(n_steps)
    acc = np.zeros(n_steps)
    # latent smooth trajectory: a sum of slow sinusoids
    t = np.arange(n_steps) * dt
    acc_true = 0.3 * np.sin(2 * np.pi * t / 20.0) + 0.15 * np.cos(2 * np.pi * t / 7.0)
    vel[0], pos[0] = 0.1, 0.0
    for i in range(1, n_steps):
        vel[i] = vel[i - 1] + acc_true[i] * dt
        pos[i] = pos[i - 1] + vel[i] * dt
    obs = pos + rng.normal(0.0, 0.5, n_steps)  # heavily noisy
    return pos, vel, acc_true, obs


def main():
    pos, vel, acc_true, obs = simulate_latent_human()

    eye = Eye(dt=0.1, obs_noise=0.5, process_noise=0.05)
    est_pos, est_vel, est_acc = [], [], []
    for z in obs:
        s = eye.update(z)
        est_pos.append(s[0])
        est_vel.append(s[1])
        est_acc.append(s[2])

    est_pos = np.array(est_pos)
    est_vel = np.array(est_vel)
    est_acc = np.array(est_acc)

    # reconstruction error vs raw observation error
    raw_err = np.sqrt(np.mean((obs - pos) ** 2))
    est_err = np.sqrt(np.mean((est_pos - pos) ** 2))
    print("=" * 56)
    print("THE EYE — latent dynamics from noisy text observations")
    print("=" * 56)
    print(f"raw observation RMSE   = {raw_err:.4f}")
    print(f"Eye position  RMSE     = {est_err:.4f}")
    print(f"denoising gain         = {raw_err / max(est_err, 1e-9):.1f}x")
    print()
    print("recovered latent velocity / acceleration (mean |.|):")
    print(f"  velocity     = {np.mean(np.abs(est_vel)):.4f}  (true {np.mean(np.abs(vel)):.4f})")
    print(f"  acceleration = {np.mean(np.abs(est_acc)):.4f}  (true {np.mean(np.abs(acc_true)):.4f})")
    print()
    print("The Eye tracks the trajectory, not the noise. The state IS the measurement.")
    print("Build instruction: test on n >= 100 humans.")


if __name__ == "__main__":
    main()
