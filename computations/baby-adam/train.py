"""
Baby Adam — Training Script

Trains BabyAdam on the Obsidian vault corpus.
Character-level. CPU-friendly. Built-in measurement probes.

Usage:
    python train.py                        # Default config
    python train.py --steps 10000          # More training
    python train.py --resume checkpoint.pt # Resume from checkpoint
    python train.py --forever --resume checkpoint_7000.pt  # Run until Ctrl+C
"""

import os
import sys
import time
import json
import argparse
import urllib.parse
import torch
import torch.nn.functional as F
from pathlib import Path
from model import BabyAdam, BabyAdamConfig


# ═══════════════════════════════════════════════════════════════════════
# DATA PIPELINE
# ═══════════════════════════════════════════════════════════════════════

def _kitadel_discover(vault_path: str) -> list:
    """Use Kitadel metasearch to discover and rank vault markdown files.
    
    Returns list of (absolute_path, relevance_score) sorted by relevance.
    Falls back gracefully if Kitadel unavailable.
    """
    try:
        kitadel_path = os.path.expanduser(
            "~/Documents/ObsidianVault/tools/kitadel/kitadel.py"
        )
        kitadel_dir = os.path.dirname(kitadel_path)
        
        if not os.path.exists(kitadel_path):
            return []
        
        # Import kitadel as a module
        sys.path.insert(0, kitadel_dir)
        import kitadel
        
        # Use hybrid vault search to discover relevant files by topic
        results = kitadel.search_vault_hybrid(
            "transformer architecture physics cosmology trading attention mechanism",
            n=200
        )
        
        paths = []
        seen = set()
        for r in results:
            # Extract file path from obsidian:// URL
            url = r.get('url', '')
            # URL format: obsidian://open?vault=ObsidianVault&file=wiki/some-note
            if 'file=' in url:
                file_part = url.split('file=')[-1]
                file_part = urllib.parse.unquote(file_part)
                # Convert to filesystem path
                vault = Path(vault_path)
                fs_path = vault / file_part
                if fs_path.exists() and str(fs_path) not in seen:
                    seen.add(str(fs_path))
                    paths.append((str(fs_path), r.get('score', 1.0)))
        
        sys.path.remove(kitadel_dir)
        return paths
        
    except Exception as e:
        print(f"[kitadel] Discovery skipped: {e}")
        if 'kitadel_dir' in dir() and kitadel_dir in sys.path:
            sys.path.remove(kitadel_dir)
    
    return []


def load_vault_corpus(vault_path: str = None, max_chars: int = 10_000_000,
                      use_metasearch: bool = True) -> str:
    """
    Load all markdown files from the Obsidian vault.
    Can use Kitadel metasearch for topic-aware file discovery.
    Returns a single string of concatenated text.
    """
    if vault_path is None:
        vault_path = os.path.expanduser("~/vault")
    
    vault = Path(vault_path)
    if not vault.exists():
        raise FileNotFoundError(f"Vault not found at {vault_path}")
    
    text_parts = []
    total_chars = 0
    
    # Try Kitadel metasearch first for topic-aware file ordering
    if use_metasearch:
        metasearch_files = _kitadel_discover(vault_path)
        if metasearch_files:
            print(f"[kitadel] Discovered {len(metasearch_files)} files via metasearch")
            for file_path, score in metasearch_files:
                p = Path(file_path)
                if not p.exists():
                    p = vault / file_path  # try relative
                if p.exists() and p.suffix == '.md':
                    try:
                        content = p.read_text(errors='ignore')
                        if len(content) > 10:
                            text_parts.append(content)
                            total_chars += len(content)
                            if total_chars >= max_chars:
                                break
                    except:
                        continue
    
    # Fallback: rglob all markdown files
    if total_chars < max_chars:
        remaining = max_chars - total_chars
        for md_file in vault.rglob("*.md"):
            # Skip hidden dirs
            if any(part.startswith('.') for part in md_file.parts 
                   if part not in ('.', '..')):
                continue
            
            # Skip files already loaded via metasearch
            already_loaded = False
            for tp in text_parts:
                # Quick check — if content starts the same, skip
                pass
            
            try:
                content = md_file.read_text(errors='ignore')
                if len(content) > 10:  # Skip empty/stub files
                    text_parts.append(content)
                    total_chars += len(content)
                    if total_chars >= max_chars:
                        break
            except:
                continue
    
    corpus = "\n\n".join(text_parts)
    print(f"Loaded {len(text_parts)} notes, {len(corpus):,} chars")
    return corpus


def prepare_data(text: str, cfg: BabyAdamConfig) -> tuple[torch.Tensor, torch.Tensor]:
    """
    Convert text to character-level tensors.
    ASCII only (vocab_size=256). Non-ASCII chars mapped to '?'.
    """
    # Convert to bytes, replace non-ASCII with '?'
    clean = text.encode('ascii', errors='replace').decode('ascii')
    
    # Convert to tensor
    data = torch.tensor([ord(c) for c in clean], dtype=torch.long)
    
    # Split train/val (90/10)
    split = int(0.9 * len(data))
    train_data = data[:split]
    val_data = data[split:]
    
    print(f"Train: {len(train_data):,} chars, Val: {len(val_data):,} chars")
    return train_data, val_data


def get_batch(data: torch.Tensor, cfg: BabyAdamConfig) -> tuple[torch.Tensor, torch.Tensor]:
    """Get a random batch of sequences."""
    ix = torch.randint(0, len(data) - cfg.max_seq_len - 1, (cfg.batch_size,))
    
    x = torch.stack([data[i:i + cfg.max_seq_len] for i in ix])
    y = torch.stack([data[i + 1:i + cfg.max_seq_len + 1] for i in ix])
    
    return x, y


# ═══════════════════════════════════════════════════════════════════════
# TRAINING LOOP
# ═══════════════════════════════════════════════════════════════════════

def train(cfg: BabyAdamConfig, resume_from: str = None, vault_path: str = None,
          forever: bool = False):
    """Main training loop."""
    
    import math
    
    # ── Setup ──
    device = torch.device('cpu')
    print(f"Device: {device}")
    
    # Model
    model = BabyAdam(cfg).to(device)
    print(f"Model: {model.n_params:,} parameters")
    print(f"Config: d_model={cfg.d_model}, n_layers={cfg.n_layers}, "
          f"n_heads={cfg.n_heads}, d_ff={cfg.d_ff}")
    
    # Optimizer
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=cfg.learning_rate,
        weight_decay=cfg.weight_decay,
        betas=(0.9, 0.95)
    )
    
    # Learning rate scheduler (cosine with warmup, then flat at min_lr forever)
    def get_lr(step: int) -> float:
        if step < cfg.warmup_steps:
            return cfg.learning_rate * (step + 1) / cfg.warmup_steps
        if step >= cfg.max_steps:
            return cfg.min_lr
        decay_ratio = (step - cfg.warmup_steps) / (cfg.max_steps - cfg.warmup_steps)
        coeff = 0.5 * (1.0 + math.cos(math.pi * decay_ratio))
        return cfg.min_lr + coeff * (cfg.learning_rate - cfg.min_lr)
    
    # Resume if requested
    start_step = 0
    if resume_from:
        print(f"Resuming from {resume_from}")
        checkpoint = torch.load(resume_from, map_location=device, weights_only=False)
        model.load_state_dict(checkpoint['model_state_dict'])
        optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        start_step = checkpoint['step'] + 1
        print(f"Resumed at step {start_step}")
    
    # Data
    print("\nLoading vault corpus...")
    corpus = load_vault_corpus(vault_path=vault_path)
    train_data, val_data = prepare_data(corpus, cfg)
    
    # ── Training ──
    mode = "FOREVER (--forever)" if forever else f"{cfg.max_steps} steps"
    print(f"\n{'='*60}")
    print(f"Training: {mode}")
    print(f"Batch size: {cfg.batch_size}, Seq len: {cfg.max_seq_len}")
    print(f"{'='*60}\n")
    
    model.train()
    train_losses = []
    val_losses = []
    measurements_log = []
    best_val_loss = float('inf')
    t0 = time.time()
    
    step = start_step
    try:
        while True:
            if not forever and step >= cfg.max_steps:
                break
            # Learning rate
            lr = get_lr(step)
            for param_group in optimizer.param_groups:
                param_group['lr'] = lr
            
            # Get batch
            x, y = get_batch(train_data, cfg)
            x, y = x.to(device), y.to(device)
            
            # Forward
            result = model(x, return_measurements=(step % cfg.logdet_probe_every == 0))
            logits = result['logits']
            
            # Loss
            loss = F.cross_entropy(
                logits.view(-1, cfg.vocab_size),
                y.view(-1),
                ignore_index=-1
            )
            
            # Backward
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), cfg.grad_clip)
            optimizer.step()
            
            # Log
            train_losses.append(loss.item())
            
            if step % cfg.logdet_probe_every == 0 and 'measurements' in result:
                measurements_log.append({
                    'step': step,
                    **result['measurements']
                })
            
            # Print progress
            if step % 100 == 0:
                elapsed = time.time() - t0
            
                # Validation
                model.eval()
                with torch.no_grad():
                    vx, vy = get_batch(val_data, cfg)
                    vx, vy = vx.to(device), vy.to(device)
                    vresult = model(vx)
                    vloss = F.cross_entropy(
                        vresult['logits'].view(-1, cfg.vocab_size),
                        vy.view(-1)
                    )
                    val_losses.append((step, vloss.item()))
                model.train()
            
                # Measurement
                logdet_str = ""
                if measurements_log:
                    m = measurements_log[-1]
                    if 'logdet_mean' in m:
                        logdet_str = f" | logdet={m['logdet_mean']:.1f}"
                expert_str = ""
                if measurements_log:
                    m = measurements_log[-1]
                    if 'routing_entropy_mean' in m:
                        expert_str = f" | H_route={m['routing_entropy_mean']:.2f}"
                    if 'expert_utilization' in m:
                        util = m['expert_utilization'][-1]  # last layer
                        top_experts = sorted(range(len(util)), key=lambda i: util[i], reverse=True)
                        expert_str += f" | top_exp={top_experts[0]}"
            
                total = '∞' if forever else str(cfg.max_steps)
                print(f"Step {step:5d}/{total} | "
                      f"loss={loss.item():.4f} | val_loss={vloss.item():.4f} | "
                      f"lr={lr:.2e} | {elapsed:.0f}s{logdet_str}{expert_str}")
            
                # Save best
                if vloss.item() < best_val_loss:
                    best_val_loss = vloss.item()
                    save_checkpoint(model, optimizer, step, train_losses, val_losses, 
                                  measurements_log, 'checkpoint_best.pt')
                    print(f"  → Best val_loss: {best_val_loss:.4f}")
            
            # Periodic checkpoint
            if step % 1000 == 0 and step > 0:
                ckpt_name = f'checkpoint_{step}.pt'
                save_checkpoint(model, optimizer, step, train_losses, val_losses,
                              measurements_log, ckpt_name)
                # Rotate: keep only last 3 periodic checkpoints to avoid disk fill
                import glob as _glob
                ckpts = sorted(_glob.glob('checkpoint_*.pt'))
                for old in ckpts[:-3]:
                    try:
                        os.remove(old)
                    except OSError:
                        pass
            
            step += 1
    
    except KeyboardInterrupt:
        print(f"\n\nInterrupted at step {step}. Saving checkpoint...")
    
    # ── Final save ──
    final_step = step - 1 if step > start_step else 0
    save_checkpoint(model, optimizer, final_step, train_losses, val_losses,
                  measurements_log, 'checkpoint_final.pt')
    
    print(f"\n{'='*60}")
    print(f"Training complete!")
    print(f"Best val_loss: {best_val_loss:.4f}")
    print(f"Total time: {time.time() - t0:.0f}s")
    print(f"Checkpoints saved to checkpoint_best.pt, checkpoint_final.pt")
    print(f"{'='*60}")
    
    return model, train_losses, val_losses, measurements_log


def save_checkpoint(model, optimizer, step, train_losses, val_losses, measurements, path):
    """Save training checkpoint."""
    checkpoint = {
        'step': step,
        'model_state_dict': model.state_dict(),
        'optimizer_state_dict': optimizer.state_dict(),
        'train_losses': train_losses,
        'val_losses': val_losses,
        'measurements_log': measurements,
        'config': model.cfg,
        'n_params': model.n_params,
    }
    torch.save(checkpoint, path)


# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Train Baby Adam')
    parser.add_argument('--steps', type=int, default=5000, help='Max training steps')
    parser.add_argument('--d-model', type=int, default=256, help='Hidden dimension')
    parser.add_argument('--n-layers', type=int, default=6, help='Transformer layers')
    parser.add_argument('--n-heads', type=int, default=8, help='Attention heads')
    parser.add_argument('--batch-size', type=int, default=32, help='Batch size')
    parser.add_argument('--lr', type=float, default=3e-4, help='Learning rate')
    parser.add_argument('--resume', type=str, default=None, help='Resume from checkpoint')
    parser.add_argument('--vault', type=str, default=None, help='Vault path (default: ~/vault)')
    parser.add_argument('--forever', action='store_true', help='Run indefinitely (Ctrl+C to stop)')
    
    args = parser.parse_args()
    
    cfg = BabyAdamConfig(
        d_model=args.d_model,
        n_layers=args.n_layers,
        n_heads=args.n_heads,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        max_steps=args.steps,
    )
    
    # Baby config uses smaller defaults
    if args.d_model == 256 and args.n_layers == 6:
        print("🐣 Baby Adam (default config)")
        print(f"   {cfg.d_model}d × {cfg.n_layers}L = ~{cfg.d_model * cfg.d_model * cfg.n_layers * 6 // 1_000_000}M params")
    
    model, train_losses, val_losses, measurements = train(
        cfg, resume_from=args.resume, vault_path=args.vault, forever=args.forever)
