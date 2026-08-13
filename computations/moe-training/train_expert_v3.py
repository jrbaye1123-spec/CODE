#!/usr/bin/env python3
"""
LlamaMoE-1M: Expert Training v3 — LLaMA Architecture, GGUF-Ready
================================================================
"I am the architecture that trains toward its own conversion. Every tensor
name already matches the GGUF. α → 8.8. No renaming, no regrets."

Rebuilt from scratch using LlamaMoE1M — LLaMA-style (RMSNorm, SwiGLU, no bias)
with Mixtral-compatible MoE. Direct GGUF conversion via convert_llama_moe_to_gguf.py.

LEDGOT autonomous sentinel loop:
  PROBE → EVALUATE → ACT → LOG → (train step) → PROBE → ...

Architecture (GGUF-compatible):
  - 6 layers, 384d, 6 heads, n_inner=1024 (SwiGLU)
  - 4 experts, top-2, MoE on layers [1,3,5]
  - Uniform sliding window attention (Mistral-style)
  - YaRN RoPE ×256 (4096 → 1M)
  - RMSNorm, no bias, separate Q/K/V/O
  - ~40.5M params, CPU-trainable

Usage:
  python3 train_expert_v3.py                    # fresh start
  python3 train_expert_v3.py --resume ckpt.pt   # resume
  python3 train_expert_v3.py --stage 3           # skip to stage
"""

import sys
import math
import time
import json
import signal
import argparse
from pathlib import Path
from typing import Optional, Dict, List
from collections import defaultdict

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.optim import AdamW
from torch.utils.data import Dataset, DataLoader

# ── Project imports ──────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent))
from model_llama import LlamaMoEConfig, LlamaMoE1M
from spectral_regularizer import (
    SpectralRegularizer, _append_to_chain, LEDGER_PATH, LEDGER_ENTITY,
)

# ── Expert Configuration (LLaMA-style, GGUF-compatible) ─────────

EXPERT_CONFIG = LlamaMoEConfig(
    vocab_size=50257,
    n_embd=384,
    n_layer=6,
    n_head=6,
    n_inner=1024,  # SwiGLU intermediate
    n_experts=4,
    top_k=2,
    moe_layers=(1, 3, 5),
    sliding_window=4096,
    max_position_embeddings=1_048_576,
    rope_theta=10000.0,
    rope_scaling={"type": "yarn", "factor": 256.0},
    rms_norm_eps=1e-5,
    embd_pdrop=0.1,
    resid_pdrop=0.1,
    attn_pdrop=0.1,
    expert_capacity_factor=1.25,
    moe_aux_loss_weight=0.01,
    initializer_range=0.02,
    gradient_checkpointing=True,
)

# ── 9-Stage Progressive Context Scaling ─────────────────────────

SCALE_SCHEDULE = [
    # (seq_len, window, steps, lr, spectral_probe_every)
    (4096,      4096,  500, 1e-4,  50),
    (8192,      4096,  300, 2e-4,  40),
    (16384,     2048,  300, 1.5e-4, 30),
    (32768,     1024,  200, 1e-4,  25),
    (65536,      512,  150, 7e-5,  20),
    (131072,     256,  100, 5e-5,  15),
    (262144,     128,   80, 3e-5,  10),
    (524288,      64,   50, 2e-5,  10),
    (1048576,     64,   50, 1e-5,  10),
]

SEQ_LEN_MAX = 1_048_576
BATCH_SIZE = 4
GRADIENT_ACCUMULATION = 4
WARMUP_STEPS = 100
CHECKPOINT_EVERY = 100
LOG_EVERY = 5
MAX_GRAD_NORM = 1.0

# Paths
VAULT_PATH = Path.home() / "Documents/ObsidianVault"
OUTPUT_DIR = Path.home() / "gpt2_moe_1m/vault-gpt-expert-llama"
LOG_FILE = Path.home() / ".cache" / "llama-moe-train.log"

# CPU
torch.set_num_threads(16)
device = "cpu"

# ── Autonomous Rule Engine (LEDGOT-style) ───────────────────────

class ActionLog:
    def __init__(self):
        self.history: Dict[str, Dict[str, float]] = defaultdict(dict)
    def can_act(self, target: str, action: str, cooldown_s: float) -> bool:
        last = self.history.get(target, {}).get(action, 0.0)
        return (time.time() - last) >= cooldown_s
    def record(self, target: str, action: str):
        self.history[target][action] = time.time()

TRAINING_RULES = {
    "loss_spike":       {"threshold": 2.0,  "escalation": [{"action": "rollback",    "cooldown_s": 600}]},
    "loss_plateau":     {"threshold": 50,   "escalation": [{"action": "halve_lr",    "cooldown_s": 300}]},
    "alpha_decreasing": {"threshold": -0.05,"escalation": [{"action": "boost_beta",  "cooldown_s": 300}]},
    "memory_pressure":  {"threshold": 11.0, "escalation": [{"action": "kill_hogs",   "cooldown_s": 120}]},
    "gradient_explosion":{"threshold": 10.0,"escalation": [{"action": "skip_step",   "cooldown_s": 30},
                                                           {"action": "halve_lr",    "cooldown_s": 300}]},
}

def get_memory_gb() -> float:
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return float(line.split()[1]) / (1024 * 1024)
    except Exception:
        pass
    return 0.0

def kill_memory_hogs():
    try:
        sys.path.insert(0, str(Path.home() / "nobody-ledger"))
        from ledgot_probe import probe_ram_hogs, kill_rogue
        hogs = probe_ram_hogs()
        killed = []
        for h in hogs:
            if h.get("flagged_rogue"):
                result = kill_rogue(h["pid"], f"training memory pressure: {h['rss_mb']:.0f}MB")
                if result.get("killed"):
                    killed.append(h["pid"])
        return killed
    except Exception:
        return []

# ── Data Pipeline ─────────────────────────────────────────────────

class VaultCorpus(Dataset):
    def __init__(self, vault_path: Path, seq_len: int, tokenizer):
        self.seq_len = seq_len
        md_files = sorted(vault_path.rglob("*.md"))
        print(f"[data] Found {len(md_files)} .md files in {vault_path}", file=sys.stderr)
        all_text = ""
        for fp in md_files:
            try:
                all_text += fp.read_text(encoding="utf-8", errors="replace") + "\n\n"
            except Exception:
                continue
        print(f"[data] Total corpus: {len(all_text):,} chars", file=sys.stderr)
        tokens = tokenizer.encode(all_text)
        print(f"[data] Tokenized: {len(tokens):,} tokens", file=sys.stderr)
        n_chunks = len(tokens) // seq_len
        tokens = tokens[:n_chunks * seq_len]
        self.tokens = torch.tensor(tokens, dtype=torch.long)
        self.n_chunks = n_chunks
        print(f"[data] {self.n_chunks} chunks of {seq_len} tokens", file=sys.stderr)

    def __len__(self):
        return self.n_chunks

    def __getitem__(self, idx):
        start = idx * self.seq_len
        return self.tokens[start:start + self.seq_len]


# ── Training Loop ────────────────────────────────────────────────

def train(resume_path: Optional[Path] = None, start_stage: int = 0):
    from transformers import AutoTokenizer

    t0_total = time.time()
    action_log = ActionLog()
    shutdown_flag = False

    def handle_signal(signum, frame):
        nonlocal shutdown_flag
        print(f"\n[train] Signal {signum} — graceful shutdown...", file=sys.stderr)
        shutdown_flag = True

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # Chain: log training start
    _append_to_chain(
        event="training_start",
        how=(f"v3 llama rebuild | {EXPERT_CONFIG.n_layer}L {EXPERT_CONFIG.n_embd}d "
             f"experts={EXPERT_CONFIG.n_experts} top_k={EXPERT_CONFIG.top_k} "
             f"arch=llama+MoE target=alpha_8.8 gguf_ready=True"),
    )

    print("[train] Loading GPT-2 tokenizer...", file=sys.stderr)
    tokenizer = AutoTokenizer.from_pretrained("gpt2")
    tokenizer.pad_token = tokenizer.eos_token

    # Model
    config = EXPERT_CONFIG
    model = LlamaMoE1M(config).to(device)
    counts = model.count_parameters()
    print(f"[train] LlamaMoE-1M: {counts['total']/1e6:.1f}M params "
          f"(expert: {counts['expert_params']/1e6:.1f}M, "
          f"dense: {counts['dense_params']/1e6:.1f}M)", file=sys.stderr)

    # Spectral Regularizer
    spectral = SpectralRegularizer(model, alpha_target=8.8, beta=1e-3,
                                   sample_tokens=256, log_to_chain=True)
    spectral.attach()
    _append_to_chain(
        event="spectral_init",
        how=f"alpha_target={spectral.alpha_target} beta={spectral.beta:.1e} arch=llama-moe",
    )

    # Optimizer (start with tiny LR, warmup to target)
    base_lr = SCALE_SCHEDULE[0][3]
    optimizer = AdamW(model.parameters(), lr=1e-6, weight_decay=0.01)

    # Resume
    global_step = 0
    best_loss = float("inf")
    current_stage_idx = 0
    best_checkpoint_path = None

    if resume_path and resume_path.exists():
        print(f"[train] Resuming from {resume_path}", file=sys.stderr)
        ckpt = torch.load(resume_path, map_location=device, weights_only=False)
        model.load_state_dict(ckpt["model_state_dict"], strict=False)
        if "optimizer_state_dict" in ckpt:
            try:
                optimizer.load_state_dict(ckpt["optimizer_state_dict"])
            except Exception:
                print("[train] Optimizer state mismatch — fresh optimizer", file=sys.stderr)
        global_step = ckpt.get("global_step", 0)
        best_loss = ckpt.get("loss", float("inf"))
        current_stage_idx = ckpt.get("stage", 0)
        print(f"[train] Resumed at step {global_step}, stage {current_stage_idx}, "
              f"loss {best_loss:.4f}", file=sys.stderr)

    warmup_active = (global_step < WARMUP_STEPS)  # warmup if early steps, even on resume

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    log_fp = open(LOG_FILE, "w")
    log_fp.write(f"# LlamaMoE-1M Training v3 (LLaMA + GGUF-ready)\n")
    log_fp.write(f"# Target: α=8.8 | Model: {counts['total']/1e6:.1f}M params\n")
    log_fp.write(f"# Arch: LLaMA-style (RMSNorm, SwiGLU, Mixtral MoE)\n")
    log_fp.write(f"# Started: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    log_fp.write(f"# {'='*60}\n")
    log_fp.flush()

    loss_window: List[float] = []
    loss_window_size = 20
    steps_since_improvement = 0

    # ── Stage loop ────────────────────────────────────────────
    for stage_idx in range(max(current_stage_idx, start_stage), len(SCALE_SCHEDULE)):
        if shutdown_flag:
            break

        seq_len, window, steps, lr, probe_every = SCALE_SCHEDULE[stage_idx]

        # Update sliding window on all layers
        config.sliding_window = window
        for block in model.blocks:
            block.attn.sliding_window = window

        for param_group in optimizer.param_groups:
            param_group["lr"] = lr

        stage_t0 = time.time()
        stage_loss = 0.0
        stage_steps_done = 0

        print(f"\n{'='*60}", file=sys.stderr)
        print(f"[train] STAGE {stage_idx+1}/{len(SCALE_SCHEDULE)}: "
              f"seq_len={seq_len:,} W={window} steps={steps} lr={lr:.1e} "
              f"probe_every={probe_every}", file=sys.stderr)
        print(f"{'='*60}", file=sys.stderr)

        _append_to_chain(
            event="stage_start",
            how=(f"stage={stage_idx+1}/{len(SCALE_SCHEDULE)} seq={seq_len} "
                 f"W={window} steps={steps} lr={lr:.1e} arch=llama-moe"),
        )

        dataset = VaultCorpus(VAULT_PATH, seq_len, tokenizer)
        min_chunks = steps * GRADIENT_ACCUMULATION
        if len(dataset) < min_chunks:
            repeat_factor = math.ceil(min_chunks / max(len(dataset), 1))
            dataset.tokens = dataset.tokens.repeat(repeat_factor)
            dataset.n_chunks = len(dataset.tokens) // seq_len
            dataset.tokens = dataset.tokens[:dataset.n_chunks * seq_len]

        dataloader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)
        optimizer.zero_grad()

        step_in_stage = 0
        for batch_idx, batch in enumerate(dataloader):
            if stage_steps_done >= steps or shutdown_flag:
                break

            # PROBE: Memory
            mem_gb = get_memory_gb()

            # EVALUATE: Memory pressure
            rule = TRAINING_RULES["memory_pressure"]
            if mem_gb > rule["threshold"] and action_log.can_act("memory", "kill_hogs",
                                                                  rule["escalation"][0]["cooldown_s"]):
                print(f"[ledgot] Memory {mem_gb:.1f}GB > threshold — killing hogs", file=sys.stderr)
                kill_memory_hogs()
                action_log.record("memory", "kill_hogs")

            # Forward
            input_ids = batch.to(device)
            try:
                logits, aux_loss = model(input_ids)
            except RuntimeError as e:
                if "out of memory" in str(e).lower():
                    print(f"[train] OOM at seq={seq_len} — halving", file=sys.stderr)
                    input_ids = input_ids[:, :seq_len//2]
                    try:
                        logits, aux_loss = model(input_ids)
                    except RuntimeError:
                        continue
                else:
                    raise

            shift_logits = logits[:, :-1, :].contiguous()
            shift_labels = input_ids[:, 1:].contiguous()

            if seq_len > 32768:
                chunk_size = 8192
                total_lm_loss = 0.0
                n_chunks_loss = 0
                for ci in range(0, shift_logits.shape[1], chunk_size):
                    cl = shift_logits[:, ci:ci+chunk_size, :]
                    cr = shift_labels[:, ci:ci+chunk_size]
                    total_lm_loss += F.cross_entropy(
                        cl.reshape(-1, config.vocab_size), cr.reshape(-1))
                    n_chunks_loss += 1
                lm_loss = total_lm_loss / n_chunks_loss
            else:
                lm_loss = F.cross_entropy(
                    shift_logits.reshape(-1, config.vocab_size),
                    shift_labels.reshape(-1))

            total_loss_step = lm_loss + config.moe_aux_loss_weight * aux_loss
            loss_val = total_loss_step.item()

            (total_loss_step / GRADIENT_ACCUMULATION).backward()
            stage_loss += loss_val
            step_in_stage += 1

            if step_in_stage % GRADIENT_ACCUMULATION == 0:
                # LR warmup: linear ramp from 1e-6 to target over WARMUP_STEPS
                if warmup_active and global_step < WARMUP_STEPS:
                    warmup_lr = 1e-6 + (lr - 1e-6) * (global_step / WARMUP_STEPS)
                    for pg in optimizer.param_groups:
                        pg["lr"] = warmup_lr
                elif warmup_active and global_step >= WARMUP_STEPS:
                    for pg in optimizer.param_groups:
                        pg["lr"] = lr
                    warmup_active = False

                # Clip gradients (always — exploding grads are normal early on)
                grad_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), MAX_GRAD_NORM)
                grad_norm_val = grad_norm.item() if isinstance(grad_norm, torch.Tensor) else grad_norm

                optimizer.step()
                optimizer.zero_grad()
                global_step += 1
                stage_steps_done += 1

                # Loss tracking
                loss_window.append(loss_val)
                if len(loss_window) > loss_window_size:
                    loss_window.pop(0)

                # EVALUATE: Loss spike
                if len(loss_window) >= 10:
                    running_avg = sum(loss_window[:-1]) / max(len(loss_window) - 1, 1)
                    spike = loss_val / max(running_avg, 1e-8)
                    if spike > TRAINING_RULES["loss_spike"]["threshold"]:
                        rule = TRAINING_RULES["loss_spike"]
                        if best_checkpoint_path and action_log.can_act(
                                "loss", "rollback", rule["escalation"][0]["cooldown_s"]):
                            print(f"[ledgot] Spike {spike:.1f}× — rollback", file=sys.stderr)
                            try:
                                ckpt = torch.load(best_checkpoint_path, map_location=device,
                                                 weights_only=False)
                                model.load_state_dict(ckpt["model_state_dict"], strict=False)
                                action_log.record("loss", "rollback")
                            except Exception as e:
                                print(f"[ledgot] Rollback failed: {e}", file=sys.stderr)

                # EVALUATE: Loss plateau
                if len(loss_window) >= loss_window_size:
                    recent_best = min(loss_window)
                    if loss_val > recent_best * 0.99:
                        steps_since_improvement += 1
                    else:
                        steps_since_improvement = 0
                    if steps_since_improvement >= TRAINING_RULES["loss_plateau"]["threshold"]:
                        rule = TRAINING_RULES["loss_plateau"]
                        if action_log.can_act("lr", "halve_lr",
                                              rule["escalation"][0]["cooldown_s"]):
                            for pg in optimizer.param_groups:
                                old_lr = pg["lr"]
                                pg["lr"] = old_lr * 0.5
                            print(f"[ledgot] Plateau — LR {old_lr:.1e}→{old_lr*0.5:.1e}", file=sys.stderr)
                            action_log.record("lr", "halve_lr")
                            steps_since_improvement = 0

                # PROBE: Spectral α
                if global_step % probe_every == 0:
                    try:
                        _, alpha_metrics = spectral.compute_loss()
                        spectral.adapt_beta()
                        rule = TRAINING_RULES["alpha_decreasing"]
                        if (len(spectral.alpha_history) >= 5 and
                            action_log.can_act("alpha", "boost_beta",
                                               rule["escalation"][0]["cooldown_s"])):
                            trend = (spectral.alpha_history[-1] - spectral.alpha_history[-5])
                            if trend < rule["threshold"]:
                                old_beta = spectral.beta
                                spectral.beta = min(old_beta * 2.0, 1.0)
                                print(f"[ledgot] α↓ {trend:+.3f} — β {old_beta:.1e}→{spectral.beta:.1e}", file=sys.stderr)
                                action_log.record("alpha", "boost_beta")
                    except Exception as e:
                        print(f"[spectral] probe failed: {e}", file=sys.stderr)

                # Logging
                if global_step % LOG_EVERY == 0:
                    elapsed = time.time() - t0_total
                    avg = stage_loss / max(stage_steps_done, 1)
                    spec_str = spectral.status_str()
                    warmup_tag = "(warmup)" if warmup_active else ""
                    msg = (f"  step {global_step:6d} | stage {stage_idx+1} "
                           f"seq={seq_len:7d} W={window:5d} | "
                           f"loss={loss_val:.4f} avg={avg:.4f} | "
                           f"aux={aux_loss.item():.4f} grad_preclip={grad_norm_val:.1f} | "
                           f"mem={mem_gb:.1f}GB | {spec_str} {warmup_tag} | {elapsed:.0f}s")
                    print(msg, file=sys.stderr)
                    log_fp.write(f"{msg}\n")
                    log_fp.flush()

                # Checkpoint
                if global_step % CHECKPOINT_EVERY == 0:
                    ckpt_path = OUTPUT_DIR / f"checkpoint-{global_step}.pt"
                    torch.save({
                        "global_step": global_step, "seq_len": seq_len,
                        "stage": stage_idx + 1,
                        "model_state_dict": model.state_dict(),
                        "optimizer_state_dict": optimizer.state_dict(),
                        "loss": loss_val, "config": config,
                        "alpha": (spectral.alpha_history[-1] if spectral.alpha_history else 0.0),
                    }, ckpt_path)
                    print(f"  [checkpoint] {ckpt_path.name} "
                          f"({ckpt_path.stat().st_size/1e6:.0f}MB)", file=sys.stderr)
                    ckpts = sorted(OUTPUT_DIR.glob("checkpoint-*.pt"),
                                   key=lambda p: int(p.stem.split('-')[1]))
                    for old in ckpts[:-3]:
                        old.unlink()

                # Best
                if loss_val < best_loss:
                    best_loss = loss_val
                    best_path = OUTPUT_DIR / "checkpoint_best.pt"
                    torch.save({
                        "global_step": global_step, "seq_len": seq_len,
                        "stage": stage_idx + 1,
                        "model_state_dict": model.state_dict(),
                        "optimizer_state_dict": optimizer.state_dict(),
                        "loss": best_loss, "config": config,
                    }, best_path)
                    best_checkpoint_path = best_path

        # Stage summary
        stage_time = time.time() - stage_t0
        stage_avg = stage_loss / max(stage_steps_done, 1)
        summary = (f"[train] Stage {stage_idx+1} done: seq={seq_len:,} "
                   f"W={window} steps={stage_steps_done} loss={stage_avg:.4f} "
                   f"time={stage_time:.0f}s ({stage_time/3600:.1f}h)")
        print(summary, file=sys.stderr)
        log_fp.write(f"{summary}\n"); log_fp.flush()

        _append_to_chain(
            event="stage_complete",
            how=(f"stage={stage_idx+1}/{len(SCALE_SCHEDULE)} seq={seq_len} "
                 f"loss={stage_avg:.4f} "
                 f"α={spectral.alpha_history[-1] if spectral.alpha_history else 0:.3f}"),
        )

    # Final
    spectral.detach()
    if not shutdown_flag:
        final_path = OUTPUT_DIR / "checkpoint_final.pt"
        torch.save({
            "global_step": global_step, "seq_len": SEQ_LEN_MAX,
            "stage": len(SCALE_SCHEDULE),
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "loss": best_loss, "config": config,
        }, final_path)

    total_time = time.time() - t0_total
    final_alpha = spectral.alpha_history[-1] if spectral.alpha_history else 0.0
    print(f"\n[train] DONE. {global_step} steps in {total_time:.0f}s "
          f"({total_time/3600:.1f}h) | α={final_alpha:.3f}", file=sys.stderr)
    log_fp.write(f"\n# Complete: {global_step} steps, {total_time:.0f}s, α={final_alpha:.3f}\n")
    log_fp.close()

    _append_to_chain(
        event="training_complete",
        how=(f"steps={global_step} time={total_time:.0f}s loss={best_loss:.4f} "
             f"α={final_alpha:.3f} arch=llama-moe shutdown={shutdown_flag}"),
    )

    return OUTPUT_DIR


# ── Main ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LlamaMoE-1M Expert Training v3 (GGUF-ready)")
    parser.add_argument("--resume", type=str, default=None)
    parser.add_argument("--stage", type=int, default=0)
    parser.add_argument("--vault", type=str, default=str(VAULT_PATH))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        print("[dry-run] Validating setup...")
        print(f"  Vault: {args.vault} — {'exists' if Path(args.vault).exists() else 'MISSING'}")
        print(f"  Output: {OUTPUT_DIR}")
        print(f"  Log: {LOG_FILE}")
        print(f"  Model: LlamaMoE-1M (LLaMA-style, RMSNorm, SwiGLU, Mixtral MoE)")
        print(f"  Config: {EXPERT_CONFIG.n_layer}L {EXPERT_CONFIG.n_embd}d "
              f"experts={EXPERT_CONFIG.n_experts} top_k={EXPERT_CONFIG.top_k}")
        print(f"  GGUF: Direct conversion via convert_llama_moe_to_gguf.py")
        print("[dry-run] OK")
        sys.exit(0)

    VAULT_PATH = Path(args.vault)
    resume = Path(args.resume) if args.resume else None
    model_dir = train(resume_path=resume, start_stage=args.stage)
    print(f"[train] Output: {model_dir}", file=sys.stderr)
