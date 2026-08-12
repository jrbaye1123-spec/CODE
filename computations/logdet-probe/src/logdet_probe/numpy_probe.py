"""
logdet_probe.numpy_probe — Canonical NumPy implementation of the logdet covariance probe.

This is one of the two canonical backends (numpy for NOX OS state samples;
torch for MoeSubject activation probes). The mathematical definition is shared:

    φ = logdet( (X - μ)^T (X - μ) / (n-1) + ε I )

with sign handling (neg/zero det → -inf), B/S/d flattening, centering optional.

Used for:
- S_horizon (holographic screen area in bulk projection)
- conditioning (ProcessMonitor / subregion boundary)
- capacity / degradation detection
"""
from __future__ import annotations

from typing import List, Optional

import numpy as np


def compute_logdet_covariance(
    x: np.ndarray, eps: float = 1e-3, center: bool = True
) -> float:
    """
    Compute logdet(Σ + εI) of a batch of vectors (the intrinsic measurement).

    This is the NumPy half of the single canonical source of truth (shared with
    torch_probe) for S_horizon, layer conditioning, holographic screen area,
    covariance volume, spectral conditioning.

    Preserves the mathematical structure from the fixed-point measurement
    apparatus and geometric incompleteness theorem: the (regularized)
    volume of the empirical distribution in the (bulk/projected) space.

    x: array of shape (n, d) or (B, S, d) — will be flattened to samples×dim
    eps: ridge for numerical stability (matches s_hor_eps, cov_reg)
    Returns: python float (logdet value, or -inf if not posdef)

    φ-map: the determinant of the gram matrix (after centering) is the
    product of eigenvalues = volume scaling factor of the parallelepiped
    spanned by the centered samples in feature space.
    """
    x = np.asarray(x, dtype=np.float64)
    if x.ndim > 2:
        x = x.reshape(-1, x.shape[-1])
    n = x.shape[0]
    if n < 2:
        return 0.0
    if center:
        x = x - x.mean(axis=0, keepdims=True)
    cov = (x.T @ x) / (n - 1 + 1e-8)
    d = cov.shape[0]
    cov_reg = cov + eps * np.eye(d, dtype=cov.dtype)
    sign, logdet = np.linalg.slogdet(cov_reg)
    if sign > 0:
        return float(logdet)
    else:
        return float("-inf")


def compute_logdet_from_byte_samples(
    recent_samples: List[bytes], eps: float = 1e-4
) -> float:
    """
    NOX-specific: preprocess byte samples (common prefix length, byte→int64 array)
    then delegate to the canonical numeric compute_logdet_covariance.

    This extracts the logic that lived in ProcessMonitor._compute_conditioning
    so that the linear algebra is no longer duplicated and the φ is one
    canonical across torch (Moe) and numpy (NOX).

    recent_samples: list of bytes (recent state observations, e.g. last 50)
    eps: small ridge (1e-4 chosen for byte vectors to regularize without
         dominating the scale; nullspace contrib k*log(eps) is uniform shift).

    Returns: float logdet or 0.0 (insufficient data) or -inf .
    """
    if not recent_samples or len(recent_samples) < 2:
        return 0.0
    min_len = min(len(s) for s in recent_samples)
    truncated = [s[:min_len] for s in recent_samples]
    array = np.array([list(b) for b in truncated], dtype=np.float64)
    if array.shape[0] < 2 or array.shape[1] < 2:
        return 0.0
    return compute_logdet_covariance(array, eps=eps, center=True)
