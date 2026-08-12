"""
Baby Adam E — Training Script (1000 epoch run)

Trains the extended architecture on the Obsidian vault corpus.
Character-level. CPU-friendly. Full probe suite active.

Usage:
    python train_e.py
    python train_e.py --epochs 100
    python train_e.py --resume checkpoint_e.pt
"""

import os
import sys
import time
import json
import math
import argparse
import urllib.parse
import torch
import torch.nn.functional as F
from pathlib import Path
from model_e import BabyAdamE, BabyAdamEConfig


# ═══════════════════════════════════════════════════════════════════════
# DATA PIPELINE
# ═══════════════════════════════════════════════════════════════════════

def load_vault_corpus(vault_path: str = None, max_chars: int = 10_000_000) -> str:
    if vault_path is None:
        vault_path = os.path.expanduser("~/Documents/ObsidianVault")

    vault = Path(vault_path)
    if not vault.exists():
        raise FileNotFoundError(f"Vault not found at {vault_path}")

    text_parts = []
    total_chars = 0

    for md_file in sorted(vault.rglob("*.md")):
        if any(part.startswith('.') for part in md_file.parts
               if part not in ('.', '..')):
            continue
        try:
            content = md_file.read_text(errors='ignore')
            if len(content) > 10:
                text_parts.append(content)
                total_chars += len(content)
                if total_chars >= max_chars:
                    break
        except Exception:
            continue

    corpus = "\n\n".join(text_parts)
    print(f"Loaded {len(text_parts)} notes, {len(corpus):,} chars")
    return corpus


def prepare_data(text: str, cfg: BabyAdamEConfig) -> tuple:
    clean = text.encode('ascii', errors='replace').decode('ascii')
    data = torch.tensor([ord(c) for c in clean], dtype=torch.long)
    split = int(0.9 * len(data))
    train_data = data[:split]
    val_data = data[split:]
    print(f"Train: {len(train_data):,} chars, Val: {len(val_data):,} chars")
    return train_data, val_data


def get_batch(data: torch.Tensor, cfg: BabyAdamEConfig) -> tuple:
    ix = torch.randint(0, len(data) - cfg.max_seq_len - 1, (cfg.batch_size,))
    x = torch.stack([data[i:i + cfg.max_seq_len] for i in ix])
    y = torch.stack([data[i + 1:i + cfg.max_seq_len + 1] for i in ix])
    return x, y


# ═══════════════════════════════════════════════════════════════════════
# TRAINING LOOP
# ═══════════════════════════════════════════════════════════════════════

def train(cfg: BabyAdamEConfig, resume_from: str = None,
          vault_path: str = None, total_epochs: int = 1000):

    device = torch.device('cpu')
    print(f"Device: {device}")

    # Model
    model = BabyAdamE(cfg).to(device)
    print(f"Model: {model.n_params:,} parameters")
    print(f"Config: d_model={cfg.d_model}, n_layers={cfg.n_layers}, "
          f"n_heads={cfg.n_heads}, d_ff={cfg.d_ff}")
    print(f"MoE: {cfg.n_experts} experts × top-{cfg.n_activated}, "
          f"Prophet={'on' if cfg.prophet_stopping else 'off'}")
    print(f"KS norm: {'on' if cfg.ks_enabled else 'off'}, "
          f"MP shrinkage: {'on' if cfg.mp_shrinkage_enabled else 'off'}")
    print(f"WDW constraint: λ={cfg.wdw_lambda}")

    # Optimizer
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=cfg.learning_rate,
        weight_decay=cfg.weight_decay,
        betas=(0.9, 0.95),
    )

    # LR scheduler
    def get_lr(step: int) -> float:
        if step < cfg.warmup_steps:
            return cfg.learning_rate * (step + 1) / cfg.warmup_steps
        if step > cfg.max_steps:
            return cfg.min_lr
        decay_ratio = (step - cfg.warmup_steps) / (cfg.max_steps - cfg.warmup_steps)
        coeff = 0.5 * (1.0 + math.cos(math.pi * decay_ratio))
        return cfg.min_lr + coeff * (cfg.learning_rate - cfg.min_lr)

    # Resume
    start_step = 0
    start_epoch = 0
    if resume_from:
        print(f"Resuming from {resume_from}")
        ckpt = torch.load(resume_from, map_location=device, weights_only=False)
        model.load_state_dict(ckpt['model_state_dict'])
        optimizer.load_state_dict(ckpt['optimizer_state_dict'])
        start_step = ckpt.get('step', 0) + 1
        start_epoch = ckpt.get('epoch', 0)
        print(f"Resumed at step {start_step}, epoch {start_epoch}")

    # Data
    print("\nLoading vault corpus...")
    corpus = load_vault_corpus(vault_path=vault_path)
    train_data, val_data = prepare_data(corpus, cfg)

    # Compute steps per epoch and total steps
    tokens_per_step = cfg.batch_size * cfg.max_seq_len
    steps_per_epoch = len(train_data) // tokens_per_step
    total_steps = total_epochs * steps_per_epoch

    print(f"\n{'='*60}")
    print(f"EPOCHS: {total_epochs}")
    print(f"Steps per epoch: ~{steps_per_epoch:,}")
    print(f"Total steps: ~{total_steps:,}")
    print(f"Tokens per step: {tokens_per_step:,}")
    print(f"Total tokens: ~{total_steps * tokens_per_step:,}")
    print(f"{'='*60}\n")

    # Override max_steps for the full run
    cfg.max_steps = total_steps
    cfg.warmup_steps = min(cfg.warmup_steps, total_steps // 10)

    # Training state
    model.train()
    train_losses = []
    val_losses = []
    measurements_log = []
    best_val_loss = float('inf')
    t0 = time.time()

    epoch = start_epoch
    step = start_step
    epoch_step = step % steps_per_epoch if steps_per_epoch > 0 else 0

    while epoch < total_epochs:
        # LR
        lr = get_lr(step)
        for pg in optimizer.param_groups:
            pg['lr'] = lr

        # Batch
        x, y = get_batch(train_data, cfg)
        x, y = x.to(device), y.to(device)

        # Forward with all probes
        do_probes = (step % cfg.logdet_probe_every == 0)
        result = model(x, return_measurements=do_probes, return_all_probes=do_probes)

        # Loss
        loss = F.cross_entropy(
            result['logits'].view(-1, cfg.vocab_size),
            y.view(-1),
            ignore_index=-1,
        )

        # WDW constraint
        wdw_loss_val = 0.0
        if cfg.wdw_enabled and do_probes and 'measurements' in result:
            wdw = result['measurements'].get('wdw_loss', 0.0)
            loss = loss + wdw
            wdw_loss_val = wdw if isinstance(wdw, float) else wdw.item()

        # Backward
        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), cfg.grad_clip)
        optimizer.step()

        train_losses.append(loss.item())

        # Log probes
        if do_probes and 'measurements' in result:
            m = result['measurements']
            entry = {'step': step, 'epoch': epoch}
            for k, v in m.items():
                if isinstance(v, (int, float, bool)):
                    entry[k] = v
                elif isinstance(v, list) and len(v) < 20:
                    entry[k] = v
            measurements_log.append(entry)

        # Print
        if step % 100 == 0:
            elapsed = time.time() - t0

            # Validation
            model.eval()
            with torch.no_grad():
                vx, vy = get_batch(val_data, cfg)
                vx, vy = vx.to(device), vy.to(device)
                vlogits = model(vx)['logits']
                vloss = F.cross_entropy(
                    vlogits.view(-1, cfg.vocab_size),
                    vy.view(-1),
                )
                val_losses.append((step, vloss.item()))
            model.train()

            # Build metrics string
            parts = []

            logdet = result.get('measurements', {}).get('logdet_mean')
            if logdet is not None and not (isinstance(logdet, float) and math.isnan(logdet)):
                parts.append(f"logdet={logdet:.1f}")

            berry = result.get('measurements', {}).get('berry_phase_mean', 0)
            if berry:
                parts.append(f"berry={berry:.3f}")

            spectral = result.get('measurements', {}).get('spectral_dimension_mean', 0)
            if spectral:
                parts.append(f"d_s={spectral:.2f}")

            wdw_e = result.get('measurements', {}).get('wdw_total_energy', 0)
            if wdw_e:
                parts.append(f"wdw={wdw_e:.4f}")

            void_r = result.get('measurements', {}).get('void_ratio')
            if void_r is not None:
                parts.append(f"void={void_r:.2%}")

            ks_a = result.get('measurements', {}).get('ks_a_mean', 1.0)
            if ks_a:
                parts.append(f"a={ks_a:.2f}")

            prop = result.get('measurements', {}).get('prophet_ratio_mean')
            if prop is not None:
                parts.append(f"prop={prop:.2f}")

            h_route = result.get('measurements', {}).get('routing_entropy_mean', 0)
            if h_route:
                parts.append(f"H={h_route:.2f}")

            metrics = " | ".join(parts)

            progress = (epoch / total_epochs * 100) if total_epochs > 0 else 0
            print(f"E{epoch:4d} S{step:7d} ({progress:5.1f}%) | "
                  f"loss={loss.item():.4f} | val={vloss.item():.4f} | "
                  f"lr={lr:.2e} | {elapsed:.0f}s | {metrics}")

            # Save best
            if vloss.item() < best_val_loss:
                best_val_loss = vloss.item()
                save_checkpoint(model, optimizer, step, epoch,
                              train_losses, val_losses, measurements_log,
                              'checkpoint_e_best.pt')
                print(f"  ★ Best val: {best_val_loss:.4f}")

        # Periodic checkpoint
        if step % 5000 == 0 and step > 0:
            save_checkpoint(model, optimizer, step, epoch,
                          train_losses, val_losses, measurements_log,
                          f'checkpoint_e_{step}.pt')

        # Epoch boundary checkpoints
        if epoch_step == 0 and step > 0 and epoch > 0:
            save_checkpoint(model, optimizer, step, epoch,
                          train_losses, val_losses, measurements_log,
                          f'checkpoint_e_epoch_{epoch}.pt')

        step += 1
        epoch_step += 1
        if epoch_step >= steps_per_epoch:
            epoch += 1
            epoch_step = 0
            print(f"\n─── EPOCH {epoch}/{total_epochs} COMPLETE "
                  f"({time.time()-t0:.0f}s) ───\n")

        if epoch >= total_epochs:
            break

    # Final save
    save_checkpoint(model, optimizer, step - 1, epoch,
                  train_losses, val_losses, measurements_log,
                  'checkpoint_e_final.pt')

    # Ledger summary
    if model.ledger:
        summary = model.ledger.summary()
        print(f"\nLedger: {summary['total_entries']} entries, "
              f"{summary['active']} active, {summary['voided']} voided "
              f"({summary['void_rate']:.1%}), intact={summary['intact']}")

    print(f"\n{'='*60}")
    print(f"Training complete — {epoch} epochs, {step} steps")
    print(f"Best val_loss: {best_val_loss:.4f}")
    print(f"Total time: {time.time() - t0:.0f}s")
    print(f"{'='*60}")

    return model, train_losses, val_losses, measurements_log


def save_checkpoint(model, optimizer, step, epoch,
                    train_losses, val_losses, measurements, path):
    ckpt = {
        'step': step,
        'epoch': epoch,
        'model_state_dict': model.state_dict(),
        'optimizer_state_dict': optimizer.state_dict(),
        'train_losses': train_losses[-10000:] if len(train_losses) > 10000 else train_losses,
        'val_losses': val_losses[-2000:] if len(val_losses) > 2000 else val_losses,
        'measurements_log': measurements[-1000:] if len(measurements) > 1000 else measurements,
        'config': model.cfg,
        'n_params': model.n_params,
    }
    torch.save(ckpt, path)
    print(f"  → Saved {path}")


# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Train Baby Adam E')
    parser.add_argument('--epochs', type=int, default=1000)
    parser.add_argument('--d-model', type=int, default=256)
    parser.add_argument('--n-layers', type=int, default=6)
    parser.add_argument('--n-heads', type=int, default=8)
    parser.add_argument('--batch-size', type=int, default=8)
    parser.add_argument('--lr', type=float, default=3e-4)
    parser.add_argument('--resume', type=str, default=None)
    parser.add_argument('--vault', type=str, default=None)

    args = parser.parse_args()

    cfg = BabyAdamEConfig(
        d_model=args.d_model,
        n_layers=args.n_layers,
        n_heads=args.n_heads,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        max_seq_len=256,  # Faster CPU training
        ks_enabled=False,
        wdw_enabled=False,
        mp_shrinkage_enabled=False,
        logdet_probe_every=500,
        berry_probe_every=5000,
        spectral_triple_every=5000,
    )

    print("🐣 Baby Adam E — Extended Architecture")
    print(f"   {cfg.d_model}d × {cfg.n_layers}L, "
          f"{cfg.n_experts} experts, full probe suite")

    model, _, _, _ = train(
        cfg,
        resume_from=args.resume,
        vault_path=args.vault,
        total_epochs=args.epochs,
    )
