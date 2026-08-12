#!/usr/bin/env python3
"""
Controlled replication: match test accuracy between β=0 and β=0.9
by training the slower (β=0) model for more epochs.

If α still differs after accuracy-matching, the symplectic contribution
is genuine — not a convergence artifact.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.utils.data import DataLoader, Subset
from torchvision import datasets, transforms
import numpy as np
from scipy import stats
import copy
import json

SEED = 42
torch.manual_seed(SEED)
np.random.seed(SEED)

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Device: {DEVICE}")

# ── reused from prior run ────────────────────────────────────────────

class SmallCNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv1 = nn.Conv2d(1, 16, 3, padding=1)
        self.conv2 = nn.Conv2d(16, 32, 3, padding=1)
        self.pool = nn.MaxPool2d(2, 2)
        self.fc1 = nn.Linear(32 * 7 * 7, 128)
        self.fc2 = nn.Linear(128, 10)

    def forward(self, x):
        x = self.pool(F.relu(self.conv1(x)))
        x = self.pool(F.relu(self.conv2(x)))
        x = x.view(x.size(0), -1)
        x = F.relu(self.fc1(x))
        x = self.fc2(x)
        return x

transform = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize((0.1307,), (0.3081,))
])

train_full = datasets.MNIST("./data", train=True, download=True, transform=transform)
test_full  = datasets.MNIST("./data", train=False, download=True, transform=transform)

N_TRAIN = 20000
N_FIM = 2000
train_set = Subset(train_full, range(N_TRAIN))
fim_set   = Subset(train_full, range(N_TRAIN, N_TRAIN + N_FIM))
test_set  = Subset(test_full, range(2000))

def count_params(model):
    return sum(p.numel() for p in model.parameters())

def evaluate(model, loader):
    model.eval()
    correct, total = 0, 0
    with torch.no_grad():
        for x, y in loader:
            x, y = x.to(DEVICE), y.to(DEVICE)
            correct += (model(x).argmax(1) == y).sum().item()
            total += y.size(0)
    return correct / total

def get_param_vector(model):
    return torch.cat([p.data.view(-1) for p in model.parameters()])

def compute_diagonal_fim(model, loader, loss_fn):
    model.eval()
    n_params = count_params(model)
    fim_diag = torch.zeros(n_params, device=DEVICE)
    n_samples = 0
    for x, y in loader:
        x, y = x.to(DEVICE), y.to(DEVICE)
        B = x.size(0)
        for i in range(B):
            model.zero_grad()
            loss = loss_fn(model(x[i:i+1]), y[i:i+1])
            loss.backward()
            offset = 0
            for p in model.parameters():
                n = p.numel()
                if p.grad is not None:
                    fim_diag[offset:offset+n] += p.grad.data.view(-1) ** 2
                offset += n
            n_samples += 1
        if n_samples % 400 == 0:
            print(f"    FIM: {n_samples} samples...")
    fim_diag /= n_samples
    return fim_diag

def extract_alpha(fim_diag, tail_frac=0.3):
    eigs = fim_diag.cpu().numpy()
    eigs = np.sort(eigs)[::-1]
    eigs = eigs[eigs > 0]
    D = len(eigs)
    n_tail = max(int(D * tail_frac), 20)
    x = np.log(np.arange(1, n_tail + 1))
    y = np.log(eigs[:n_tail])
    slope, _, r_value, _, std_err = stats.linregress(x, y)
    alpha = -slope
    # Bootstrap
    alphas = []
    for _ in range(200):
        idx = np.random.choice(n_tail, size=n_tail, replace=True)
        s, _, _, _, _ = stats.linregress(x[idx], y[idx])
        alphas.append(-s)
    return alpha, np.std(alphas), r_value**2, eigs

# ── train to target accuracy ─────────────────────────────────────────

def train_to_target(model, target_acc=0.975, max_epochs=100, 
                    lr=0.01, momentum=0.0, batch_size=128, 
                    patience=5, label="model"):
    """Train until test accuracy reaches target or max_epochs."""
    train_loader = DataLoader(train_set, batch_size=batch_size, shuffle=True)
    test_loader  = DataLoader(test_set, batch_size=batch_size)
    
    opt = optim.SGD(model.parameters(), lr=lr, momentum=momentum)
    criterion = nn.CrossEntropyLoss()
    
    best_acc = 0.0
    best_state = None
    stall_count = 0
    
    for epoch in range(1, max_epochs + 1):
        model.train()
        epoch_loss = 0.0
        for x, y in train_loader:
            x, y = x.to(DEVICE), y.to(DEVICE)
            opt.zero_grad()
            loss = criterion(model(x), y)
            loss.backward()
            opt.step()
            epoch_loss += loss.item() * x.size(0)
        epoch_loss /= len(train_set)
        
        test_acc = evaluate(model, test_loader)
        
        if test_acc > best_acc:
            best_acc = test_acc
            best_state = copy.deepcopy(model.state_dict())
            stall_count = 0
        else:
            stall_count += 1
        
        if epoch % 5 == 0 or test_acc >= target_acc:
            print(f"  [{label}] epoch {epoch:3d}  acc={test_acc:.4f}  "
                  f"loss={epoch_loss:.4f}  stall={stall_count}")
        
        if test_acc >= target_acc:
            print(f"  → Target accuracy {target_acc:.4f} reached at epoch {epoch}")
            break
        
        if stall_count >= patience:
            print(f"  → Stalled for {patience} epochs, restoring best ({best_acc:.4f})")
            model.load_state_dict(best_state)
            break
    
    return model, test_acc, epoch

# ── run ───────────────────────────────────────────────────────────────

print("\n" + "="*60)
print("CONTROLLED EXPERIMENT: accuracy-matched α comparison")
print("="*60)

loss_fn = nn.CrossEntropyLoss()
fim_loader = DataLoader(fim_set, batch_size=1, shuffle=False)

# First train momentum model (faster) to establish target accuracy
print("\n--- Phase 1: Train momentum model to convergence ---")
model_mom = SmallCNN().to(DEVICE)
model_mom, acc_mom, epochs_mom = train_to_target(
    model_mom, target_acc=0.98, max_epochs=30,
    lr=0.01, momentum=0.9, patience=10, label="β=0.9"
)

print(f"\n  Momentum model final: acc={acc_mom:.4f} in {epochs_mom} epochs")
pnorm_mom = get_param_vector(model_mom).norm().item()
print(f"  ||w|| = {pnorm_mom:.1f}")

# Now train SGD model to match that accuracy
print(f"\n--- Phase 2: Train SGD (β=0) to match accuracy ({acc_mom:.4f}) ---")
model_sgd = SmallCNN().to(DEVICE)
model_sgd, acc_sgd, epochs_sgd = train_to_target(
    model_sgd, target_acc=acc_mom, max_epochs=100,
    lr=0.01, momentum=0.0, patience=15, label="β=0"
)

print(f"\n  SGD model final: acc={acc_sgd:.4f} in {epochs_sgd} epochs")
pnorm_sgd = get_param_vector(model_sgd).norm().item()
print(f"  ||w|| = {pnorm_sgd:.1f}")

# Compute FIM for both
print(f"\n--- Phase 3: Compute FIM for both models ---")

print("\n  FIM for β=0 model...")
fim_sgd = compute_diagonal_fim(model_sgd, fim_loader, loss_fn)
alpha_sgd, err_sgd, r2_sgd, eigs_sgd = extract_alpha(fim_sgd)

print(f"    α(β=0)   = {alpha_sgd:.4f} ± {err_sgd:.4f}  (R²={r2_sgd:.4f})")
print(f"    λ_max = {eigs_sgd[0]:.6f}")

print("\n  FIM for β=0.9 model...")
fim_mom = compute_diagonal_fim(model_mom, fim_loader, loss_fn)
alpha_mom, err_mom, r2_mom, eigs_mom = extract_alpha(fim_mom)

print(f"    α(β=0.9) = {alpha_mom:.4f} ± {err_mom:.4f}  (R²={r2_mom:.4f})")
print(f"    λ_max = {eigs_mom[0]:.6f}")

# Comparison
delta = alpha_mom - alpha_sgd
sigma = np.sqrt(err_sgd**2 + err_mom**2)

print(f"\n{'='*60}")
print(f"CONTROLLED COMPARISON (accuracy-matched)")
print(f"{'='*60}")
print(f"  Training epochs:  β=0 → {epochs_sgd}, β=0.9 → {epochs_mom}")
print(f"  Matched accuracy: {acc_sgd:.4f} ≈ {acc_mom:.4f}")
print(f"  Param norm:       ||w||={pnorm_sgd:.1f} vs {pnorm_mom:.1f}")
print(f"  α(β=0)   = {alpha_sgd:.4f} ± {err_sgd:.4f}")
print(f"  α(β=0.9) = {alpha_mom:.4f} ± {err_mom:.4f}")
print(f"  Δα       = {delta:+.4f} ± {sigma:.4f}  ({abs(delta)/sigma:.1f}σ)")
print(f"  Significance: {'***' if abs(delta)/sigma > 3 else '*' if abs(delta)/sigma > 2 else 'ns'}")

result = {
    "experiment": "accuracy-matched",
    "sgd_epochs": epochs_sgd,
    "momentum_epochs": epochs_mom,
    "sgd_accuracy": acc_sgd,
    "momentum_accuracy": acc_mom,
    "sgd_param_norm": pnorm_sgd,
    "momentum_param_norm": pnorm_mom,
    "alpha_no_momentum": float(alpha_sgd),
    "alpha_no_momentum_err": float(err_sgd),
    "alpha_no_momentum_r2": float(r2_sgd),
    "alpha_with_momentum": float(alpha_mom),
    "alpha_with_momentum_err": float(err_mom),
    "alpha_with_momentum_r2": float(r2_mom),
    "delta_alpha": float(delta),
    "sigma_delta": float(sigma),
    "significance_sigma": float(abs(delta)/sigma),
}

with open("/home/jacquesmyo/Desktop/fimbound_controlled.json", "w") as f:
    json.dump(result, f, indent=2)
print(f"\nSaved to /home/jacquesmyo/Desktop/fimbound_controlled.json")
