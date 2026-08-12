import torch
import numpy as np
from pathlib import Path

def generate_synthetic_layer(
    layer_idx: int,
    N: int = 1024,
    Kmax: int = 20,
    d: int = 4096,
    spectrum_type: str = "isotropic",
    seed: int = 12345,
    output_dir: str = "./synthetic_cache"
) -> None:
    """
    Generate synthetic G tensor for a layer.

    spectrum_type:
        - "isotropic": Sigma = 8.8 * I
        - "spiked": Sigma = diag(8.8*d, 0, 0, ...)
        - "anisotropic": Sigma = diag(10, 8, 6, 4, 2, ...) with trace = 8.8*d
    """
    torch.manual_seed(seed + layer_idx)
    np.random.seed(seed + layer_idx)

    if spectrum_type == "isotropic":
        Sigma = 8.8 * torch.eye(d, dtype=torch.float32)

    elif spectrum_type == "spiked":
        Sigma = torch.zeros(d, d, dtype=torch.float32)
        Sigma[0, 0] = 8.8 * d

    elif spectrum_type == "anisotropic":
        # Exponentially decaying spectrum
        decay = torch.linspace(1.0, 0.01, d)
        # Normalize to trace = 8.8 * d
        trace_target = 8.8 * d
        eigenvalues = decay / decay.sum() * trace_target
        Sigma = torch.diag(eigenvalues)

    else:
        raise ValueError(f"Unknown spectrum_type: {spectrum_type}")

    # Compute Cholesky factor L such that Sigma = L L^T
    L = torch.linalg.cholesky(Sigma)

    # Generate G: [N, Kmax, d]
    # Each row is drawn from N(0, Sigma)
    # We can generate standard normal Z and multiply by L^T
    Z = torch.randn(N * Kmax, d, dtype=torch.float32)
    G = Z @ L.T  # Now rows have covariance Sigma
    G = G.reshape(N, Kmax, d)

    # Save
    Path(output_dir).mkdir(exist_ok=True, parents=True)
    torch.save({"G": G}, Path(output_dir) / f"layer_{layer_idx:02d}.pt")
    print(f"Generated layer_{layer_idx:02d}.pt ({spectrum_type}) -> {G.shape}")