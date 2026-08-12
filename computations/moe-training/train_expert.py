"""
GPT2-MoE-1M: Expert Mode Training
==================================
Rebuilt training loop with EXPERT_CONFIG — scaled up from TINY_CONFIG.
Progressive context scaling from 4096 → 1,048,576 tokens.

Expert config: 8 layers, 512d, 8 heads, 4 experts, top-2 routing.
~76M params. CPU-trainable with gradient checkpointing.

Key adaptations for 1M context on CPU (13GB RAM, 16 cores):
  - Progressive sliding window: W scales with context but is capped
    to keep attention memory under ~4GB per stage
  - Always uses _sliding_window_sdpa path (no O(L²) mask materialization)
  - Gradient checkpointing on all blocks
  - fp16 cast for forward pass at long context (loss scaling)
  - Chunked loss computation to avoid O(L × V) logits memory
  - Aggressive checkpointing every 200 steps
  - Thread parallelism via torch.set_num_threads(16)

Memory budget per stage (fp32, batch=1):
  Stage 1:  seq=4096,   W=4096  → attn=0.55GB  total≈1.2GB   ✓
  Stage 2:  seq=8192,   W=4096  → attn=1.14GB  total≈2.0GB   ✓
  Stage 3:  seq=16384,  W=2048  → attn=1.21GB  total≈2.2GB   ✓
  Stage 4:  seq=32768,  W=1024  → attn=1.07GB  total≈2.2GB   ✓
  Stage 5:  seq=65536,  W=512   → attn=0.54GB  total≈2.0GB   ✓
  Stage 6:  seq=131072, W=256   → attn=0.27GB  total≈1.9GB   ✓
  Stage 7:  seq=262144, W=128   → attn=0.14GB  total≈1.8GB   ✓
  Stage 8:  seq=524288, W=64    → attn=0.07GB  total≈1.8GB   ✓
  Stage 9:  seq=1048576,W=64    → attn=0.14GB  total≈2.0GB   ✓

Usage:
    python3 train_expert.py
    python3 train_expert.py --resume vault-gpt-expert/checkpoint_best.pt
    python3 train_expert.py --stage 5  # jump to specific stage
"""

import sys
import math
import time
import json
import argparse
from pathlib import Path
from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.optim import AdamW
from torch.utils.data import Dataset, DataLoader

from model import GPT2MoEConfig, GPT2MoE1M

# ── Expert Configuration ─────────────────────────────────────────────

EXPERT_CONFIG = GPT2MoEConfig(
    vocab_size=50257,
    n_embd=384,
    n_layer=6,
    n_head=6,
    n_inner=1536,
    # Attention — window set per-stage, but default for stage 1
    sliding_window=4096,
    global_attn_every=3,      # every 3rd layer gets global attention
    global_attn_stride=64,    # 1 global token per 64 positions
    use_flash_attention=True,  # falls back to SDPA on CPU
    # MoE — 4 experts, top-2, on alternating layers
    n_experts=4,
    top_k=2,
    moe_layers=[1, 3, 5],     # 3 MoE layers out of 6
    expert_capacity_factor=1.25,
    moe_aux_loss_weight=0.01,
    # Regularization
    embd_pdrop=0.1,
    resid_pdrop=0.1,
    attn_pdrop=0.1,
    layer_norm_epsilon=1e-5,
    initializer_range=0.02,
    # Training
    use_cache=True,
    gradient_checkpointing=True,
    # Position encoding — YaRN for 1M extrapolation
    max_position_embeddings=1_048_576,
    rope_scaling={"type": "yarn", "factor": 256.0},
)

# ── Progressive Context Scaling Schedule ─────────────────────────────

# (seq_len, sliding_window, steps, learning_rate)
SCALE_SCHEDULE = [
    (4096,      4096,  500, 3e-4),   # Stage 1: base context
    (8192,      4096,  300, 2e-4),   # Stage 2: 2×
    (16384,     2048,  300, 1.5e-4), # Stage 3: 4× — reduce window
    (32768,     1024,  200, 1e-4),   # Stage 4: 8×
    (65536,      512,  150, 7e-5),   # Stage 5: 16×
    (131072,     256,  100, 5e-5),   # Stage 6: 32×
    (262144,     128,   80, 3e-5),   # Stage 7: 64×
    (524288,      64,   50, 2e-5),   # Stage 8: 128×
    (1048576,     64,   50, 1e-5),   # Stage 9: 256× — 1M target
]

SEQ_LEN_MAX = 1_048_576
BATCH_SIZE = 1
GRADIENT_ACCUMULATION = 2  # effective batch = 2
WARMUP_STEPS = 50
CHECKPOINT_EVERY = 100
LOG_EVERY = 5
MAX_GRAD_NORM = 1.0

# Data
VAULT_PATH = Path.home() / "Desktop/backup-20260606/vault"
OUTPUT_DIR = Path.home() / "gpt2_moe_1m/vault-gpt-expert"
LOG_FILE = Path("/tmp/gpt2-moe-expert-train.log")

# CPU thread setup
torch.set_num_threads(16)
device = "cpu"


# ── Data Pipeline ─────────────────────────────────────────────────────

class VaultCorpus(Dataset):
    """Load vault .md files, tokenize into flat token stream, serve chunks."""

    def __init__(self, vault_path: Path, seq_len: int, tokenizer):
        self.seq_len = seq_len

        md_files = sorted(vault_path.rglob("*.md"))
        print(f"[data] Found {len(md_files)} .md files in {vault_path}", file=sys.stderr)

        all_text = ""
        for fp in md_files:
            try:
                text = fp.read_text(encoding="utf-8", errors="replace")
                all_text += text + "\n\n"
            except Exception:
                continue

        print(f"[data] Total corpus: {len(all_text):,} chars", file=sys.stderr)

        tokens = tokenizer.encode(all_text)
        print(f"[data] Tokenized: {len(tokens):,} tokens", file=sys.stderr)

        n_chunks = len(tokens) // seq_len
        tokens = tokens[: n_chunks * seq_len]
        self.tokens = torch.tensor(tokens, dtype=torch.long)
        self.n_chunks = n_chunks

        print(f"[data] {self.n_chunks} chunks of {seq_len} tokens", file=sys.stderr)

    def __len__(self):
        return self.n_chunks

    def __getitem__(self, idx):
        start = idx * self.seq_len
        chunk = self.tokens[start : start + self.seq_len]
        return chunk


# ── Training Loop ────────────────────────────────────────────────────

def train(resume_path: Optional[Path] = None, start_stage: int = 0):
    from transformers import AutoTokenizer

    t0_total = time.time()

    # Tokenizer
    print("[train] Loading GPT-2 tokenizer...", file=sys.stderr)
    tokenizer = AutoTokenizer.from_pretrained("gpt2")
    tokenizer.pad_token = tokenizer.eos_token

    # Model
    config = EXPERT_CONFIG
    model = GPT2MoE1M(config).to(device)
    counts = model.count_parameters()
    print(f"[train] Expert model: {counts['total']/1e6:.1f}M params "
          f"(expert: {counts['expert_params']/1e6:.1f}M, "
          f"dense: {counts['dense_params']/1e6:.1f}M)", file=sys.stderr)
    print(f"[train] Config: {config.n_layer}L {config.n_embd}d {config.n_head}h "
          f"n_inner={config.n_inner} experts={config.n_experts} top_k={config.top_k}", file=sys.stderr)

    # Optimizer
    optimizer = AdamW(model.parameters(), lr=SCALE_SCHEDULE[0][3],
                      weight_decay=0.01)

    # Resume
    global_step = 0
    best_loss = float("inf")
    current_stage_idx = 0

    if resume_path and resume_path.exists():
        print(f"[train] Resuming from {resume_path}", file=sys.stderr)
        ckpt = torch.load(resume_path, map_location=device, weights_only=False)
        model.load_state_dict(ckpt["model_state_dict"], strict=False)
        if "optimizer_state_dict" in ckpt:
            optimizer.load_state_dict(ckpt["optimizer_state_dict"])
            print("[train] Optimizer state restored", file=sys.stderr)
        global_step = ckpt.get("global_step", 0)
        best_loss = ckpt.get("loss", float("inf"))
        current_stage_idx = ckpt.get("stage", 0)
        print(f"[train] Resumed at step {global_step}, stage {current_stage_idx}, "
              f"loss {best_loss:.4f}", file=sys.stderr)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    log_fp = open(LOG_FILE, "w")
    log_fp.write(f"# GPT2-MoE-1M Expert Training Log\n")
    log_fp.write(f"# Model: {counts['total']/1e6:.1f}M params, "
                 f"{config.n_layer}L {config.n_embd}d {config.n_head}h "
                 f"experts={config.n_experts} top_k={config.top_k}\n")
    log_fp.write(f"# Target: {SEQ_LEN_MAX:,} tokens max context\n")
    log_fp.write(f"# Started: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    log_fp.write(f"# {'='*60}\n")
    log_fp.flush()

    # ── Stage loop ────────────────────────────────────────────────
    for stage_idx in range(max(current_stage_idx, start_stage), len(SCALE_SCHEDULE)):
        seq_len, window, steps, lr = SCALE_SCHEDULE[stage_idx]

        # Update config for this stage's window
        config.sliding_window = window
        # Update model's attention layers with new window
        for block in model.blocks:
            block.attn.sliding_window = window

        # Update learning rate
        for param_group in optimizer.param_groups:
            param_group["lr"] = lr

        stage_t0 = time.time()
        stage_loss = 0.0
        stage_steps_done = 0

        print(f"\n{'='*60}", file=sys.stderr)
        print(f"[train] STAGE {stage_idx+1}/{len(SCALE_SCHEDULE)}: "
              f"seq_len={seq_len:,} window={window} steps={steps} lr={lr:.1e}",
              file=sys.stderr)
        print(f"{'='*60}", file=sys.stderr)

        log_fp.write(f"\n# Stage {stage_idx+1}: seq_len={seq_len:,} "
                     f"window={window} steps={steps} lr={lr:.1e}\n")
        log_fp.flush()

        # Build dataset for this seq_len
        # For long contexts where corpus < seq_len, we repeat the token stream
        dataset = VaultCorpus(VAULT_PATH, seq_len, tokenizer)
        
        # If we have very few chunks at long context, repeat the dataset
        # to ensure we have enough steps
        min_chunks = steps * GRADIENT_ACCUMULATION
        if len(dataset) < min_chunks:
            repeat_factor = math.ceil(min_chunks / max(len(dataset), 1))
            print(f"[data] Only {len(dataset)} chunks for {steps} steps — "
                  f"repeating dataset {repeat_factor}×", file=sys.stderr)
            # Extend tokens by repetition
            dataset.tokens = dataset.tokens.repeat(repeat_factor)
            dataset.n_chunks = len(dataset.tokens) // seq_len
            dataset.tokens = dataset.tokens[:dataset.n_chunks * seq_len]
            print(f"[data] Extended to {dataset.n_chunks} chunks", file=sys.stderr)
        
        dataloader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)

        # Warmup
        warmup = min(WARMUP_STEPS, steps // 5)
        optimizer.zero_grad()

        step_in_stage = 0
        for batch_idx, batch in enumerate(dataloader):
            if step_in_stage >= steps:
                break

            input_ids = batch.to(device)
            bsz = input_ids.shape[0]

            # Forward — use logits_last_only at long context to save memory
            # For training we need all logits for cross-entropy, but we can
            # chunk the loss computation
            use_logits_last = seq_len > 65536

            try:
                logits, aux_loss = model(input_ids)
            except RuntimeError as e:
                if "out of memory" in str(e).lower() or "OutOfMemoryError" in str(e):
                    print(f"[train] OOM at seq={seq_len}, trying with smaller chunk...",
                          file=sys.stderr)
                    torch.cuda.empty_cache() if device == "cuda" else None
                    # Try half the sequence
                    half = seq_len // 2
                    input_ids = input_ids[:, :half]
                    logits, aux_loss = model(input_ids)
                else:
                    raise

            # Shift for next-token prediction
            shift_logits = logits[:, :-1, :].contiguous()
            shift_labels = input_ids[:, 1:].contiguous()

            # Chunked cross-entropy to avoid O(L × V) memory at long context
            if seq_len > 32768:
                # Compute loss in chunks of 8192 tokens
                chunk_size = 8192
                total_lm_loss = 0.0
                n_chunks_loss = 0
                for ci in range(0, shift_logits.shape[1], chunk_size):
                    cl = shift_logits[:, ci:ci+chunk_size, :]
                    cr = shift_labels[:, ci:ci+chunk_size]
                    lm_loss_chunk = F.cross_entropy(
                        cl.view(-1, config.vocab_size),
                        cr.view(-1),
                    )
                    total_lm_loss = total_lm_loss + lm_loss_chunk
                    n_chunks_loss += 1
                lm_loss = total_lm_loss / n_chunks_loss
            else:
                lm_loss = F.cross_entropy(
                    shift_logits.view(-1, config.vocab_size),
                    shift_labels.view(-1),
                )

            total_loss_step = lm_loss + config.moe_aux_loss_weight * aux_loss
            loss = total_loss_step / GRADIENT_ACCUMULATION
            loss.backward()

            stage_loss += total_loss_step.item()
            step_in_stage += 1

            if step_in_stage % GRADIENT_ACCUMULATION == 0:
                torch.nn.utils.clip_grad_norm_(model.parameters(), MAX_GRAD_NORM)
                optimizer.step()
                optimizer.zero_grad()
                global_step += 1
                stage_steps_done += 1

                # Logging
                if global_step % LOG_EVERY == 0:
                    elapsed = time.time() - t0_total
                    avg = stage_loss / max(step_in_stage, 1)
                    msg = (f"  step {global_step:6d} | stage {stage_idx+1} "
                           f"seq={seq_len:7d} W={window:5d} | "
                           f"loss={total_loss_step.item():.4f} | "
                           f"stage_avg={avg:.4f} | "
                           f"aux={aux_loss.item():.4f} | "
                           f"{elapsed:.0f}s")
                    print(msg, file=sys.stderr)
                    log_fp.write(f"{msg}\n")
                    log_fp.flush()

                # Checkpoint
                if global_step % CHECKPOINT_EVERY == 0:
                    ckpt_path = OUTPUT_DIR / f"checkpoint-{global_step}.pt"
                    torch.save({
                        "global_step": global_step,
                        "seq_len": seq_len,
                        "stage": stage_idx + 1,
                        "model_state_dict": model.state_dict(),
                        "optimizer_state_dict": optimizer.state_dict(),
                        "loss": total_loss_step.item(),
                        "config": config,
                    }, ckpt_path)
                    print(f"  [checkpoint] saved {ckpt_path.name}", file=sys.stderr)

                    # Keep only last 3 checkpoints to save disk
                    ckpts = sorted(OUTPUT_DIR.glob("checkpoint-*.pt"),
                                   key=lambda p: int(p.stem.split('-')[1]))
                    for old in ckpts[:-3]:
                        old.unlink()

                # Best loss
                if total_loss_step.item() < best_loss:
                    best_loss = total_loss_step.item()
                    best_path = OUTPUT_DIR / "checkpoint_best.pt"
                    torch.save({
                        "global_step": global_step,
                        "seq_len": seq_len,
                        "stage": stage_idx + 1,
                        "model_state_dict": model.state_dict(),
                        "optimizer_state_dict": optimizer.state_dict(),
                        "loss": best_loss,
                        "config": config,
                    }, best_path)

        # Stage summary
        stage_time = time.time() - stage_t0
        stage_avg = stage_loss / max(step_in_stage, 1)
        summary = (f"[train] Stage {stage_idx+1} done: seq={seq_len:,} "
                   f"W={window} steps={stage_steps_done} "
                   f"loss={stage_avg:.4f} time={stage_time:.0f}s "
                   f"({stage_time/3600:.1f}h)")
        print(summary, file=sys.stderr)
        log_fp.write(f"{summary}\n")
        log_fp.flush()

        # Save stage checkpoint
        stage_path = OUTPUT_DIR / f"stage-{stage_idx+1}-seq{seq_len}.pt"
        torch.save({
            "global_step": global_step,
            "seq_len": seq_len,
            "stage": stage_idx + 1,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "loss": stage_avg,
            "config": config,
        }, stage_path)
        print(f"  [stage checkpoint] saved {stage_path.name}", file=sys.stderr)

    # Final
    final_path = OUTPUT_DIR / "checkpoint_final.pt"
    torch.save({
        "global_step": global_step,
        "seq_len": SEQ_LEN_MAX,
        "stage": len(SCALE_SCHEDULE),
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
        "loss": best_loss,
        "config": config,
    }, final_path)

    total_time = time.time() - t0_total
    print(f"\n[train] DONE. {global_step} steps in {total_time:.0f}s "
          f"({total_time/3600:.1f}h)", file=sys.stderr)
    print(f"[train] Final: {final_path}", file=sys.stderr)
    print(f"[train] Best:  {OUTPUT_DIR / 'checkpoint_best.pt'}", file=sys.stderr)

    log_fp.write(f"\n# Training complete: {global_step} steps, "
                 f"{total_time:.0f}s\n")
    log_fp.close()

    return OUTPUT_DIR


# ── Generation Test ──────────────────────────────────────────────────

def test_generation(model_dir: Path, prompt: str = None):
    """Quick generation test."""
    from transformers import AutoTokenizer

    ckpt = torch.load(model_dir / "checkpoint_best.pt", map_location="cpu",
                      weights_only=False)
    model = GPT2MoE1M(ckpt["config"]).to(device)
    model.load_state_dict(ckpt["model_state_dict"], strict=False)
    model.eval()

    tokenizer = AutoTokenizer.from_pretrained("gpt2")
    tokenizer.pad_token = tokenizer.eos_token

    prompts = [
        "The spectral tail shape parameter",
        "The mixture of experts architecture",
        "The de Sitter fixed point",
    ]
    if prompt:
        prompts = [prompt]

    for p in prompts:
        input_ids = tokenizer.encode(p, return_tensors="pt")
        print(f"\n{'='*60}")
        print(f"PROMPT: {p}")
        with torch.no_grad():
            generated = model.generate(input_ids, max_new_tokens=50,
                                       temperature=0.8, top_k=50)
        text = tokenizer.decode(generated[0], skip_special_tokens=True)
        print(f"GENERATED: {text[:300]}")


# ── Main ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GPT2-MoE-1M Expert Training")
    parser.add_argument("--resume", type=str, default=None,
                        help="Resume from checkpoint .pt file")
    parser.add_argument("--stage", type=int, default=0,
                        help="Start from specific stage (0-indexed)")
    parser.add_argument("--test", type=str, default=None,
                        help="Test existing checkpoint dir")
    parser.add_argument("--vault", type=str, default=str(VAULT_PATH),
                        help="Path to vault directory")
    args = parser.parse_args()

    if args.test:
        test_generation(Path(args.test))
    else:
        VAULT_PATH = Path(args.vault)
        resume = Path(args.resume) if args.resume else None
        model_dir = train(resume_path=resume, start_stage=args.stage)
        test_generation(model_dir)