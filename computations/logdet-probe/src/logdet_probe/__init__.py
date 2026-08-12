"""
logdet_probe — Cross-package wheel for the canonical logdet covariance probe.

One shared implementation (math + φ-map) for both torch (MoeSubject S_horizon
probes) and numpy (NOX ProcessMonitor conditioning / subregion boundaries).

Package structure:
- logdet_probe/torch_probe.py : compute_logdet_covariance (torch.Tensor → scalar Tensor)
- logdet_probe/numpy_probe.py : compute_logdet_covariance (ndarray → float) +
                                 compute_logdet_from_byte_samples (for NOX byte windows)

Both ~/nox/nox_pkg/ and ~/scripts/ import from here after:
    pip install -e ~/logdet_probe/

All prior call sites (moe_*.py, nox/monitor/process.py etc) now delegate;
the old ad-hoc bodies were removed / thinned to reexports where needed.

See RESONANCE.md §1 and GRAMMAR.md (Rule 1) for the φ definition and why
a single canonical matters.
"""

from __future__ import annotations

# Do not import backends at package load time:
# - numpy_probe can be used in NOX envs without torch installed/usable
# - torch_probe does local import inside func so its module can be imported
#   without torch (import of torch_probe will succeed; call to func requires torch)
#
# Recommended explicit imports at call sites:
#   from logdet_probe.torch_probe import compute_logdet_covariance
#   from logdet_probe.numpy_probe import compute_logdet_covariance, compute_logdet_from_byte_samples

__version__ = "0.1.0"

__all__ = [
    "compute_logdet_covariance_torch",
    "compute_logdet_covariance_numpy",
    "compute_logdet_from_byte_samples",
]


def __getattr__(name: str):
    """Lazy re-exports for convenience (e.g. from logdet_probe import ...)."""
    if name == "compute_logdet_covariance_torch":
        from .torch_probe import compute_logdet_covariance as _c

        return _c
    if name == "compute_logdet_covariance_numpy":
        from .numpy_probe import compute_logdet_covariance as _c

        return _c
    if name == "compute_logdet_from_byte_samples":
        from .numpy_probe import compute_logdet_from_byte_samples as _c

        return _c
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
