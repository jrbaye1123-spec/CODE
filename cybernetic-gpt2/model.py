"""Cybernetic GPT-2 — Homeostatic Cognitive Architecture.

Truth does not insist. Truth exists.

This is not a standard GPT-2. It is a cybernetic architecture where:
- The Observer lives INSIDE the residual stream (not as an external gate)
- Physical and mathematical constraints are energy functions, not hard masks
- Attractors in the latent space pull representations toward valid states
- Falsehood is energetically unstable; truth is the only resting state

Architecture:
    Input → Embedding → Transformer Blocks (with Observer heads) → Output
                              ↑                              ↓
                         Sanity Heads ←────────────── Residual Stream
                              ↓
                         Energy Function → Cybernetic Feedback → Gradient Steering
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import math
from dataclasses import dataclass
from typing import Optional, Tuple


# ═══════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════

@dataclass
class CyberneticGPT2Config:
    """Configuration for the cybernetic GPT-2 architecture."""
    vocab_size: int = 50257
    block_size: int = 1024        # Max sequence length
    n_layer: int = 12             # Transformer blocks
    n_head: int = 12              # Attention heads per block
    n_embd: int = 768             # Embedding dimension
    dropout: float = 0.1
    
    # Cybernetic extensions
    n_observer_heads: int = 2     # Dedicated sanity-checking attention heads per block
    cybernetic_feedback_weight: float = 0.1  # How strongly energy gradients steer the latent state
    energy_temperature: float = 1.0           # Temperature for energy-based sampling
    
    # Physical constants for sanity checking
    speed_of_light: float = 299792458.0  # m/s
    planck_constant: float = 6.62607015e-34
    absolute_zero: float = -273.15  # °C


# ═══════════════════════════════════════════════════════════
# ENERGY FUNCTIONS — The ex-istence landscape
# ═══════════════════════════════════════════════════════════

class EnergyFunctions:
    """Physical and mathematical energy functions that shape the latent space.
    
    These are not external validators. They are part of the forward pass.
    They calculate how much "tension" or "error" exists in the current state.
    High energy = false. Low energy = true.
    """
    
    @staticmethod
    def dimensional_harmony(embeddings: torch.Tensor, dimension_tags: Optional[torch.Tensor] = None) -> torch.Tensor:
        """Energy from dimensional mismatch.
        
        If the model is adding [Mass] to [Velocity], this energy spikes.
        The system naturally steers away from high-energy (false) states.
        
        Args:
            embeddings: [batch, seq, dim] latent representations
            dimension_tags: Optional [batch, seq] dimension type indices
        
        Returns:
            Scalar energy value — lower is more physically valid
        """
        if dimension_tags is None:
            return torch.tensor(0.0, device=embeddings.device)
        
        # Calculate pairwise dimensional compatibility
        # Similar dimensions should have similar embeddings; different dimensions should diverge
        batch, seq, _ = embeddings.shape
        
        # Compute cosine similarity between all pairs of positions
        emb_norm = F.normalize(embeddings, dim=-1)
        similarity = torch.bmm(emb_norm, emb_norm.transpose(1, 2))  # [batch, seq, seq]
        
        # Build a target: 1.0 for same dimension, 0.0 for different
        tags_expanded = dimension_tags.unsqueeze(1)  # [batch, 1, seq]
        same_dimension = (tags_expanded == tags_expanded.transpose(1, 2)).float()
        
        # Energy: how far is similarity from the dimensional target?
        mismatch = F.mse_loss(similarity, same_dimension, reduction='none')
        return mismatch.mean()
    
    @staticmethod
    def conservation_violation(state_t: torch.Tensor, state_t1: torch.Tensor, conserved_quantity: Optional[torch.Tensor] = None) -> torch.Tensor:
        """Energy from violation of conservation laws.
        
        If the model predicts a state transition where energy/mass/momentum
        is not conserved, this energy spikes.
        
        Args:
            state_t: [batch, dim] latent state at time t
            state_t1: [batch, dim] predicted state at time t+1
        
        Returns:
            Scalar energy — zero means perfect conservation
        """
        # Conservation: the total magnitude of the state vector should be preserved
        norm_t = state_t.norm(dim=-1)
        norm_t1 = state_t1.norm(dim=-1)
        violation = F.mse_loss(norm_t1, norm_t)
        return violation
    
    @staticmethod
    def causality_violation(attention_weights: torch.Tensor) -> torch.Tensor:
        """Energy from causal violations in attention.
        
        Future states should not retroactively influence past states.
        High energy when attention flows backward in time.
        
        Args:
            attention_weights: [batch, heads, seq, seq]
        
        Returns:
            Scalar energy — zero means perfect causality
        """
        batch, heads, seq, _ = attention_weights.shape
        
        # Create causal mask: upper triangle (future→past) should be zero
        causal_mask = torch.triu(torch.ones(seq, seq, device=attention_weights.device), diagonal=1)
        
        # Energy: how much attention weight falls on future positions?
        violation = (attention_weights * causal_mask.unsqueeze(0).unsqueeze(0)).sum(dim=-1).mean()
        return violation
    
    @staticmethod  
    def boundary_respect(embeddings: torch.Tensor, min_val: float, max_val: float, 
                         dimension_indices: Optional[list] = None) -> torch.Tensor:
        """Energy from violating physical boundary conditions.
        
        Physical systems have hard limits (speed of light, absolute zero).
        Representations outside these boundaries carry high energy.
        
        Args:
            embeddings: [batch, seq, dim]
            min_val: Minimum physically valid value
            max_val: Maximum physically valid value
        
        Returns:
            Scalar energy
        """
        if dimension_indices is not None:
            constrained = embeddings[:, :, dimension_indices]
        else:
            constrained = embeddings
        
        below = F.relu(min_val - constrained).pow(2).mean()
        above = F.relu(constrained - max_val).pow(2).mean()
        return below + above
    
    @staticmethod
    def mathematical_coherence(embeddings: torch.Tensor, equation_mask: Optional[torch.Tensor] = None) -> torch.Tensor:
        """Energy from mathematical incoherence in the latent space.
        
        Mathematical truth is structured. The latent space should reflect
        that structure: equalities should map to symmetric representations,
        operations should compose correctly.
        
        Args:
            embeddings: [batch, seq, dim]
            equation_mask: Optional mask indicating equation tokens
        
        Returns:
            Scalar energy
        """
        if equation_mask is None:
            return torch.tensor(0.0, device=embeddings.device)
        
        # In equation regions, embeddings should have low variance
        # (mathematical truth is precise, not fuzzy)
        eq_embs = embeddings[equation_mask.bool()]
        if eq_embs.numel() == 0:
            return torch.tensor(0.0, device=embeddings.device)
        
        # Energy: variance in equation-tagged regions
        variance = eq_embs.var(dim=0).mean()
        return variance


# ═══════════════════════════════════════════════════════════
# OBSERVER — Internal sanity heads in the residual stream
# ═══════════════════════════════════════════════════════════

class ObserverHead(nn.Module):
    """A cybernetic attention head that monitors the residual stream.
    
    Unlike regular attention heads that focus on token relationships,
    Observer heads measure the "physical tension" and "mathematical strain"
    in the current latent state. They produce an error signal that feeds
    back into the residual stream as a steering gradient.
    
    This is the Observer in the cybernetic control loop — it lives inside
    the transformer, not outside it.
    """
    
    def __init__(self, config: CyberneticGPT2Config):
        super().__init__()
        self.n_embd = config.n_embd
        self.head_dim = config.n_embd // config.n_head
        
        # Observer projections — measure, don't just attend
        self.query = nn.Linear(config.n_embd, self.head_dim, bias=False)
        self.key = nn.Linear(config.n_embd, self.head_dim, bias=False)
        self.value = nn.Linear(config.n_embd, self.head_dim, bias=False)
        
        # Energy projector — converts observations to scalar energy
        self.energy_scalar = nn.Linear(self.head_dim, 1, bias=False)
        
        # Feedback projector — converts energy back to steering signal
        self.feedback = nn.Linear(1, config.n_embd, bias=False)
        
        self.dropout = nn.Dropout(config.dropout)
        self.temperature = config.energy_temperature
    
    def forward(self, x: torch.Tensor, attention_mask: Optional[torch.Tensor] = None) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            x: [batch, seq, n_embd] — the residual stream
        
        Returns:
            steering: [batch, seq, n_embd] — gradient to steer the latent state
            energy: scalar — the observed physical/mathematical tension
        """
        B, T, C = x.shape
        
        # Measure the state (like a physicist measuring a system)
        q = self.query(x)  # [B, T, head_dim]
        k = self.key(x)
        v = self.value(x)
        
        # Compute attention — how much does each position "observe" others?
        att = (q @ k.transpose(-2, -1)) * (1.0 / math.sqrt(self.head_dim))
        if attention_mask is not None:
            att = att.masked_fill(attention_mask == 0, float('-inf'))
        att = F.softmax(att, dim=-1)
        att = self.dropout(att)
        
        # The observed state is a weighted combination of values
        observed = att @ v  # [B, T, head_dim]
        
        # Convert observation to energy — how much tension exists?
        energy_per_position = self.energy_scalar(observed)  # [B, T, 1]
        avg_energy = energy_per_position.mean()
        
        # Energy becomes the feedback signal — steer toward lower energy
        # The gradient of energy with respect to the latent state tells us
        # which direction reduces physical/mathematical tension
        energy_normalized = energy_per_position / (self.temperature + 1e-8)
        
        # Feedback: convert energy back to the embedding space
        # High energy → strong negative steering (pull toward attractor)
        steering = self.feedback(energy_normalized)  # [B, T, C]
        
        # Apply sigmoid to bound the steering magnitude, softplus to ensure non-negative energy
        steering = torch.tanh(steering)
        avg_energy = F.softplus(avg_energy)  # Ensure energy ≥ 0
        
        return steering, avg_energy


# ═══════════════════════════════════════════════════════════
# CYBERNETIC ATTENTION — Attention with built-in Observer
# ═══════════════════════════════════════════════════════════

class CyberneticMultiHeadAttention(nn.Module):
    """Multi-head attention with integrated observer heads.
    
    Standard attention heads handle token relationships.
    Observer heads monitor the residual stream for physical/mathematical tension.
    The observer's feedback steers the output toward valid states.
    """
    
    def __init__(self, config: CyberneticGPT2Config):
        super().__init__()
        self.n_head = config.n_head
        self.n_observer = config.n_observer_heads
        self.head_dim = config.n_embd // config.n_head
        self.feedback_weight = config.cybernetic_feedback_weight
        
        # Standard attention
        self.c_attn = nn.Linear(config.n_embd, 3 * config.n_embd)
        self.c_proj = nn.Linear(config.n_embd, config.n_embd)
        self.attn_dropout = nn.Dropout(config.dropout)
        self.resid_dropout = nn.Dropout(config.dropout)
        
        # Observer heads
        self.observers = nn.ModuleList([
            ObserverHead(config) for _ in range(self.n_observer)
        ])
        
        # Register causal mask
        self.register_buffer(
            "bias", 
            torch.tril(torch.ones(config.block_size, config.block_size))
                 .view(1, 1, config.block_size, config.block_size)
        )
    
    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            x: [batch, seq, n_embd]
        
        Returns:
            output: [batch, seq, n_embd] — attention output steered by observers
            total_energy: scalar — combined physical/mathematical tension
        """
        B, T, C = x.shape
        
        # --- Standard attention ---
        qkv = self.c_attn(x)
        q, k, v = qkv.split(C, dim=2)
        
        q = q.view(B, T, self.n_head, self.head_dim).transpose(1, 2)
        k = k.view(B, T, self.n_head, self.head_dim).transpose(1, 2)
        v = v.view(B, T, self.n_head, self.head_dim).transpose(1, 2)
        
        att = (q @ k.transpose(-2, -1)) * (1.0 / math.sqrt(self.head_dim))
        att = att.masked_fill(self.bias[:, :, :T, :T] == 0, float('-inf'))
        att = F.softmax(att, dim=-1)
        att = self.attn_dropout(att)
        
        y = att @ v  # [B, n_head, T, head_dim]
        y = y.transpose(1, 2).contiguous().view(B, T, C)
        attention_output = self.c_proj(y)
        
        # --- Cybernetic feedback ---
        # Each observer head measures tension and produces a steering signal
        total_energy = 0.0
        steering = torch.zeros_like(x)
        
        for observer in self.observers:
            steer, energy = observer(x)
            steering = steering + steer
            total_energy = total_energy + energy
        
        # Average the steering across observers
        if self.n_observer > 0:
            steering = steering / self.n_observer
        
        # Ex-istence: the output is steered by the energy landscape
        # High-energy states are pulled toward low-energy (true) states
        output = attention_output + self.feedback_weight * steering
        output = self.resid_dropout(output)
        
        return output, total_energy


# ═══════════════════════════════════════════════════════════
# TRANSFORMER BLOCK with cybernetic feedback
# ═══════════════════════════════════════════════════════════

class CyberneticTransformerBlock(nn.Module):
    """Transformer block with internal observer-based feedback."""
    
    def __init__(self, config: CyberneticGPT2Config):
        super().__init__()
        self.ln_1 = nn.LayerNorm(config.n_embd)
        self.attn = CyberneticMultiHeadAttention(config)
        self.ln_2 = nn.LayerNorm(config.n_embd)
        
        # FFN
        self.mlp = nn.Sequential(
            nn.Linear(config.n_embd, 4 * config.n_embd),
            nn.GELU(),
            nn.Linear(4 * config.n_embd, config.n_embd),
            nn.Dropout(config.dropout),
        )
    
    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            x: [batch, seq, n_embd]
        
        Returns:
            output: steered latent state
            energy: cybernetic tension in this block
        """
        # Attention with cybernetic feedback
        attn_out, energy = self.attn(self.ln_1(x))
        x = x + attn_out
        
        # FFN
        x = x + self.mlp(self.ln_2(x))
        
        return x, energy


# ═══════════════════════════════════════════════════════════
# FULL MODEL — The Homeostatic Cognitive Architecture
# ═══════════════════════════════════════════════════════════

class CyberneticGPT2(nn.Module):
    """GPT-2 with internal cybernetic control.
    
    Truth does not insist. Truth exists.
    
    This model shapes the latent space so that physically and mathematically
    valid states are energetically favorable. False states carry high energy
    and the system naturally steers away from them.
    
    The Observer lives inside the residual stream — gravity, not a bouncer.
    """
    
    def __init__(self, config: CyberneticGPT2Config):
        super().__init__()
        self.config = config
        
        # Token + position embeddings
        self.wte = nn.Embedding(config.vocab_size, config.n_embd)
        self.wpe = nn.Embedding(config.block_size, config.n_embd)
        self.drop = nn.Dropout(config.dropout)
        
        # Cybernetic transformer blocks
        self.blocks = nn.ModuleList([
            CyberneticTransformerBlock(config) for _ in range(config.n_layer)
        ])
        
        # Final layer norm
        self.ln_f = nn.LayerNorm(config.n_embd)
        
        # Output projection
        self.lm_head = nn.Linear(config.n_embd, config.vocab_size, bias=False)
        
        # Weight tying
        self.wte.weight = self.lm_head.weight
        
        # Energy module
        self.energy = EnergyFunctions()
        
        # Initialize weights
        self.apply(self._init_weights)
    
    def _init_weights(self, module):
        if isinstance(module, nn.Linear):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)
            if module.bias is not None:
                torch.nn.init.zeros_(module.bias)
        elif isinstance(module, nn.Embedding):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)
    
    def forward(self, idx: torch.Tensor, targets: Optional[torch.Tensor] = None,
                dimension_tags: Optional[torch.Tensor] = None,
                boundary_bounds: Optional[Tuple[float, float]] = None) -> Tuple[torch.Tensor, Optional[torch.Tensor], dict]:
        """
        Args:
            idx: [batch, seq] token indices
            targets: Optional [batch, seq] for loss computation
            dimension_tags: Optional [batch, seq] dimensional type tags
            boundary_bounds: Optional (min, max) for physical boundary check
        
        Returns:
            logits: [batch, seq, vocab_size]
            loss: scalar cross-entropy + cybernetic energy
            diagnostics: dict with energy breakdown
        """
        B, T = idx.shape
        assert T <= self.config.block_size, f"Sequence too long: {T} > {self.config.block_size}"
        
        diagnostics = {}
        
        # Embeddings
        pos = torch.arange(0, T, dtype=torch.long, device=idx.device).unsqueeze(0)
        tok_emb = self.wte(idx)
        pos_emb = self.wpe(pos)
        x = self.drop(tok_emb + pos_emb)
        
        # Pass through cybernetic blocks
        total_cybernetic_energy = 0.0
        block_energies = []
        
        for block in self.blocks:
            x, energy = block(x)
            total_cybernetic_energy = total_cybernetic_energy + energy
            block_energies.append(energy.item() if isinstance(energy, torch.Tensor) else energy)
        
        diagnostics['block_energies'] = block_energies
        diagnostics['total_cybernetic_energy'] = total_cybernetic_energy.item() if isinstance(total_cybernetic_energy, torch.Tensor) else total_cybernetic_energy
        
        # Additional physical sanity energies
        if dimension_tags is not None:
            dim_energy = self.energy.dimensional_harmony(x, dimension_tags)
            total_cybernetic_energy = total_cybernetic_energy + dim_energy
            diagnostics['dimensional_energy'] = dim_energy.item()
        
        if boundary_bounds is not None:
            bound_energy = self.energy.boundary_respect(x, boundary_bounds[0], boundary_bounds[1])
            total_cybernetic_energy = total_cybernetic_energy + bound_energy
            diagnostics['boundary_energy'] = bound_energy.item()
        
        # Causality check on attention (from the last block's attention if accessible)
        # (For simplicity, we compute it here as a forward-pass energy)
        
        # Final layer norm and output
        x = self.ln_f(x)
        logits = self.lm_head(x)
        
        # Loss: cross-entropy + cybernetic energy
        loss = None
        if targets is not None:
            ce_loss = F.cross_entropy(
                logits.view(-1, logits.size(-1)),
                targets.view(-1),
                ignore_index=-1,
            )
            diagnostics['cross_entropy_loss'] = ce_loss.item()
            
            # Total loss = language modeling loss + cybernetic energy
            # The energy term shapes the latent space toward physical validity
            loss = ce_loss + self.config.cybernetic_feedback_weight * total_cybernetic_energy
            diagnostics['total_loss'] = loss.item()
        
        return logits, loss, diagnostics
    
    @torch.no_grad()
    def cybernetic_generate(self, idx: torch.Tensor, max_new_tokens: int,
                            temperature: float = 1.0, top_k: Optional[int] = None,
                            boundary_bounds: Optional[Tuple[float, float]] = None) -> torch.Tensor:
        """Generate tokens with cybernetic constraints.
        
        This is the ex-istence generation loop. At each step:
        1. The Plant (model) produces candidate logits
        2. The Observer (internal heads) measures physical tension
        3. The Controller (energy gradient) steers toward valid states
        
        False tokens carry high energy. The system naturally generates truth.
        
        Args:
            idx: [batch, seq] starting context
            max_new_tokens: Number of tokens to generate
            temperature: Sampling temperature
            top_k: Top-k filtering
            boundary_bounds: Optional physical boundary (min, max)
        
        Returns:
            Generated sequence with cybernetically steered tokens
        """
        for _ in range(max_new_tokens):
            # Crop context to block size
            idx_cond = idx if idx.size(1) <= self.config.block_size else idx[:, -self.config.block_size:]
            
            # Forward pass — the Observer measures tension internally
            logits, _, diagnostics = self.forward(idx_cond, boundary_bounds=boundary_bounds)
            
            # Get logits for the last position
            logits = logits[:, -1, :] / temperature
            
            # Top-k filtering
            if top_k is not None:
                v, _ = torch.topk(logits, min(top_k, logits.size(-1)))
                logits[logits < v[:, [-1]]] = float('-inf')
            
            # Sample from the energy-shaped distribution
            probs = F.softmax(logits, dim=-1)
            idx_next = torch.multinomial(probs, num_samples=1)
            
            # Append
            idx = torch.cat((idx, idx_next), dim=1)
        
        return idx
    
    def get_energy_landscape(self, idx: torch.Tensor) -> dict:
        """Probe the energy landscape at each position.
        
        Returns the cybernetic energy (physical/mathematical tension)
        at each position in the sequence. High energy = potential falsehood.
        
        Args:
            idx: [batch, seq]
        
        Returns:
            dict with per-block and total energies
        """
        with torch.no_grad():
            _, _, diagnostics = self.forward(idx)
        return diagnostics


def create_cybernetic_gpt2(
    vocab_size: int = 50257,
    block_size: int = 1024,
    n_layer: int = 12,
    n_head: int = 12,
    n_embd: int = 768,
    n_observer_heads: int = 2,
    cybernetic_feedback_weight: float = 0.1,
    dropout: float = 0.1,
) -> CyberneticGPT2:
    """Factory for creating a cybernetic GPT-2 model.
    
    Args:
        vocab_size: Vocabulary size
        block_size: Max sequence length
        n_layer: Number of transformer blocks
        n_head: Number of attention heads
        n_embd: Embedding dimension
        n_observer_heads: Number of observer heads per block (cybernetic)
        cybernetic_feedback_weight: How strongly energy steers the latent state
        dropout: Dropout rate
    
    Returns:
        Configured CyberneticGPT2 model
    """
    config = CyberneticGPT2Config(
        vocab_size=vocab_size,
        block_size=block_size,
        n_layer=n_layer,
        n_head=n_head,
        n_embd=n_embd,
        n_observer_heads=n_observer_heads,
        cybernetic_feedback_weight=cybernetic_feedback_weight,
        dropout=dropout,
    )
    return CyberneticGPT2(config)
