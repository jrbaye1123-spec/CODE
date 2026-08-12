"""Direction 1: ML Architecture Phase Diagram — reproduce Φ(d) = std(logdet) sweep."""
import torch, torch.nn as nn, torch.nn.functional as F
from torch.utils.data import DataLoader
from torchvision import datasets, transforms
import json, time, numpy as np, sys

torch.manual_seed(42)
HIDDEN_DIM, NUM_LAYERS, EPOCHS, BATCH_SIZE, LR = 128, 8, 5, 64, 0.001

class ResidualMLP(nn.Module):
    def __init__(self, num_residual_layers):
        super().__init__()
        self.num_res = num_residual_layers
        layers = [nn.Linear(784, HIDDEN_DIM)]
        for _ in range(NUM_LAYERS - 1):
            layers.append(nn.Linear(HIDDEN_DIM, HIDDEN_DIM))
        self.layers = nn.ModuleList(layers)
        self.output = nn.Linear(HIDDEN_DIM, 10)
        self.residual_layers = list(range(NUM_LAYERS - num_residual_layers, NUM_LAYERS))

    def forward(self, x):
        x = x.view(-1, 784)
        residuals = {}
        h = F.relu(self.layers[0](x))
        residuals[0] = h
        for i in range(1, NUM_LAYERS):
            h_in = h
            h = F.relu(self.layers[i](h))
            if i in self.residual_layers and i > 0:
                h = h + residuals.get(i-2, h_in)
            residuals[i] = h
        return self.output(h)

def compute_logdets(model, loader):
    model.eval()
    activations = {i: [] for i in range(NUM_LAYERS)}
    def hook_fn(idx):
        def hook(module, inp, out):
            activations[idx].append(out.detach().cpu())
        return hook
    hooks = [layer.register_forward_hook(hook_fn(i)) for i, layer in enumerate(model.layers)]
    with torch.no_grad():
        for data, _ in loader:
            model(data)
    for h in hooks: h.remove()
    logdets = []
    for i in range(NUM_LAYERS):
        act = torch.cat(activations[i], dim=0)
        act = act - act.mean(dim=0, keepdim=True)
        cov = (act.T @ act) / (act.shape[0] - 1) + 1e-3 * torch.eye(act.shape[1])
        sign, ld = torch.linalg.slogdet(cov)
        if sign <= 0:
            eigs = torch.linalg.eigvalsh(cov)
            eigs = torch.clamp(eigs, min=1e-10)
            logdets.append(float(torch.sum(torch.log(eigs))))
        else:
            logdets.append(float(ld))
    return logdets

print("Loading MNIST...", flush=True)
transform = transforms.Compose([transforms.ToTensor(), transforms.Normalize((0.1307,), (0.3081,))])
train_ds = datasets.MNIST('/tmp', train=True, download=True, transform=transform)
train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True)

results = []
for num_res in range(0, NUM_LAYERS + 1):
    frac = num_res / NUM_LAYERS
    sys.stdout.write(f"d={frac:.3f} training..."); sys.stdout.flush()
    model = ResidualMLP(num_res)
    opt = torch.optim.Adam(model.parameters(), lr=LR)
    crit = nn.CrossEntropyLoss()
    t0 = time.time()
    for ep in range(EPOCHS):
        model.train()
        total = 0
        for d, t in train_loader:
            opt.zero_grad()
            loss = crit(model(d), t)
            loss.backward(); opt.step()
            total += loss.item()
        sys.stdout.write(f" ep{ep+1}:{total/len(train_loader):.2f}"); sys.stdout.flush()
    elapsed = time.time() - t0
    logdets = compute_logdets(model, train_loader)
    std = float(np.std(logdets))
    results.append({'num_res': num_res, 'frac': frac, 'logdets': logdets, 'std': std, 'time': elapsed})
    sys.stdout.write(f" Φ={std:.1f} ({elapsed:.0f}s)\n"); sys.stdout.flush()

print("\n=== DIRECTION 1 RESULTS ===")
print(f"{'d':>8} {'Φ(std)':>12}")
for r in results:
    print(f"{r['frac']:8.3f} {r['std']:12.1f}")
peak_idx = np.argmax([r['std'] for r in results])
print(f"\nPeak: Φ={results[peak_idx]['std']:.1f} at d={results[peak_idx]['frac']:.2f}")
print(f"Baseline (d=0): Φ={results[0]['std']:.1f}")
print(f"Collapse (d=1): Φ={results[-1]['std']:.1f} ({results[-1]['std']/results[0]['std']*100:.0f}%)")
print(f"Non-monotonic: {'YES' if results[peak_idx]['frac'] > 0 and results[peak_idx]['frac'] < 1.0 else 'NO'}")
print(f"Critical threshold d≈0.50: Φ(d=0.50)={results[4]['std']:.1f} vs baseline {results[0]['std']:.1f} ({'BELOW' if results[4]['std'] < results[0]['std'] else 'ABOVE'})")

with open('/home/j/vault/output/experiments/architecture-phase/phase_diagram_verify.json', 'w') as f:
    json.dump(results, f, indent=2)
print("\nDONE. Saved to phase_diagram_verify.json")
