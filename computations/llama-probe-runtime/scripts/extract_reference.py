#!/usr/bin/env python3
"""
Ground-truth hidden state extraction for probe validation.

Loads an FP16 model via HuggingFace transformers, runs a fixed 32-token
prompt, extracts hidden states at the specified layer, and saves to .npy.

Usage:
    python3 extract_reference.py --model meta-llama/Llama-3.2-1B \\
        --prompt "The quick brown fox jumps over the lazy dog" \\
        --layer 6 --output reference_h_i.npy

Requirements: torch, transformers, numpy (pip install into venv)
"""

import argparse
import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


def extract_hidden_states(
    model_name: str,
    prompt: str,
    layer_idx: int,
    max_tokens: int = 32,
) -> np.ndarray:
    """Extract hidden states at a specific layer for the given prompt.

    Returns:
        np.ndarray of shape [n_tokens, hidden_dim] — the hidden states
        at `layer_idx` for each token position.
    """
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.float32,
        device_map="cpu",
        output_hidden_states=True,
    )
    model.eval()

    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=max_tokens)
    input_ids = inputs["input_ids"]

    with torch.no_grad():
        outputs = model(input_ids, output_hidden_states=True)

    # outputs.hidden_states is a tuple of (embedding, layer_0, layer_1, ..., layer_N)
    # layer_idx 0 = embedding, layer_idx 1 = first transformer block output, etc.
    # We want the output AFTER transformer block `layer_idx`, so index layer_idx+1
    hidden = outputs.hidden_states[layer_idx + 1]  # [1, n_tokens, hidden_dim]
    h = hidden.squeeze(0).cpu().numpy().astype(np.float32)  # [n_tokens, hidden_dim]

    print(f"Model: {model_name}")
    print(f"Prompt: {prompt}")
    print(f"Tokens: {h.shape[0]}, Hidden dim: {h.shape[1]}")
    print(f"Layer: {layer_idx} (after transformer block {layer_idx})")
    print(f"Range: [{h.min():.6f}, {h.max():.6f}], mean={h.mean():.6f}")

    return h


def compute_logdet(h: np.ndarray, eps: float = 1e-6) -> float:
    """Compute logdet(cov(h) + eps*I) — the unitary invariant."""
    h_centered = h - h.mean(axis=0, keepdims=True)
    cov = (h_centered.T @ h_centered) / (h.shape[0] - 1)
    cov_reg = cov + np.eye(cov.shape[0]) * eps
    sign, logdet = np.linalg.slogdet(cov_reg)
    if sign <= 0:
        return -float("inf")
    return float(logdet)


def main():
    parser = argparse.ArgumentParser(description="Extract reference hidden states for probe validation")
    parser.add_argument("--model", default="google/gemma-3-1b-it", help="HF model name")
    parser.add_argument("--prompt", default="The quick brown fox jumps over the lazy dog", help="Input prompt")
    parser.add_argument("--layer", type=int, default=6, help="Transformer layer index")
    parser.add_argument("--output", default="reference_h_i.npy", help="Output .npy file")
    parser.add_argument("--max-tokens", type=int, default=32, help="Max tokens")
    args = parser.parse_args()

    h = extract_hidden_states(args.model, args.prompt, args.layer, args.max_tokens)
    logdet = compute_logdet(h)

    np.save(args.output, h)
    print(f"\nSaved {h.shape} to {args.output}")
    print(f"logdet(cov(h)) = {logdet:.6f}")


if __name__ == "__main__":
    main()
