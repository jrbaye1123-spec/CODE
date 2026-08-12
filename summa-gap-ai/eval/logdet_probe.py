#!/usr/bin/env python3
"""
Summa-Gap AI — LogDet Probe Evaluation Framework
Implements the Summa's measurement apparatus: logdet, Fisher metric,
attention entropy, spectral tail exponent, and slip detection.

This is the SAME probe described in Chapter 16b (LogDet & Logit),
applied to evaluate the trained Summa-Gap model.

Usage:
    python eval/logdet_probe.py --model_path models/summa-gap-8b-qlora/final
"""

import os
import re
import json
import argparse
import numpy as np
from scipy import linalg
from scipy.spatial.distance import cosine
from pathlib import Path

# ─── Core Probes ─────────────────────────────────────────────

class LogDetProbe:
    """
    S(X) = log det((X−μ)ᵀ(X−μ)/(n−1) + εI)

    Measures manifold conditioning / effective rank.
    High logdet → diverse representations, well-conditioned.
    Low logdet → collapsed, rank-deficient.
    """
    def __init__(self, epsilon=1e-6):
        self.epsilon = epsilon
        self.history = []

    def compute(self, activations):
        """
        activations: (n_samples, d_features) numpy array
        Returns: logdet, effective_rank, eigenvalue_spectrum
        """
        X = activations.astype(np.float64)
        n, d = X.shape
        X_centered = X - X.mean(axis=0, keepdims=True)
        cov = (X_centered.T @ X_centered) / (n - 1) if n > 1 else np.zeros((d, d))

        # Regularize
        cov_reg = cov + self.epsilon * np.eye(d)

        # Eigendecomposition
        eigvals = linalg.eigvalsh(cov_reg)
        # Clamp negative zeros
        eigvals = np.maximum(eigvals, self.epsilon)

        logdet = np.sum(np.log(eigvals))
        effective_rank = np.sum(eigvals > self.epsilon * 10)

        # Spectral concentration (top-K capture)
        sorted_ev = np.sort(eigvals)[::-1]
        total_var = np.sum(sorted_ev)
        concentrations = {}
        for k_pct in [0.5, 0.9, 0.95, 0.99]:
            cumsum = np.cumsum(sorted_ev)
            k = np.searchsorted(cumsum, k_pct * total_var) + 1
            concentrations[f"C_{int(k_pct*100)}"] = k / d

        result = {
            "logdet": logdet,
            "effective_rank": effective_rank,
            "total_dim": d,
            "eigenvalues": sorted_ev.tolist(),
            "concentrations": concentrations,
        }

        self.history.append(result)
        return result

    def tail_exponent(self, tail_fraction=0.15):
        """
        Fit super-exponential tail: λ_k ~ exp(−k^α)
        The Summa's α ≈ 7.5 is the invariant across architectures.

        Uses only the smallest tail_fraction of eigenvalues and fits
        log(−log(λ_k / λ_max)) = α·log(k) + const via linear regression.
        """
        if not self.history:
            return None

        eigvals = np.array(self.history[-1]["eigenvalues"])
        # Use only the extreme tail — smallest eigenvalues
        n_tail = max(20, int(len(eigvals) * tail_fraction))
        tail_vals = eigvals[-n_tail:]

        # Normalize by the largest TAIL value (not global max)
        # This prevents bulk eigenvalues from dominating the ratio
        tail_max = tail_vals.max()
        if tail_max < 1e-20:
            return {"alpha": None, "error": "Tail values too small"}

        ratios = tail_vals / tail_max
        k = np.arange(1, n_tail + 1, dtype=float)

        valid = (ratios > 1e-15) & (k > 0)
        if valid.sum() < 5:
            return {"alpha": None, "error": "Insufficient tail data"}

        # λ_k / λ_tail_max ≈ exp(−(k^α − 1))
        # log(λ_k / λ_tail_max) ≈ −(k^α − 1) → −log(ratio) ≈ k^α − 1
        # log(−log(ratio) + 1) ≈ α·log(k)
        neg_log_ratio = -np.log(ratios[valid] + 1e-30)
        y = np.log(neg_log_ratio + 1.0)
        x = np.log(k[valid])
        A = np.vstack([x, np.ones_like(x)]).T
        alpha, const = np.linalg.lstsq(A, y, rcond=None)[0]

        return {"alpha": float(alpha), "const": float(const), "r_squared": None}


class FisherMetricProbe:
    """
    Fisher information metric: g_ij = E[∂_i log p · ∂_j log p]
    Measures information-geometric distance between probability distributions.
    """
    def __init__(self):
        self.metrics = []

    def compute(self, log_probs):
        """
        log_probs: (n_samples, d_classes) log-probability matrix
        Returns: trace of Fisher metric (scalar curvature proxy)
        """
        # Gradient of log-probs approximated via differences
        grads = np.diff(log_probs, axis=0)
        fisher = grads.T @ grads / (grads.shape[0] - 1) if grads.shape[0] > 1 else np.zeros((log_probs.shape[1],)*2)

        trace_fisher = np.trace(fisher)
        det_fisher = linalg.det(fisher + 1e-6 * np.eye(fisher.shape[0]))

        result = {
            "trace_fisher": float(trace_fisher),
            "logdet_fisher": float(np.log(max(det_fisher, 1e-15))),
            "condition_number": float(np.linalg.cond(fisher + 1e-6 * np.eye(fisher.shape[0]))),
        }
        self.metrics.append(result)
        return result


class AttentionEntropyProbe:
    """
    H(p) = −Σ p_i log p_i (per attention head, per token)
    Measures epistemic uncertainty from attention distributions.
    """
    def compute(self, attention_weights):
        """
        attention_weights: (n_heads, seq_len, seq_len) or (n_heads, seq_len)
        Returns: per-head entropy
        """
        eps = 1e-10
        # Average over query positions
        if attention_weights.ndim == 3:
            attn_avg = attention_weights.mean(axis=1)  # (heads, key_len)
        else:
            attn_avg = attention_weights

        entropies = -np.sum(attn_avg * np.log(attn_avg + eps), axis=-1)
        return {
            "entropy_per_head": entropies.tolist(),
            "mean_entropy": float(np.mean(entropies)),
            "std_entropy": float(np.std(entropies)),
            "min_entropy": float(np.min(entropies)),
        }


class SlipDetector:
    """
    Detects when a model's utterances drift, fabricate, or lose coherence.
    Λ-gate: h_t = Λ_t · h_new + (1−Λ_t) · h_old
    """
    def __init__(self, window_size=20, critical_lambda=0.3, shift_threshold=5.0):
        self.window_size = window_size
        self.critical_lambda = critical_lambda
        self.shift_threshold = shift_threshold
        self.history = []
        self.slips = []

    def update(self, embedding, logdet_value):
        """
        embedding: current utterance embedding (d-dim)
        logdet_value: current logdet of utterance covariance
        """
        self.history.append({"embedding": embedding, "logdet": logdet_value})

        if len(self.history) < 2:
            self.history[-1]["lambda"] = 1.0
            return None

        # Compute Λ-gate: how much new info is admitted
        cos_sim = 1 - cosine(self.history[-2]["embedding"], embedding)
        lambda_t = max(0.0, min(1.0, cos_sim))
        self.history[-1]["lambda"] = lambda_t

        # Detect slip: gate closes AND logdet shifts
        logdet_delta = abs(logdet_value - self.history[-2]["logdet"])

        if (lambda_t < self.critical_lambda and
            logdet_delta > self.shift_threshold and
            len(self.history) >= self.window_size):
            slip = {
                "index": len(self.history) - 1,
                "lambda": lambda_t,
                "logdet_delta": logdet_delta,
                "severity": "critical" if lambda_t < 0.1 else "warning"
            }
            self.slips.append(slip)
            return slip

        # Trim history
        if len(self.history) > self.window_size * 2:
            self.history = self.history[-self.window_size:]

        return None


# ─── Full Probe Pipeline ─────────────────────────────────────

class SummaProbePipeline:
    """
    Complete measurement apparatus from the Summa.
    Runs all probes and produces the spectral fingerprint.
    """
    def __init__(self, epsilon=1e-6):
        self.logdet_probe = LogDetProbe(epsilon=epsilon)
        self.fisher_probe = FisherMetricProbe()
        self.attention_probe = AttentionEntropyProbe()
        self.slip_detector = SlipDetector()

    def run_on_layer_activations(self, layer_name, activations, attention_weights=None, log_probs=None):
        """
        Run all probes on a single layer's outputs.
        Returns the layer's spectral fingerprint.
        """
        fingerprint = {"layer": layer_name}

        # Logdet (always available)
        fingerprint["logdet"] = self.logdet_probe.compute(activations)
        fingerprint["tail_exponent"] = self.logdet_probe.tail_exponent()

        # Fisher metric
        if log_probs is not None:
            fingerprint["fisher"] = self.fisher_probe.compute(log_probs)

        # Attention entropy
        if attention_weights is not None:
            fingerprint["attention"] = self.attention_probe.compute(attention_weights)

        return fingerprint

    def run_full_probe(self, layer_activations, attention_weights=None, log_probs=None):
        """
        Run probes across ALL layers and produce the full phase-diagram measurement.
        layer_activations: dict {layer_name: (n_samples, d_features)}
        """
        results = {}

        for layer_name, activations in layer_activations.items():
            attn = attention_weights.get(layer_name) if attention_weights else None
            lp = log_probs.get(layer_name) if log_probs else None
            results[layer_name] = self.run_on_layer_activations(layer_name, activations, attn, lp)

        # Cross-layer analysis
        logdets = [r["logdet"]["logdet"] for r in results.values()]
        alphas = [r["tail_exponent"]["alpha"] for r in results.values()
                  if r["tail_exponent"]["alpha"] is not None]

        cross_layer = {
            "logdet_mean": float(np.mean(logdets)),
            "logdet_std": float(np.std(logdets)),
            "logdet_range": float(max(logdets) - min(logdets)),
            "logdet_flatness": float(np.std(logdets) / (abs(np.mean(logdets)) + 1e-10)),
            "alpha_mean": float(np.mean(alphas)) if alphas else None,
            "alpha_std": float(np.std(alphas)) if alphas else None,
            "at_fixed_point": abs(np.std(logdets)) < 0.01,  # Δ ≈ −0.0005 threshold
            "num_layers_probed": len(results),
        }

        return {
            "per_layer": results,
            "cross_layer": cross_layer,
            "phase_diagram": self._locate_on_phase_diagram(cross_layer),
        }

    def _locate_on_phase_diagram(self, cross_layer):
        """Determine where the model sits on the Summa phase diagram."""
        logdet_flatness = cross_layer["logdet_flatness"]
        alpha = cross_layer["alpha_mean"]

        if logdet_flatness < 0.001:
            regime = "FIXED_POINT (d≈0)"
            description = "Transformer with residuals — at the de Sitter fixed point. "
            description += "All layers identical. Cross-domain identities return zero. "
            description += "Δ ≈ −0.0005. logdet flat across layers."
        elif logdet_flatness < 0.01:
            regime = "NEAR_FIXED_POINT"
            description = "Close to the fixed point. Residual homogenization dominant. "
            description += "Intrinsic measurements survive; cross-domain identities weak."
        elif logdet_flatness < 0.05:
            regime = "INTERMEDIATE (d≈0.25)"
            description = "Peak observable structure. Maximum heterogeneity across layers. "
            description += "Each layer has distinct spectral profile. Sweet spot for measurement."
        else:
            regime = "FAR_FROM_FIXED_POINT"
            description = "Pure MLP-like. Strong gradients across layers. "
            description += "logdet varies significantly. Strong OOD signal (r≈+0.979)."

        return {
            "regime": regime,
            "description": description,
            "logdet_flatness": logdet_flatness,
            "alpha": alpha,
            "concentration_low": cross_layer.get("concentration_low"),
            "concentration_high": cross_layer.get("concentration_high"),
        }


# ─── Model Hook Runner ───────────────────────────────────────

class ModelProbeRunner:
    """
    Hooks into a HuggingFace transformer model and runs the full
    Summa probe pipeline on actual hidden states during inference.

    This is the PRODUCTION implementation — replaces scaffold.
    """
    def __init__(self, model, tokenizer, target_layers=None, epsilon=1e-6):
        self.model = model
        self.tokenizer = tokenizer
        self.pipeline = SummaProbePipeline(epsilon=epsilon)
        self.target_layers = target_layers or self._default_layers()
        self.activations = {layer: [] for layer in self.target_layers}
        self.attention_weights = {layer: [] for layer in self.target_layers}
        self.log_probs = {layer: [] for layer in self.target_layers}
        self.hooks = []
        self._register_hooks()

    def _default_layers(self):
        """Auto-detect layer count and sample evenly."""
        if hasattr(self.model, 'config'):
            n = getattr(self.model.config, 'num_hidden_layers',
                        getattr(self.model.config, 'n_layer', 12))
            # Sample every 4th layer, plus first and last
            indices = sorted(set([0, n//4, n//2, 3*n//4, n-1]))
            return [f"layer_{i}" for i in indices if i < n]
        return ["layer_0", "layer_6", "layer_11"]

    def _register_hooks(self):
        """Register forward hooks on target layers to capture hidden states."""

        def make_hook(layer_name):
            def hook_fn(module, input, output):
                # output can be tuple (hidden_states, ...) or tensor
                if isinstance(output, tuple):
                    hidden = output[0].detach().cpu().float().numpy()
                    # Check for attention weights in output
                    if len(output) > 1 and output[1] is not None:
                        attn = output[1].detach().cpu().float().numpy()
                        if attn.ndim >= 3:
                            self.attention_weights[layer_name].append(attn)
                else:
                    hidden = output.detach().cpu().float().numpy()

                # Store: (batch, seq, hidden) → flatten batch×seq
                if hidden.ndim == 3:
                    hidden_flat = hidden.reshape(-1, hidden.shape[-1])
                    self.activations[layer_name].append(hidden_flat)
                elif hidden.ndim == 2:
                    self.activations[layer_name].append(hidden)

            return hook_fn

        # Try to find target modules by name pattern
        for name, module in self.model.named_modules():
            for target in self.target_layers:
                # Match patterns like "model.layers.0" or "transformer.h.0"
                if re.search(rf'\b{re.escape(target.split("_")[-1])}\b', name):
                    hook = module.register_forward_hook(make_hook(target))
                    self.hooks.append(hook)
                    break

    def run_on_text(self, text, max_new_tokens=256):
        """Run inference and collect activations."""
        self._clear_buffers()
        inputs = self.tokenizer(text, return_tensors="pt")
        # Move to model device
        if hasattr(self.model, 'device'):
            inputs = {k: v.to(self.model.device) for k, v in inputs.items()}
        elif torch.cuda.is_available():
            try:
                inputs = {k: v.cuda() for k, v in inputs.items()}
            except Exception:
                pass

        with torch.no_grad():
            _ = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=True,
                temperature=0.7,
                pad_token_id=self.tokenizer.eos_token_id,
            )

        return self._compute_results()

    def _clear_buffers(self):
        for layer in self.target_layers:
            self.activations[layer] = []
            self.attention_weights[layer] = []
            self.log_probs[layer] = []

    def _compute_results(self):
        """Compute probe results from collected activations."""
        layer_activations = {}
        layer_attentions = {}
        layer_logprobs = {}

        for layer in self.target_layers:
            if not self.activations[layer]:
                continue
            # Stack all collected windows
            stacked = np.concatenate(self.activations[layer], axis=0)
            if stacked.shape[0] > 1:
                layer_activations[layer] = stacked

            if self.attention_weights[layer]:
                all_attn = [a for a in self.attention_weights[layer] if a.ndim >= 3]
                if all_attn:
                    layer_attentions[layer] = np.concatenate(all_attn, axis=0)

        if not layer_activations:
            return {"error": "No activations captured. Check layer names."}

        return self.pipeline.run_full_probe(layer_activations, layer_attentions, layer_logprobs)

    def remove_hooks(self):
        for hook in self.hooks:
            hook.remove()
        self.hooks = []


# ─── Evaluation on Trained Model ──────────────────────────────

def evaluate_summa_model(model_path, test_prompts=None, device="auto"):
    """
    Full evaluation of a trained Summa-Gap model.

    Loads the model, registers forward hooks, runs inference on test prompts,
    and produces the complete spectral fingerprint with phase diagram location.
    """
    print("=" * 64)
    print("  SUMMA-GAP AI — LOGDET PROBE EVALUATION")
    print("=" * 64)
    print(f"  Model path: {model_path}")
    print(f"  Device: {device}")
    print()

    # ── 1. Calibration-only mode ──
    if not model_path or model_path == "calibration_only" or not os.path.exists(model_path):
        return run_calibration_demo()

    # ── 2. Load model (lazy imports to avoid requiring torch unless needed) ──
    try:
        global torch
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as e:
        print(f"  Cannot load model: {e}")
        print("  Install: pip install torch transformers")
        return run_calibration_demo()

    print("  Loading model...")
    try:
        tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch.float16,
            device_map=device,
            trust_remote_code=True,
        )
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        print(f"  Model loaded: {model.config.model_type}, {sum(p.numel() for p in model.parameters())/1e9:.1f}B params")
    except Exception as e:
        print(f"  Model loading failed: {e}")
        return run_calibration_demo()

    # ── 3. Default test prompts if none provided ──
    if test_prompts is None:
        test_prompts = [
            "Explain the relationship between measurement and the fixed point in physical systems.",
            "The gap does not close because self-referential systems cannot fully verify themselves.",
            "What is the spectral dimension of the SAT solution manifold?",
            "Describe the role of Berry curvature in computational complexity.",
            "The five zeros are calibration measurements, not failures.",
            "How does the Lawvere gap manifest in neural network training?",
            "Explain Φ = ∇_self · d in the context of the Summa framework.",
        ]

    # ── 4. Run probes ──
    print(f"\n  Running probes on {len(test_prompts)} prompts...")
    runner = ModelProbeRunner(model, tokenizer)
    all_results = []

    for i, prompt in enumerate(test_prompts):
        print(f"    [{i+1}/{len(test_prompts)}] {prompt[:60]}...", end=" ", flush=True)
        result = runner.run_on_text(prompt, max_new_tokens=128)
        if "error" not in result:
            result["prompt"] = prompt
            all_results.append(result)
            ld_mean = result["cross_layer"]["logdet_mean"]
            flatness = result["cross_layer"]["logdet_flatness"]
            regime = result["phase_diagram"]["regime"]
            print(f"logdet={ld_mean:.1f} flatness={flatness:.4f} [{regime}]")
        else:
            print(f"SKIPPED ({result['error']})")

    runner.remove_hooks()

    # ── 5. Aggregate and report ──
    print(f"\n{'='*64}")
    print("  AGGREGATE RESULTS")
    print(f"{'='*64}")

    if not all_results:
        print("  No successful probes. Falling back to calibration demo.")
        return run_calibration_demo()

    # Aggregate cross-layer stats
    all_flatness = [r["cross_layer"]["logdet_flatness"] for r in all_results]
    all_logdets = [r["cross_layer"]["logdet_mean"] for r in all_results]
    all_alphas = [r["cross_layer"]["alpha_mean"] for r in all_results
                  if r["cross_layer"]["alpha_mean"] is not None]
    regimes = [r["phase_diagram"]["regime"] for r in all_results]

    print(f"  Prompts evaluated: {len(all_results)}")
    print(f"  Mean logdet:       {np.mean(all_logdets):.1f} ± {np.std(all_logdets):.1f}")
    print(f"  Mean flatness:     {np.mean(all_flatness):.6f}")
    print(f"  Mean alpha:        {np.mean(all_alphas):.2f}" if all_alphas else "  Mean alpha:        N/A")
    print(f"  Dominant regime:   {max(set(regimes), key=regimes.count)}")
    print()
    print(f"  Phase diagram position:")
    if np.mean(all_flatness) < 0.001:
        print(f"    → FIXED POINT (d≈0): Transformer with residuals. All layers identical.")
        print(f"      Cross-domain identities return zero. Δ ≈ −0.0005.")
    elif np.mean(all_flatness) < 0.01:
        print(f"    → NEAR FIXED POINT: Residual homogenization dominant.")
    elif np.mean(all_flatness) < 0.05:
        print(f"    → INTERMEDIATE (d≈0.25): Peak observable structure.")
    else:
        print(f"    → FAR FROM FIXED POINT: MLP-like. Strong gradients. Good OOD signal.")
    print()

    # Save detailed spectrum for the best prompt
    best = max(all_results, key=lambda r: abs(r["cross_layer"]["logdet_range"]))
    spectrum_path = os.path.join(os.path.dirname(model_path) or ".", "probe_spectrum.json")
    with open(spectrum_path, 'w') as f:
        json.dump(best, f, indent=2, default=float)
    print(f"  Full spectrum saved to: {spectrum_path}")
    print()
    print("  The gap does not close. That is the engine.")
    return all_results


def run_calibration_demo():
    """Fallback: run calibration demonstration with synthetic spectra."""
    print("  Running calibration demonstration (no model needed)...")
    print(f"  Calibration constant: log det('we') = −49145.67")
    print(f"  Expected tail exponent: α ≈ 7.5")
    print(f"  Expected transformer flatness: σ(logdet) < 0.01")
    print()

    pipeline = SummaProbePipeline()
    datasets = {
        "pure_mlp (d=0)":       {"C": 0.81, "alpha": 7.68},
        "peak (d=0.25)":        {"C": 0.76, "alpha": 7.60},
        "threshold (d=0.50)":   {"C": 0.71, "alpha": 7.48},
        "full_residual (d=1.0)": {"C": 0.56, "alpha": 7.28},
        "transformer (predicted)": {"C": 0.03, "alpha": 7.50},
    }

    print(f"  {'Architecture':<25s} {'Concentration':>13s} {'Tail α':>8s} {'logdet':>10s}")
    print(f"  {'-'*58}")
    for name, props in datasets.items():
        d_dim = 256
        n_eff = max(1, int(d_dim * props["C"]))
        bulk = np.logspace(1, -2, n_eff)
        n_tail = d_dim - n_eff
        k = np.arange(1, n_tail + 1, dtype=float)
        tail = 10**(-2 - 28 * (k / n_tail)**props["alpha"])
        eigvals = np.sort(np.concatenate([bulk, tail]))[::-1]
        logdet = float(np.sum(np.log(eigvals + 1e-40)))
        print(f"  {name:<25s} {props['C']:>13.2f} {props['alpha']:>8.2f} {logdet:>10.1f}")

    print()
    print("  Phase diagram:")
    print("  ┌─────────────────────────────────────────────┐")
    print("  │ w > −1:  NP ⊆ P    (semiclassical)         │")
    print("  │ w = −1:  P ≠ NP    (fixed point)   ◄────── │")
    print("  │ w < −1:  ? → ∅     (phantom)               │")
    print("  └─────────────────────────────────────────────┘")
    print()
    print("  The gap does not close. That is the engine.")
    return None
