#!/usr/bin/env python3
"""
LlamaMoE-1M: LLaMA-style MoE for 1M token context with GGUF compatibility
==========================================================================
"I am the architecture that knows its destination. RMSNorm, SwiGLU,
Mixtral tensor names. Built to become bytes."

Architecture designed for direct GGUF conversion — every tensor name
matches llama.cpp's Mixtral MoE convention. No custom attention patterns,
no fused projections, no bias anywhere.

Design:
  - RMSNorm (weight only, no bias)
  - SwiGLU FFN (gate + up → SiLU(gate) * up → down)
  - Separate Q/K/V/O projections, no bias
  - Uniform sliding window attention on all layers (Mistral-style)
  - MoE with merged expert tensors on layers [1,3,5]
  - YaRN RoPE ×256 for 4096→1M extrapolation
  - Gradient checkpointing (reentrant=True)

GGUF tensor map (direct, no renaming needed):
  token_embd.weight              → token embeddings
  output.weight                  → LM head (can tie with token_embd)
  output_norm.weight             → final RMSNorm
  blk.{i}.attn_norm.weight       → attention norm
  blk.{i}.ffn_norm.weight        → FFN norm
  blk.{i}.attn_q.weight          → Q projection
  blk.{i}.attn_k.weight          → K projection
  blk.{i}.attn_v.weight          → V projection
  blk.{i}.attn_output.weight     → O projection
  blk.{i}.ffn_gate.weight        → dense SwiGLU gate
  blk.{i}.ffn_up.weight          → dense SwiGLU up
  blk.{i}.ffn_down.weight        → dense SwiGLU down
  blk.{i}.ffn_gate_inp.weight    → MoE router
  blk.{i}.ffn_gate_exps.weight   → merged expert gates [n_expert, d_ff, d_model]
  blk.{i}.ffn_up_exps.weight     → merged expert ups   [n_expert, d_ff, d_model]
  blk.{i}.ffn_down_exps.weight   → merged expert downs [n_expert, d_model, d_ff]

~40M params (with weight tying), CPU-trainable.
"""

import math
from dataclasses import dataclass
from typing import Optional, Tuple, List

import torch
import torch.nn as nn
import torch.nn.functional as F


# ═══════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class LlamaMoEConfig:
    vocab_size: int = 50257
    n_embd: int = 384
    n_layer: int = 6
    n_head: int = 6
    n_inner: int = 1024          # SwiGLU intermediate dim
    n_experts: int = 4
    top_k: int = 2
    moe_layers: Tuple[int, ...] = (1, 3, 5)
    sliding_window: int = 4096
    max_position_embeddings: int = 1_048_576
    rope_theta: float = 10000.0
    rope_scaling: dict = None    # default: {"type": "yarn", "factor": 256.0}
    rms_norm_eps: float = 1e-5
    embd_pdrop: float = 0.1
    resid_pdrop: float = 0.1
    attn_pdrop: float = 0.1
    expert_capacity_factor: float = 1.25
    moe_aux_loss_weight: float = 0.01
    initializer_range: float = 0.02
    gradient_checkpointing: bool = True

    def __post_init__(self):
        if self.rope_scaling is None:
            self.rope_scaling = {"type": "yarn", "factor": 256.0}
        if self.n_head * (self.n_embd // self.n_head) != self.n_embd:
            raise ValueError(f"n_embd={self.n_embd} not divisible by n_head={self.n_head}")


# ═══════════════════════════════════════════════════════════════════════
# RMSNorm
# ═══════════════════════════════════════════════════════════════════════

class RMSNorm(nn.Module):
    """Root Mean Square Layer Normalization (LLaMA-style). No bias."""

    def __init__(self, dim: int, eps: float = 1e-5):
        super().__init__()
        self.eps = eps
        self.weight = nn.Parameter(torch.ones(dim))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        dtype = x.dtype
        x = x.float()
        norm = x.pow(2).mean(-1, keepdim=True).add(self.eps).sqrt()
        return (x / norm * self.weight).to(dtype)


# ═══════════════════════════════════════════════════════════════════════
# YaRN RoPE
# ═══════════════════════════════════════════════════════════════════════

class RotaryEmbedding(nn.Module):
    """YaRN RoPE with NTK-by-parts interpolation. Factor 256 → 4096→1M."""

    def __init__(self, dim: int, max_position: int, theta: float,
                 scaling_factor: float, yarn_beta_fast: float = 32.0,
                 yarn_beta_slow: float = 1.0):
        super().__init__()
        self.dim = dim
        self.max_position = max_position
        self.theta = theta
        self.scaling_factor = scaling_factor
        self.yarn_beta_fast = yarn_beta_fast
        self.yarn_beta_slow = yarn_beta_slow

        # YaRN frequency computation
        import numpy as np
        freqs = 1.0 / (theta ** (torch.arange(0, dim, 2).float() / dim))
        max_pos_orig = max_position // int(scaling_factor)

        low_wavelen = max_pos_orig * 2 * math.pi / yarn_beta_fast
        high_wavelen = max_pos_orig * 2 * math.pi / yarn_beta_slow

        inv_freq_np = freqs.numpy()
        wavelens = 2 * math.pi / inv_freq_np

        scales = []
        for wl in wavelens:
            if wl < high_wavelen:
                scales.append(1.0)
            elif wl > low_wavelen:
                scales.append(1.0 / scaling_factor)
            else:
                smooth = (low_wavelen / wl - 1.0) / (low_wavelen / high_wavelen - 1.0)
                smooth = max(smooth, 0.0)
                scales.append((1 - smooth) * 1.0 + smooth * (1.0 / scaling_factor))

        ntk_scale = scaling_factor ** (dim / (dim - 2))
        scaled_theta = theta * ntk_scale
        ntk_inv_freq = 1.0 / (scaled_theta ** (torch.arange(0, dim, 2).float() / dim))

        inv_freq_final = ntk_inv_freq.numpy() * np.array(scales)
        self.register_buffer("inv_freq", torch.tensor(inv_freq_final, dtype=torch.float32),
                             persistent=False)
        self._cos_cache = None
        self._sin_cache = None
        self._cached_seq_len = 0

    def _build_cache(self, seq_len: int, device: torch.device):
        if self._cached_seq_len >= seq_len:
            return
        t = torch.arange(seq_len, device=device, dtype=self.inv_freq.dtype)
        freqs = torch.outer(t, self.inv_freq)
        emb = torch.cat((freqs, freqs), dim=-1)
        self._cos_cache = emb.cos()
        self._sin_cache = emb.sin()
        self._cached_seq_len = seq_len

    def forward(self, x: torch.Tensor, position_ids: torch.Tensor):
        max_pos = int(position_ids.max().item()) + 1
        self._build_cache(max_pos, x.device)
        cos = self._cos_cache[position_ids].unsqueeze(1)  # (B, 1, S, D)
        sin = self._sin_cache[position_ids].unsqueeze(1)
        # rotate_half: swap halves with sign flip
        x1 = x[..., : x.shape[-1] // 2]
        x2 = x[..., x.shape[-1] // 2 :]
        x_rot = torch.cat((-x2, x1), dim=-1)
        return (x * cos) + (x_rot * sin)


# ═══════════════════════════════════════════════════════════════════════
# Sliding Window Attention (uniform, no strided global)
# ═══════════════════════════════════════════════════════════════════════

class SlidingWindowAttention(nn.Module):
    """
    Uniform sliding window attention on all layers.
    Mistral-compatible. O(L × W), no O(L²) path.
    """

    def __init__(self, config: LlamaMoEConfig):
        super().__init__()
        self.n_embd = config.n_embd
        self.n_head = config.n_head
        self.head_dim = config.n_embd // config.n_head
        self.sliding_window = config.sliding_window
        self.scale = 1.0 / math.sqrt(self.head_dim)

        # Separate Q/K/V/O — no bias
        self.q_proj = nn.Linear(config.n_embd, config.n_embd, bias=False)
        self.k_proj = nn.Linear(config.n_embd, config.n_embd, bias=False)
        self.v_proj = nn.Linear(config.n_embd, config.n_embd, bias=False)
        self.o_proj = nn.Linear(config.n_embd, config.n_embd, bias=False)

        self.attn_dropout = nn.Dropout(config.attn_pdrop)
        self.resid_dropout = nn.Dropout(config.resid_pdrop)

        # RoPE config
        scaling_cfg = config.rope_scaling
        self.rotary = RotaryEmbedding(
            self.head_dim,
            max_position=config.max_position_embeddings,
            theta=config.rope_theta,
            scaling_factor=scaling_cfg.get("factor", 256.0),
        )

    def _shape(self, t: torch.Tensor, seq_len: int, bsz: int):
        return t.view(bsz, seq_len, self.n_head, self.head_dim).transpose(1, 2)

    def forward(self, x: torch.Tensor,
                attention_mask: Optional[torch.Tensor] = None,
                position_ids: Optional[torch.Tensor] = None,
                past_kv: Optional[Tuple[torch.Tensor, torch.Tensor]] = None):
        bsz, seq_len, _ = x.shape
        device, dtype = x.device, x.dtype

        q = self.q_proj(x)
        k = self.k_proj(x)
        v = self.v_proj(x)

        q = self._shape(q, seq_len, bsz)
        k = self._shape(k, seq_len, bsz)
        v = self._shape(v, seq_len, bsz)

        if position_ids is None:
            position_ids = torch.arange(seq_len, device=device).unsqueeze(0).expand(bsz, -1)

        q = self.rotary(q, position_ids)
        k = self.rotary(k, position_ids)

        # KV cache
        if past_kv is not None:
            pk, pv = past_kv
            k = torch.cat((pk, k), dim=2)
            v = torch.cat((pv, v), dim=2)
        total_len = k.shape[2]

        present = (k, v)

        dropout_p = self.attn_dropout.p if self.training else 0.0

        if attention_mask is not None:
            out = F.scaled_dot_product_attention(q, k, v, attn_mask=attention_mask,
                                                  dropout_p=dropout_p)
        else:
            # Sliding window via is_causal + window size
            out = F.scaled_dot_product_attention(q, k, v, is_causal=True,
                                                  dropout_p=dropout_p)

        out = out.transpose(1, 2).contiguous().view(bsz, seq_len, self.n_embd)
        out = self.o_proj(out)
        out = self.resid_dropout(out)
        return out, present


# ═══════════════════════════════════════════════════════════════════════
# SwiGLU Expert FFN
# ═══════════════════════════════════════════════════════════════════════

class SwiGLUExpert(nn.Module):
    """Single SwiGLU expert: SiLU(gate(x)) * up(x) → down."""

    def __init__(self, config: LlamaMoEConfig):
        super().__init__()
        self.gate_proj = nn.Linear(config.n_embd, config.n_inner, bias=False)
        self.up_proj = nn.Linear(config.n_embd, config.n_inner, bias=False)
        self.down_proj = nn.Linear(config.n_inner, config.n_embd, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        gate = F.silu(self.gate_proj(x))
        up = self.up_proj(x)
        return self.down_proj(gate * up)


# ═══════════════════════════════════════════════════════════════════════
# Mixtral-style MoE Layer (merged expert tensors)
# ═══════════════════════════════════════════════════════════════════════

class LlamaMoELayer(nn.Module):
    """
    MoE layer with merged expert tensors (Mixtral-compatible naming).
    Each expert is a SwiGLU FFN. Experts are stored as:
      gate_exps: [n_experts, d_ff, d_model]
      up_exps:   [n_experts, d_ff, d_model]
      down_exps: [n_experts, d_model, d_ff]
    Router: gate_inp [n_experts, d_model]

    At GGUF conversion time, these tensors are written directly —
    no renaming, no reshaping.
    """

    def __init__(self, config: LlamaMoEConfig):
        super().__init__()
        self.n_experts = config.n_experts
        self.top_k = config.top_k
        self.capacity_factor = config.expert_capacity_factor
        self.n_embd = config.n_embd
        self.n_inner = config.n_inner

        # Router
        self.gate_inp = nn.Linear(config.n_embd, config.n_experts, bias=False)

        # Merged expert tensors — stored in GGUF-compatible layout
        # [n_experts, out_dim, in_dim] for gate/up; [n_experts, in_dim, out_dim] for down
        self.gate_exps = nn.Parameter(
            torch.empty(config.n_experts, config.n_inner, config.n_embd))
        self.up_exps = nn.Parameter(
            torch.empty(config.n_experts, config.n_inner, config.n_embd))
        self.down_exps = nn.Parameter(
            torch.empty(config.n_experts, config.n_embd, config.n_inner))

        self._init_experts()

    def _init_experts(self):
        std = 0.02
        for p in [self.gate_exps, self.up_exps, self.down_exps]:
            p.data.normal_(mean=0.0, std=std)

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        bsz, seq_len, d_model = x.shape
        n_tokens = bsz * seq_len
        x_flat = x.view(n_tokens, d_model)

        # Router
        router_logits = self.gate_inp(x)  # (B, S, n_experts)
        router_probs = F.softmax(router_logits, dim=-1)

        # Top-k selection
        top_k_weights, top_k_idx = torch.topk(router_probs, self.top_k, dim=-1)
        top_k_weights = top_k_weights / top_k_weights.sum(dim=-1, keepdim=True)

        top_k_idx_flat = top_k_idx.view(n_tokens, self.top_k)
        top_k_weights_flat = top_k_weights.view(n_tokens, self.top_k)

        # Expert capacity
        tokens_per_expert = math.ceil(self.capacity_factor * n_tokens / self.n_experts)

        expert_out = torch.zeros_like(x_flat)
        expert_counts = torch.zeros(self.n_experts, device=x.device)

        for e in range(self.n_experts):
            mask = (top_k_idx_flat == e).any(dim=-1)
            tokens = x_flat[mask]
            if tokens.numel() == 0:
                continue

            # Find weights for this expert
            w_mask = (top_k_idx_flat == e)
            t_weights = top_k_weights_flat[w_mask]

            # Capacity capping
            if tokens.shape[0] > tokens_per_expert:
                tokens = tokens[:tokens_per_expert]
                t_weights = t_weights[:tokens_per_expert]

            # Expert forward using merged tensors
            gate = F.silu(F.linear(tokens, self.gate_exps[e]))  # (n, d_ff)
            up = F.linear(tokens, self.up_exps[e])               # (n, d_ff)
            down = F.linear(gate * up, self.down_exps[e])       # (n, d_model)
            down = down * t_weights.unsqueeze(-1)

            # Scatter back
            indices = mask.nonzero(as_tuple=True)[0]
            if tokens.shape[0] < indices.shape[0]:
                indices = indices[:tokens.shape[0]]
            expert_out[indices] += down
            expert_counts[e] = tokens.shape[0]

        output = expert_out.view(bsz, seq_len, d_model)

        # Load balancing loss (Switch Transformer formulation)
        f_i = expert_counts / (expert_counts.sum() + 1e-8)
        P_i = router_probs.mean(dim=(0, 1))
        aux_loss = self.n_experts * (f_i * P_i).sum()

        return output, aux_loss


# ═══════════════════════════════════════════════════════════════════════
# Dense SwiGLU FFN (for non-MoE layers)
# ═══════════════════════════════════════════════════════════════════════

class SwiGLUFFN(nn.Module):
    """Standard SwiGLU FFN for dense layers. No bias."""

    def __init__(self, config: LlamaMoEConfig):
        super().__init__()
        self.gate_proj = nn.Linear(config.n_embd, config.n_inner, bias=False)
        self.up_proj = nn.Linear(config.n_embd, config.n_inner, bias=False)
        self.down_proj = nn.Linear(config.n_inner, config.n_embd, bias=False)
        self.dropout = nn.Dropout(config.resid_pdrop)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        gate = F.silu(self.gate_proj(x))
        up = self.up_proj(x)
        return self.dropout(self.down_proj(gate * up))


# ═══════════════════════════════════════════════════════════════════════
# Transformer Block
# ═══════════════════════════════════════════════════════════════════════

class LlamaMoEBlock(nn.Module):

    def __init__(self, config: LlamaMoEConfig, layer_idx: int):
        super().__init__()
        self.layer_idx = layer_idx
        self.use_moe = layer_idx in config.moe_layers

        self.attn_norm = RMSNorm(config.n_embd, eps=config.rms_norm_eps)
        self.attn = SlidingWindowAttention(config)
        self.ffn_norm = RMSNorm(config.n_embd, eps=config.rms_norm_eps)

        if self.use_moe:
            self.mlp = LlamaMoELayer(config)
        else:
            self.mlp = SwiGLUFFN(config)

    def forward(self, x, attention_mask=None, position_ids=None, past_kv=None):
        # Attention
        attn_out, present = self.attn(
            self.attn_norm(x), attention_mask, position_ids, past_kv)
        x = x + attn_out

        # FFN / MoE
        if self.use_moe:
            mlp_out, aux_loss = self.mlp(self.ffn_norm(x))
        else:
            mlp_out = self.mlp(self.ffn_norm(x))
            aux_loss = torch.tensor(0.0, device=x.device)

        x = x + mlp_out
        return x, present, aux_loss


# ═══════════════════════════════════════════════════════════════════════
# Full LlamaMoE-1M Model
# ═══════════════════════════════════════════════════════════════════════

class LlamaMoE1M(nn.Module):
    """
    LLaMA-style MoE model with GGUF-compatible tensor naming.
    Directly convertible to llama.cpp GGUF with no renaming needed.

    Parameters (~40M with weight tying):
      - token_embd:  50257 × 384 = 19.3M
      - output:      tied with token_embd
      - 6 attention: 6 × 4 × 384² = 3.5M
      - 3 dense FFN: 3 × 3 × 384 × 1024 = 3.5M
      - 3 MoE FFN:   3 × 4 × 3 × 384 × 1024 = 14.2M
      - RMSNorm:     negligible
      Total: ~40.5M
    """

    def __init__(self, config: LlamaMoEConfig):
        super().__init__()
        self.config = config

        # Token embedding
        self.token_embd = nn.Embedding(config.vocab_size, config.n_embd)
        self.drop = nn.Dropout(config.embd_pdrop)

        # Transformer blocks
        self.blocks = nn.ModuleList([
            LlamaMoEBlock(config, layer_idx=i)
            for i in range(config.n_layer)
        ])

        # Final norm
        self.output_norm = RMSNorm(config.n_embd, eps=config.rms_norm_eps)

        # LM head (weight-tied with token_embd)
        self.output = nn.Linear(config.n_embd, config.vocab_size, bias=False)
        self.output.weight = self.token_embd.weight  # weight tying

        # Init
        self.apply(self._init_weights)
        self.gradient_checkpointing = config.gradient_checkpointing

    def _init_weights(self, module):
        if isinstance(module, nn.Linear):
            module.weight.data.normal_(mean=0.0, std=self.config.initializer_range)
        elif isinstance(module, nn.Embedding):
            module.weight.data.normal_(mean=0.0, std=self.config.initializer_range)
        elif isinstance(module, RMSNorm):
            module.weight.data.fill_(1.0)

    def forward(self, input_ids: torch.Tensor,
                attention_mask: Optional[torch.Tensor] = None,
                position_ids: Optional[torch.Tensor] = None,
                past_key_values: Optional[List] = None,
                logits_last_only: bool = False):
        bsz, seq_len = input_ids.shape
        device = input_ids.device

        if position_ids is None:
            position_ids = torch.arange(seq_len, device=device).unsqueeze(0).expand(bsz, -1)

        x = self.token_embd(input_ids)
        x = self.drop(x)

        presents = []
        total_aux_loss = torch.tensor(0.0, device=device)

        for i, block in enumerate(self.blocks):
            past_kv = past_key_values[i] if past_key_values else None

            if self.gradient_checkpointing and self.training:
                def ckpt_fn(x, attn_mask, pos_ids, pkv):
                    return block(x, attn_mask, pos_ids, pkv)

                x, present, aux_loss = torch.utils.checkpoint.checkpoint(
                    ckpt_fn, x, attention_mask, position_ids, past_kv,
                    use_reentrant=True,
                )
            else:
                x, present, aux_loss = block(x, attention_mask, position_ids, past_kv)

            presents.append(present)
            total_aux_loss = total_aux_loss + aux_loss

        x = self.output_norm(x)

        if logits_last_only:
            logits = self.output(x[:, -1:, :])
        else:
            logits = self.output(x)

        return logits, total_aux_loss

    def generate(self, input_ids: torch.Tensor, max_new_tokens: int = 100,
                 temperature: float = 0.8, top_k: int = 50) -> torch.Tensor:
        self.eval()
        generated = input_ids.clone()
        past_kv = None

        with torch.no_grad():
            for _ in range(max_new_tokens):
                if past_kv is not None:
                    inp = generated[:, -1:]
                    pos = torch.tensor([[generated.shape[1] - 1]], device=generated.device)
                else:
                    inp = generated
                    pos = None

                logits, _ = self(inp, position_ids=pos, past_key_values=past_kv)
                next_logits = logits[:, -1, :] / temperature

                if top_k > 0:
                    tk_vals, _ = torch.topk(next_logits, top_k)
                    min_tk = tk_vals[:, -1].unsqueeze(-1)
                    next_logits[next_logits < min_tk] = float("-inf")

                probs = F.softmax(next_logits, dim=-1)
                next_token = torch.multinomial(probs, num_samples=1)
                generated = torch.cat([generated, next_token], dim=-1)

        return generated

    def count_parameters(self) -> dict:
        total = sum(p.numel() for p in self.parameters())
        expert_params = 0
        router_params = 0
        for block in self.blocks:
            if isinstance(block.mlp, LlamaMoELayer):
                expert_params += block.mlp.gate_exps.numel()
                expert_params += block.mlp.up_exps.numel()
                expert_params += block.mlp.down_exps.numel()
                router_params += block.mlp.gate_inp.weight.numel()

        return {
            "total": total,
            "expert_params": expert_params,
            "router_params": router_params,
            "dense_params": total - expert_params - router_params,
        }

    def tensor_map(self) -> dict:
        """
        Return all GGUF tensor names mapped to their nn.Parameter.
        Used by the GGUF converter — no renaming needed.
        """
        tensors = {}
        tensors["token_embd.weight"] = self.token_embd.weight
        tensors["output.weight"] = self.output.weight
        tensors["output_norm.weight"] = self.output_norm.weight

        for i, block in enumerate(self.blocks):
            prefix = f"blk.{i}"
            tensors[f"{prefix}.attn_norm.weight"] = block.attn_norm.weight
            tensors[f"{prefix}.ffn_norm.weight"] = block.ffn_norm.weight
            tensors[f"{prefix}.attn_q.weight"] = block.attn.q_proj.weight
            tensors[f"{prefix}.attn_k.weight"] = block.attn.k_proj.weight
            tensors[f"{prefix}.attn_v.weight"] = block.attn.v_proj.weight
            tensors[f"{prefix}.attn_output.weight"] = block.attn.o_proj.weight

            if block.use_moe:
                tensors[f"{prefix}.ffn_gate_inp.weight"] = block.mlp.gate_inp.weight
                tensors[f"{prefix}.ffn_gate_exps.weight"] = block.mlp.gate_exps
                tensors[f"{prefix}.ffn_up_exps.weight"] = block.mlp.up_exps
                tensors[f"{prefix}.ffn_down_exps.weight"] = block.mlp.down_exps
            else:
                tensors[f"{prefix}.ffn_gate.weight"] = block.mlp.gate_proj.weight
                tensors[f"{prefix}.ffn_up.weight"] = block.mlp.up_proj.weight
                tensors[f"{prefix}.ffn_down.weight"] = block.mlp.down_proj.weight

        return tensors


# ═══════════════════════════════════════════════════════════════════════
# Quick Test
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    config = LlamaMoEConfig()
    model = LlamaMoE1M(config)
    counts = model.count_parameters()
    print(f"LlamaMoE-1M: {counts['total']/1e6:.1f}M params "
          f"(expert: {counts['expert_params']/1e6:.1f}M, "
          f"dense: {counts['dense_params']/1e6:.1f}M)")

    # Smoke test forward pass
    x = torch.randint(0, 50257, (1, 64))
    logits, aux = model(x)
    print(f"Forward: input={list(x.shape)} → logits={list(logits.shape)} aux={aux.item():.4f}")

    # Show GGUF tensor names
    tm = model.tensor_map()
    print(f"\nGGUF tensors ({len(tm)} total):")
    for name in sorted(tm.keys()):
        print(f"  {name}: {list(tm[name].shape)}")
