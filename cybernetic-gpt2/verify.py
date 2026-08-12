"""Verification — Cybernetic GPT-2: build, forward, generate, energy landscape."""

import sys
import torch

# Add parent to path
sys.path.insert(0, '/home/nakamichi/cybernetic-gpt2')
from model import CyberneticGPT2, CyberneticGPT2Config, EnergyFunctions, create_cybernetic_gpt2


def main():
    p = 0
    f = 0
    
    def ok(name, cond, detail=""):
        nonlocal p, f
        if cond:
            p += 1
            print(f"  OK  {name}")
        else:
            f += 1
            print(f"  FAIL {name}  {detail}")
    
    print("=" * 50)
    print("CYBERNETIC GPT-2 — VERIFICATION")
    print("=" * 50)
    
    # --- 1. Model creation ---
    print("\n[1] Model creation")
    config = CyberneticGPT2Config(
        vocab_size=1000,
        block_size=128,
        n_layer=4,
        n_head=4,
        n_embd=256,
        n_observer_heads=2,
        cybernetic_feedback_weight=0.1,
    )
    model = CyberneticGPT2(config)
    ok("model created", model is not None)
    
    param_count = sum(p.numel() for p in model.parameters())
    ok("has parameters", param_count > 0, f"params={param_count}")
    ok("has blocks", len(model.blocks) == config.n_layer)
    ok("has observer heads", len(model.blocks[0].attn.observers) == config.n_observer_heads)
    ok("has energy module", model.energy is not None)
    
    # --- 2. Forward pass ---
    print("\n[2] Forward pass")
    batch_size, seq_len = 2, 32
    idx = torch.randint(0, config.vocab_size, (batch_size, seq_len))
    targets = torch.randint(0, config.vocab_size, (batch_size, seq_len))
    
    logits, loss, diagnostics = model.forward(idx, targets=targets)
    ok("logits shape", logits.shape == (batch_size, seq_len, config.vocab_size),
       f"got {logits.shape}")
    ok("loss is scalar", loss is not None and loss.dim() == 0,
       f"loss shape={loss.shape if loss is not None else None}")
    ok("diagnostics has block_energies", "block_energies" in diagnostics)
    ok("diagnostics has total_cybernetic_energy", "total_cybernetic_energy" in diagnostics)
    ok("diagnostics has cross_entropy_loss", "cross_entropy_loss" in diagnostics)
    ok("diagnostics has total_loss", "total_loss" in diagnostics)
    
    block_energies = diagnostics.get("block_energies", [])
    ok("block energies are scalars", all(isinstance(e, (int, float)) for e in block_energies))
    ok("total cybernetic energy non-negative", 
       diagnostics.get("total_cybernetic_energy", -1) >= 0,
       f"got {diagnostics.get('total_cybernetic_energy')}")
    
    print(f"  cross_entropy_loss: {diagnostics.get('cross_entropy_loss', '?'):.4f}")
    print(f"  cybernetic_energy: {diagnostics.get('total_cybernetic_energy', '?'):.4f}")
    print(f"  total_loss: {diagnostics.get('total_loss', '?'):.4f}")
    
    # --- 3. Forward pass with dimension tags ---
    print("\n[3] Forward pass with dimensional constraints")
    dim_tags = torch.randint(0, 3, (batch_size, seq_len))  # 3 dimension types
    logits2, loss2, diag2 = model.forward(idx, targets=targets, dimension_tags=dim_tags)
    ok("dimensional energy computed", "dimensional_energy" in diag2)
    ok("dimensional energy non-negative", diag2.get("dimensional_energy", -1) >= 0)
    
    # --- 4. Forward pass with boundary bounds ---
    print("\n[4] Forward pass with physical boundaries")
    logits3, loss3, diag3 = model.forward(idx, targets=targets, boundary_bounds=(-1.0, 1.0))
    ok("boundary energy computed", "boundary_energy" in diag3)
    ok("boundary energy non-negative", diag3.get("boundary_energy", -1) >= 0)
    
    # --- 5. Cybernetic generation ---
    print("\n[5] Cybernetic generation")
    seed = torch.randint(0, config.vocab_size, (1, 8))
    generated = model.cybernetic_generate(seed, max_new_tokens=16, temperature=0.8, top_k=50)
    ok("generation produces output", generated.shape[1] == 24)  # 8 + 16
    ok("generation within vocab", (generated < config.vocab_size).all())
    ok("generation preserves seed", (generated[0, :8] == seed[0]).all())
    
    # --- 6. Energy landscape ---
    print("\n[6] Energy landscape probing")
    energy_map = model.get_energy_landscape(idx)
    ok("energy map has block_energies", "block_energies" in energy_map)
    ok("energy map has total_energy", "total_cybernetic_energy" in energy_map)
    
    # --- 7. EnergyFunctions unit tests ---
    print("\n[7] EnergyFunctions")
    ef = EnergyFunctions()
    
    # Dimensional harmony
    emb = torch.randn(2, 8, 64)
    tags = torch.randint(0, 3, (2, 8))
    dh = ef.dimensional_harmony(emb, tags)
    ok("dimensional_harmony returns scalar", dh.dim() == 0)
    
    # Conservation violation
    s1 = torch.randn(2, 64)
    s2 = torch.randn(2, 64) * 1.5  # Deliberately different
    cv = ef.conservation_violation(s1, s2)
    ok("conservation_violation returns scalar", cv.dim() == 0)
    
    # Boundary respect
    br = ef.boundary_respect(emb, -1.0, 1.0)
    ok("boundary_respect returns scalar", br.dim() == 0)
    
    # Mathematical coherence
    eq_mask = torch.zeros(2, 8, dtype=torch.bool)
    eq_mask[:, 2:5] = True
    mc = ef.mathematical_coherence(emb, eq_mask)
    ok("mathematical_coherence returns scalar", mc.dim() == 0)
    
    # --- Summary ---
    print(f"\n{'=' * 50}")
    print(f"  PASSED: {p}  FAILED: {f}")
    print(f"{'=' * 50}")
    
    return 0 if f == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
