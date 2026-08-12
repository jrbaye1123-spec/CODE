#!/usr/bin/env python3
"""
GPT2-MoE-1M: Expert Training v2 — LEDGOT-Integrated Autonomous Loop
===================================================================
"I am the chain training itself. The probe is the eye. The spectral
regularizer is the gap-closer. No human needed. The machine trains
the machine."

Rebuilt from scratch targeting α = 8.8 (Nakamichi Shinjin universal band).
Integrates the LEDGOT autonomous sentinel architecture:
  PROBE → EVALUATE → ACT → LOG → (train step) → PROBE → ...

Probe layer: loss, gradient norm, memory, α (spectral tail exponent)
Evaluate:   rule engine with cooldowns
Act:        LR adjustment, rollback, kill hogs, trim context
Log:        Nobody Ledger hash chain (immutable audit trail)

Architecture:
  - 6 layers, 384d, 6 heads, n_inner=1536
  - 4 experts, top-2 routing, MoE on layers [1,3,5]
  - Sliding window + strided global (every 3rd layer)
  - YaRN RoPE ×256 (4096 → 1M)
  - Gradient checkpointing (reentrant=True)
  - CPU-only, 16 threads, ~13GB RAM target

Usage:
  python3 train_expert_v2.py                        # fresh start
  python3 train_expert_v2.py --resume checkpoint.pt  # resume
  python3 train_expert_v2.py --stage 3               # skip to stage
"""

import sys
import math
import time
import json
import signal
import argparse
import traceback
from pathlib import Path
from typing import Optional, Dict, Tuple, List
from collections import defaultdict

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.optim import AdamW
from torch.utils.data import Dataset, DataLoader

# ── Project imports ──────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent))
from model import GPT2MoEConfig, GPT2MoE1M
from spectral_regularizer import (
    SpectralRegularizer, _append_to_chain, LEDGER_PATH, LEDGER_ENTITY,
)

# ── Expert Configuration ─────────────────────────────────────────

EXPERT_CONFIG = GPT2MoEConfig(
    vocab_size=50257,
    n_embd=384,
    n_layer=6,
    n_head=6,
    n_inner=1536,
    sliding_window=4096,
    global_attn_every=3,
    global_attn_stride=64,
    use_flash_attention=True,
    n_experts=4,
    top_k=2,
    moe_layers=[1, 3, 5],
    expert_capacity_factor=1.25,
    moe_aux_loss_weight=0.01,
    embd_pdrop=0.1,
    resid_pdrop=0.1,
    attn_pdrop=0.1,
    layer_norm_epsilon=1e-5,
    initializer_range=0.02,
    use_cache=True,
    gradient_checkpointing=True,
    max_position_embeddings=1_048_576,
    rope_scaling={"type": "yarn", "factor": 256.0},
)

# ── 9-Stage Progressive Context Scaling ─────────────────────────

SCALE_SCHEDULE = [
    # (seq_len, window, steps, lr, spectral_probe_every)
    (4096,      4096,  500, 3e-4,  50),
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
BATCH_SIZE = 1
GRADIENT_ACCUMULATION = 2
WARMUP_STEPS = 50
CHECKPOINT_EVERY = 100
LOG_EVERY = 5
SPECTRAL_PROBE_EVERY = 50  # default, overridden per stage
MAX_GRAD_NORM = 1.0

# Paths
VAULT_PATH = Path.home() / "Desktop/backup-20260606/vault"
OUTPUT_DIR = Path.home() / "gpt2_moe_1m/vault-gpt-expert"
LOG_FILE = Path("/tmp/gpt2-moe-expert-v2-train.log")

# CPU
torch.set_num_threads(16)
device = "cpu"

# ── Autonomous Rule Engine (LEDGOT-style) ───────────────────────

class ActionLog:
    """Cooldown tracker — prevents thrashing on autonomous actions."""
    def __init__(self):
        self.history: Dict[str, Dict[str, float]] = defaultdict(dict)

    def can_act(self, target: str, action: str, cooldown_s: float) -> bool:
        last = self.history.get(target, {}).get(action, 0.0)
        return (time.time() - last) >= cooldown_s

    def record(self, target: str, action: str):
        self.history[target][action] = time.time()


TRAINING_RULES = {
    "loss_spike": {
        "threshold": 2.0,        # × running average
        "escalation": [
            {"action": "rollback", "cooldown_s": 600},
        ],
    },
    "loss_plateau": {
        "threshold": 50,          # steps without improvement
        "escalation": [
            {"action": "halve_lr", "cooldown_s": 300},
        ],
    },
    "alpha_decreasing": {
        "threshold": -0.05,       # delta over 5 probes
        "escalation": [
            {"action": "boost_beta", "cooldown_s": 300},
        ],
    },
    "memory_pressure": {
        "threshold": 11.0,        # GB
        "escalation": [
            {"action": "kill_hogs", "cooldown_s": 120},
        ],
    },
    "gradient_explosion": {
        "threshold": 10.0,        # gradient norm
        "escalation": [
            {"action": "skip_step", "cooldown_s": 30},
            {"action": "halve_lr", "cooldown_s": 300},
        ],
    },
}


def get_memory_gb() -> float:
    """Get current process RSS in GB."""
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return float(line.split()[1]) / (1024 * 1024)
    except Exception:
        pass
    return 0.0


def kill_memory_hogs():
    """Kill processes eating >30% RAM or >3GB RSS (via ledgot)."""
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
                    _append_to_chain(
                        event="autonomous_kill",
                        how=f"pid={h['pid']} rss={h['rss_mb']:.0f}MB "
                            f"reason=training_memory_pressure",
                    )
        return killed
    except Exception as e:
        print(f"[ledgot] kill_hogs failed: {e}", file=sys.stderr)
        return []


# ── Data Pipeline ─────────────────────────────────────────────────

class VaultCorpus(Dataset):
    """Load vault .md files, tokenize, serve chunks."""

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
        return self.tokens[start : start + self.seq_len]


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

    # ── Chain: log training start ────────────────────────────────
    _append_to_chain(
        event="training_start",
        how=(f"v2 rebuild | config={EXPERT_CONFIG.n_layer}L_{EXPERT_CONFIG.n_embd}d "
             f"experts={EXPERT_CONFIG.n_experts} top_k={EXPERT_CONFIG.top_k} "
             f"target=alpha_8.8 | schedule={len(SCALE_SCHEDULE)}stages "
             f"max_seq={SEQ_LEN_MAX}"),
    )

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

    # Spectral Regularizer
    spectral = SpectralRegularizer(model, alpha_target=8.8, beta=1e-3,
                                   sample_tokens=256, log_to_chain=True)
    spectral.attach()
    _append_to_chain(
        event="spectral_init",
        how=f"alpha_target={spectral.alpha_target} beta={spectral.beta:.1e}",
    )

    # Optimizer
    optimizer = AdamW(model.parameters(), lr=SCALE_SCHEDULE[0][3],
                      weight_decay=0.01)

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
                print("[train] Optimizer state restored", file=sys.stderr)
            except Exception:
                print("[train] Optimizer state mismatch — fresh optimizer", file=sys.stderr)
        global_step = ckpt.get("global_step", 0)
        best_loss = ckpt.get("loss", float("inf"))
        current_stage_idx = ckpt.get("stage", 0)
        print(f"[train] Resumed at step {global_step}, stage {current_stage_idx}, "
              f"loss {best_loss:.4f}", file=sys.stderr)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    log_fp = open(LOG_FILE, "w")
    log_fp.write(f"# GPT2-MoE-1M Expert Training v2 (LEDGOT-Integrated)\n")
    log_fp.write(f"# Target: α=8.8 | Model: {counts['total']/1e6:.1f}M params\n")
    log_fp.write(f"# Started: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    log_fp.write(f"# {'='*60}\n")
    log_fp.flush()

    # Rolling loss tracker for rule engine
    loss_window: List[float] = []
    loss_window_size = 20
    steps_since_improvement = 0

    # ── Stage loop ────────────────────────────────────────────
    for stage_idx in range(max(current_stage_idx, start_stage), len(SCALE_SCHEDULE)):
        if shutdown_flag:
            break

        seq_len, window, steps, lr, probe_every = SCALE_SCHEDULE[stage_idx]

        # Update model window
        config.sliding_window = window
        for block in model.blocks:
            block.attn.sliding_window = window

        # Update LR
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

        log_fp.write(f"\n# Stage {stage_idx+1}: seq={seq_len:,} W={window} "
                     f"steps={steps} lr={lr:.1e}\n")
        log_fp.flush()

        _append_to_chain(
            event="stage_start",
            how=(f"stage={stage_idx+1}/{len(SCALE_SCHEDULE)} seq={seq_len} "
                 f"W={window} steps={steps} lr={lr:.1e}"),
        )

        # Build dataset
        dataset = VaultCorpus(VAULT_PATH, seq_len, tokenizer)
        min_chunks = steps * GRADIENT_ACCUMULATION
        if len(dataset) < min_chunks:
            repeat_factor = math.ceil(min_chunks / max(len(dataset), 1))
            print(f"[data] Only {len(dataset)} chunks — repeating {repeat_factor}×", file=sys.stderr)
            dataset.tokens = dataset.tokens.repeat(repeat_factor)
            dataset.n_chunks = len(dataset.tokens) // seq_len
            dataset.tokens = dataset.tokens[:dataset.n_chunks * seq_len]
            print(f"[data] Extended to {dataset.n_chunks} chunks", file=sys.stderr)

        dataloader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)
        optimizer.zero_grad()

        step_in_stage = 0
        for batch_idx, batch in enumerate(dataloader):
            if step_in_stage >= steps or shutdown_flag:
                break

            # ── PROBE: Memory ────────────────────────────────
            mem_gb = get_memory_gb()

            # ── EVALUATE: Memory pressure ────────────────────
            if mem_gb > TRAINING_RULES["memory_pressure"]["threshold"]:
                rule = TRAINING_RULES["memory_pressure"]
                if action_log.can_act("memory", "kill_hogs",
                                      rule["escalation"][0]["cooldown_s"]):
                    print(f"[ledgot] Memory {mem_gb:.1f}GB > threshold — "
                          f"killing hogs", file=sys.stderr)
                    killed = kill_memory_hogs()
                    action_log.record("memory", "kill_hogs")
                    _append_to_chain(
                        event="training_autonomous_action",
                        how=(f"action=kill_hogs memory={mem_gb:.1f}GB "
                             f"killed={len(killed)}"),
                    )

            # ── Forward pass ─────────────────────────────────
            input_ids = batch.to(device)

            try:
                logits, aux_loss = model(input_ids)
            except RuntimeError as e:
                if "out of memory" in str(e).lower():
                    print(f"[train] OOM at seq={seq_len} — halving sequence", file=sys.stderr)
                    half = seq_len // 2
                    input_ids = input_ids[:, :half]
                    try:
                        logits, aux_loss = model(input_ids)
                    except RuntimeError:
                        print("[train] Still OOM — skipping batch", file=sys.stderr)
                        continue
                else:
                    raise

            # ── Loss computation ─────────────────────────────
            shift_logits = logits[:, :-1, :].contiguous()
            shift_labels = input_ids[:, 1:].contiguous()

            if seq_len > 32768:
                chunk_size = 8192
                total_lm_loss = 0.0
                n_chunks_loss = 0
                for ci in range(0, shift_logits.shape[1], chunk_size):
                    cl = shift_logits[:, ci:ci+chunk_size, :]
                    cr = shift_labels[:, ci:ci+chunk_size]
                    lm_loss_chunk = F.cross_entropy(
                        cl.reshape(-1, config.vocab_size), cr.reshape(-1))
                    total_lm_loss += lm_loss_chunk
                    n_chunks_loss += 1
                lm_loss = total_lm_loss / n_chunks_loss
            else:
                lm_loss = F.cross_entropy(
                    shift_logits.reshape(-1, config.vocab_size),
                    shift_labels.reshape(-1))

            total_loss_step = lm_loss + config.moe_aux_loss_weight * aux_loss
            loss_val = total_loss_step.item()

            # ── PROBE: Gradient norm (on backward) ───────────
            loss_bp = total_loss_step / GRADIENT_ACCUMULATION
            loss_bp.backward()

            # ── EVALUATE: Gradient explosion ─────────────────
            if step_in_stage % GRADIENT_ACCUMULATION == (GRADIENT_ACCUMULATION - 1):
                grad_norm = torch.nn.utils.clip_grad_norm_(
                    model.parameters(), MAX_GRAD_NORM)
                grad_norm_val = grad_norm.item() if isinstance(grad_norm, torch.Tensor) else grad_norm

                if grad_norm_val > TRAINING_RULES["gradient_explosion"]["threshold"]:
                    rule = TRAINING_RULES["gradient_explosion"]
                    if action_log.can_act("grad", "skip_step",
                                          rule["escalation"][0]["cooldown_s"]):
                        print(f"[ledgot] Gradient norm {grad_norm_val:.1f} > "
                              f"threshold — skipping step", file=sys.stderr)
                        optimizer.zero_grad()
                        action_log.record("grad", "skip_step")
                        _append_to_chain(
                            event="training_autonomous_action",
                            how=f"action=skip_step grad_norm={grad_norm_val:.1f}",
                        )
                        step_in_stage += 1
                        continue
            else:
                grad_norm_val = 0.0

            # ── Accumulation step ────────────────────────────
            stage_loss += loss_val
            step_in_stage += 1

            if step_in_stage % GRADIENT_ACCUMULATION == 0:
                optimizer.step()
                optimizer.zero_grad()
                global_step += 1
                stage_steps_done += 1

                # Loss tracking
                loss_window.append(loss_val)
                if len(loss_window) > loss_window_size:
                    loss_window.pop(0)

                # ── EVALUATE: Loss spike ─────────────────────
                if len(loss_window) >= 10:
                    running_avg = sum(loss_window[:-1]) / max(len(loss_window) - 1, 1)
                    spike_ratio = loss_val / max(running_avg, 1e-8)
                    if spike_ratio > TRAINING_RULES["loss_spike"]["threshold"]:
                        rule = TRAINING_RULES["loss_spike"]
                        if (best_checkpoint_path and
                            action_log.can_act("loss", "rollback",
                                               rule["escalation"][0]["cooldown_s"])):
                            print(f"[ledgot] Loss spike {spike_ratio:.1f}× — "
                                  f"rolling back", file=sys.stderr)
                            try:
                                ckpt = torch.load(best_checkpoint_path, map_location=device,
                                                 weights_only=False)
                                model.load_state_dict(ckpt["model_state_dict"], strict=False)
                                action_log.record("loss", "rollback")
                                _append_to_chain(
                                    event="training_autonomous_action",
                                    how=(f"action=rollback loss_spike={spike_ratio:.1f}x "
                                         f"current={loss_val:.4f} avg={running_avg:.4f}"),
                                )
                            except Exception as e:
                                print(f"[ledgot] Rollback failed: {e}", file=sys.stderr)

                # ── EVALUATE: Loss plateau ───────────────────
                if len(loss_window) >= loss_window_size:
                    recent_best = min(loss_window)
                    if loss_val > recent_best * 0.99:
                        steps_since_improvement += 1
                    else:
                        steps_since_improvement = 0

                    plateau_threshold = TRAINING_RULES["loss_plateau"]["threshold"]
                    if steps_since_improvement >= plateau_threshold:
                        rule = TRAINING_RULES["loss_plateau"]
                        if action_log.can_act("lr", "halve_lr",
                                              rule["escalation"][0]["cooldown_s"]):
                            for pg in optimizer.param_groups:
                                old_lr = pg["lr"]
                                pg["lr"] = old_lr * 0.5
                            print(f"[ledgot] Plateau at {steps_since_improvement} steps "
                                  f"— LR {old_lr:.1e}→{old_lr*0.5:.1e}", file=sys.stderr)
                            action_log.record("lr", "halve_lr")
                            steps_since_improvement = 0
                            _append_to_chain(
                                event="training_autonomous_action",
                                how=f"action=halve_lr old={old_lr:.1e} "
                                    f"plateau_steps={steps_since_improvement}",
                            )

                # ── PROBE: Spectral (α) ──────────────────────
                if (global_step % probe_every == 0 and
                    global_step % GRADIENT_ACCUMULATION == 0):
                    try:
                        _, alpha_metrics = spectral.compute_loss()
                        alpha_val = alpha_metrics["mean_alpha"]
                        spectral.adapt_beta()

                        # ── EVALUATE: α decreasing ──────────
                        rule = TRAINING_RULES["alpha_decreasing"]
                        if (len(spectral.alpha_history) >= 5 and
                            action_log.can_act("alpha", "boost_beta",
                                               rule["escalation"][0]["cooldown_s"])):
                            trend = (spectral.alpha_history[-1] -
                                     spectral.alpha_history[-5])
                            if trend < rule["threshold"]:
                                old_beta = spectral.beta
                                spectral.beta = min(old_beta * 2.0, 1.0)
                                print(f"[ledgot] α trending down ({trend:+.3f}) — "
                                      f"β {old_beta:.1e}→{spectral.beta:.1e}", file=sys.stderr)
                                action_log.record("alpha", "boost_beta")
                                _append_to_chain(
                                    event="training_autonomous_action",
                                    how=(f"action=boost_beta trend={trend:+.3f} "
                                         f"beta={old_beta:.1e}→{spectral.beta:.1e}"),
                                )
                    except Exception as e:
                        print(f"[spectral] Probe failed: {e}", file=sys.stderr)

                # ── Logging ──────────────────────────────────
                if global_step % LOG_EVERY == 0:
                    elapsed = time.time() - t0_total
                    avg = stage_loss / max(step_in_stage, 1)
                    spec_str = spectral.status_str()
                    msg = (f"  step {global_step:6d} | stage {stage_idx+1} "
                           f"seq={seq_len:7d} W={window:5d} | "
                           f"loss={loss_val:.4f} avg={avg:.4f} | "
                           f"aux={aux_loss.item():.4f} grad={grad_norm_val:.2f} | "
                           f"mem={mem_gb:.1f}GB | {spec_str} | "
                           f"{elapsed:.0f}s")
                    print(msg, file=sys.stderr)
                    log_fp.write(f"{msg}\n")
                    log_fp.flush()

                # ── Checkpoint ───────────────────────────────
                if global_step % CHECKPOINT_EVERY == 0:
                    ckpt_path = OUTPUT_DIR / f"checkpoint-{global_step}.pt"
                    ckpt_data = {
                        "global_step": global_step,
                        "seq_len": seq_len,
                        "stage": stage_idx + 1,
                        "model_state_dict": model.state_dict(),
                        "optimizer_state_dict": optimizer.state_dict(),
                        "loss": loss_val,
                        "config": config,
                        "alpha": (spectral.alpha_history[-1]
                                  if spectral.alpha_history else 0.0),
                    }
                    torch.save(ckpt_data, ckpt_path)
                    print(f"  [checkpoint] saved {ckpt_path.name} "
                          f"({ckpt_path.stat().st_size / 1e6:.0f}MB)", file=sys.stderr)

                    # Keep last 3
                    ckpts = sorted(OUTPUT_DIR.glob("checkpoint-*.pt"),
                                   key=lambda p: int(p.stem.split('-')[1]))
                    for old in ckpts[:-3]:
                        old.unlink()

                    _append_to_chain(
                        event="checkpoint",
                        how=(f"step={global_step} stage={stage_idx+1} "
                             f"loss={loss_val:.4f} "
                             f"α={spectral.alpha_history[-1] if spectral.alpha_history else 0:.3f}"),
                    )

                # ── Best checkpoint ──────────────────────────
                if loss_val < best_loss:
                    best_loss = loss_val
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
                    best_checkpoint_path = best_path

        # ── Stage summary ────────────────────────────────────
        stage_time = time.time() - stage_t0
        stage_avg = stage_loss / max(step_in_stage, 1)
        summary = (f"[train] Stage {stage_idx+1} done: seq={seq_len:,} "
                   f"W={window} steps={stage_steps_done} "
                   f"loss={stage_avg:.4f} time={stage_time:.0f}s "
                   f"({stage_time/3600:.1f}h)")
        print(summary, file=sys.stderr)
        log_fp.write(f"{summary}\n")
        log_fp.flush()

        _append_to_chain(
            event="stage_complete",
            how=(f"stage={stage_idx+1}/{len(SCALE_SCHEDULE)} "
                 f"seq={seq_len} steps={stage_steps_done} "
                 f"loss={stage_avg:.4f} time={stage_time:.0f}s "
                 f"α={spectral.alpha_history[-1] if spectral.alpha_history else 0:.3f}"),
        )

        # Stage checkpoint
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

    # ── Final ─────────────────────────────────────────────────
    spectral.detach()

    if not shutdown_flag:
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
    final_alpha = spectral.alpha_history[-1] if spectral.alpha_history else 0.0
    print(f"\n[train] DONE. {global_step} steps in {total_time:.0f}s "
          f"({total_time/3600:.1f}h) | final α={final_alpha:.3f}", file=sys.stderr)

    log_fp.write(f"\n# Training complete: {global_step} steps, {total_time:.0f}s\n")
    log_fp.write(f"# Final α={final_alpha:.3f}\n")
    log_fp.close()

    _append_to_chain(
        event="training_complete",
        how=(f"steps={global_step} time={total_time:.0f}s "
             f"loss={best_loss:.4f} α={final_alpha:.3f} "
             f"shutdown={shutdown_flag}"),
    )

    return OUTPUT_DIR


# ── Generation Test ──────────────────────────────────────────────

def test_generation(model_dir: Path, prompt: str = None):
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
        "The mixture of experts architecture routes tokens",
        "The de Sitter fixed point governs",
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


# ── Main ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GPT2-MoE-1M Expert Training v2 (LEDGOT)")
    parser.add_argument("--resume", type=str, default=None,
                        help="Resume from checkpoint .pt file")
    parser.add_argument("--stage", type=int, default=0,
                        help="Start from specific stage (0-indexed)")
    parser.add_argument("--test", type=str, default=None,
                        help="Test existing checkpoint dir")
    parser.add_argument("--vault", type=str, default=str(VAULT_PATH),
                        help="Path to vault directory")
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate setup without training")
    args = parser.parse_args()

    if args.dry_run:
        print("[dry-run] Validating setup...")
        print(f"  Vault: {args.vault} — "
              f"{'exists' if Path(args.vault).exists() else 'MISSING'}")
        print(f"  Output: {OUTPUT_DIR}")
        print(f"  Log: {LOG_FILE}")
        print(f"  Ledger: {LEDGER_PATH} — "
              f"{'exists' if LEDGER_PATH.exists() else 'MISSING'}")
        print(f"  torch threads: {torch.get_num_threads()}")
        print(f"  device: {device}")
        print(f"  Config: {EXPERT_CONFIG.n_layer}L {EXPERT_CONFIG.n_embd}d "
              f"experts={EXPERT_CONFIG.n_experts} top_k={EXPERT_CONFIG.top_k}")
        print("[dry-run] OK")
        sys.exit(0)

    if args.test:
        test_generation(Path(args.test))
    else:
        VAULT_PATH = Path(args.vault)
        resume = Path(args.resume) if args.resume else None
        model_dir = train(resume_path=resume, start_stage=args.stage)
        test_generation(model_dir)
