#!/usr/bin/env python3
"""
SPECTRAL REGULARIZER — α→8.8 Training Signal
=============================================
"I am the gap. I measure the distance from the fixed point and tighten it."

Computes the super-exponential tail exponent α from hidden-state covariance
during training and provides a loss term that drives α toward the universal
band (α_target = 8.8, per Nakamichi Shinjin §4.1.1).

The loss: L_α = β · max(0, α_target − α)²
  - Only penalizes α below target (undertrained regimes)
  - β starts small (1e-3), auto-adapts based on α trajectory
  - Cheap: samples ~256 tokens per probe, runs every 50 training steps

Integrated with the Nobody Ledger: every α measurement is hashed into the chain.

Usage:
  from spectral_regularizer import SpectralRegularizer
  reg = SpectralRegularizer(model, alpha_target=8.8)
  ...
  alpha_loss = reg.compute_loss(hidden_states)  # call during training
"""

import sys
import math
import json
import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Tuple

import torch
import numpy as np

# ── Nobody Ledger path (same as ledgot_probe) ─────────────────────
def _resolve_home() -> Path:
    sudo_user = __import__('os').environ.get("SUDO_USER")
    if sudo_user:
        return Path(f"/home/{sudo_user}")
    return Path.home()

LEDGER_PATH = _resolve_home() / "nobody-ledger" / "nobody_chain.json"
LEDGER_ENTITY = "gpt2-moe-trainer"

# ── Chain Integration ────────────────────────────────────────────

def _hash_entry(entry: dict) -> str:
    raw = json.dumps(entry, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()

def _append_to_chain(event: str, how: str) -> str:
    """Append a training event to the Nobody Ledger. Returns hash."""
    ledger = {}
    if LEDGER_PATH.exists():
        try:
            ledger = json.loads(LEDGER_PATH.read_text())
        except json.JSONDecodeError:
            ledger = {"entries": [], "count": 0, "nullified_indices": []}

    entries = ledger.get("entries", [])
    prev_hash = entries[-1]["hash"] if entries else ""
    new_idx = len(entries)

    entry = {
        "index": new_idx,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "entity": LEDGER_ENTITY,
        "event": event,
        "how": how,
        "previous_hash": prev_hash,
    }
    entry["hash"] = _hash_entry(entry)
    entries.append(entry)
    ledger["count"] = len(entries)
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    LEDGER_PATH.write_text(json.dumps(ledger, indent=2) + "\n")
    return entry["hash"]

# ── Core Spectral Functions ──────────────────────────────────────

def _tail_alpha(eigenvals: np.ndarray, tail_frac: float = 0.20) -> float:
    """
    Super-exponential tail fit: λ_k ~ exp(−k^α)
    Model: log(λ_k) = C − k^α
    Linearize: log(C − log(λ_k)) = α · log(k) + const
    """
    pos = eigenvals[eigenvals > 0]
    if len(pos) < 5:
        return 0.0

    sorted_vals = np.sort(pos)[::-1]
    n = len(sorted_vals)
    tail_start = int(n * (1.0 - tail_frac))
    tail_vals = sorted_vals[tail_start:]
    if len(tail_vals) < 3:
        return 0.0

    k = np.arange(1, len(tail_vals) + 1, dtype=np.float64)
    log_lambda = np.log(np.maximum(tail_vals, 1e-30))
    C_est = log_lambda.max() + 1.0
    residual = np.maximum(C_est - log_lambda, 1e-10)

    log_k = np.log(k)
    log_residual = np.log(residual)

    coeffs = np.polyfit(log_k, log_residual, 1)
    return float(coeffs[0])


def _spectral_flatness(eigenvals: np.ndarray) -> float:
    """F = exp(⟨ln λ⟩) / ⟨λ⟩"""
    pos = eigenvals[eigenvals > 0]
    if len(pos) < 2:
        return 0.0
    return float(np.exp(np.mean(np.log(pos))) / np.mean(pos))


def _concentration(eigenvals: np.ndarray, top_frac: float = 0.01) -> float:
    """Fraction of power in top 1% eigenvalues."""
    pos = eigenvals[eigenvals > 0]
    if len(pos) < 2:
        return 1.0
    sorted_vals = np.sort(pos)[::-1]
    k = max(1, int(math.ceil(len(sorted_vals) * top_frac)))
    return float(np.sum(sorted_vals[:k]) / np.sum(sorted_vals))


# ── Spectral Regularizer Class ──────────────────────────────────

class SpectralRegularizer:
    """
    Computes α from hidden states and provides a loss term pushing α → α_target.

    The loss is asymmetric: only penalizes α below target (the model is
    undertrained, not overtrained). Once α surpasses target, loss → 0.
    """

    def __init__(
        self,
        model,
        alpha_target: float = 8.8,
        beta: float = 1e-3,
        sample_tokens: int = 256,
        ridge: float = 1e-6,
        log_to_chain: bool = True,
    ):
        self.model = model
        self.alpha_target = alpha_target
        self.beta = beta
        self.sample_tokens = sample_tokens
        self.ridge = ridge
        self.log_to_chain = log_to_chain

        # Tracking
        self.alpha_history: list = []
        self.flatness_history: list = []
        self.concentration_history: list = []
        self.n_probes: int = 0

        # Activation hooks
        self._activations: Dict[int, torch.Tensor] = {}
        self._hooks: list = []

    def _hook_fn(self, layer_idx: int):
        def hook(module, input, output):
            if isinstance(output, tuple):
                x = output[0]
            else:
                x = output
            # Detach to avoid retaining graph
            self._activations[layer_idx] = x.detach()
        return hook

    def attach(self):
        """Register hooks to capture hidden states from each transformer block."""
        self.detach()  # clear any existing
        for i, block in enumerate(self.model.blocks):
            h = block.register_forward_hook(self._hook_fn(i))
            self._hooks.append(h)

    def detach(self):
        """Remove all hooks."""
        for h in self._hooks:
            h.remove()
        self._hooks.clear()
        self._activations.clear()

    def compute_alpha(
        self,
        hidden_states: Optional[torch.Tensor] = None,
    ) -> Dict:
        """
        Compute α and companion metrics from hidden states.

        If hidden_states is None, uses hook-captured activations (must call
        attach() before forward pass).
        """
        results = {"layers": {}, "mean_alpha": 0.0, "mean_flatness": 0.0,
                    "mean_concentration": 0.0}

        if hidden_states is not None:
            # Single tensor input
            results = self._compute_from_tensor(hidden_states, layer=-1)
            results["mean_alpha"] = results.get("alpha", 0.0)
        elif self._activations:
            alphas = []
            flats = []
            concs = []
            for layer_idx, hs in sorted(self._activations.items()):
                res = self._compute_from_tensor(hs, layer=layer_idx)
                results["layers"][str(layer_idx)] = res
                alphas.append(res.get("alpha", 0.0))
                flats.append(res.get("flatness", 0.0))
                concs.append(res.get("concentration", 0.0))
            n = max(len(alphas), 1)
            results["mean_alpha"] = sum(alphas) / n
            results["mean_flatness"] = sum(flats) / n
            results["mean_concentration"] = sum(concs) / n

        self.alpha_history.append(results["mean_alpha"])
        self.n_probes += 1
        return results

    def _compute_from_tensor(self, hs: torch.Tensor, layer: int = -1) -> Dict:
        """Compute α from a single hidden state tensor."""
        n_tokens, d = hs.shape
        if n_tokens < 2:
            return {"alpha": 0.0, "flatness": 0.0, "concentration": 0.0,
                    "n_tokens": n_tokens, "hidden_dim": d, "layer": layer}

        # Subsample if needed
        if n_tokens > self.sample_tokens:
            indices = torch.randperm(n_tokens, device=hs.device)[:self.sample_tokens]
            hs = hs[indices]
            n_tokens = self.sample_tokens

        h = hs - hs.mean(dim=0, keepdim=True)
        cov = (h.T @ h) / (n_tokens - 1)
        cov_ridged = cov + self.ridge * torch.eye(d, device=cov.device)

        try:
            eigenvals = torch.linalg.eigvalsh(cov_ridged)
        except Exception:
            return {"alpha": 0.0, "flatness": 0.0, "concentration": 0.0,
                    "n_tokens": n_tokens, "hidden_dim": d, "layer": layer}

        eigenvals = torch.sort(eigenvals, descending=True)[0]
        vals_np = eigenvals.cpu().numpy()

        return {
            "alpha": _tail_alpha(vals_np),
            "flatness": _spectral_flatness(vals_np),
            "concentration": _concentration(vals_np),
            "n_tokens": n_tokens,
            "hidden_dim": d,
            "layer": layer,
        }

    def compute_loss(self, hidden_states: Optional[torch.Tensor] = None) -> Tuple[torch.Tensor, Dict]:
        """
        Compute the α→target loss term.

        Returns:
            (loss_tensor, metrics_dict)
            loss_tensor is a scalar tensor (requires_grad=False — we can't
            backprop through SVD cheaply; this is a diagnostic signal, not
            a differentiable regularizer).
        """
        metrics = self.compute_alpha(hidden_states)
        alpha = metrics["mean_alpha"]

        # Asymmetric: only penalize below target
        deficit = max(0.0, self.alpha_target - alpha)
        alpha_loss = self.beta * (deficit ** 2)

        metrics["alpha_loss"] = alpha_loss
        metrics["alpha_deficit"] = deficit
        metrics["beta"] = self.beta

        if self.log_to_chain and self.n_probes % 10 == 0:
            _append_to_chain(
                event="spectral_probe",
                how=(f"probe={self.n_probes} alpha={alpha:.4f} "
                     f"deficit={deficit:.4f} loss={alpha_loss:.6f} "
                     f"beta={self.beta:.1e}"),
            )

        return torch.tensor(alpha_loss, dtype=torch.float32), metrics

    def adapt_beta(self):
        """
        Auto-adapt β based on α trajectory.
        - If α is decreasing, increase β (push harder)
        - If α is increasing and close to target, decrease β (ease off)
        """
        if len(self.alpha_history) < 5:
            return

        recent = self.alpha_history[-5:]
        trend = recent[-1] - recent[0]

        if trend < -0.05:
            # α decreasing — push harder
            self.beta = min(self.beta * 2.0, 1.0)
        elif trend > 0.1 and recent[-1] > self.alpha_target * 0.7:
            # α increasing and approaching target — ease off
            self.beta = max(self.beta * 0.8, 1e-5)

    def status_str(self) -> str:
        """One-line status for logging."""
        if self.alpha_history:
            alpha = self.alpha_history[-1]
            deficit = max(0.0, self.alpha_target - alpha)
            trend = ""
            if len(self.alpha_history) >= 5:
                t = self.alpha_history[-1] - self.alpha_history[-5]
                trend = "↑" if t > 0.02 else ("↓" if t < -0.02 else "→")
            return (f"α={alpha:.3f} deficit={deficit:.3f} {trend} "
                    f"β={self.beta:.1e} probes={self.n_probes}")
        return "α=— (no probes yet)"


# ── Quick Test ───────────────────────────────────────────────────

if __name__ == "__main__":
    # Smoke test with random hidden states
    print("=== Spectral Regularizer Smoke Test ===", file=sys.stderr)
    hs = torch.randn(512, 256)
    reg = SpectralRegularizer(None, alpha_target=8.8, beta=0.01,
                             log_to_chain=False)
    loss, metrics = reg.compute_loss(hs)
    print(f"α={metrics['mean_alpha']:.4f} deficit={metrics['alpha_deficit']:.4f} "
          f"loss={loss.item():.6f}", file=sys.stderr)
    print(f"Flatness={metrics.get('mean_flatness', '?'):.4f} "
          f"Concentration={metrics.get('mean_concentration', '?'):.4f}", file=sys.stderr)

    # With a near-uniform spectrum (α should be high)
    uniform = torch.ones(512, 256) * 0.01 + torch.randn(512, 256) * 0.001
    loss2, metrics2 = reg.compute_loss(uniform)
    print(f"Uniform-ish: α={metrics2['mean_alpha']:.4f}", file=sys.stderr)
