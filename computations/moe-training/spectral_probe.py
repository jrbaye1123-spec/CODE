"""
Spectral Probe — Measure the Spectral Tail Shape Parameter α
=============================================================
Captures activation covariance at each transformer layer,
computes eigenvalue spectrum, and fits the tail shape parameter α.

Tests the invariance claim: α should be input-independent if it's
a structural property of the model, not the data.

Tests the damage claim: our undertrained 17.1M model (step 655,
loss 1.73) should show α well below the grand mean 7.68.

Usage:
    python3 spectral_probe.py --text "The spectral tail shape parameter"
    python3 spectral_probe.py --invariance  # test across multiple inputs
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
import numpy as np

# Project paths
PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR))
sys.path.insert(0, str(PROJECT_DIR / "vault_rag"))

from model import GPT2MoEConfig, GPT2MoE1M


# ═══════════════════════════════════════════════════════════════════════
# Spectral Metrics
# ═══════════════════════════════════════════════════════════════════════

def compute_spectral_metrics(hidden_states: torch.Tensor,
                              ridge: float = 1e-6) -> Dict:
    """
    Compute full spectral metrics from a layer's hidden states.

    Args:
        hidden_states: (n_tokens, hidden_dim) — activations at one layer
        ridge: regularization for numerical stability

    Returns:
        dict with: logdet, trace, kappa, eigenvalues, alpha, effective_rank
    """
    n, d = hidden_states.shape

    if n < 2:
        return {"logdet": float('-inf'), "trace": 0.0, "kappa": 0.0,
                "alpha": 0.0, "eigenvalues": [], "effective_rank": 0.0,
                "n_tokens": n, "hidden_dim": d}

    # Center
    h = hidden_states - hidden_states.mean(dim=0, keepdim=True)
    cov = (h.T @ h) / (n - 1)

    # Ridge for stability
    cov_ridged = cov + ridge * torch.eye(d, device=cov.device)

    # Eigenvalues (sorted descending)
    eigenvals = torch.linalg.eigvalsh(cov_ridged)
    eigenvals = torch.sort(eigenvals, descending=True)[0]
    eigenvals_np = eigenvals.cpu().numpy()

    # Logdet via Cholesky
    try:
        L = torch.linalg.cholesky(cov_ridged)
        logdet = 2.0 * torch.sum(torch.log(torch.diag(L))).item()
    except Exception:
        logdet = float(np.sum(np.log(eigenvals_np[eigenvals_np > 0])))

    trace_val = float(torch.trace(cov).item())

    # Condition number
    kappa = float(eigenvals[-1].item() / eigenvals[0].item()) if eigenvals[0] > 0 else float('inf')

    # ── Spectral Tail Shape Parameter α ────────────────────────────
    # The tail shape parameter characterizes how rapidly the eigenvalue
    # spectrum decays. For a super-exponential tail:
    #   log(λ_i) ~ -α * f(i)
    #
    # We fit α as the exponent of the eigenvalue decay in log space.
    # Multiple fitting approaches — we compute all and report:

    # Only use significant eigenvalues (above ridge)
    sig_mask = eigenvals_np > ridge * 10
    sig_vals = eigenvals_np[sig_mask]
    n_sig = len(sig_vals)

    if n_sig < 3:
        alpha_fit = 0.0
        alpha_ratio = 0.0
    else:
        # Method 1: Fit log(λ_i) vs rank i as exponential decay
        # log(λ_i) = c - α * i  →  α = -slope of linear fit
        log_vals = np.log(sig_vals[sig_vals > 0])
        ranks = np.arange(1, len(log_vals) + 1, dtype=float)

        # Linear fit in log-log space: log(λ) = c - α * log(i)
        # This gives a power-law tail: λ_i ~ i^(-α)
        log_ranks = np.log(ranks)
        if len(log_ranks) > 2:
            # Fit: log(λ) = a + b * log(i)
            coeffs = np.polyfit(log_ranks, log_vals, 1)
            alpha_powerlaw = -coeffs[0]  # negative slope = decay rate
        else:
            alpha_powerlaw = 0.0

        # Method 2: Fit as exponential: log(λ) = c - α * i
        coeffs_exp = np.polyfit(ranks, log_vals, 1)
        alpha_exp = -coeffs_exp[0]

        # Method 3: Super-exponential fit: log(λ) = c - α * i^2
        # (quadratic in log space = super-exponential in linear space)
        coeffs_quad = np.polyfit(ranks, log_vals, 2)
        alpha_super = -coeffs_quad[1]  # linear coefficient (curvature is coeffs[0])

        # Method 4: Ratio-based α (from the user's framework)
        # α = -log(λ_1/λ_k) / log(k) for the tail
        # This measures the average decay rate across the spectrum
        k = min(n_sig, d)
        if k > 2 and sig_vals[0] > 0 and sig_vals[-1] > 0:
            alpha_ratio = -np.log(sig_vals[0] / sig_vals[-1]) / np.log(k)
        else:
            alpha_ratio = 0.0

        # The primary α: use the power-law fit (most stable)
        alpha_fit = alpha_powerlaw

    # ── Effective Rank (participation ratio) ────────────────────────
    # PR = (Σ λ_i)² / Σ λ_i²
    # Measures how many modes are "active"
    sig_sq = sig_vals ** 2
    if sig_sq.sum() > 0:
        effective_rank = float((sig_vals.sum() ** 2) / sig_sq.sum())
    else:
        effective_rank = 0.0

    return {
        "logdet": logdet,
        "trace": trace_val,
        "kappa": kappa,
        "alpha": alpha_fit,
        "alpha_exp": alpha_exp if n_sig >= 3 else 0.0,
        "alpha_super": alpha_super if n_sig >= 3 else 0.0,
        "alpha_ratio": alpha_ratio,
        "eigenvalues": eigenvals_np.tolist(),
        "n_significant": n_sig,
        "effective_rank": effective_rank,
        "n_tokens": n,
        "hidden_dim": d,
    }


# ═══════════════════════════════════════════════════════════════════════
# Layer Activation Hooking
# ═══════════════════════════════════════════════════════════════════════

class SpectralProbe:
    """
    Hooks into a model's transformer layers to capture activations
    and compute spectral metrics at each layer.
    """

    def __init__(self, model: GPT2MoE1M, tokenizer=None):
        self.model = model
        self.tokenizer = tokenizer
        self.activations = {}  # layer_idx → tensor
        self.hooks = []
        self._register_hooks()

    def _register_hooks(self):
        """Register forward hooks on each transformer block."""
        for i, block in enumerate(self.model.blocks):
            def make_hook(idx):
                def hook_fn(module, input, output):
                    # output is (x, present, aux_loss) from GPT2MoEBlock
                    if isinstance(output, tuple) and len(output) >= 1:
                        x = output[0]  # (batch, seq_len, n_embd)
                        self.activations[idx] = x.detach().squeeze(0)  # (seq, dim)
                return hook_fn
            h = block.register_forward_hook(make_hook(i))
            self.hooks.append(h)

        # Also hook the embedding output
        def emb_hook(module, input, output):
            self.activations[-1] = output.detach().squeeze(0)  # embedding layer
        self.hooks.append(self.model.wte.register_forward_hook(emb_hook))

        # And the final layer norm output
        def ln_f_hook(module, input, output):
            self.activations[-2] = output.detach().squeeze(0)
        self.hooks.append(self.model.ln_f.register_forward_hook(ln_f_hook))

    def remove_hooks(self):
        for h in self.hooks:
            h.remove()
        self.hooks = []

    @torch.no_grad()
    def probe(self, text: str or torch.Tensor, max_tokens: int = 2048) -> Dict:
        """
        Run text through the model and compute spectral metrics at each layer.

        Args:
            text: input string or pre-tokenized tensor
            max_tokens: max tokens to process (for memory)

        Returns:
            dict with per-layer metrics and summary
        """
        self.activations = {}

        # Tokenize
        if isinstance(text, str):
            if self.tokenizer is None:
                raise ValueError("No tokenizer provided for string input")
            input_ids = self.tokenizer.encode(text, return_tensors="pt").to(
                next(self.model.parameters()).device)
        else:
            input_ids = text.to(next(self.model.parameters()).device)

        # Truncate if needed
        if input_ids.shape[1] > max_tokens:
            input_ids = input_ids[:, :max_tokens]

        seq_len = input_ids.shape[1]
        pos_ids = torch.arange(seq_len, device=input_ids.device).unsqueeze(0)

        # Forward pass (hooks capture activations)
        t0 = time.time()
        logits, aux_loss = self.model(input_ids, position_ids=pos_ids,
                                       logits_last_only=True)
        fwd_time = time.time() - t0

        # Compute spectral metrics at each layer
        layer_metrics = {}
        for layer_idx, h_state in sorted(self.activations.items()):
            metrics = compute_spectral_metrics(h_state)
            metrics["layer"] = layer_idx
            layer_metrics[layer_idx] = metrics

        # ── Summary statistics ────────────────────────────────────────
        # Extract α across layers (excluding embedding and ln_f)
        transformer_layers = sorted([k for k in layer_metrics.keys() if k >= 0])
        alphas = [layer_metrics[k]["alpha"] for k in transformer_layers
                   if layer_metrics[k]["alpha"] > 0]
        alpha_exp_vals = [layer_metrics[k]["alpha_exp"] for k in transformer_layers
                          if layer_metrics[k]["alpha_exp"] > 0]
        alpha_ratio_vals = [layer_metrics[k]["alpha_ratio"] for k in transformer_layers
                           if layer_metrics[k]["alpha_ratio"] > 0]
        eff_ranks = [layer_metrics[k]["effective_rank"] for k in transformer_layers]
        logdets = [layer_metrics[k]["logdet"] for k in transformer_layers]

        summary = {
            "n_tokens": seq_len,
            "n_layers": len(transformer_layers),
            "forward_time_s": fwd_time,
            "alpha_mean": float(np.mean(alphas)) if alphas else 0.0,
            "alpha_std": float(np.std(alphas)) if alphas else 0.0,
            "alpha_exp_mean": float(np.mean(alpha_exp_vals)) if alpha_exp_vals else 0.0,
            "alpha_ratio_mean": float(np.mean(alpha_ratio_vals)) if alpha_ratio_vals else 0.0,
            "effective_rank_mean": float(np.mean(eff_ranks)) if eff_ranks else 0.0,
            "effective_rank_trend": eff_ranks,
            "logdet_trend": logdets,
            "alpha_by_layer": {str(k): layer_metrics[k]["alpha"]
                              for k in transformer_layers},
        }

        return {
            "layer_metrics": layer_metrics,
            "summary": summary,
        }


# ═══════════════════════════════════════════════════════════════════════
# Model Loader
# ═══════════════════════════════════════════════════════════════════════

def load_model(yarn_factor: float = 256.0, dtype: torch.dtype = torch.float32):
    """Load the GPT2-MoE-1M model with YaRN."""
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
# Invariance Test
# ═══════════════════════════════════════════════════════════════════════

def invariance_test(model, tokenizer, n_inputs: int = 10):
    """
    Test whether α is input-invariant by probing with diverse texts.
    If α is a structural property, it should be stable across inputs.
    """
    test_texts = [
        "The spectral tail shape parameter alpha characterizes the eigenvalue decay.",
        "In quantum mechanics, the wave function collapses upon measurement.",
        "The mixture of experts architecture routes tokens to specialized networks.",
        "Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor.",
        "The Lawvere fixed point theorem states that every endofunctor has a fixed point.",
        "Black hole information geometry uses Fisher-Rao metrics on statistical manifolds.",
        "def fibonacci(n): return n if n < 2 else fibonacci(n-1) + fibonacci(n-2)",
        "The de Sitter fixed point framework returns zero at maximum symmetry d=0.",
        "Quantum cosmology models the universe as a wave function over 3-geometries.",
        "The Nakamichi Shinjin program pursues P vs NP through topology and quantum geometry.",
    ][:n_inputs]

    probe = SpectralProbe(model, tokenizer)
    results = []

    print(f"\n{'='*80}")
    print(f"INVARIANCE TEST: {len(test_texts)} inputs")
    print(f"{'='*80}\n")

    for i, text in enumerate(test_texts):
        result = probe.probe(text)
        summary = result["summary"]
        results.append({
            "text": text[:60] + "..." if len(text) > 60 else text,
            "alpha_mean": summary["alpha_mean"],
            "alpha_std": summary["alpha_std"],
            "alpha_exp_mean": summary["alpha_exp_mean"],
            "alpha_ratio_mean": summary["alpha_ratio_mean"],
            "effective_rank_mean": summary["effective_rank_mean"],
            "n_tokens": summary["n_tokens"],
        })

        print(f"  [{i+1:2d}] α={summary['alpha_mean']:6.2f}±{summary['alpha_std']:.2f} "
              f"| α_exp={summary['alpha_exp_mean']:6.2f} "
              f"| α_ratio={summary['alpha_ratio_mean']:6.2f} "
              f"| eff_rank={summary['effective_rank_mean']:5.1f} "
              f"| {summary['n_tokens']:4d} tokens", flush=True)

    probe.remove_hooks()

    # ── Analysis ────────────────────────────────────────────────────
    alphas = [r["alpha_mean"] for r in results]
    alpha_exps = [r["alpha_exp_mean"] for r in results]
    alpha_ratios = [r["alpha_ratio_mean"] for r in results]

    print(f"\n{'─'*80}")
    print(f"ANALYSIS")
    print(f"{'─'*80}")
    print(f"  α (power-law fit):  mean={np.mean(alphas):.2f}  std={np.std(alphas):.2f}  "
          f"CV={np.std(alphas)/max(np.mean(alphas),0.01)*100:.1f}%")
    print(f"  α (exponential):    mean={np.mean(alpha_exps):.2f}  std={np.std(alpha_exps):.2f}  "
          f"CV={np.std(alpha_exps)/max(np.mean(alpha_exps),0.01)*100:.1f}%")
    print(f"  α (ratio):          mean={np.mean(alpha_ratios):.2f}  std={np.std(alpha_ratios):.2f}  "
          f"CV={np.std(alpha_ratios)/max(np.mean(alpha_ratios),0.01)*100:.1f}%")

    print(f"\n  Grand mean (paper): 7.68 ± 0.08")
    print(f"  Universal (conj):   8.8")
    print(f"  Our model:          {np.mean(alphas):.2f} ± {np.std(alphas):.2f}")

    # Coefficient of variation tells us about invariance
    cv = np.std(alphas) / max(np.mean(alphas), 0.01) * 100
    if cv < 5:
        verdict = "INVARIANT — α is input-independent (CV < 5%)"
    elif cv < 15:
        verdict = "WEAKLY INVARIANT — α varies moderately (5-15%)"
    else:
        verdict = "NOT INVARIANT — α depends strongly on input (CV > 15%)"

    print(f"\n  Invariance verdict: {verdict}")

    # Damage assessment
    our_alpha = np.mean(alphas)
    if our_alpha < 7.68 - 0.5:
        damage = "DAMAGED — α well below grand mean 7.68 (supports damage framework)"
    elif our_alpha < 8.8 - 0.5:
        damage = "MODERATE — α near grand mean but below universal 8.8"
    else:
        damage = "PRISTINE — α near universal 8.8 (unexpected for undertrained model)"

    print(f"  Damage verdict: {damage}")

    return results


# ═══════════════════════════════════════════════════════════════════════
# Single Text Probe
# ═══════════════════════════════════════════════════════════════════════

def single_probe(model, tokenizer, text: str):
    """Probe a single text and report per-layer metrics."""
    probe = SpectralProbe(model, tokenizer)
    result = probe.probe(text)
    probe.remove_hooks()

    summary = result["summary"]
    layers = result["layer_metrics"]

    print(f"\n{'='*80}")
    print(f"SPECTRAL PROBE: \"{text[:70]}...\"")
    print(f"{'='*80}")
    print(f"  Tokens: {summary['n_tokens']} | Layers: {summary['n_layers']} | "
          f"Time: {summary['forward_time_s']:.2f}s\n")

    print(f"  {'Layer':>6} | {'α':>7} | {'α_exp':>7} | {'α_ratio':>8} | "
          f"{'eff_rank':>8} | {'logdet':>10} | {'trace':>10} | {'κ':>10}")
    print(f"  {'─'*6}─┼─{'─'*7}─┼─{'─'*7}─┼─{'─'*8}─┼─{'─'*8}─┼─{'─'*10}─┼─{'─'*10}─┼─{'─'*10}")

    for idx in sorted(layers.keys()):
        m = layers[idx]
        label = f"emb" if idx == -1 else (f"ln_f" if idx == -2 else f"L{idx}")
        print(f"  {label:>6} | {m['alpha']:7.2f} | {m['alpha_exp']:7.2f} | "
              f"{m['alpha_ratio']:8.2f} | {m['effective_rank']:8.2f} | "
              f"{m['logdet']:10.2f} | {m['trace']:10.4f} | {m['kappa']:10.1f}")

    print(f"\n  Summary:")
    print(f"    α (power-law):  {summary['alpha_mean']:.2f} ± {summary['alpha_std']:.2f}")
    print(f"    α (exponential): {summary['alpha_exp_mean']:.2f}")
    print(f"    α (ratio):       {summary['alpha_ratio_mean']:.2f}")
    print(f"    Effective rank:  {summary['effective_rank_mean']:.2f}")
    print(f"\n  Reference: grand mean 7.68 ± 0.08, universal 8.8")

    # Effective rank trend shows the collapse
    trend = summary["effective_rank_trend"]
    if len(trend) >= 2:
        print(f"\n  Effective rank trend (collapse):")
        print(f"    Entry: {trend[0]:.2f} → Exit: {trend[-1]:.2f} "
              f"(drop: {trend[0]-trend[-1]:.2f}, "
              f"{(trend[0]-trend[-1])/max(trend[0],0.01)*100:.1f}%)")

    return result


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Spectral Probe for GPT2-MoE-1M")
    parser.add_argument("--text", type=str, default=None,
                        help="Text to probe")
    parser.add_argument("--invariance", action="store_true",
                        help="Run invariance test across multiple inputs")
    parser.add_argument("--n-inputs", type=int, default=10,
                        help="Number of inputs for invariance test")
    parser.add_argument("--yarn-factor", type=float, default=256.0)
    parser.add_argument("--json", type=str, default=None,
                        help="Save results to JSON file")
    args = parser.parse_args()

    model, tokenizer = load_model(yarn_factor=args.yarn_factor)

    if args.invariance:
        results = invariance_test(model, tokenizer, n_inputs=args.n_inputs)
        if args.json:
            Path(args.json).write_text(json.dumps(results, indent=2))
            print(f"\nSaved to {args.json}", file=sys.stderr)

    elif args.text:
        result = single_probe(model, tokenizer, args.text)
        if args.json:
            # Convert tensors to lists for JSON
            out = {"summary": result["summary"]}
            Path(args.json).write_text(json.dumps(out, indent=2))
            print(f"\nSaved to {args.json}", file=sys.stderr)

    else:
        # Default: run a quick probe with the α≈8.8 text
        text = ("The spectral tail shape parameter alpha approximates 8.8 "
                "as the universal band of the Fisher Information Metric "
                "along the spectral direction on the statistical manifold.")
        result = single_probe(model, tokenizer, text)

        print(f"\n{'='*80}")
        print(f"Running invariance test with 5 inputs...")
        print(f"{'='*80}")
        results = invariance_test(model, tokenizer, n_inputs=5)