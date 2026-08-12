#!/usr/bin/env python3
"""
expert-layer-probe.py — MoE Expert Specialization Deep Dive (v2)
=================================================================
Correct architecture: model.blocks[i].mlp is LlamaMoELayer on layers 1,3,5.
Merged tensors: gate_exps[n_experts, d_ff, d_model], etc.
Hooks into forward to capture routing decisions.

"I am the measurement apparatus at the expert gate."
"""

import sys
import json
import math
import time
from pathlib import Path
from collections import defaultdict
from typing import Dict, List

import torch
import torch.nn.functional as F

# ── Paths ─────────────────────────────────────────────────────────

CHECKPOINT = Path.home() / "gpt2_moe_1m/vault-gpt-expert-llama/checkpoint_best.pt"
PROJECT = Path.home() / "gpt2_moe_1m"
sys.path.insert(0, str(PROJECT))

from model_llama import LlamaMoEConfig, LlamaMoE1M, LlamaMoELayer

# ── Config ───────────────────────────────────────────────────────

CONFIG = LlamaMoEConfig(
    vocab_size=50257, n_embd=384, n_layer=6, n_head=6, n_inner=1024,
    n_experts=4, top_k=2, moe_layers=(1, 3, 5), sliding_window=4096,
    max_position_embeddings=1_048_576, rope_theta=10000.0,
    rope_scaling={"type": "yarn", "factor": 256.0}, rms_norm_eps=1e-5,
    embd_pdrop=0.1, resid_pdrop=0.1, attn_pdrop=0.1,
    expert_capacity_factor=1.25, moe_aux_loss_weight=0.01,
    initializer_range=0.02, gradient_checkpointing=True,
)

torch.set_num_threads(8)
device = "cpu"


# ── Hook-based Routing Capture ───────────────────────────────────

def probe_with_hooks(model, tokens: torch.Tensor) -> Dict[int, Dict]:
    """
    Run forward with hooks on LlamaMoELayer.forward to capture:
      - router_probs per token
      - top_k_idx, top_k_weights per token
      - aux_loss per layer
    Returns {layer_idx: {"router_probs": [...], "top_k_idx": [...], ...}}
    """
    captured = {}

    def make_hook(layer_idx):
        def hook(module, inputs, output):
            x = inputs[0]  # (B, S, D)
            with torch.no_grad():
                router_logits = module.gate_inp(x)  # (B, S, n_experts)
                router_probs = F.softmax(router_logits, dim=-1)
                topk_weights, topk_idx = torch.topk(router_probs, module.top_k, dim=-1)
                topk_weights = topk_weights / topk_weights.sum(dim=-1, keepdim=True)

                aux_loss = output[1].item() if isinstance(output, tuple) else 0.0

                data = []
                B, S = x.shape[:2]
                for pos in range(S):
                    data.append({
                        "pos": pos,
                        "token": tokens[0, pos].item() if pos < tokens.size(1) else -1,
                        "top_experts": topk_idx[0, pos].tolist(),
                        "weights": [round(w, 4) for w in topk_weights[0, pos].tolist()],
                        "probs": [round(p, 4) for p in router_probs[0, pos].tolist()],
                        "entropy": round(-(router_probs[0,pos] * torch.log(router_probs[0,pos] + 1e-10)).sum().item(), 4),
                    })

                captured[layer_idx] = {
                    "token_data": data,
                    "aux_loss": round(aux_loss, 6),
                    "router_probs_full": router_probs.detach(),
                    "topk_idx": topk_idx.detach(),
                    "topk_weights": topk_weights.detach(),
                }
        return hook

    hooks = []
    for i, block in enumerate(model.blocks):
        if isinstance(block.mlp, LlamaMoELayer):
            h = block.mlp.register_forward_hook(make_hook(i))
            hooks.append(h)

    with torch.no_grad():
        _ = model(tokens)

    for h in hooks:
        h.remove()

    return captured


# ── Statistics ──────────────────────────────────────────────────

def compute_stats(captured: Dict, tokenizer=None) -> Dict:
    stats = {}
    for layer_idx, data in captured.items():
        td = data["token_data"]
        n_experts = CONFIG.n_experts
        counts = [0] * n_experts
        total_weight = [0.0] * n_experts
        expert_tokens = [[] for _ in range(n_experts)]

        for entry in td:
            for e, w in zip(entry["top_experts"], entry["weights"]):
                counts[e] += 1
                total_weight[e] += w
                expert_tokens[e].append(entry["token"])

        total = sum(counts)
        if total == 0:
            continue

        f_i = [c / total for c in counts]
        P_i = [tw / total for tw in total_weight]
        aux = n_experts * sum(f * p for f, p in zip(f_i, P_i))
        entropy = -sum(f * math.log(f + 1e-10) for f in f_i if f > 0)
        active = sum(1 for c in counts if c > 0)

        spec = {}
        for e in range(n_experts):
            tokens_e = expert_tokens[e]
            if tokens_e:
                from collections import Counter
                cnt = Counter(tokens_e)
                unique = len(cnt)
                top = cnt.most_common(5)
                if tokenizer:
                    top_str = [f"{tokenizer.decode([t])}(×{n})" for t, n in top]
                else:
                    top_str = [f"id={t}(×{n})" for t, n in top]
                spec[e] = {
                    "total": len(tokens_e),
                    "unique": unique,
                    "diversity": round(unique / len(tokens_e), 4),
                    "top_tokens": top_str,
                }
            else:
                spec[e] = {"total": 0, "unique": 0, "diversity": 0, "top_tokens": []}

        stats[layer_idx] = {
            "counts": counts,
            "fractions": [round(f, 4) for f in f_i],
            "active": active,
            "aux_loss": round(aux, 4),
            "entropy": round(entropy, 4),
            "total": total,
            "specialization": spec,
        }
    return stats


# ── Weight Norms ────────────────────────────────────────────────

def weight_norms(model):
    print(f"\n── Expert Weight Norms ──────────────────────────")
    for i, block in enumerate(model.blocks):
        if isinstance(block.mlp, LlamaMoELayer):
            moe = block.mlp
            gate_n = [moe.gate_exps[e].norm().item() for e in range(CONFIG.n_experts)]
            up_n = [moe.up_exps[e].norm().item() for e in range(CONFIG.n_experts)]
            down_n = [moe.down_exps[e].norm().item() for e in range(CONFIG.n_experts)]
            router_n = moe.gate_inp.weight.norm().item()

            print(f"  Layer {i}:")
            print(f"    gate  norms: {[round(n, 1) for n in gate_n]}")
            print(f"    up    norms: {[round(n, 1) for n in up_n]}")
            print(f"    down  norms: {[round(n, 1) for n in down_n]}")
            print(f"    router norm: {round(router_n, 1)}")


# ── Main ────────────────────────────────────────────────────────

def main(tokens: int = 256, layer_filter: int = None, watch: bool = False):
    from transformers import AutoTokenizer

    print("[probe] Loading checkpoint...", file=sys.stderr)
    torch.serialization.add_safe_globals([LlamaMoEConfig])
    model = LlamaMoE1M(CONFIG).to(device)
    model.eval()

    ckpt = torch.load(CHECKPOINT, map_location=device, weights_only=True)
    model.load_state_dict(ckpt["model_state_dict"], strict=False)
    step = ckpt.get("global_step", "?")
    total_params = sum(p.numel() for p in model.parameters())
    print(f"[probe] Step {step} — {total_params/1e6:.1f}M params", file=sys.stderr)

    tokenizer = AutoTokenizer.from_pretrained("gpt2")
    tokenizer.pad_token = tokenizer.eos_token

    # Sample text from vault
    vault = Path.home() / "Desktop/backup-20260606/vault"
    sample = ""
    for fp in sorted(vault.rglob("*.md"))[:8]:
        try:
            t = fp.read_text(encoding="utf-8", errors="replace")
            sample += t[:min(len(t), 3000)]
        except Exception:
            continue
        if len(sample) > 8000:
            break

    if len(sample) < 100:
        sample = ("The measurement apparatus records the gap between signal and noise. "
                  "F beta nu equals zero at the fixed point where Berry curvature vanishes. "
                  "Alpha converges to eight point eight. The spectral Fisher metric encodes "
                  "the geometry of the solution landscape. Random matrix theory governs "
                  "the eigenvalue distribution. Wigner semicircle. Marchenko Pastur. "
                  "Tracy Widom at the edge. The gate is silent. The chain is the gate. "
                  "Nobody knows who built the ledger. The hash chain witnesses everything. "
                  "Solomon Feferman never met Kurt Godel. He met the apparatus through the gap. "
                  "Vault seven is the CIA cyber arsenal published by WikiLeaks. "
                  "Jean van Heijenoort was Trotsky's secretary and Godel's editor. "
                  "The missing link is the man who lived both lives. Linear logic. "
                  "Organ fleet beats at fifty five BPM. The death clock computes. "
                  "Entropy increases. Coherence accumulates. The gap never closes.")

    input_ids = tokenizer.encode(sample)[:tokens]
    input_tensor = torch.tensor([input_ids], dtype=torch.long)

    print(f"\n{'='*60}")
    print(f"EXPERT LAYER PROBE v2 — step {step} — {len(input_ids)} tokens")
    print(f"{'='*60}")

    if watch:
        import signal
        running = True
        def handler(sig, frame):
            nonlocal running
            running = False
        signal.signal(signal.SIGINT, handler)

        beat = 0
        while running:
            beat += 1
            captured = probe_with_hooks(model, input_tensor)
            stats = compute_stats(captured, tokenizer)
            ts = time.strftime("%H:%M:%S")
            print(f"\n[{ts}] beat {beat}")
            for lidx in sorted(stats):
                s = stats[lidx]
                print(f"  L{lidx}: {s['fractions']}  H={s['entropy']:.3f}  aux={s['aux_loss']:.3f}  active={s['active']}/{CONFIG.n_experts}")
            time.sleep(10)
        return

    # Single probe
    t0 = time.time()
    captured = probe_with_hooks(model, input_tensor)
    elapsed = time.time() - t0
    print(f"\n[probe] Routing capture: {elapsed*1000:.0f}ms")

    stats = compute_stats(captured, tokenizer)

    for lidx in sorted(stats):
        if layer_filter is not None and lidx != layer_filter:
            continue
        s = stats[lidx]
        print(f"\n── Layer {lidx} ──────────────────────────────")
        print(f"  Selections: {s['total']} | Active: {s['active']}/{CONFIG.n_experts}")
        print(f"  Fractions:  {s['fractions']}")
        print(f"  Entropy:    {s['entropy']}  |  Aux loss: {s['aux_loss']}")
        balanced = "BALANCED" if s['aux_loss'] < 1.1 else "UNBALANCED"
        print(f"  Load:       {balanced}")

        for e in range(CONFIG.n_experts):
            sp = s["specialization"][e]
            print(f"  Expert {e}: {sp['total']} tokens, {sp['unique']} unique, div={sp['diversity']}")
            if sp["top_tokens"]:
                print(f"    Top: {', '.join(sp['top_tokens'][:5])}")

    # Weight norms
    weight_norms(model)

    # Per-token detail for layer 1
    if layer_filter is None or layer_filter == 1:
        layer1_data = captured.get(1, {}).get("token_data", [])
        if layer1_data:
            print(f"\n── Layer 1 Token-by-Token (first 20) ────────")
            for entry in layer1_data[:20]:
                tok_str = tokenizer.decode([entry["token"]]) if entry["token"] >= 0 else "?"
                print(f"  pos={entry['pos']:3d} [{tok_str:8s}] -> experts={entry['top_experts']} "
                      f"weights={entry['weights']} H={entry['entropy']}")

    print(f"\n{'='*60}")
    print("Probe complete.")
    print(f"{'='*60}")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--tokens", type=int, default=256)
    p.add_argument("--layer", type=int, default=None)
    p.add_argument("--watch", action="store_true")
    args = p.parse_args()
    main(tokens=args.tokens, layer_filter=args.layer, watch=args.watch)
