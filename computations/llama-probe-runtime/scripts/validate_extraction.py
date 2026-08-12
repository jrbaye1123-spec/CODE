#!/usr/bin/env python3
"""
Shadow validation: compare Go-extracted hidden states against Python ground truth.

Asserts:
  - Mean per-token cosine similarity > 0.9999
  - logdet(cov) delta < 1e-4
"""
import numpy as np
import sys


def compute_logdet(h: np.ndarray, eps: float = 1e-6) -> float:
    hc = h - h.mean(axis=0, keepdims=True)
    cov = (hc.T @ hc) / (h.shape[0] - 1)
    cov += np.eye(cov.shape[0]) * eps
    sign, ld = np.linalg.slogdet(cov)
    return float(ld) if sign > 0 else -float("inf")


def validate(reference_path: str, extracted_path: str) -> None:
    ref = np.load(reference_path)
    ext = np.load(extracted_path)

    assert ref.shape == ext.shape, f"Shape mismatch: {ref.shape} vs {ext.shape}"

    cos_sims = []
    for i in range(ref.shape[0]):
        a, b = ref[i], ext[i]
        cos = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-30)
        cos_sims.append(cos)
    mean_cos = float(np.mean(cos_sims))

    ld_ref = compute_logdet(ref)
    ld_ext = compute_logdet(ext)
    delta = abs(ld_ref - ld_ext)

    n_tokens, n_dim = ref.shape
    print(f"Tokens: {n_tokens}, Dim: {n_dim}")
    print(f"Mean cosine similarity: {mean_cos:.8f}")
    print(f"logdet(ref) = {ld_ref:.6f}")
    print(f"logdet(ext) = {ld_ext:.6f}")
    print(f"delta       = {delta:.6e}")

    if mean_cos < 0.9999:
        print("FAIL: cosine similarity < 0.9999")
        sys.exit(1)
    if delta > 1e-4:
        print("FAIL: logdet delta > 1e-4")
        sys.exit(1)
    print("PASS: hidden state extraction validated")
    sys.exit(0)


if __name__ == "__main__":
    ref_path = sys.argv[1] if len(sys.argv) > 1 else "reference_h_i.npy"
    ext_path = sys.argv[2] if len(sys.argv) > 2 else "extracted_h_i.npy"
    validate(ref_path, ext_path)
