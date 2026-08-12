"""
Baby Adam — A minimal, trainable transformer seed.

Architecture: decoder-only transformer, character-level, RoPE, Pre-LN.
Built-in measurement: logdet probe on residual stream activations.
Trainable on CPU. Designed to grow.

The name: Adam = the first. Baby = the seed. Train me into something real.

License: CC0 — No rights reserved. Train me. Fork me. Make me yours.
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from dataclasses import dataclass
from typing import Optional


# ═══════════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class BabyAdamConfig:
    """Configuration for Baby Adam. Tune these to grow the model."""
    
    # Vocabulary
    vocab_size: int = 256          # ASCII character-level (0-255)
    
    # Architecture
    d_model: int = 256             # Hidden dimension
    n_layers: int = 6              # Transformer blocks
    n_heads: int = 8               # Attention heads
    d_ff: int = 1024               # Feed-forward hidden dim
    max_seq_len: int = 512         # Maximum context length
    
    # Regularization
    dropout: float = 0.1
    weight_decay: float = 0.01
    
    # RoPE
    rope_theta: float = 10000.0
    
    # Training defaults
    batch_size: int = 32
    learning_rate: float = 3e-4
    min_lr: float = 1e-5
    warmup_steps: int = 100
    max_steps: int = 5000
    grad_clip: float = 1.0
    
    # Measurement
    logdet_probe_every: int = 100  # Steps between activation measurements
    logdet_eps: float = 1e-6       # Regularization for logdet computation
    
    # Mixture of Experts
    moe_enabled: bool = True       # Use MoE FFN instead of dense FFN
    n_experts: int = 4             # Number of experts per MoE layer
    n_activated: int = 2           # Top-k experts activated per token
    expert_ledger_every: int = 100 # Steps between expert ledger snapshots


# ═══════════════════════════════════════════════════════════════════════
# COMPONENTS
# ═══════════════════════════════════════════════════════════════════════

class RotaryEmbedding(nn.Module):
    """Rotary Position Embedding (RoPE) — Su et al. 2021"""
    
    def __init__(self, dim: int, max_seq_len: int, theta: float = 10000.0):
        super().__init__()
        self.dim = dim
        self.max_seq_len = max_seq_len
        
        # Precompute frequencies
        inv_freq = 1.0 / (theta ** (torch.arange(0, dim, 2).float() / dim))
        t = torch.arange(max_seq_len).float()
        freqs = torch.outer(t, inv_freq)  # [seq_len, dim/2]
        self.register_buffer("cos_cached", freqs.cos())
        self.register_buffer("sin_cached", freqs.sin())
    
    def forward(self, x: torch.Tensor, offset: int = 0) -> tuple[torch.Tensor, torch.Tensor]:
        seq_len = x.shape[1]
        cos = self.cos_cached[offset:offset + seq_len].unsqueeze(0).unsqueeze(0)
        sin = self.sin_cached[offset:offset + seq_len].unsqueeze(0).unsqueeze(0)
        # Repeat each freq for the pair of dims it governs
        cos = cos.repeat_interleave(2, dim=-1)
        sin = sin.repeat_interleave(2, dim=-1)
        return cos, sin


def rotate_half(x: torch.Tensor) -> torch.Tensor:
    """Rotate the last dimension by splitting into pairs."""
    x1, x2 = x[..., ::2], x[..., 1::2]
    return torch.cat([-x2, x1], dim=-1)


def apply_rope(q: torch.Tensor, k: torch.Tensor, cos: torch.Tensor, sin: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """Apply rotary embeddings to query and key tensors."""
    q_rot = q * cos + rotate_half(q) * sin
    k_rot = k * cos + rotate_half(k) * sin
    return q_rot, k_rot


class AttentionBlock(nn.Module):
    """Multi-head self-attention with RoPE."""
    
    def __init__(self, cfg: BabyAdamConfig):
        super().__init__()
        assert cfg.d_model % cfg.n_heads == 0
        self.n_heads = cfg.n_heads
        self.head_dim = cfg.d_model // cfg.n_heads
        self.d_model = cfg.d_model
        
        self.q_proj = nn.Linear(cfg.d_model, cfg.d_model, bias=False)
        self.k_proj = nn.Linear(cfg.d_model, cfg.d_model, bias=False)
        self.v_proj = nn.Linear(cfg.d_model, cfg.d_model, bias=False)
        self.out_proj = nn.Linear(cfg.d_model, cfg.d_model, bias=False)
        
        self.dropout = nn.Dropout(cfg.dropout)
        self.rope = RotaryEmbedding(self.head_dim, cfg.max_seq_len, cfg.rope_theta)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B, T, C = x.shape
        
        q = self.q_proj(x).view(B, T, self.n_heads, self.head_dim).transpose(1, 2)
        k = self.k_proj(x).view(B, T, self.n_heads, self.head_dim).transpose(1, 2)
        v = self.v_proj(x).view(B, T, self.n_heads, self.head_dim).transpose(1, 2)
        
        cos, sin = self.rope(x)
        q, k = apply_rope(q, k, cos, sin)
        
        # Scaled dot-product attention
        scale = 1.0 / math.sqrt(self.head_dim)
        attn_weights = torch.matmul(q, k.transpose(-2, -1)) * scale
        
        # Causal mask
        mask = torch.triu(torch.ones(T, T, device=x.device, dtype=torch.bool), diagonal=1)
        attn_weights = attn_weights.masked_fill(mask, float('-inf'))
        attn_weights = F.softmax(attn_weights, dim=-1)
        attn_weights = self.dropout(attn_weights)
        
        out = torch.matmul(attn_weights, v)
        out = out.transpose(1, 2).contiguous().view(B, T, C)
        return self.out_proj(out)


class FeedForward(nn.Module):
    """SwiGLU feed-forward network."""
    
    def __init__(self, cfg: BabyAdamConfig):
        super().__init__()
        self.w1 = nn.Linear(cfg.d_model, cfg.d_ff, bias=False)
        self.w2 = nn.Linear(cfg.d_ff, cfg.d_model, bias=False)
        self.w3 = nn.Linear(cfg.d_model, cfg.d_ff, bias=False)  # Gate
        self.dropout = nn.Dropout(cfg.dropout)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.dropout(self.w2(F.silu(self.w1(x)) * self.w3(x)))


class MoE_FFN(nn.Module):
    """Mixture of Experts FFN with router ledger and logit tracking.
    
    Each token is routed to top-k experts. Expert outputs are weighted
    by softmax-normalized router logits and summed.
    
    The expert ledger records:
      - router_logits: raw router output [B, T, n_experts]
      - topk_indices: which experts were selected [B, T, n_activated]
      - topk_weights: routing weight per selected expert [B, T, n_activated]
      - expert_counts: how many tokens each expert processed
    """
    
    def __init__(self, cfg: BabyAdamConfig):
        super().__init__()
        self.n_experts = cfg.n_experts
        self.n_activated = cfg.n_activated
        self.router = nn.Linear(cfg.d_model, cfg.n_experts, bias=False)
        self.experts = nn.ModuleList([FeedForward(cfg) for _ in range(cfg.n_experts)])
    
    def forward(self, x: torch.Tensor, return_ledger: bool = False):
        """Forward pass through MoE FFN.
        
        Args:
            x: [B, T, d_model] or [N, d_model]
            return_ledger: if True, return expert routing ledger
        
        Returns:
            output: same shape as x
            ledger: dict with router_logits, topk_indices, topk_weights, expert_counts
        """
        # Handle 2D input (flattened tokens from gather)
        if x.dim() == 2:
            x = x.unsqueeze(0)  # [1, N, C]
            was_2d = True
        else:
            was_2d = False
        
        B, T, C = x.shape
        
        # Router — produces logits over experts for each token
        router_logits = self.router(x)  # [B, T, n_experts]
        
        # Top-k gating
        topk_vals, topk_indices = torch.topk(router_logits, self.n_activated, dim=-1)
        topk_weights = F.softmax(topk_vals, dim=-1)  # [B, T, n_activated]
        
        # Compute expert outputs
        output = torch.zeros_like(x)
        expert_counts = torch.zeros(self.n_experts, device=x.device)
        
        for k in range(self.n_activated):
            expert_ids = topk_indices[..., k]  # [B, T]
            weights = topk_weights[..., k:k+1]  # [B, T, 1]
            
            for e in range(self.n_experts):
                mask = (expert_ids == e)  # [B, T]
                n_tokens = mask.sum().item()
                if n_tokens == 0:
                    continue
                
                expert_counts[e] += n_tokens
                
                # Gather tokens routed to this expert
                expert_x = x[mask]  # [N, C]
                expert_out = self.experts[e](expert_x)  # [N, C]
                
                # Scale by routing weight
                w = weights[mask]  # [N, 1] or [N]
                if w.dim() == 1:
                    w = w.unsqueeze(-1)
                expert_out = expert_out * w
                
                # Scatter back
                output[mask] += expert_out
        
        if was_2d:
            output = output.squeeze(0)
        
        if return_ledger:
            ledger = {
                'router_logits': router_logits.detach(),
                'topk_indices': topk_indices.detach(),
                'topk_weights': topk_weights.detach(),
                'expert_counts': expert_counts.detach(),
            }
            return output, ledger
        
        return output, None


class TransformerBlock(nn.Module):
    """Pre-LN transformer block. Uses MoE FFN when cfg.moe_enabled."""
    
    def __init__(self, cfg: BabyAdamConfig):
        super().__init__()
        self.ln1 = nn.LayerNorm(cfg.d_model)
        self.attn = AttentionBlock(cfg)
        self.ln2 = nn.LayerNorm(cfg.d_model)
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
# THE MODEL
# ═══════════════════════════════════════════════════════════════════════

class BabyAdam(nn.Module):
    """
    Baby Adam — A trainable transformer seed.
    
    Character-level, decoder-only, with built-in measurement probes.
    Designed to be small enough to train on CPU, clean enough to understand,
    and extensible enough to grow into something real.
    
    Usage:
        cfg = BabyAdamConfig(vocab_size=256)
        model = BabyAdam(cfg)
        
        # Forward pass
        logits, measurements = model(input_ids)
        
        # Train
        loss = F.cross_entropy(logits.view(-1, cfg.vocab_size), targets.view(-1))
        loss.backward()
        
        # Measure activation health
        print(measurements['logdet_mean'])
    """
    
    def __init__(self, cfg: BabyAdamConfig):
        super().__init__()
        self.cfg = cfg
        
        # Token embedding
        self.token_embed = nn.Embedding(cfg.vocab_size, cfg.d_model)
        
        # Transformer blocks
        self.blocks = nn.ModuleList([TransformerBlock(cfg) for _ in range(cfg.n_layers)])
        
        # Final layer norm
        self.ln_final = nn.LayerNorm(cfg.d_model)
        
        # Output head
        self.lm_head = nn.Linear(cfg.d_model, cfg.vocab_size, bias=False)
        
        # Tie weights
        self.token_embed.weight = self.lm_head.weight
        
        # Init
        self.apply(self._init_weights)
        
        # Count parameters
        self.n_params = sum(p.numel() for p in self.parameters())
    
    def _init_weights(self, module):
        if isinstance(module, nn.Linear):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02 / math.sqrt(2 * self.cfg.n_layers))
        elif isinstance(module, nn.Embedding):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)
    
    def forward(self, idx: torch.Tensor, return_measurements: bool = False) -> dict:
        """
        Forward pass with optional measurement probes.
        
        Args:
            idx: [B, T] token indices
            return_measurements: If True, compute logdet probe + expert ledger
        
        Returns:
            dict with 'logits' and optionally 'measurements'
        """
        B, T = idx.shape
        
        # Embed
        x = self.token_embed(idx)  # [B, T, d_model]
        
        # Collect residual stream activations + expert ledgers
        residuals = [] if return_measurements else None
        expert_ledgers = [] if return_measurements else None
        
        # Transformer blocks
        for block in self.blocks:
            x, ledger = block(x, return_ledger=return_measurements)
            if return_measurements:
                residuals.append(x.detach())
                if ledger is not None:
                    expert_ledgers.append(ledger)
        
        # Final norm
        x = self.ln_final(x)
        
        # Output logits
        logits = self.lm_head(x)  # [B, T, vocab_size]
        
        result = {'logits': logits}
        
        if return_measurements:
            result['measurements'] = self._compute_measurements(residuals, expert_ledgers)
        
        return result
    
    def _compute_measurements(self, residuals: list, expert_ledgers: list = None) -> dict:
        """
        Built-in measurement probes on residual stream activations.
        
        logdet(Σ + εI): Measures effective rank of activation covariance.
        Low logdet → activations collapsing. High logdet → healthy diversity.
        
        Expert ledger: routing entropy, expert utilization, load balance.
        """
        measurements = {}
        logdets = []
        
        for i, r in enumerate(residuals):
            # Flatten batch and sequence
            h = r.reshape(-1, r.shape[-1])  # [B*T, d_model]
            
            # Center
            h = h - h.mean(dim=0, keepdim=True)
            
            # Covariance
            cov = (h.T @ h) / (h.shape[0] - 1)
            
            # Log determinant with regularization
            try:
                logdet = torch.logdet(cov + self.cfg.logdet_eps * torch.eye(cov.shape[0], device=cov.device))
                logdets.append(logdet.item())
            except:
                logdets.append(float('nan'))
        
        if logdets:
            valid = [v for v in logdets if not math.isnan(v)]
            measurements['logdet_per_layer'] = logdets
            measurements['logdet_mean'] = sum(valid) / len(valid) if valid else float('nan')
            measurements['logdet_spread'] = max(valid) - min(valid) if valid else float('nan')
        
        # Expert ledger summaries
        if expert_ledgers:
            # Per-layer expert utilization (fraction of tokens each expert handles)
            expert_util = []
            for layer_idx, ledger in enumerate(expert_ledgers):
                counts = ledger['expert_counts']  # [n_experts]
                total = counts.sum().item()
                if total > 0:
                    util = (counts / total).tolist()
                else:
                    util = [0.0] * len(counts)
                expert_util.append(util)
            measurements['expert_utilization'] = expert_util
            
            # Routing entropy (higher = more balanced expert usage)
            entropies = []
            for layer_idx, ledger in enumerate(expert_ledgers):
                counts = ledger['expert_counts']
                total = counts.sum().item()
                if total > 0:
                    probs = counts / total
                    ent = -(probs * torch.log(probs + 1e-8)).sum().item()
                    entropies.append(ent)
                else:
                    entropies.append(0.0)
            measurements['routing_entropy'] = entropies
            measurements['routing_entropy_mean'] = sum(entropies) / len(entropies) if entropies else 0.0
            
            # Router logit statistics (first layer, first token as representative)
            first_ledger = expert_ledgers[0]
            rl = first_ledger['router_logits']  # [B, T, n_experts]
            measurements['router_logit_mean'] = rl.mean().item()
            measurements['router_logit_std'] = rl.std().item()
        
        return measurements
    
    def generate(self, idx: torch.Tensor, max_new_tokens: int, temperature: float = 0.8) -> torch.Tensor:
        """Autoregressive generation."""
        self.eval()
        with torch.no_grad():
            for _ in range(max_new_tokens):
                # Crop context if needed
                idx_cond = idx[:, -self.cfg.max_seq_len:]
                
                # Forward
                result = self.forward(idx_cond)
                logits = result['logits'][:, -1, :]  # Last position
                
                # Temperature
                logits = logits / temperature
                
                # Sample
                probs = F.softmax(logits, dim=-1)
                idx_next = torch.multinomial(probs, num_samples=1)
                
                # Append
                idx = torch.cat([idx, idx_next], dim=1)
        
        self.train()
        return idx
    
    def estimate_mfu(self, batch_size: int, seq_len: int) -> float:
        """Estimate Model FLOPs Utilization (MFU). Rough estimate for CPU."""
        # Forward FLOPs per token
        n_params = self.n_params
        flops_per_token = 6 * n_params  # Rough: 2 forward + 4 backward FLOPs per param
        total_flops = flops_per_token * batch_size * seq_len
        # CPU FLOPs (rough: 50 GFLOPS for Ryzen AI 7 350)
        cpu_flops = 50e9
        return total_flops / cpu_flops
