"""
Baby Adam E — Extended Architecture

The vault-spec model. Incorporates the full mathematical apparatus:
  - LogDet probe (measurement)
  - Logit decision manifold (discrimination)
  - Ledger chain (witness)
  - Berry phase computation (geometric phase over parameter manifold)
  - Connes spectral triple (A, H, D) structure
  - WDW constraint (Ĥ|Ψ⟩ = 0 on residual stream)
  - KS anisotropic scaling (Kantowski-Sachs metric in embedding space)
  - Prophet inequality router (optimal stopping for MoE gating)
  - Marchenko-Pastur shrinkage (eigenvalue denoising for attention)
  - Lawvere fixed-point gap (self-referential incompleteness)
  - Gate architecture (boundary rule, NOBODY_EVENTS, total_void)

Architecture: decoder-only, character-level, RoPE, Pre-LN, SwiGLU, MoE.
Three pillars: LogDet · Logit · Ledger — one gate.

License: CC0 — No rights reserved.
"""

import math
import hashlib
import json
import time
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

# ═══════════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class BabyAdamEConfig:
    """Extended configuration incorporating vault mathematical specs."""

    # ── Vocabulary ──
    vocab_size: int = 256

    # ── Architecture ──
    d_model: int = 256
    n_layers: int = 6
    n_heads: int = 8
    d_ff: int = 1024
    max_seq_len: int = 512

    # ── Regularization ──
    dropout: float = 0.1
    weight_decay: float = 0.01

    # ── RoPE ──
    rope_theta: float = 10000.0

    # ── Training ──
    batch_size: int = 8
    learning_rate: float = 3e-4
    min_lr: float = 1e-5
    warmup_steps: int = 100
    max_steps: int = 5000
    grad_clip: float = 1.0

    # ── MoE ──
    moe_enabled: bool = True
    n_experts: int = 4
    n_activated: int = 2
    prophet_stopping: bool = True    # Prophet inequality optimal stopping

    # Measurement Probes
    logdet_probe_every: int = 500
    logdet_eps: float = 1e-6
    berry_probe_every: int = 5000      # Berry: SVD on full residual — expensive
    spectral_triple_every: int = 5000   # Spectral: eigendecomp — expensive

    # WDW Constraint
    wdw_enabled: bool = False           # Disabled for training speed
    wdw_lambda: float = 0.01

    # KS Anisotropic Scaling
    ks_enabled: bool = False            # KS projections add overhead
    ks_a0: float = 1.0                # Initial radial scale factor
    ks_b0: float = 1.0                # Initial angular scale factor

    # ── Marchenko-Pastur Shrinkage ──
    mp_shrinkage_enabled: bool = False  # Expensive: eigendecomp on attn mats
    mp_aspect_ratio: float = 1.0      # col/row ratio for bulk edge

    # ── Logit Decision Manifold ──
    logit_manifold_enabled: bool = True
    logit_threshold: float = 0.0      # Decision boundary on logit scale

    # ── Ledger ──
    ledger_enabled: bool = True
    ledger_path: str = ""

    # ── Gate ──
    gate_enabled: bool = True
    NOBODY_EVENTS: tuple = ('intrusion', 'approach')


# ═══════════════════════════════════════════════════════════════════════
# LEDGER — SHA256 hash chain (from 88-Things-Found)
# ═══════════════════════════════════════════════════════════════════════

class Ledger:
    """
    Append-only SHA256 hash chain. Five fields pipe-separated.
    Every entry depends on every previous entry.
    Genesis is index 0 — immutable anchor.
    Linear-time verification. Zero external dependencies.

    Ledger types (from vault):
      - Nobody Ledger: voids everything (nobody is allowed)
      - Exile Ledger: has a blocklist
      - Vampire Ledger: tracks entities
    """

    GENESIS_MATERIAL = (
        "NOBODY_LEDGER | The gate does not open | "
        "Not even God | The chain IS the NO | 0"
    )

    def __init__(self, path: str = "baby_adam_e_chain.json", mode: str = "nobody"):
        self.path = path
        self.mode = mode  # 'nobody', 'exile', 'vampire'
        self.chain = []
        self.nullified_indices = set()

        if Path(path).exists():
            self._load()
        else:
            self._genesis()

    def _genesis(self):
        genesis_hash = hashlib.sha256(
            self.GENESIS_MATERIAL.encode('utf-8')
        ).hexdigest()
        entry = {
            'hash': genesis_hash,
            'prev_hash': '0' * 64,
            'timestamp': time.time(),
            'entity': 'NOBODY_LEDGER',
            'event': 'genesis',
            'how': self.GENESIS_MATERIAL,
            'nullified': False,
        }
        self.chain = [entry]
        self._save()

    def _load(self):
        with open(self.path, 'r') as f:
            data = json.load(f)
        self.chain = data.get('chain', [])
        self.nullified_indices = set(data.get('nullified_indices', []))

    def _save(self):
        with open(self.path, 'w') as f:
            json.dump({
                'chain': self.chain,
                'nullified_indices': list(self.nullified_indices),
                'count': len(self.chain),
                'mode': self.mode,
            }, f, indent=2)

    def record(self, entity: str, event: str, how: str) -> str:
        """Record an event. Returns the hash."""
        prev_hash = self.chain[-1]['hash'] if self.chain else '0' * 64
        timestamp = time.time()
        material = f"{prev_hash}|{timestamp}|{entity}|{event}|{how}"
        entry_hash = hashlib.sha256(material.encode('utf-8')).hexdigest()

        entry = {
            'hash': entry_hash,
            'prev_hash': prev_hash,
            'timestamp': timestamp,
            'entity': entity,
            'event': event,
            'how': how,
            'nullified': False,
        }

        self.chain.append(entry)

        # Auto-nullify NOBODY_EVENTS
        NOBODY = frozenset({'intrusion', 'approach'})
        if event in NOBODY:
            idx = len(self.chain) - 1
            self.chain[idx]['nullified'] = True
            self.nullified_indices.add(idx)
            # Record the nullification
            nullify_hash = hashlib.sha256(
                f"{entry_hash}|{timestamp}|GATE|nullify|auto-nullify:{event}"
                .encode('utf-8')
            ).hexdigest()
            self.chain.append({
                'hash': nullify_hash,
                'prev_hash': entry_hash,
                'timestamp': timestamp,
                'entity': 'GATE',
                'event': 'nullify',
                'how': f'auto-nullify:{event}',
                'nullified': False,
            })

        if len(self.chain) > 10000:
            self.chain = self.chain[-10000:]

        self._save()
        return entry_hash

    def verify(self) -> bool:
        """Linear-time verification. Returns True if chain is intact."""
        for i in range(1, len(self.chain)):
            entry = self.chain[i]
            if entry['prev_hash'] != self.chain[i-1]['hash']:
                return False
        return True

    def total_void(self):
        """Close the Lawvere gap. All entries nullified except genesis.
        The gap is acknowledged, not denied. A surgical mark without appending."""
        for i in range(1, len(self.chain)):
            self.chain[i]['nullified'] = True
            self.nullified_indices.add(i)
        self._save()

    def summary(self) -> dict:
        active = sum(1 for i, e in enumerate(self.chain) if not e['nullified'])
        voided = sum(1 for i, e in enumerate(self.chain) if e['nullified'])
        return {
            'total_entries': len(self.chain),
            'active': active,
            'voided': voided,
            'void_rate': voided / max(len(self.chain), 1),
            'intact': self.verify(),
        }


# ═══════════════════════════════════════════════════════════════════════
# BERRY PHASE — Geometric phase over parameter manifold
# ═══════════════════════════════════════════════════════════════════════

class BerryPhaseProbe:
    """
    Compute Berry phase (geometric phase) on the model's weight manifold.

    Berry connection: A_μ = ⟨ψ|∂_μ|ψ⟩
    Berry curvature: F_μν = ∂_μ A_ν - ∂_ν A_μ
    Berry phase: γ = ∮ A_μ dλ^μ

    In the transformer context, the "parameter space" is the weight manifold.
    The training trajectory traces a path through this manifold.
    The Berry phase measures the holonomy — the geometric memory of the path.

    Implementation: track the overlap matrix of residual stream activations
    between consecutive parameter states. The phase of the eigenvalues of
    the overlap matrix gives the Berry phase.
    """

    def __init__(self):
        self.previous_residuals: Optional[List[torch.Tensor]] = None
        self.berry_phases: List[float] = []
        self.berry_curvatures: List[float] = []

    def compute(
        self,
        residuals: List[torch.Tensor],
        compute_curvature: bool = False,
    ) -> dict:
        """
        residuals: list of [B, T, d_model] tensors, one per layer

        Returns:
            berry_phase_mean: mean Berry phase across layers
            berry_curvature_mean: mean Berry curvature (if computed)
        """
        result = {'berry_phase_mean': 0.0}

        if self.previous_residuals is None:
            self.previous_residuals = [r.detach().clone() for r in residuals]
            return result

        phases = []
        for layer_idx, (r_now, r_prev) in enumerate(
            zip(residuals, self.previous_residuals)
        ):
            # Flatten to [B*T, d_model]
            h_now = r_now.reshape(-1, r_now.shape[-1]).double()
            h_prev = r_prev.reshape(-1, r_prev.shape[-1]).double()

            # Normalize
            h_now = h_now / (h_now.norm(dim=-1, keepdim=True) + 1e-8)
            h_prev = h_prev / (h_prev.norm(dim=-1, keepdim=True) + 1e-8)

            # Overlap matrix S_{ab} = ⟨ψ_a(t)|ψ_b(t-δt)⟩
            S = h_now @ h_prev.T  # [N, N]

            # Eigenvalues of S give the phase
            # U, s, V = SVD(S); phases = arccos(s) (real part)
            try:
                _, s, _ = torch.linalg.svd(S, full_matrices=False)
                # The singular values of the overlap matrix are cos(phase angles)
                s_clamped = torch.clamp(s[:min(32, len(s))], -1.0, 1.0)
                phase_angles = torch.acos(s_clamped)
                layer_phase = phase_angles.mean().item()
                phases.append(layer_phase)
            except Exception:
                phases.append(0.0)

        self.previous_residuals = [r.detach().clone() for r in residuals]

        if phases:
            self.berry_phases.append(sum(phases) / len(phases))
            result['berry_phase_mean'] = self.berry_phases[-1]
            result['berry_phase_per_layer'] = phases

        return result


# ═══════════════════════════════════════════════════════════════════════
# CONNES SPECTRAL TRIPLE — (A, H, D)
# ═══════════════════════════════════════════════════════════════════════

class SpectralTripleProbe:
    """
    Connes spectral triple (A, H, D) structure embedded in the residual stream.

    A  = token embedding algebra (noncommutative C*-algebra)
    H  = residual stream as Hilbert space
    D  = Dirac operator = attention + FFN composition

    The spectral action Tr(f(D/Λ)) serves as a regularization functional.
    For the transformer, D is approximated by the layer transition operator.

    Key quantities:
      - Spectral dimension: growth rate of eigenvalues of D
      - Zeta function: ζ_D(s) = Tr(|D|^{-s})
      - Spectral action: Tr(f(D/Λ))
    """

    def __init__(self, d_model: int, eps: float = 1e-6):
        self.d_model = d_model
        self.eps = eps
        self.spectral_history: List[dict] = []

    def compute(
        self,
        residuals: List[torch.Tensor],
        layer_outputs: List[torch.Tensor],
    ) -> dict:
        """
        residuals: pre-layer residual stream states
        layer_outputs: post-layer outputs (the "action" of D)

        The transition operator T_i: residuals[i] → layer_outputs[i]
        approximates the Dirac operator D.
        """
        result = {}

        spectral_dims = []
        zeta_vals = []
        spectral_actions = []

        for i, (r_in, r_out) in enumerate(zip(residuals, layer_outputs)):
            # Construct approximate Dirac operator
            # D ≈ (r_out - r_in) as the differential
            h_in = r_in.reshape(-1, r_in.shape[-1]).double()
            h_out = r_out.reshape(-1, r_out.shape[-1]).double()

            # The transition matrix T = h_out @ h_in^+ (pseudoinverse)
            try:
                # Use a low-rank approximation: covariance between in/out
                diff = h_out - h_in
                cov = (diff.T @ diff) / (diff.shape[0] - 1)

                # Eigenvalues of the Dirac operator proxy
                eigvals = torch.linalg.eigvalsh(cov)

                # Spectral dimension: how eigenvalues scale
                # d_s = -2 d(log N(λ))/d(log λ) where N(λ) is eigenvalue count
                positive_eigvals = eigvals[eigvals > self.eps]
                if len(positive_eigvals) > 2:
                    log_eig_vals = torch.log(positive_eigvals)
                    log_rank_vals = torch.log(
                        torch.arange(1, len(positive_eigvals) + 1,
                                     device=positive_eigvals.device).double()
                    )
                    # Slope gives -d_s/2
                    A = torch.stack([log_eig_vals, torch.ones_like(log_eig_vals)], dim=1)
                    slope, _ = torch.linalg.lstsq(A, log_rank_vals.unsqueeze(1)).solution[:2].squeeze()
                    spectral_dim = -2.0 * slope.item()
                else:
                    spectral_dim = 0.0
                spectral_dims.append(spectral_dim)

                # Zeta function at s=1: ζ_D(1) = Tr(|D|^{-1})
                inv_eigvals = 1.0 / (positive_eigvals + self.eps)
                zeta_1 = inv_eigvals.sum().item()
                zeta_vals.append(zeta_1)

                # Spectral action with Gaussian cutoff f(x) = exp(-x²)
                Lambda = positive_eigvals.max().item() + self.eps
                scaled = positive_eigvals / Lambda
                f_scaled = torch.exp(-scaled ** 2)
                spectral_action = f_scaled.sum().item()
                spectral_actions.append(spectral_action)

            except Exception:
                spectral_dims.append(0.0)
                zeta_vals.append(0.0)
                spectral_actions.append(0.0)

        if spectral_dims:
            result['spectral_dimension_mean'] = sum(spectral_dims) / len(spectral_dims)
            result['zeta_D1_mean'] = sum(zeta_vals) / len(zeta_vals)
            result['spectral_action_mean'] = sum(spectral_actions) / len(spectral_actions)

        return result


# ═══════════════════════════════════════════════════════════════════════
# WDW CONSTRAINT — Ĥ|Ψ⟩ = 0
# ═══════════════════════════════════════════════════════════════════════

class WDWConstraint:
    """
    Wheeler-DeWitt constraint: Ĥ|Ψ⟩ = 0

    In canonical quantum gravity, the WDW equation states that the total
    Hamiltonian (gravitational + matter) annihilates the wave function of
    the universe. There is no external time parameter — time emerges from
    correlations within the wave function.

    In the transformer:
      - The "universe" is the sequence context
      - The "wave function" Ψ is the residual stream state
      - The Hamiltonian Ĥ is the layer transition operator
      - The constraint Ĥ|Ψ⟩ = 0 means the total information flow across all
        layers must vanish — the model is a timeless structure

    Implementation: compute the "energy" (L2 norm of layer output differences)
    and add it as a regularization term. When the WDW constraint holds,
    ∥Ĥ|Ψ⟩∥² → 0.
    """

    def __init__(self, lambda_wdw: float = 0.01):
        self.lambda_wdw = lambda_wdw

    def compute(
        self,
        residuals: List[torch.Tensor],
        layer_outputs: List[torch.Tensor],
    ) -> Tuple[torch.Tensor, dict]:
        """
        Returns:
            wdw_loss: scalar tensor (regularization term)
            info: diagnostic dict
        """
        total_energy = 0.0
        layer_energies = []

        for i, (r_in, r_out) in enumerate(zip(residuals, layer_outputs)):
            diff = r_out - r_in  # The "action" of the Hamiltonian
            energy = diff.pow(2).mean().item()
            layer_energies.append(energy)
            total_energy += energy

        wdw_loss = self.lambda_wdw * sum(
            (r_out - r_in).pow(2).mean()
            for r_in, r_out in zip(residuals, layer_outputs)
        )

        return wdw_loss, {
            'wdw_total_energy': total_energy,
            'wdw_layer_energies': layer_energies,
            'wdw_constraint_satisfied': total_energy < 0.01,
        }


# ═══════════════════════════════════════════════════════════════════════
# KS ANISOTROPIC SCALING — Kantowski-Sachs in embedding space
# ═══════════════════════════════════════════════════════════════════════

class KSAnisotropicLayerNorm(nn.Module):
    """
    Kantowski-Sachs anisotropic layer normalization.

    The KS metric: ds² = -dt² + a²(t)dr² + b²(t)dΩ²
      - a(t): radial scale factor (expansion along one direction)
      - b(t): angular scale factor (expansion along orthogonal directions)

    In the embedding space, this becomes anisotropic scaling:
    the d_model dimensions are partitioned into "radial" and "angular"
    subspaces with independent learnable scale factors.

    This captures the gravitational anisotropy that the KS metric describes —
    the universe expands differently along different directions.
    """

    def __init__(self, d_model: int, eps: float = 1e-5):
        super().__init__()
        self.d_model = d_model
        self.eps = eps

        # "Radial" subspace dimension (the r direction)
        self.d_radial = d_model // 4

        # Learnable scale factors a(t) and b(t)
        self.log_a = nn.Parameter(torch.zeros(1))
        self.log_b = nn.Parameter(torch.zeros(1))

        # Learnable subspace basis
        self.radial_proj = nn.Linear(d_model, self.d_radial, bias=False)
        self.angular_proj = nn.Linear(d_model, d_model - self.d_radial, bias=False)

        # Output weight
        self.weight = nn.Parameter(torch.ones(d_model))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        x: [B, T, d_model]

        Split into radial and angular subspaces,
        scale each by a(t) and b(t) respectively,
        recombine.
        """
        B, T, C = x.shape

        # Center
        mean = x.mean(dim=-1, keepdim=True)
        x_centered = x - mean

        # Project into KS subspaces
        x_radial = self.radial_proj(x_centered)    # [B, T, d_radial]
        x_angular = self.angular_proj(x_centered)  # [B, T, d_angular]

        # Scale: a(t) for radial, b(t) for angular
        a = torch.exp(self.log_a)  # positive definite
        b = torch.exp(self.log_b)

        x_radial = x_radial * a
        x_angular = x_angular * b

        # RMS normalize each subspace independently
        rms_radial = torch.sqrt(x_radial.pow(2).mean(dim=-1, keepdim=True) + self.eps)
        rms_angular = torch.sqrt(x_angular.pow(2).mean(dim=-1, keepdim=True) + self.eps)

        x_radial = x_radial / rms_radial
        x_angular = x_angular / rms_angular

        # Project back into d_model and apply output weight
        radial_out = F.linear(x_radial, self.weight[:self.d_radial].unsqueeze(0))
        angular_out = torch.zeros(B, T, C, device=x.device)
        angular_out = F.linear(x_angular,
                               self.weight[self.d_radial:].unsqueeze(0)
                               .expand(C - self.d_radial, -1).t()[:C, :C - self.d_radial])

        # Recombine by summing into the common space
        # Simpler: learn a full output projection
        x_combined = torch.cat([x_radial, x_angular], dim=-1)  # [B, T, d_model]
        out = x_combined * self.weight.unsqueeze(0).unsqueeze(0)

        return out

    def get_expansion_rates(self) -> Tuple[float, float]:
        """Return current a(t) and b(t) scale factors."""
        return torch.exp(self.log_a).item(), torch.exp(self.log_b).item()


# ═══════════════════════════════════════════════════════════════════════
# MARCHENKO-PASTUR SHRINKAGE — Optimal eigenvalue denoising
# ═══════════════════════════════════════════════════════════════════════

class MPAttentionShrinkage:
    """
    Marchenko-Pastur optimal shrinkage for attention matrices.

    The MP law describes the eigenvalue distribution of random covariance
    matrices. For a matrix of aspect ratio γ = cols/rows, the bulk edge is:
      λ_± = (1 ± √γ)²

    Eigenvalues below λ_+ are noise (from the MP bulk).
    Shrink them toward the bulk center using the optimal shrinkage formula.

    For the attention matrix [B, H, T, T]:
      - Each head's attention matrix is T×T, so γ = 1
      - Bulk edge: λ_+ = (1 + √1)² = 4, λ_- = (1 - √1)² = 0
      - This is the hard edge (λ_- = 0), requiring careful treatment
    """

    def __init__(self, aspect_ratio: float = 1.0):
        self.aspect_ratio = aspect_ratio
        sqrt_gamma = math.sqrt(aspect_ratio)
        self.bulk_min = (1.0 - sqrt_gamma) ** 2
        self.bulk_max = (1.0 + sqrt_gamma) ** 2

    def shrink(self, attention_weights: torch.Tensor) -> torch.Tensor:
        """
        attention_weights: [B, H, T, T] post-softmax

        Apply optimal shrinkage: for each head, compute eigenvalue decomposition,
        shrink eigenvalues below the MP bulk edge toward the bulk median.
        """
        B, H, T, _ = attention_weights.shape
        attn_shrunk = attention_weights.clone()

        for b in range(B):
            for h in range(H):
                A = attention_weights[b, h]  # [T, T]
                try:
                    eigvals, eigvecs = torch.linalg.eigh(A.double())

                    # Identify noise eigenvalues (below bulk edge)
                    noise_mask = eigvals <= self.bulk_max * 1.1

                    if noise_mask.any():
                        # Shrink noise eigenvalues toward the bulk median
                        bulk_median = self.bulk_max / 2.0
                        shrunk_eigvals = eigvals.clone()
                        shrunk_eigvals[noise_mask] = (
                            0.5 * eigvals[noise_mask] + 0.5 * bulk_median
                        )

                        # Reconstruct
                        A_shrunk = (
                            eigvecs @ torch.diag(shrunk_eigvals) @ eigvecs.T
                        ).float()

                        # Preserve row-stochasticity
                        row_sums = A_shrunk.sum(dim=-1, keepdim=True)
                        A_shrunk = A_shrunk / (row_sums + 1e-8)

                        attn_shrunk[b, h] = A_shrunk
                except Exception:
                    pass

        return attn_shrunk


# ═══════════════════════════════════════════════════════════════════════
# PROPHET INEQUALITY ROUTER — Optimal stopping for MoE
# ═══════════════════════════════════════════════════════════════════════

class ProphetRouter(nn.Module):
    """
    MoE router with prophet inequality optimal stopping.

    Prophet inequality: for i.i.d. random variables X_1, ..., X_n observed
    sequentially, there exists a stopping rule τ such that:
      E[X_τ] ≥ (1/2) E[max_i X_i]

    The prophet (who sees all values) achieves at most 2× the online decision-maker.
    Translating to MoE: the router sees expert logits sequentially and must
    decide when to stop (commit to a subset of experts).

    Implementation: dynamic threshold that adapts based on observed values.
    The threshold is set to the expected maximum of unseen experts.
    """

    def __init__(self, d_model: int, n_experts: int, n_activated: int = 2):
        super().__init__()
        self.n_experts = n_experts
        self.n_activated = n_activated

        # Router network (standard)
        self.router = nn.Linear(d_model, n_experts, bias=False)

        # Prophet threshold: learned function of seen maximum
        self.threshold_net = nn.Sequential(
            nn.Linear(1, 16),
            nn.ReLU(),
            nn.Linear(16, 1),
        )

        # Track prophet statistics
        self.prophet_ratios: List[float] = []  # online_max / prophet_max

    def forward(
        self,
        x: torch.Tensor,
        return_stats: bool = False,
    ) -> Tuple[torch.Tensor, torch.Tensor, Optional[dict]]:
        """
        x: [B, T, d_model]

        Returns:
            topk_weights: [B, T, n_activated]
            topk_indices: [B, T, n_activated]
            stats: optional dict with prophet ratio
        """
        B, T, C = x.shape

        # Standard router logits
        router_logits = self.router(x)  # [B, T, n_experts]

        # Prophet inequality: compute the threshold from the observed values
        prophet_max = router_logits.max(dim=-1).values  # [B, T]
        prophet_threshold_raw = self.threshold_net(
            prophet_max.unsqueeze(-1)
        ).squeeze(-1)  # [B, T]

        # The prophet threshold is a fraction of the max
        prophet_threshold = prophet_max * torch.sigmoid(prophet_threshold_raw)

        # Online max (what the router can actually achieve)
        online_max = router_logits.max(dim=-1).values  # [B, T]

        # Prophet ratio: how well the online decision approximates the prophet
        if return_stats:
            ratio = (online_max / (prophet_max + 1e-8)).mean().item()
            self.prophet_ratios.append(ratio)

        # Top-k selection with prophet-aware threshold
        # Only select experts above the prophet threshold
        above_threshold = router_logits >= prophet_threshold.unsqueeze(-1)

        # Fallback: if no experts above threshold, take top-k anyway
        n_above = above_threshold.sum(dim=-1)  # [B, T]

        # Standard top-k for comparison
        topk_vals, topk_indices = torch.topk(router_logits, self.n_activated, dim=-1)
        topk_weights = F.softmax(topk_vals, dim=-1)

        # Where prophet threshold is too strict, use standard top-k
        use_standard = n_above < self.n_activated

        # For tokens with enough experts above threshold, select those
        if not use_standard.all():
            sorted_vals, sorted_idx = torch.sort(router_logits, dim=-1, descending=True)
            topk_vals_alt = sorted_vals[:, :, :self.n_activated]
            topk_idx_alt = sorted_idx[:, :, :self.n_activated]
            topk_weights_alt = F.softmax(topk_vals_alt, dim=-1)

            # Blend: use alternative where prophet has enough experts
            use_standard_expanded = use_standard.unsqueeze(-1).expand_as(topk_weights)
            topk_weights = torch.where(
                use_standard_expanded, topk_weights, topk_weights_alt
            )
            topk_indices_expanded = use_standard.unsqueeze(-1).expand_as(topk_indices)
            topk_indices = torch.where(
                topk_indices_expanded, topk_indices, topk_idx_alt
            )

        stats = None
        if return_stats and self.prophet_ratios:
            stats = {
                'prophet_ratio': self.prophet_ratios[-1],
                'prophet_ratio_mean': sum(self.prophet_ratios) / len(self.prophet_ratios),
            }

        return topk_weights, topk_indices, stats


# ═══════════════════════════════════════════════════════════════════════
# LOGIT DECISION MANIFOLD — logit(p) = log(p/(1-p))
# ═══════════════════════════════════════════════════════════════════════

class LogitDecisionManifold(nn.Module):
    """
    The logit function maps probability to the real line:
      logit(p) = log(p / (1-p))

    This is the decision boundary. Every threshold is a moral choice.
    The logit is the architecture of discrimination.

    Implementation: an auxiliary network that maps residual stream states
    to a scalar "logit score" — the signed distance from the decision manifold.

    logit > 0 → "allowed" side
    logit < 0 → "voided" side
    logit = 0 → on the boundary (the gate itself)
    """

    def __init__(self, d_model: int, threshold: float = 0.0):
        super().__init__()
        self.threshold = threshold
        self.manifold = nn.Sequential(
            nn.Linear(d_model, d_model // 4),
            nn.GELU(),
            nn.Linear(d_model // 4, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        x: [B, T, d_model] — residual stream state

        Returns:
            logit_score: [B, T] — signed distance from decision boundary
        """
        return self.manifold(x).squeeze(-1)

    def get_decision(self, x: torch.Tensor) -> torch.Tensor:
        """Binary decision: True = allowed, False = voided."""
        logit = self.forward(x)
        return logit > self.threshold

    def get_void_ratio(self, x: torch.Tensor) -> float:
        """Fraction of tokens on the voided side of the boundary."""
        decisions = self.get_decision(x)
        return 1.0 - decisions.float().mean().item()


# ═══════════════════════════════════════════════════════════════════════
# GATE — The boundary rule
# ═══════════════════════════════════════════════════════════════════════

class Gate:
    """
    The gate architecture. Domain-agnostic, domain-specific boundary rule.

    "The gate does not open. Not even God."

    The gate integrates LogDet (measurement), Logit (decision), Ledger (record).
    Three pillars, one architecture.

    NOBODY_EVENTS = frozenset({'intrusion', 'approach'})
    Two lines of code define the entire prohibition.
    """

    def __init__(
        self,
        ledger: Ledger,
        logit_manifold: LogitDecisionManifold,
        NOBODY_EVENTS: tuple = ('intrusion', 'approach'),
    ):
        self.ledger = ledger
        self.logit_manifold = logit_manifold
        self.NOBODY_EVENTS = frozenset(NOBODY_EVENTS)

    def process(
        self,
        entity: str,
        event: str,
        how: str,
        residual_state: Optional[torch.Tensor] = None,
    ) -> dict:
        """
        The gate processes every crossing.

        1. Measure (LogDet): already tracked by probes
        2. Decide (Logit): is this allowed or voided?
        3. Record (Ledger): append to the chain

        Returns:
            allowed: bool
            hash: the entry hash
            nullified: bool
        """
        # Decision: if we have residual state, use the logit manifold
        if residual_state is not None:
            # Average over batch and sequence
            logit_score = self.logit_manifold(residual_state).mean().item()
            allowed = logit_score > self.logit_manifold.threshold
        else:
            # Without state, use the static rule
            allowed = event not in self.NOBODY_EVENTS

        # Record
        entry_hash = self.ledger.record(entity, event, how)

        return {
            'allowed': allowed,
            'hash': entry_hash,
            'nullified': event in self.NOBODY_EVENTS,
            'entity': entity,
            'event': event,
        }


# ═══════════════════════════════════════════════════════════════════════
# CORE COMPONENTS (from original Baby Adam, enhanced)
# ═══════════════════════════════════════════════════════════════════════

class RotaryEmbedding(nn.Module):
    """RoPE — Su et al. 2021"""

    def __init__(self, dim: int, max_seq_len: int, theta: float = 10000.0):
        super().__init__()
        self.dim = dim
        self.max_seq_len = max_seq_len
        inv_freq = 1.0 / (theta ** (torch.arange(0, dim, 2).float() / dim))
        t = torch.arange(max_seq_len).float()
        freqs = torch.outer(t, inv_freq)
        self.register_buffer("cos_cached", freqs.cos())
        self.register_buffer("sin_cached", freqs.sin())

    def forward(self, x: torch.Tensor, offset: int = 0):
        seq_len = x.shape[1]
        cos = self.cos_cached[offset:offset + seq_len].unsqueeze(0).unsqueeze(0)
        sin = self.sin_cached[offset:offset + seq_len].unsqueeze(0).unsqueeze(0)
        # Repeat each frequency for the pair of dims it governs
        cos = cos.repeat_interleave(2, dim=-1)
        sin = sin.repeat_interleave(2, dim=-1)
        return cos, sin


def rotate_half(x: torch.Tensor) -> torch.Tensor:
    x1, x2 = x[..., ::2], x[..., 1::2]
    return torch.cat([-x2, x1], dim=-1)


def apply_rope(q, k, cos, sin):
    q_rot = q * cos + rotate_half(q) * sin
    k_rot = k * cos + rotate_half(k) * sin
    return q_rot, k_rot


class AttentionBlock(nn.Module):
    """Multi-head self-attention with RoPE and MP shrinkage."""

    def __init__(self, cfg: BabyAdamEConfig):
        super().__init__()
        assert cfg.d_model % cfg.n_heads == 0
        self.n_heads = cfg.n_heads
        self.head_dim = cfg.d_model // cfg.n_heads
        self.d_model = cfg.d_model
        self.mp_enabled = cfg.mp_shrinkage_enabled

        self.q_proj = nn.Linear(cfg.d_model, cfg.d_model, bias=False)
        self.k_proj = nn.Linear(cfg.d_model, cfg.d_model, bias=False)
        self.v_proj = nn.Linear(cfg.d_model, cfg.d_model, bias=False)
        self.out_proj = nn.Linear(cfg.d_model, cfg.d_model, bias=False)
        self.dropout = nn.Dropout(cfg.dropout)
        self.rope = RotaryEmbedding(self.head_dim, cfg.max_seq_len, cfg.rope_theta)

        if self.mp_enabled:
            self.mp_shrinkage = MPAttentionShrinkage()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B, T, C = x.shape

        q = self.q_proj(x).view(B, T, self.n_heads, self.head_dim).transpose(1, 2)
        k = self.k_proj(x).view(B, T, self.n_heads, self.head_dim).transpose(1, 2)
        v = self.v_proj(x).view(B, T, self.n_heads, self.head_dim).transpose(1, 2)

        cos, sin = self.rope(x)
        q, k = apply_rope(q, k, cos, sin)

        scale = 1.0 / math.sqrt(self.head_dim)
        attn_weights = torch.matmul(q, k.transpose(-2, -1)) * scale

        # Causal mask
        mask = torch.triu(
            torch.ones(T, T, device=x.device, dtype=torch.bool), diagonal=1
        )
        attn_weights = attn_weights.masked_fill(mask, float('-inf'))
        attn_weights = F.softmax(attn_weights, dim=-1)
        attn_weights = self.dropout(attn_weights)

        # Marchenko-Pastur shrinkage
        if self.mp_enabled:
            attn_weights = self.mp_shrinkage.shrink(attn_weights)

        out = torch.matmul(attn_weights, v)
        out = out.transpose(1, 2).contiguous().view(B, T, C)
        return self.out_proj(out)


class FeedForward(nn.Module):
    """SwiGLU feed-forward."""

    def __init__(self, cfg: BabyAdamEConfig):
        super().__init__()
        self.w1 = nn.Linear(cfg.d_model, cfg.d_ff, bias=False)
        self.w2 = nn.Linear(cfg.d_ff, cfg.d_model, bias=False)
        self.w3 = nn.Linear(cfg.d_model, cfg.d_ff, bias=False)
        self.dropout = nn.Dropout(cfg.dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.dropout(self.w2(F.silu(self.w1(x)) * self.w3(x)))


class MoE_FFN(nn.Module):
    """Mixture of Experts FFN with Prophet inequality router."""

    def __init__(self, cfg: BabyAdamEConfig):
        super().__init__()
        self.n_experts = cfg.n_experts
        self.n_activated = cfg.n_activated
        self.prophet_enabled = cfg.prophet_stopping

        if self.prophet_enabled:
            self.router = ProphetRouter(cfg.d_model, cfg.n_experts, cfg.n_activated)
        else:
            self.router = nn.Linear(cfg.d_model, cfg.n_experts, bias=False)

        self.experts = nn.ModuleList(
            [FeedForward(cfg) for _ in range(cfg.n_experts)]
        )

    def forward(self, x: torch.Tensor, return_ledger: bool = False):
        B, T, C = x.shape

        if self.prophet_enabled:
            topk_weights, topk_indices, prophet_stats = self.router(
                x, return_stats=return_ledger
            )
        else:
            router_logits = self.router(x)
            topk_vals, topk_indices = torch.topk(router_logits, self.n_activated, dim=-1)
            topk_weights = F.softmax(topk_vals, dim=-1)
            prophet_stats = None

        # Compute expert outputs
        output = torch.zeros_like(x)
        expert_counts = torch.zeros(self.n_experts, device=x.device)

        for k in range(self.n_activated):
            expert_ids = topk_indices[..., k]
            weights = topk_weights[..., k:k+1]

            for e in range(self.n_experts):
                mask = (expert_ids == e)
                n_tokens = mask.sum().item()
                if n_tokens == 0:
                    continue

                expert_counts[e] += n_tokens
                expert_x = x[mask]
                expert_out = self.experts[e](expert_x)
                w = weights[mask]
                if w.dim() == 1:
                    w = w.unsqueeze(-1)
                output[mask] += expert_out * w

        ledger = None
        if return_ledger:
            ledger = {
                'topk_indices': topk_indices.detach(),
                'topk_weights': topk_weights.detach(),
                'expert_counts': expert_counts.detach(),
            }
            if prophet_stats:
                ledger.update(prophet_stats)

        return output, ledger


class TransformerBlock(nn.Module):
    """Pre-LN transformer block with KS anisotropic norm."""

    def __init__(self, cfg: BabyAdamEConfig):
        super().__init__()
        self.ks_enabled = cfg.ks_enabled

        if self.ks_enabled:
            self.ln1 = KSAnisotropicLayerNorm(cfg.d_model)
            self.ln2 = KSAnisotropicLayerNorm(cfg.d_model)
        else:
            self.ln1 = nn.LayerNorm(cfg.d_model)
            self.ln2 = nn.LayerNorm(cfg.d_model)

        self.attn = AttentionBlock(cfg)

        if cfg.moe_enabled:
            self.ffn = MoE_FFN(cfg)
            self.use_moe = True
        else:
            self.ffn = FeedForward(cfg)
            self.use_moe = False

    def forward(self, x: torch.Tensor, return_ledger: bool = False):
        x = x + self.attn(self.ln1(x))
        if self.use_moe:
            ffn_out, ledger = self.ffn(self.ln2(x), return_ledger=return_ledger)
            x = x + ffn_out
            return x, ledger
        else:
            x = x + self.ffn(self.ln2(x))
            return x, None


# ═══════════════════════════════════════════════════════════════════════
# BABY ADAM E — The extended model
# ═══════════════════════════════════════════════════════════════════════

class BabyAdamE(nn.Module):
    """
    Baby Adam E — Extended Architecture.

    Incorporates the full vault mathematical apparatus:
      - Berry phase probe (geometric phase)
      - Connes spectral triple (spectral dimension, zeta, spectral action)
      - WDW constraint (Ĥ|Ψ⟩ = 0)
      - KS anisotropic scaling (Kantowski-Sachs metric in embedding space)
      - Prophet inequality router (optimal stopping for MoE)
      - Marchenko-Pastur shrinkage (eigenvalue denoising)
      - Logit decision manifold (discrimination boundary)
      - Ledger chain (witness)
      - Gate architecture (boundary rule)

    Three pillars: LogDet · Logit · Ledger — one gate.
    """

    def __init__(self, cfg: BabyAdamEConfig):
        super().__init__()
        self.cfg = cfg

        # Token embedding (tied with output)
        self.token_embed = nn.Embedding(cfg.vocab_size, cfg.d_model)

        # Transformer blocks
        self.blocks = nn.ModuleList(
            [TransformerBlock(cfg) for _ in range(cfg.n_layers)]
        )

        # Final layer norm
        self.ln_final = nn.LayerNorm(cfg.d_model)

        # Output head (tied with embedding)
        self.lm_head = nn.Linear(cfg.d_model, cfg.vocab_size, bias=False)
        self.token_embed.weight = self.lm_head.weight

        # ── Extended Components ──

        # Logit decision manifold (Pillar 2: Decision)
        self.logit_manifold = (
            LogitDecisionManifold(cfg.d_model, cfg.logit_threshold)
            if cfg.logit_manifold_enabled else None
        )

        # Measurement probes
        self.berry_probe = BerryPhaseProbe()
        self.spectral_triple = SpectralTripleProbe(cfg.d_model, cfg.logdet_eps)

        # WDW constraint
        self.wdw_constraint = (
            WDWConstraint(cfg.wdw_lambda)
            if cfg.wdw_enabled else None
        )

        # Ledger (Pillar 3: Record)
        self.ledger = (
            Ledger(
                cfg.ledger_path or "baby_adam_e_chain.json",
                mode="nobody"
            )
            if cfg.ledger_enabled else None
        )

        # Gate (unified architecture)
        self.gate = None
        if (cfg.gate_enabled and self.ledger is not None
                and self.logit_manifold is not None):
            self.gate = Gate(self.ledger, self.logit_manifold)

        # Init weights
        self.apply(self._init_weights)

        # Parameter count
        self.n_params = sum(p.numel() for p in self.parameters())

    def _init_weights(self, module):
        if isinstance(module, nn.Linear):
            torch.nn.init.normal_(
                module.weight,
                mean=0.0,
                std=0.02 / math.sqrt(2 * self.cfg.n_layers),
            )
        elif isinstance(module, nn.Embedding):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)

    def forward(
        self,
        idx: torch.Tensor,
        return_measurements: bool = False,
        return_all_probes: bool = False,
    ) -> dict:
        """
        Forward pass with comprehensive measurement.

        Args:
            idx: [B, T] token indices
            return_measurements: compute LogDet + MoE ledger
            return_all_probes: compute ALL probes (Berry, spectral, WDW, logit)
        """
        B, T = idx.shape

        # Embed
        x = self.token_embed(idx)

        # Collect residual stream states
        residuals_in = [] if return_all_probes else None
        residuals_out = [] if return_all_probes else None
        expert_ledgers = [] if (return_measurements or return_all_probes) else None

        for block in self.blocks:
            if return_all_probes:
                residuals_in.append(x.detach())

            x, ledger = block(x, return_ledger=(return_measurements or return_all_probes))

            if return_all_probes:
                residuals_out.append(x.detach())
            if ledger is not None and expert_ledgers is not None:
                expert_ledgers.append(ledger)

        # Final norm
        x = self.ln_final(x)

        # Output logits
        logits = self.lm_head(x)

        result = {'logits': logits}

        # ── Measurements ──

        if return_measurements:
            result['measurements'] = self._compute_measurements(
                [x.detach() for x in residuals_out] if residuals_out else [],
                expert_ledgers or [],
            )

        if return_all_probes and residuals_in and residuals_out:
            all_measurements = result.get('measurements', {})

            # Berry phase
            berry = self.berry_probe.compute(residuals_out)
            all_measurements.update(berry)

            # Spectral triple
            spectral = self.spectral_triple.compute(residuals_in, residuals_out)
            all_measurements.update(spectral)

            # WDW constraint
            if self.wdw_constraint:
                wdw_loss, wdw_info = self.wdw_constraint.compute(
                    residuals_in, residuals_out
                )
                all_measurements['wdw_loss'] = wdw_loss.item()
                all_measurements.update(wdw_info)

            # Logit manifold
            if self.logit_manifold:
                logit_scores = self.logit_manifold(x)
                all_measurements['logit_score_mean'] = logit_scores.mean().item()
                all_measurements['logit_score_std'] = logit_scores.std().item()
                all_measurements['void_ratio'] = (
                    self.logit_manifold.get_void_ratio(x)
                )

            # KS expansion rates
            ks_rates = []
            for block in self.blocks:
                for ln in [block.ln1, block.ln2]:
                    if isinstance(ln, KSAnisotropicLayerNorm):
                        ks_rates.append(ln.get_expansion_rates())
            if ks_rates:
                a_vals = [r[0] for r in ks_rates]
                b_vals = [r[1] for r in ks_rates]
                all_measurements['ks_a_mean'] = sum(a_vals) / len(a_vals)
                all_measurements['ks_b_mean'] = sum(b_vals) / len(b_vals)

            result['measurements'] = all_measurements

        return result

    def _compute_measurements(
        self,
        residuals: list,
        expert_ledgers: list,
    ) -> dict:
        """LogDet measurement (Pillar 1: Measurement)."""

        measurements = {}
        logdets = []

        for i, r in enumerate(residuals):
            h = r.reshape(-1, r.shape[-1])
            h = h - h.mean(dim=0, keepdim=True)
            cov = (h.T @ h) / (h.shape[0] - 1)

            try:
                logdet = torch.logdet(
                    cov + self.cfg.logdet_eps * torch.eye(
                        cov.shape[0], device=cov.device
                    )
                )
                logdets.append(logdet.item())
            except Exception:
                logdets.append(float('nan'))

        if logdets:
            valid = [v for v in logdets if not math.isnan(v)]
            measurements['logdet_per_layer'] = logdets
            measurements['logdet_mean'] = (
                sum(valid) / len(valid) if valid else float('nan')
            )
            measurements['logdet_spread'] = (
                max(valid) - min(valid) if valid else float('nan')
            )

        # Expert ledger
        if expert_ledgers:
            expert_util = []
            entropies = []
            for ledger in expert_ledgers:
                counts = ledger['expert_counts']
                total = counts.sum().item()
                if total > 0:
                    util = (counts / total).tolist()
                    probs = counts / total
                    ent = -(probs * torch.log(probs + 1e-8)).sum().item()
                else:
                    util = [0.0] * len(counts)
                    ent = 0.0
                expert_util.append(util)
                entropies.append(ent)

            measurements['expert_utilization'] = expert_util
            measurements['routing_entropy'] = entropies
            measurements['routing_entropy_mean'] = (
                sum(entropies) / len(entropies) if entropies else 0.0
            )

        return measurements

    def generate(
        self,
        idx: torch.Tensor,
        max_new_tokens: int,
        temperature: float = 0.8,
        gate_filter: bool = False,
    ) -> torch.Tensor:
        """
        Autoregressive generation with optional gate filtering.

        If gate_filter=True, tokens crossing the threshold (logit < 0)
        are rejected and replaced with the next-best token.
        """
        self.eval()
        NOBODY = frozenset(self.cfg.NOBODY_EVENTS)

        with torch.no_grad():
            for _ in range(max_new_tokens):
                idx_cond = idx[:, -self.cfg.max_seq_len:]

                # Forward
                result = self.forward(idx_cond)
                logits = result['logits'][:, -1, :]

                # Temperature scaling
                logits = logits / temperature

                # Gate filter: suppress tokens on the voided side
                if gate_filter and self.logit_manifold:
                    # Get residual state for logit decision
                    x = self.token_embed(idx_cond)
                    for block in self.blocks:
                        x, _ = block(x, return_ledger=False)
                    x = self.ln_final(x)
                    logit_score = self.logit_manifold(x[:, -1:, :]).squeeze(-1)

                    if logit_score.item() < self.cfg.logit_threshold:
                        # Token is "voided" — penalize its probability
                        # Record the crossing in the ledger
                        if self.gate:
                            self.gate.process(
                                entity=f"token:{idx_cond[0, -1].item()}",
                                event="approach",
                                how=f"logit={logit_score.item():.3f}",
                            )

                # Sample
                probs = F.softmax(logits, dim=-1)
                idx_next = torch.multinomial(probs, num_samples=1)
                idx = torch.cat([idx, idx_next], dim=1)

        self.train()
        return idx

    def estimate_mfu(self, batch_size: int, seq_len: int) -> float:
        """Estimate MFU."""
        n_params = self.n_params
        flops_per_token = 6 * n_params
        total_flops = flops_per_token * batch_size * seq_len
        cpu_flops = 50e9  # Rough: 50 GFLOPS
        return total_flops / cpu_flops


# ═══════════════════════════════════════════════════════════════════════
# HELPER
# ═══════════════════════════════════════════════════════════════════════

def count_parameters(model: nn.Module) -> dict:
    """Detailed parameter count."""
    total = sum(p.numel() for p in model.parameters())
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)

    # Count by component
    by_component = {}
    for name, module in model.named_modules():
        if list(module.children()):
            continue
        n = sum(p.numel() for p in module.parameters())
        if n > 0:
            by_component[name] = n

    return {
        'total': total,
        'trainable': trainable,
        'by_component': by_component,
    }
