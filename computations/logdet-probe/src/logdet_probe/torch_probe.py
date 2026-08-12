"""
logdet_probe.torch_probe — Canonical PyTorch implementation of the logdet covariance probe.

This is one of the two canonical backends (torch for MoeSubject activation probes;
numpy for NOX OS state samples). The mathematical definition is shared:

    φ = logdet( (X - μ)^T (X - μ) / (n-1) + ε I )

with sign handling (neg/zero det → -inf), B/S/d flattening, centering optional.

Used for:
- S_horizon (holographic screen area in bulk projection)
- conditioning / degradation / phase Φ in Moe layers
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import torch as _torch


def compute_logdet_covariance(
    x: "torch.Tensor",
    eps: float = 1e-3,
    center: bool = True,
) -> "torch.Tensor":
    """
    Compute logdet(Σ + εI) of a batch of vectors (the intrinsic measurement).

    This is the single source of truth for:
    - S_horizon in MoeBulkBoundary / injected consciousness probes
    - layer conditioning / degradation detection (phase sweeps, infer)
    - holographic screen area, covariance volume, spectral conditioning

    Preserves the mathematical structure from the fixed-point measurement
    apparatus and geometric incompleteness theorem: the (regularized)
    volume of the empirical distribution in the (bulk/projected) space.

    x: tensor of shape (n, d) or (B, S, d) — will be flattened to samples×dim
    eps: ridge for numerical stability (matches s_hor_eps, cov_reg)
    Returns: scalar tensor (logdet value, or -inf if not posdef)

    φ-map: the determinant of the gram matrix (after centering) is the
    product of eigenvalues = volume scaling factor of the parallelepiped
    spanned by the centered samples in feature space.

    This implementation is the canonical one; all call sites delegate here.
    The identical φ (center, cov, ridge, slogdet+sign) is realized for NumPy
    in numpy_probe (used by ProcessMonitor).
    """
    import torch as _torch  # local to avoid top-level dep if not present (e.g. pure-NOX envs)
    if not isinstance(x, _torch.Tensor):
        x = _torch.as_tensor(x, dtype=_torch.float32)
    if x.dim() > 2:
        x = x.reshape(-1, x.shape[-1])
    n = x.size(0)
    if n < 2:
        return _torch.tensor(0.0, device=x.device)
    if center:
        x = x - x.mean(dim=0, keepdim=True)
    cov = (x.t() @ x) / (n - 1 + 1e-8)
    d = cov.size(0)
    cov_reg = cov + eps * _torch.eye(d, device=cov.device, dtype=cov.dtype)
    sign, logdet = _torch.linalg.slogdet(cov_reg)
    if sign > 0:
        return logdet
    else:
        return _torch.tensor(float("-inf"), device=x.device)
