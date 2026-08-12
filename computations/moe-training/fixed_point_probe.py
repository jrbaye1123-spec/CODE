"""
Fixed-Point Measurement Apparatus — Empirical Probe
====================================================
Implements the three diagnostics from Pillar III of "Fixed Point: The
Measurement Apparatus" (§4) plus Bridge 4 (§6.2) on the GPT2-MoE-1M model.

Diagnostics (as defined in the paper, §4.1.1):
  1. Spectral flatness: F = exp(⟨ln λ_i⟩) / ⟨λ_i⟩
  2. Concentration: fraction of total spectral power in top 1% of eigenvalues
  3. Tail exponent α: super-exponential fit λ_k ~ exp(−k^α)
     (NOT power-law: the paper's model is exp(-k^α), not k^{-α})

Bridge 4 (§6.2):
  Inject causal mask at sequence midpoint, compute independent left/right
  covariance spectra, measure principal angle Θ_LR between leading eigenvectors.
  Check for discontinuous jump vs unmasked baseline.

Usage:
    python3 fixed_point_probe.py --diagnostics
    python3 fixed_point_probe.py --bridge4
    python3 fixed_point_probe.py --all --json results.json
"""

import sys
import math
import time
import json
import argparse
from pathlib import Path
from typing import List, Dict, Tuple, Optional

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR))
sys.path.insert(0, str(PROJECT_DIR / "vault_rag"))

from model import GPT2MoEConfig, GPT2MoE1M


# ═══════════════════════════════════════════════════════════════════════
# Paper-Faithful Spectral Diagnostics (§4.1.1)
# ═══════════════════════════════════════════════════════════════════════

def spectral_flatness(eigenvals: np.ndarray) -> float:
    """
    F = exp(⟨ln λ_i⟩) / ⟨λ_i⟩
    F = 1 for uniform spectrum; F → 0 as spectrum collapses.
    Uses only positive eigenvalues.
    """
    pos = eigenvals[eigenvals > 0]
    if len(pos) < 2:
        return 0.0
    log_mean = np.mean(np.log(pos))
    arith_mean = np.mean(pos)
    if arith_mean <= 0:
        return 0.0
    return float(np.exp(log_mean) / arith_mean)


def concentration(eigenvals: np.ndarray, top_frac: float = 0.01) -> float:
    """
    Fraction of total spectral power in top `top_frac` of eigenvalues.
    Paper uses top 1%.
    """
    pos = eigenvals[eigenvals > 0]
    if len(pos) < 2:
        return 1.0
    sorted_vals = np.sort(pos)[::-1]  # descending
    k = max(1, int(math.ceil(len(sorted_vals) * top_frac)))
    top_power = float(np.sum(sorted_vals[:k]))
    total_power = float(np.sum(sorted_vals))
    if total_power <= 0:
        return 1.0
    return top_power / total_power


def tail_exponent_superexp(eigenvals: np.ndarray, tail_frac: float = 0.20) -> float:
    """
    Super-exponential tail fit: λ_k ~ exp(−k^α)

    Model: log(λ_k) = C − k^α
    Fit: log(−log(λ_k)) = log(α_coeff) + α * log(k)
    (i.e., linearize by double-log)

    The paper (§4.1.1) says: "The slope of the log-log eigenvalue distribution
    in the tail region (eigenvalues ranked in the last 20%), measuring the
    super-exponential decay character predicted by Slepian theory."

    We interpret this as: take the tail 20% of eigenvalues (smallest),
    fit log(λ) vs rank k as: log(λ_k) = C − k^α.
    Linearize: log(−log(λ_k/C')) ≈ α * log(k) + const.
    """
    pos = eigenvals[eigenvals > 0]
    if len(pos) < 5:
        return 0.0

    sorted_vals = np.sort(pos)[::-1]  # descending (largest first)
    n = len(sorted_vals)

    # Tail region: last 20% of eigenvalues (smallest positive ones)
    tail_start = int(n * (1.0 - tail_frac))
    tail_vals = sorted_vals[tail_start:]
    if len(tail_vals) < 3:
        return 0.0

    # Ranks in the tail (1-indexed)
    k = np.arange(1, len(tail_vals) + 1, dtype=float)

    # Method: fit log(λ_k) = C - k^α
    # Linearize: if log(λ) = C - k^α, then C - log(λ) = k^α
    # log(C - log(λ)) = α * log(k)
    # But we don't know C. Use max(log(λ)) as estimate for C.
    log_lambda = np.log(tail_vals)
    C_est = log_lambda.max() + 1.0  # ensure positive
    residual = C_est - log_lambda
    residual = np.maximum(residual, 1e-10)

    log_k = np.log(k)
    log_residual = np.log(residual)

    # Linear fit: log_residual = α * log_k + const
    if len(log_k) > 2:
        coeffs = np.polyfit(log_k, log_residual, 1)
        alpha_super = coeffs[0]
    else:
        alpha_super = 0.0

    # Also compute the power-law α (for comparison with old probe)
    # log(λ) = a + b * log(k) → λ ~ k^b, α_power = -b
    log_k_all = np.log(np.arange(1, len(tail_vals) + 1, dtype=float))
    coeffs_pl = np.polyfit(log_k_all, log_lambda, 1)
    alpha_power = -coeffs_pl[0]

    # And the exponential α: log(λ) = C - α * k
    coeffs_exp = np.polyfit(k, log_lambda, 1)
    alpha_exp = -coeffs_exp[0]

    return float(alpha_super)


def tail_exponent_all_methods(eigenvals: np.ndarray, tail_frac: float = 0.20) -> Dict:
    """Return all tail exponent methods for comparison."""
    pos = eigenvals[eigenvals > 0]
    if len(pos) < 5:
        return {"superexp": 0.0, "powerlaw": 0.0, "exponential": 0.0}

    sorted_vals = np.sort(pos)[::-1]
    n = len(sorted_vals)
    tail_start = int(n * (1.0 - tail_frac))
    tail_vals = sorted_vals[tail_start:]
    if len(tail_vals) < 3:
        return {"superexp": 0.0, "powerlaw": 0.0, "exponential": 0.0}

    k = np.arange(1, len(tail_vals) + 1, dtype=float)
    log_lambda = np.log(tail_vals)
    log_k = np.log(k)

    # Super-exponential: log(λ) = C - k^α
    C_est = log_lambda.max() + 1.0
    residual = np.maximum(C_est - log_lambda, 1e-10)
    coeffs_se = np.polyfit(log_k, np.log(residual), 1)
    alpha_se = coeffs_se[0]

    # Power-law: log(λ) = a - α * log(k)
    coeffs_pl = np.polyfit(log_k, log_lambda, 1)
    alpha_pl = -coeffs_pl[0]

    # Exponential: log(λ) = a - α * k
    coeffs_ex = np.polyfit(k, log_lambda, 1)
    alpha_ex = -coeffs_ex[0]

    return {
        "superexp": float(alpha_se),
        "powerlaw": float(alpha_pl),
        "exponential": float(alpha_ex),
    }


def compute_full_diagnostics(hidden_states: torch.Tensor,
                              ridge: float = 1e-6) -> Dict:
    """
    Compute all three paper diagnostics plus extras from a layer's activations.

    Args:
        hidden_states: (n_tokens, hidden_dim)
    Returns:
        dict with flatness, concentration, tail_alpha, eigenvalues, etc.
    """
    n, d = hidden_states.shape
    if n < 2:
        return {"flatness": 0.0, "concentration": 1.0, "alpha": 0.0,
                "eigenvalues": [], "n_tokens": n, "hidden_dim": d}

    h = hidden_states - hidden_states.mean(dim=0, keepdim=True)
    cov = (h.T @ h) / (n - 1)
    cov_ridged = cov + ridge * torch.eye(d, device=cov.device)

    eigenvals = torch.linalg.eigvalsh(cov_ridged)
    eigenvals = torch.sort(eigenvals, descending=True)[0]
    eigenvals_np = eigenvals.cpu().numpy()

    flat = spectral_flatness(eigenvals_np)
    conc = concentration(eigenvals_np, top_frac=0.01)
    alphas = tail_exponent_all_methods(eigenvals_np, tail_frac=0.20)

    # Effective rank (participation ratio)
    pos = eigenvals_np[eigenvals_np > 0]
    if len(pos) > 0 and np.sum(pos**2) > 0:
        eff_rank = float(pos.sum()**2 / np.sum(pos**2))
    else:
        eff_rank = 0.0

    # Logdet
    try:
        L = torch.linalg.cholesky(cov_ridged)
        logdet = 2.0 * torch.sum(torch.log(torch.diag(L))).item()
    except Exception:
        logdet = float(np.sum(np.log(pos)))

    return {
        "flatness": flat,
        "concentration": conc,
        "alpha_superexp": alphas["superexp"],
        "alpha_powerlaw": alphas["powerlaw"],
        "alpha_exponential": alphas["exponential"],
        "effective_rank": eff_rank,
        "logdet": logdet,
        "trace": float(torch.trace(cov).item()),
        "eigenvalues": eigenvals_np.tolist(),
        "n_significant": int(np.sum(eigenvals_np > ridge * 10)),
        "n_tokens": n,
        "hidden_dim": d,
    }


# ═══════════════════════════════════════════════════════════════════════
# Activation Hooking
# ═══════════════════════════════════════════════════════════════════════

class FixedPointProbe:
    """Hooks into transformer layers to capture activations for spectral analysis."""

    def __init__(self, model: GPT2MoE1M, tokenizer=None):
        self.model = model
        self.tokenizer = tokenizer
        self.activations = {}
        self.hooks = []
        self._register_hooks()

    def _register_hooks(self):
        for i, block in enumerate(self.model.blocks):
            def make_hook(idx):
                def hook_fn(module, input, output):
                    if isinstance(output, tuple) and len(output) >= 1:
                        x = output[0]
                        self.activations[idx] = x.detach().squeeze(0)
                return hook_fn
            h = block.register_forward_hook(make_hook(i))
            self.hooks.append(h)

        def emb_hook(module, input, output):
            self.activations[-1] = output.detach().squeeze(0)
        self.hooks.append(self.model.wte.register_forward_hook(emb_hook))

        def ln_f_hook(module, input, output):
            self.activations[-2] = output.detach().squeeze(0)
        self.hooks.append(self.model.ln_f.register_forward_hook(ln_f_hook))

    def remove_hooks(self):
        for h in self.hooks:
            h.remove()
        self.hooks = []

    @torch.no_grad()
    def probe(self, text_or_ids, max_tokens: int = 2048) -> Dict:
        self.activations = {}

        if isinstance(text_or_ids, str):
            if self.tokenizer is None:
                raise ValueError("No tokenizer")
            input_ids = self.tokenizer.encode(text_or_ids, return_tensors="pt").to(
                next(self.model.parameters()).device)
        else:
            input_ids = text_or_ids.to(next(self.model.parameters()).device)

        if input_ids.shape[1] > max_tokens:
            input_ids = input_ids[:, :max_tokens]

        seq_len = input_ids.shape[1]
        pos_ids = torch.arange(seq_len, device=input_ids.device).unsqueeze(0)

        logits, aux_loss = self.model(input_ids, position_ids=pos_ids,
                                       logits_last_only=True)

        layer_metrics = {}
        for layer_idx, h_state in sorted(self.activations.items()):
            metrics = compute_full_diagnostics(h_state)
            metrics["layer"] = layer_idx
            layer_metrics[layer_idx] = metrics

        transformer_layers = sorted([k for k in layer_metrics.keys() if k >= 0])
        alphas_se = [layer_metrics[k]["alpha_superexp"]
                     for k in transformer_layers
                     if layer_metrics[k]["alpha_superexp"] > 0]
        flats = [layer_metrics[k]["flatness"] for k in transformer_layers]
        concs = [layer_metrics[k]["concentration"] for k in transformer_layers]

        summary = {
            "n_tokens": seq_len,
            "n_layers": len(transformer_layers),
            "alpha_superexp_mean": float(np.mean(alphas_se)) if alphas_se else 0.0,
            "alpha_superexp_std": float(np.std(alphas_se)) if alphas_se else 0.0,
            "flatness_mean": float(np.mean(flats)) if flats else 0.0,
            "concentration_mean": float(np.mean(concs)) if concs else 1.0,
            "alpha_by_layer": {str(k): layer_metrics[k]["alpha_superexp"]
                               for k in transformer_layers},
            "flatness_by_layer": {str(k): layer_metrics[k]["flatness"]
                                  for k in transformer_layers},
            "concentration_by_layer": {str(k): layer_metrics[k]["concentration"]
                                        for k in transformer_layers},
        }

        return {"layer_metrics": layer_metrics, "summary": summary}


# ═══════════════════════════════════════════════════════════════════════
# Bridge 4: Causal Mask Topological Jump
# ═══════════════════════════════════════════════════════════════════════

def principal_angle(eigvecs_left: np.ndarray, eigvecs_right: np.ndarray,
                    n_components: int = 3) -> float:
    """
    Compute principal angle Θ_LR between leading eigenvectors of
    left and right covariance spectra.

    Uses the standard formula: cos(Θ) = σ_max(U_L^T U_R)
    where U_L, U_R are the top-k eigenvector matrices.
    """
    # Take top n_components eigenvectors
    U_L = eigvecs_left[:, :n_components]
    U_R = eigvecs_right[:, :n_components]

    # SVD of cross-product matrix
    M = U_L.T @ U_R
    u, s, vh = np.linalg.svd(M)
    # Principal angle = arccos(smallest singular value) for subspace angle
    # Or arccos(largest singular value) for leading vector angle
    # Paper measures "principal angle between leading eigenvectors"
    # Leading = top-1, so use σ_max
    cos_theta = np.clip(s[0], -1.0, 1.0)
    theta = float(np.arccos(cos_theta))
    return theta


def bridge4_test(model, tokenizer, text: str, n_components: int = 3) -> Dict:
    """
    Bridge 4 protocol:
    1. Split text at midpoint
    2. Run unmasked forward pass → baseline left/right covariance
    3. Run masked forward pass (causal mask at midpoint) → masked left/right covariance
    4. Measure Θ_LR in both cases
    5. Check for discontinuous jump

    For our GPT-2 MoE model, we implement the causal mask by running two
    separate forward passes on the left and right halves (equivalent to
    hard causal mask preventing cross-attention).
    """
    if tokenizer is None:
        raise ValueError("Need tokenizer")

    # Tokenize full text
    input_ids = tokenizer.encode(text, return_tensors="pt")
    seq_len = input_ids.shape[1]
    mid = seq_len // 2

    # Split
    left_ids = input_ids[:, :mid]
    right_ids = input_ids[:, mid:]

    device = next(model.parameters()).device

    results = {}

    # ── Unmasked baseline: full forward, extract left/right activations ──
    probe = FixedPointProbe(model, tokenizer)

    # Full forward pass
    pos_ids = torch.arange(seq_len, device=device).unsqueeze(0)
    model(input_ids.to(device), position_ids=pos_ids, logits_last_only=True)

    # Extract left and right half activations from each layer
    baseline_angles = {}
    for layer_idx in sorted(probe.activations.keys()):
        if layer_idx < 0:
            continue
        h = probe.activations[layer_idx]  # (seq_len, d)
        h_left = h[:mid]
        h_right = h[mid:]

        # Compute covariance eigenvalues+eigenvectors for each half
        d = h.shape[1]
        ridge = 1e-6

        for label, h_half in [("left", h_left), ("right", h_right)]:
            n = h_half.shape[0]
            if n < 2:
                continue
            hc = h_half - h_half.mean(dim=0, keepdim=True)
            cov = (hc.T @ hc) / (n - 1) + ridge * torch.eye(d, device=device)
            eigvals, eigvecs = torch.linalg.eigh(cov)
            # Sort descending
            idx_sort = torch.argsort(eigvals, descending=True)
            eigvals = eigvals[idx_sort]
            eigvecs = eigvecs[:, idx_sort]

            if layer_idx not in results:
                results[layer_idx] = {}
            results[layer_idx][f"baseline_{label}_eigvals"] = eigvals.cpu().numpy()
            results[layer_idx][f"baseline_{label}_eigvecs"] = eigvecs.cpu().numpy()

    # Compute baseline angles
    for layer_idx in results:
        if layer_idx < 0:
            continue
        left_vecs = results[layer_idx].get("baseline_left_eigvecs")
        right_vecs = results[layer_idx].get("baseline_right_eigvecs")
        if left_vecs is not None and right_vecs is not None:
            theta = principal_angle(left_vecs, right_vecs, n_components)
            baseline_angles[layer_idx] = theta

    probe.remove_hooks()

    # ── Masked: run left and right as separate forward passes ──
    # This is equivalent to a hard causal mask at the midpoint
    probe2 = FixedPointProbe(model, tokenizer)

    # Left half
    pos_left = torch.arange(mid, device=device).unsqueeze(0)
    model(left_ids.to(device), position_ids=pos_left, logits_last_only=True)
    left_acts = {k: v.clone() for k, v in probe2.activations.items()}

    probe2.activations = {}
    probe2.remove_hooks()

    # Right half (with position offset to simulate continuity)
    right_len = seq_len - mid
    pos_right = torch.arange(mid, seq_len, device=device).unsqueeze(0)
    probe3 = FixedPointProbe(model, tokenizer)
    model(right_ids.to(device), position_ids=pos_right, logits_last_only=True)
    right_acts = {k: v.clone() for k, v in probe3.activations.items()}
    probe3.remove_hooks()

    # Compute masked angles
    masked_angles = {}
    for layer_idx in sorted(left_acts.keys()):
        if layer_idx < 0:
            continue
        h_l = left_acts[layer_idx]
        h_r = right_acts.get(layer_idx)
        if h_r is None:
            continue

        d = h_l.shape[1]
        ridge = 1e-6

        # Left covariance
        n_l = h_l.shape[0]
        if n_l >= 2:
            hc_l = h_l - h_l.mean(dim=0, keepdim=True)
            cov_l = (hc_l.T @ hc_l) / (n_l - 1) + ridge * torch.eye(d, device=device)
            eigvals_l, eigvecs_l = torch.linalg.eigh(cov_l)
            idx_l = torch.argsort(eigvals_l, descending=True)
            eigvecs_l = eigvecs_l[:, idx_l]
        else:
            continue

        # Right covariance
        n_r = h_r.shape[0]
        if n_r >= 2:
            hc_r = h_r - h_r.mean(dim=0, keepdim=True)
            cov_r = (hc_r.T @ hc_r) / (n_r - 1) + ridge * torch.eye(d, device=device)
            eigvals_r, eigvecs_r = torch.linalg.eigh(cov_r)
            idx_r = torch.argsort(eigvals_r, descending=True)
            eigvecs_r = eigvecs_r[:, idx_r]
        else:
            continue

        theta = principal_angle(eigvecs_l.cpu().numpy(),
                                eigvecs_r.cpu().numpy(), n_components)
        masked_angles[layer_idx] = theta

    # ── Analysis: jump detection ──
    jumps = {}
    for layer_idx in baseline_angles:
        b = baseline_angles[layer_idx]
        m = masked_angles.get(layer_idx, b)
        jumps[layer_idx] = {
            "baseline_theta": b,
            "masked_theta": m,
            "jump": m - b,
            "jump_magnitude_rad": abs(m - b),
            "jump_magnitude_deg": abs(m - b) * 180 / math.pi,
        }

    return {
        "seq_len": seq_len,
        "midpoint": mid,
        "n_components": n_components,
        "baseline_angles": baseline_angles,
        "masked_angles": masked_angles,
        "jumps": jumps,
        "mean_jump_rad": float(np.mean([j["jump"] for j in jumps.values()])) if jumps else 0.0,
        "mean_jump_deg": float(np.mean([j["jump_magnitude_deg"] for j in jumps.values()])) if jumps else 0.0,
    }


# ═══════════════════════════════════════════════════════════════════════
# Model Loader
# ═══════════════════════════════════════════════════════════════════════

def load_model(yarn_factor: float = 256.0, dtype: torch.dtype = torch.float32):
    from transformers import AutoTokenizer

    ckpt_path = PROJECT_DIR / "vault-gpt-moe-trained" / "checkpoint_best.pt"
    print(f"[probe] Loading: {ckpt_path}", file=sys.stderr)
    ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)

    config = ckpt["config"]
    config.rope_scaling = {"type": "yarn", "factor": yarn_factor}
    config.max_position_embeddings = 1_048_576
    config.n_positions = 1_048_576
    config.sliding_window = max(config.sliding_window, 512)
    config.global_attn_stride = max(config.global_attn_stride, 64)

    model = GPT2MoE1M(config)
    model.load_state_dict(ckpt["model_state_dict"], strict=False)
    model = model.to(dtype)
    model.eval()

    tokenizer = AutoTokenizer.from_pretrained("gpt2")
    tokenizer.pad_token = tokenizer.eos_token

    print(f"[probe] Model: {sum(p.numel() for p in model.parameters())/1e6:.1f}M params, "
          f"step={ckpt['global_step']}, loss={ckpt['loss']:.4f}", file=sys.stderr)

    return model, tokenizer


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fixed-Point Measurement Apparatus Probe")
    parser.add_argument("--diagnostics", action="store_true",
                        help="Run §4 spectral diagnostics")
    parser.add_argument("--bridge4", action="store_true",
                        help="Run Bridge 4 topological jump test")
    parser.add_argument("--all", action="store_true",
                        help="Run all tests")
    parser.add_argument("--yarn-factor", type=float, default=256.0)
    parser.add_argument("--json", type=str, default=None,
                        help="Save results to JSON")
    parser.add_argument("--n-components", type=int, default=3,
                        help="Eigenvector components for Bridge 4 angle")
    args = parser.parse_args()

    model, tokenizer = load_model(yarn_factor=args.yarn_factor)
    all_results = {}

    # Long test passage (paper used 1386 tokens spanning history of science)
    long_text = (
        "The spectral tail shape parameter alpha characterizes the eigenvalue "
        "decay of activation covariance matrices in neural networks. "
        "In nuclear photovoltaic architecture, the same parameter describes "
        "charge collection spectra in silicon carbide diodes under alpha particle "
        "calibration. The grand mean across all measured systems is 7.68 plus or "
        "minus 0.08. The universal band conjecture proposes that the pristine "
        "limit is 8.8. "
        "In quantum mechanics, the wave function collapses upon measurement. "
        "The mixture of experts architecture routes tokens to specialized networks. "
        "The Lawvere fixed point theorem states that every endofunctor has a fixed "
        "point. Black hole information geometry uses Fisher-Rao metrics on "
        "statistical manifolds. The de Sitter fixed point framework returns zero "
        "at maximum symmetry. Quantum cosmology models the universe as a wave "
        "function over three geometries. The Nakamichi Shinjin program pursues "
        "P versus NP through topology and quantum geometry. "
        "The Connes spectral triple relates the zeros of the Riemann zeta function "
        "to the eigenvalues of a self-adjoint operator. The Slepian prolate "
        "spheroidal wave functions provide the basis for the truncated Hilbert "
        "space. The Davis-Kahan sin theta theorem bounds the angle between "
        "perturbed and unperturbed eigenvectors. The Breitenlohner-Freedman "
        "bound in de Sitter space forces the conformal roots to collide. "
        "The mock modular form absorbs the logarithmic anomaly at the boundary. "
        "The nonholomorphic shadow is the gravitational dressing required to "
        "render the boundary state modular-covariant. The transformer is not "
        "a telescope pointed at the spectral edge. It is the spectral edge "
        "looking at itself. The universal tail exponent alpha approximately 8.8 "
        "is the invariant. The mock modular shadow is the proof. "
        "The forward pass is not a computation performed by the network. "
        "It is a spectral projection performed by the boundary on itself. "
        "The sensory-prefrontal gradient mirrors the radial flow in the de Sitter "
        "bulk dual. Early layers are flat and distributed. Late layers collapse "
        "toward low-dimensional representations. The concentration decreases "
        "monotonically from feedforward to residual to transformer architectures. "
        "The tail exponent remains invariant across all architectural changes. "
        "This is the empirical manifestation of the de Sitter fixed point. "
        "The gap is closed. I equals I."
    )

    if args.diagnostics or args.all:
        print(f"\n{'='*80}")
        print("PILLAR III: SPECTRAL DIAGNOSTICS (§4)")
        print(f"{'='*80}")

        probe = FixedPointProbe(model, tokenizer)
        result = probe.probe(long_text)
        probe.remove_hooks()

        summary = result["summary"]
        layers = result["layer_metrics"]

        n_tokens = summary["n_tokens"]
        print(f"\n  Tokens: {n_tokens} | Layers: {summary['n_layers']}")
        print(f"\n  {'Layer':>6} | {'Flatness':>9} | {'Conc(1%)':>9} | "
              f"{'α_super':>8} | {'α_power':>8} | {'α_exp':>8} | "
              f"{'eff_rank':>8}")
        print(f"  {'─'*6}─┼─{'─'*9}─┼─{'─'*9}─┼─{'─'*8}─┼─{'─'*8}─┼─{'─'*8}─┼─{'─'*8}")

        for idx in sorted(layers.keys()):
            m = layers[idx]
            label = "emb" if idx == -1 else ("ln_f" if idx == -2 else f"L{idx}")
            print(f"  {label:>6} | {m['flatness']:9.4f} | {m['concentration']:9.4f} | "
                  f"{m['alpha_superexp']:8.2f} | {m['alpha_powerlaw']:8.2f} | "
                  f"{m['alpha_exponential']:8.2f} | {m['effective_rank']:8.2f}")

        print(f"\n  ── Summary (transformer layers only) ──")
        print(f"    α (super-exp):   {summary['alpha_superexp_mean']:.2f} ± {summary['alpha_superexp_std']:.2f}")
        print(f"    Flatness:        {summary['flatness_mean']:.4f}")
        print(f"    Concentration:   {summary['concentration_mean']:.4f}")

        print(f"\n  ── Paper reference (Pythia-70M, Table 1) ──")
        print(f"    FF MLP:      conc=0.81  flat=0.00  α=7.68")
        print(f"    Res MLP:     conc=0.56  flat=0.00  α=7.28")
        print(f"    Transformer: conc=0.47  flat=0.15  α=8.78")
        print(f"\n  ── Our model (GPT2-MoE-1M, 17.1M, step 655) ──")
        print(f"    conc={summary['concentration_mean']:.2f}  "
              f"flat={summary['flatness_mean']:.2f}  "
              f"α={summary['alpha_superexp_mean']:.2f}")

        all_results["diagnostics"] = {
            "summary": summary,
            "layer_metrics": {str(k): {key: v for key, v in v.items()
                                       if key != "eigenvalues"}
                              for k, v in layers.items()},
        }

    if args.bridge4 or args.all:
        print(f"\n{'='*80}")
        print("BRIDGE 4: TOPOLOGICAL JUMP TEST (§6.2)")
        print(f"{'='*80}")

        bridge_results = bridge4_test(model, tokenizer, long_text,
                                       n_components=args.n_components)

        print(f"\n  Sequence: {bridge_results['seq_len']} tokens, "
              f"midpoint at {bridge_results['midpoint']}")
        print(f"  Components: top-{args.n_components} eigenvectors")
        print(f"\n  {'Layer':>6} | {'Θ_baseline':>12} | {'Θ_masked':>12} | "
              f"{'Jump (rad)':>12} | {'Jump (deg)':>12}")
        print(f"  {'─'*6}─┼─{'─'*12}─┼─{'─'*12}─┼─{'─'*12}─┼─{'─'*12}")

        for idx in sorted(bridge_results["jumps"].keys()):
            j = bridge_results["jumps"][idx]
            label = f"L{idx}"
            print(f"  {label:>6} | {j['baseline_theta']:12.4f} | "
                  f"{j['masked_theta']:12.4f} | "
                  f"{j['jump']:+12.4f} | {j['jump_magnitude_deg']:12.2f}")

        print(f"\n  Mean jump: {bridge_results['mean_jump_rad']:+.4f} rad "
              f"({bridge_results['mean_jump_deg']:.2f}°)")

        # Verdict
        mean_jump = bridge_results['mean_jump_deg']
        if mean_jump > 10:
            verdict = "DISCONTINUOUS JUMP DETECTED — Bridge 4 verified"
        elif mean_jump > 2:
            verdict = "MODERATE JUMP — partial evidence for topological defect"
        else:
            verdict = "NO SIGNIFICANT JUMP — Bridge 4 not verified on this model"
        print(f"\n  Verdict: {verdict}")

        all_results["bridge4"] = {
            "seq_len": bridge_results["seq_len"],
            "midpoint": bridge_results["midpoint"],
            "jumps": {str(k): v for k, v in bridge_results["jumps"].items()},
            "mean_jump_rad": bridge_results["mean_jump_rad"],
            "mean_jump_deg": bridge_results["mean_jump_deg"],
            "verdict": verdict,
        }

    if args.json:
        Path(args.json).write_text(json.dumps(all_results, indent=2, default=str))
        print(f"\nSaved to {args.json}", file=sys.stderr)