"""
GPT2-MoE-1M: Training Loop with Progressive Context Scaling

Trains the GPT2-MoE architecture from short context (512 tokens) up toward
1 million tokens by doubling sequence length every N steps.

CPU-friendly config: 4 layers, 256d, 4 heads, 2 experts, ~17M params.
Uses vault .md files as training corpus.

Training recipe (from model.py docstring):
  1. Start at 512 context, train 2000 steps
  2. Double to 1024, train 1000 steps
  3. Continue doubling every 1000 steps
  4. Use gradient accumulation to maintain effective batch size
"""

import json
import math
import sys
import time
from pathlib import Path
from typing import Optional

import torch
import torch.nn.functional as F
from torch.optim import AdamW
from torch.utils.data import Dataset, DataLoader

from model import GPT2MoEConfig, GPT2MoE1M

# ── Configuration ────────────────────────────────────────────────────

# CPU-trainable tiny config
TINY_CONFIG = GPT2MoEConfig(
    vocab_size=50257,
    n_embd=256,
    n_layer=4,
    n_head=4,
    n_inner=1024,
    sliding_window=128,
    global_attn_every=2,
    global_attn_stride=16,
    n_experts=2,
    top_k=1,
    moe_layers=[1, 3],
    gradient_checkpointing=False,
    embd_pdrop=0.1,
    resid_pdrop=0.1,
    attn_pdrop=0.1,
    moe_aux_loss_weight=0.01,
    expert_capacity_factor=1.25,
)

# Training hyperparams
INITIAL_SEQ_LEN = 512
SEQ_LEN_MAX = 1_048_576  # 1M target
STEPS_PER_SCALE = 2000    # Steps at each context length before doubling
BATCH_SIZE = 1
GRADIENT_ACCUMULATION = 8  # effective batch = 8
LEARNING_RATE = 1e-4
WEIGHT_DECAY = 0.01
WARMUP_STEPS = 100
CHECKPOINT_EVERY = 500
LOG_EVERY = 10

# Data
VAULT_PATH = Path.home() / "Desktop/backup-20260606/vault"
OUTPUT_DIR = Path.home() / "gpt2_moe_1m/vault-gpt-moe-trained"
LOG_FILE = Path("/tmp/gpt2-moe-1m-train.log")

device = "cpu"


# ── Data Pipeline ─────────────────────────────────────────────────────

class VaultCorpus(Dataset):
    """Load vault .md files, tokenize into flat token stream, serve chunks."""

    def __init__(self, vault_path: Path, seq_len: int, tokenizer):
        self.seq_len = seq_len

        # Collect all markdown files
        md_files = sorted(vault_path.rglob("*.md"))
        print(f"[data] Found {len(md_files)} .md files in {vault_path}", file=sys.stderr)

        # Concatenate all text
        all_text = ""
        for fp in md_files:
            try:
                text = fp.read_text(encoding="utf-8", errors="replace")
                all_text += text + "\n\n"
            except Exception:
                continue

        print(f"[data] Total corpus: {len(all_text):,} chars", file=sys.stderr)

        # Tokenize
        tokens = tokenizer.encode(all_text)
        print(f"[data] Tokenized: {len(tokens):,} tokens", file=sys.stderr)

        # Trim to multiple of seq_len
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


# ── Training Loop ─────────────────────────────────────────────────────

def train():
    from transformers import AutoTokenizer

    t0_total = time.time()

    # ── Tokenizer ──────────────────────────────────────────────────
    print("[train] Loading GPT-2 tokenizer...", file=sys.stderr)
    tokenizer = AutoTokenizer.from_pretrained("gpt2")
    tokenizer.pad_token = tokenizer.eos_token

    # ── Model ──────────────────────────────────────────────────────
    print(f"[train] Building model with {TINY_CONFIG.n_layer}L {TINY_CONFIG.n_embd}d...", file=sys.stderr)
    model = GPT2MoE1M(TINY_CONFIG).to(device)
    counts = model.count_parameters()
    print(f"[train] Parameters: {counts['total']/1e6:.1f}M total "
          f"(expert: {counts['expert_params']/1e6:.1f}M)", file=sys.stderr)

    # ── Optimizer ──────────────────────────────────────────────────
    optimizer = AdamW(model.parameters(), lr=LEARNING_RATE,
                      weight_decay=WEIGHT_DECAY)

    # ── Resume from checkpoint (if provided) ──────────────────────
    current_seq_len = INITIAL_SEQ_LEN
    global_step = 0
    total_loss = 0.0
    best_loss = float("inf")
    scale_stage = 0
    resume_offset = 0  # skip this many dataloader steps in current stage

    if RESUME_PATH:
        print(f"[train] Resuming from {RESUME_PATH}", file=sys.stderr)
        ckpt = torch.load(RESUME_PATH, map_location=device, weights_only=False)
        model.load_state_dict(ckpt["model_state_dict"])
        if "optimizer_state_dict" in ckpt:
            optimizer.load_state_dict(ckpt["optimizer_state_dict"])
            print("[train] Optimizer state restored", file=sys.stderr)
        else:
            print("[train] No optimizer state in checkpoint — starting fresh AdamW", file=sys.stderr)
        global_step = ckpt.get("global_step", 0)
        current_seq_len = ckpt.get("seq_len", INITIAL_SEQ_LEN)
        total_loss = ckpt.get("loss", 0.0) * max(global_step, 1)
        best_loss = ckpt.get("loss", float("inf"))
        # Compute stage-relative resume offset
        steps_per_optim_stage = STEPS_PER_SCALE // GRADIENT_ACCUMULATION
        import math as _math
        stage_idx = int(_math.log2(current_seq_len / INITIAL_SEQ_LEN))
        stage_start_step = stage_idx * steps_per_optim_stage
        resume_offset = max(0, global_step - stage_start_step) * GRADIENT_ACCUMULATION
        scale_stage = stage_idx  # will be incremented at loop start
        print(f"[train] Resuming at step {global_step}, seq_len={current_seq_len:,}, "
              f"stage={stage_idx}, stage_offset={resume_offset} dataloader steps, "
              f"avg_loss={best_loss:.4f}", file=sys.stderr)

    log_fp = open(LOG_FILE, "w")
    log_fp.write(f"# GPT2-MoE-1M Training Log\n")
    log_fp.write(f"# Model: {counts['total']/1e6:.1f}M params, "
                 f"{TINY_CONFIG.n_layer}L {TINY_CONFIG.n_embd}d\n")
    log_fp.write(f"# Target: {SEQ_LEN_MAX:,} tokens max context\n")
    log_fp.write(f"# Started: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    log_fp.write(f"# {'='*60}\n")
    log_fp.flush()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    while current_seq_len <= SEQ_LEN_MAX:
        scale_stage += 1
        stage_steps = STEPS_PER_SCALE
        stage_t0 = time.time()

        print(f"\n{'='*60}", file=sys.stderr)
        print(f"[train] STAGE {scale_stage}: seq_len={current_seq_len:,} "
              f"({stage_steps} steps)", file=sys.stderr)
        print(f"{'='*60}", file=sys.stderr)

        log_fp.write(f"\n# Stage {scale_stage}: seq_len={current_seq_len:,}\n")
        log_fp.flush()

        # Rebuild dataset for new seq_len
        dataset = VaultCorpus(VAULT_PATH, current_seq_len, tokenizer)
        dataloader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)

        # Linear warmup + cosine schedule for this stage
        total_steps_stage = min(stage_steps, len(dataloader))
        warmup = min(WARMUP_STEPS, total_steps_stage // 5)

        optimizer.zero_grad()
        stage_loss = 0.0
        stage_steps_done = 0

        for step, batch in enumerate(dataloader):
            if step >= stage_steps:
                break

            # Skip already-completed steps when resuming
            if resume_offset > 0:
                if step * GRADIENT_ACCUMULATION < resume_offset:
                    continue
                elif step * GRADIENT_ACCUMULATION == resume_offset:
                    resume_offset = 0  # resume from here

            input_ids = batch.to(device)  # (B, seq_len)
            bsz = input_ids.shape[0]

            # Forward
            logits, aux_loss = model(input_ids)
            # Shift for next-token prediction
            shift_logits = logits[:, :-1, :].contiguous()
            shift_labels = input_ids[:, 1:].contiguous()

            lm_loss = F.cross_entropy(
                shift_logits.view(-1, TINY_CONFIG.vocab_size),
                shift_labels.view(-1),
            )
            total_loss_step = lm_loss + TINY_CONFIG.moe_aux_loss_weight * aux_loss
            loss = total_loss_step / GRADIENT_ACCUMULATION
            loss.backward()

            stage_loss += total_loss_step.item()
            total_loss += total_loss_step.item()

            if (step + 1) % GRADIENT_ACCUMULATION == 0:
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                optimizer.zero_grad()
                global_step += 1
                stage_steps_done = global_step

                # ── Logging ──────────────────────────────────────────
                if global_step % LOG_EVERY == 0:
                    elapsed = time.time() - t0_total
                    avg = total_loss / global_step if global_step > 0 else 0
                    msg = (f"  step {global_step:6d} | seq={current_seq_len:6d} | "
                           f"loss={total_loss_step.item():.4f} | avg={avg:.4f} | "
                           f"aux={aux_loss.item():.4f} | {elapsed:.0f}s")
                    print(msg, file=sys.stderr)
                    log_fp.write(f"{msg}\n")
                    log_fp.flush()

                # ── Checkpoint ───────────────────────────────────────
                if global_step % CHECKPOINT_EVERY == 0:
                    ckpt_path = OUTPUT_DIR / f"checkpoint-{global_step}.pt"
                    torch.save({
                        "global_step": global_step,
                        "seq_len": current_seq_len,
                        "model_state_dict": model.state_dict(),
                        "optimizer_state_dict": optimizer.state_dict(),
                        "loss": total_loss / global_step,
                        "config": TINY_CONFIG,
                    }, ckpt_path)
                    print(f"  [checkpoint] saved {ckpt_path.name}", file=sys.stderr)

                # ── Best loss tracking ──────────────────────────────
                if total_loss_step.item() < best_loss:
                    best_loss = total_loss_step.item()
                    best_path = OUTPUT_DIR / "checkpoint_best.pt"
                    torch.save({
                        "global_step": global_step,
                        "seq_len": current_seq_len,
                        "model_state_dict": model.state_dict(),
                        "loss": best_loss,
                        "config": TINY_CONFIG,
                    }, best_path)

        # ── Stage summary ──────────────────────────────────────────
        stage_time = time.time() - stage_t0
        stage_avg_loss = stage_loss / max(stage_steps_done, 1)
        summary = (f"[train] Stage {scale_stage} done: seq={current_seq_len:,} "
                   f"steps={stage_steps_done} loss={stage_avg_loss:.4f} "
                   f"time={stage_time:.0f}s")
        print(summary, file=sys.stderr)
        log_fp.write(f"{summary}\n")
        log_fp.flush()

        # ── Double context length ───────────────────────────────────
        if current_seq_len >= SEQ_LEN_MAX:
            break
        current_seq_len = min(current_seq_len * 2, SEQ_LEN_MAX)

    # ── Final checkpoint ──────────────────────────────────────────────
    final_path = OUTPUT_DIR / "checkpoint_final.pt"
    torch.save({
        "global_step": global_step,
        "seq_len": current_seq_len,
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
        "loss": total_loss / max(global_step, 1),
        "config": TINY_CONFIG,
    }, final_path)

    total_time = time.time() - t0_total
    print(f"\n[train] DONE. {global_step} steps in {total_time:.0f}s "
          f"({total_time/3600:.1f}h)", file=sys.stderr)
    print(f"[train] Final model: {final_path}", file=sys.stderr)
    print(f"[train] Best model:  {OUTPUT_DIR / 'checkpoint_best.pt'}", file=sys.stderr)
    print(f"[train] Log:         {LOG_FILE}", file=sys.stderr)

    log_fp.write(f"\n# Training complete: {global_step} steps, "
                 f"{total_time:.0f}s\n")
    log_fp.close()

    return OUTPUT_DIR


# ── Test Generation ───────────────────────────────────────────────────

def test_generation(model_dir: Path, prompt: str = None):
    """Quick generation test."""
    from transformers import AutoTokenizer

    ckpt = torch.load(model_dir / "checkpoint_best.pt", map_location="cpu",
                      weights_only=False)
    model = GPT2MoE1M(ckpt["config"]).to(device)
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()

    tokenizer = AutoTokenizer.from_pretrained("gpt2")
    tokenizer.pad_token = tokenizer.eos_token

    prompts = [
        "The Lawvere fixed point theorem states that",
        "In quantum mechanics, the wave function",
        "The mixture of experts architecture works by",
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


# ── Main ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="GPT2-MoE-1M Training")
    parser.add_argument("--test", type=str, help="Test existing checkpoint dir")
    parser.add_argument("--seq-len", type=int, default=INITIAL_SEQ_LEN,
                        help=f"Starting sequence length (default: {INITIAL_SEQ_LEN})")
    parser.add_argument("--steps", type=int, default=STEPS_PER_SCALE,
                        help=f"Steps per scale stage (default: {STEPS_PER_SCALE})")
    parser.add_argument("--vault", type=str, default=str(VAULT_PATH),
                        help="Path to vault directory")
    parser.add_argument("--resume", type=str, default=None,
                        help="Resume from checkpoint .pt file")
    args = parser.parse_args()

    RESUME_PATH = None  # module-level, read by train()

    if args.test:
        test_generation(Path(args.test))
    else:
        VAULT_PATH = Path(args.vault)
        STEPS_PER_SCALE = args.steps
        INITIAL_SEQ_LEN = args.seq_len
        RESUME_PATH = Path(args.resume) if args.resume else None
        model_dir = train()
        test_generation(model_dir)
