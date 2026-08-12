#!/usr/bin/env python3
"""
FIM spectral exponent (α) comparison:
    SGD (β=0)  vs  SGD + Momentum (β=0.9)

Theory prediction: momentum introduces a symplectic structure on T*W,
modifying the FIM spectrum.  α should differ between the two optimizers.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.utils.data import DataLoader, Subset
from torchvision import datasets, transforms
import numpy as np
from scipy.optimize import curve_fit
from scipy import stats
import copy
import json
import os
from datetime import datetime

# ── reproducibility ──────────────────────────────────────────────────
SEED = 42
torch.manual_seed(SEED)
np.random.seed(SEED)
torch.backends.cudnn.deterministic = True
torch.backends.cudnn.benchmark = False

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Device: {DEVICE}")

# ── model ────────────────────────────────────────────────────────────
class SmallCNN(nn.Module):
    """~58K params — small enough for full diagonal FIM."""
    def __init__(self):
        super().__init__()
        self.conv1 = nn.Conv2d(1, 16, 3, padding=1)   # 28x28 → 28x28
        self.conv2 = nn.Conv2d(16, 32, 3, padding=1)  # 14x14 → 14x14
        self.pool = nn.MaxPool2d(2, 2)
        self.fc1 = nn.Linear(32 * 7 * 7, 128)
        self.fc2 = nn.Linear(128, 10)

    def forward(self, x):
        x = self.pool(F.relu(self.conv1(x)))   # → 14x14
        x = self.pool(F.relu(self.conv2(x)))   # → 7x7
        x = x.view(x.size(0), -1)
        x = F.relu(self.fc1(x))
        x = self.fc2(x)
        return x

# ── data ──────────────────────────────────────────────────────────────
transform = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize((0.1307,), (0.3081,))
])

train_full = datasets.MNIST("./data", train=True, download=True, transform=transform)
test_full  = datasets.MNIST("./data", train=False, download=True, transform=transform)

# Use a subset for faster iteration
N_TRAIN = 20000
N_FIM = 2000  # subset for FIM estimation (avoids one-sample per gradient)
train_set = Subset(train_full, range(N_TRAIN))
fim_set   = Subset(train_full, range(N_TRAIN, N_TRAIN + N_FIM))
test_set  = Subset(test_full, range(2000))

print(f"Train: {len(train_set)}, FIM-est: {len(fim_set)}, Test: {len(test_set)}")

# ── helpers ──────────────────────────────────────────────────────────

def count_params(model):
    return sum(p.numel() for p in model.parameters())

def evaluate(model, loader):
    model.eval()
    correct, total = 0, 0
    with torch.no_grad():
        for x, y in loader:
            x, y = x.to(DEVICE), y.to(DEVICE)
            out = model(x)
            correct += (out.argmax(1) == y).sum().item()
            total += y.size(0)
    return correct / total

def get_param_vector(model):
    """Flatten all parameters into a single vector."""
    return torch.cat([p.data.view(-1) for p in model.parameters()])

def set_param_vector(model, vec):
    """Write a flat vector back into model parameters."""
    offset = 0
    for p in model.parameters():
        n = p.numel()
        p.data.copy_(vec[offset:offset+n].view_as(p))
        offset += n

def compute_diagonal_fim(model, loader, loss_fn):
    """
    Compute the diagonal of the empirical Fisher Information Matrix.
    F_ii = E_{x,y ~ data}[ (∂_i log p(y|x))^2 ]
    
    Uses per-sample gradient accumulation over the FIM estimation set.
    Small batches (8-16) to keep the loop tractable (~250 iters for 2000 samples).
    """
    model.eval()
    n_params = count_params(model)
    fim_diag = torch.zeros(n_params, device=DEVICE)

    n_samples = 0
    for x, y in loader:
        x, y = x.to(DEVICE), y.to(DEVICE)
        B = x.size(0)
        
        for i in range(B):
            model.zero_grad()
            logits_i = model(x[i:i+1])
            loss = loss_fn(logits_i, y[i:i+1])
            loss.backward()
            
            offset = 0
            for p in model.parameters():
                n = p.numel()
                if p.grad is not None:
                    fim_diag[offset:offset+n] += p.grad.data.view(-1) ** 2
                offset += n
            n_samples += 1
        
        # Progress indicator
        if n_samples % 200 == 0:
            print(f"    FIM: {n_samples} samples processed...")

    fim_diag /= n_samples
    return fim_diag


def extract_alpha(fim_diag, tail_frac=0.3, n_bootstrap=100):
    """
    Extract spectral exponent α from the diagonal FIM.
    
    Rank eigenvalues from largest to smallest: λ_1 ≥ λ_2 ≥ ... ≥ λ_D
    Fit: log λ_k = const - α · log k  (power-law tail)
    
    tail_frac: fraction of eigenvalues to use for the fit (top eigenvalues)
    Returns: (alpha, std_err, r_squared, eigenvalues_sorted)
    """
    eigs = fim_diag.cpu().numpy()
    eigs = np.sort(eigs)[::-1]  # descending
    eigs = eigs[eigs > 0]  # discard zeros
    
    D = len(eigs)
    n_tail = max(int(D * tail_frac), 20)
    
    # Fit on the first n_tail eigenvalues (the dominant ones)
    x = np.log(np.arange(1, n_tail + 1))
    y = np.log(eigs[:n_tail])
    
    slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
    alpha = -slope  # slope is -α
    
    # Bootstrap for error
    alphas = []
    for _ in range(n_bootstrap):
        idx = np.random.choice(n_tail, size=n_tail, replace=True)
        xb, yb = x[idx], y[idx]
        s, _, _, _, _ = stats.linregress(xb, yb)
        alphas.append(-s)
    
    alpha_err = np.std(alphas)
    
    return alpha, alpha_err, r_value**2, eigs


# ── train one configuration ──────────────────────────────────────────

def train_model(model, train_loader, test_loader, optimizer_name, 
                lr=0.01, momentum=0.0, epochs=15, batch_size=128,
                save_path=None):
    """Train and return (model, history, final_test_acc)."""
    
    train_loader_dl = DataLoader(train_set, batch_size=batch_size, shuffle=True)
    test_loader_dl  = DataLoader(test_set, batch_size=batch_size)
    
    if optimizer_name == "sgd":
        opt = optim.SGD(model.parameters(), lr=lr, momentum=momentum)
    elif optimizer_name == "adam":
        opt = optim.Adam(model.parameters(), lr=lr)
    else:
        raise ValueError(f"Unknown optimizer: {optimizer_name}")
    
    scheduler = optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)
    criterion = nn.CrossEntropyLoss()
    
    history = {"train_loss": [], "test_acc": [], "param_norm": []}
    
    for epoch in range(epochs):
        model.train()
        epoch_loss = 0.0
        for x, y in train_loader_dl:
            x, y = x.to(DEVICE), y.to(DEVICE)
            opt.zero_grad()
            loss = criterion(model(x), y)
            loss.backward()
            opt.step()
            epoch_loss += loss.item() * x.size(0)
        
        epoch_loss /= len(train_set)
        scheduler.step()
        
        test_acc = evaluate(model, test_loader_dl)
        pnorm = get_param_vector(model).norm().item()
        
        history["train_loss"].append(epoch_loss)
        history["test_acc"].append(test_acc)
        history["param_norm"].append(pnorm)
        
        print(f"  Epoch {epoch+1:2d}/{epochs}  loss={epoch_loss:.4f}  "
              f"acc={test_acc:.4f}  ||w||={pnorm:.1f}")
    
    if save_path:
        torch.save(model.state_dict(), save_path)
    
    return model, history


# ── main experiment ──────────────────────────────────────────────────

def run_experiment():
    results = {}
    
    configs = [
        ("SGD (β=0)",   "sgd",  0.0),
        ("SGD (β=0.9)", "sgd",  0.9),
    ]
    
    # Save initial weights so both start identically
    init_model = SmallCNN().to(DEVICE)
    init_state = copy.deepcopy(init_model.state_dict())
    
    loss_fn = nn.CrossEntropyLoss()
    
    for name, opt_name, beta in configs:
        print(f"\n{'='*60}")
        print(f"Training: {name}")
        print(f"{'='*60}")
        
        model = SmallCNN().to(DEVICE)
        model.load_state_dict(init_state)  # identical init
        
        model, history = train_model(
            model, train_set, test_set,
            optimizer_name=opt_name,
            lr=0.01, momentum=beta, epochs=15, batch_size=128,
            save_path=f"/home/jacquesmyo/Desktop/model_{name.replace(' ', '_')}.pt"
        )
        
        # Compute diagonal FIM
        print(f"\n  Computing diagonal FIM for {name}...")
        fim_diag = compute_diagonal_fim(model, 
                                         DataLoader(fim_set, batch_size=1, shuffle=False),
                                         loss_fn)
        
        # Extract α
        alpha, alpha_err, r2, eigs = extract_alpha(fim_diag, tail_frac=0.3)
        
        print(f"\n  Results for {name}:")
        print(f"    α = {alpha:.4f} ± {alpha_err:.4f}")
        print(f"    R² = {r2:.4f}")
        print(f"    λ_max = {eigs[0]:.6f}")
        print(f"    λ_min = {eigs[-1]:.10f}")
        print(f"    condition number = {eigs[0]/eigs[-1]:.2e}")
        
        results[name] = {
            "alpha": float(alpha),
            "alpha_err": float(alpha_err),
            "r_squared": float(r2),
            "eigenvalues": eigs.tolist() if len(eigs) < 500 else f"[{len(eigs)} eigenvalues]",
            "lambda_max": float(eigs[0]),
            "condition_number": float(eigs[0]/eigs[-1]),
            "final_test_acc": history["test_acc"][-1],
            "param_norm": history["param_norm"][-1],
        }
    
    # Comparison
    print(f"\n{'='*60}")
    print(f"COMPARISON")
    print(f"{'='*60}")
    a0, ae0 = results["SGD (β=0)"]["alpha"], results["SGD (β=0)"]["alpha_err"]
    a09, ae09 = results["SGD (β=0.9)"]["alpha"], results["SGD (β=0.9)"]["alpha_err"]
    delta = a09 - a0
    sigma = np.sqrt(ae0**2 + ae09**2)
    
    print(f"  α(β=0)   = {a0:.4f} ± {ae0:.4f}")
    print(f"  α(β=0.9) = {a09:.4f} ± {ae09:.4f}")
    print(f"  Δα       = {delta:.4f} ± {sigma:.4f}  ({abs(delta)/sigma:.1f}σ)")
    print(f"  Significance: {'***' if abs(delta)/sigma > 3 else '*' if abs(delta)/sigma > 2 else 'ns'}")
    
    results["comparison"] = {
        "alpha_no_momentum": a0,
        "alpha_with_momentum": a09,
        "delta_alpha": delta,
        "sigma_delta": sigma,
        "significance_sigma": abs(delta)/sigma,
    }
    
    # Save results
    out_path = "/home/jacquesmyo/Desktop/fimbound_results.json"
    # For JSON, replace eigenvalue arrays with stats
    clean = copy.deepcopy(results)
    for k in ["SGD (β=0)", "SGD (β=0.9)"]:
        eigs_arr = np.array(results[k].get("eigenvalues_tail", []))
        clean[k]["eigenvalues_stats"] = {
            "n": results[k].get("n_eigs", 0),
            "top10": eigs_arr[:10].tolist() if len(eigs_arr) >= 10 else [],
        }
        if "eigenvalues" in clean[k]:
            del clean[k]["eigenvalues"]
        if "eigenvalues_tail" in clean[k]:
            del clean[k]["eigenvalues_tail"]
    
    with open(out_path, "w") as f:
        json.dump(clean, f, indent=2, default=str)
    print(f"\nResults saved to {out_path}")
    
    return results

if __name__ == "__main__":
    run_experiment()
