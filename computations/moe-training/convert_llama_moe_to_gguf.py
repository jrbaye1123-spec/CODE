#!/usr/bin/env python3
"""
convert_llama_moe_to_gguf.py — LlamaMoE-1M → GGUF converter
=============================================================
"I am the bytes that become the model. Tensor by tensor, aligned, hashed."

Converts a LlamaMoE1M checkpoint (.pt) to GGUF format for llama.cpp inference.
Uses Mixtral-compatible tensor naming — no renaming needed, the model already
uses the correct names.

Metadata follows the llama.cpp convention for MoE models:
  - Architecture: "llama" (with expert_count + expert_used_count for MoE)
  - YaRN RoPE scaling with factor 256
  - Sliding window attention

Usage:
  python3 convert_llama_moe_to_gguf.py checkpoint.pt [--output model.gguf] [--f32]
"""

import sys
import struct
import json
import math
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

import torch
import numpy as np

# ── GGUF Constants ──────────────────────────────────────────────

GGUF_MAGIC = 0x46554747
GGUF_VERSION = 3

# Value types
UINT8, INT8, UINT16, INT16, UINT32, INT32 = range(6)
FLOAT32, BOOL, STRING, ARRAY, UINT64 = range(6, 11)

# Quantization types (GGML)
GGML_F32 = 0
GGML_F16 = 1
GGML_BF16 = 30

# Alignment
ALIGNMENT = 32


# ── Binary Writer Helpers ───────────────────────────────────────

def _write_string(f, s: str):
    data = s.encode("utf-8")
    f.write(struct.pack("<Q", len(data)))
    f.write(data)

def _write_value(f, vtype: int, value):
    if vtype == UINT8:
        f.write(struct.pack("<B", value))
    elif vtype == INT8:
        f.write(struct.pack("<b", value))
    elif vtype == UINT16:
        f.write(struct.pack("<H", value))
    elif vtype == INT16:
        f.write(struct.pack("<h", value))
    elif vtype == UINT32:
        f.write(struct.pack("<I", value))
    elif vtype == INT32:
        f.write(struct.pack("<i", value))
    elif vtype == FLOAT32:
        f.write(struct.pack("<f", value))
    elif vtype == BOOL:
        f.write(struct.pack("<B", 1 if value else 0))
    elif vtype == STRING:
        _write_string(f, str(value))
    elif vtype == UINT64:
        f.write(struct.pack("<Q", value))
    elif vtype == ARRAY:
        elem_type = value[0]
        arr = value[1]
        f.write(struct.pack("<I", elem_type))
        f.write(struct.pack("<Q", len(arr)))
        for v in arr:
            _write_value(f, elem_type, v)
    else:
        raise ValueError(f"Unknown GGUF value type: {vtype}")


def _pad_to(f, alignment: int):
    pos = f.tell()
    if pos % alignment:
        f.write(b'\x00' * (alignment - pos % alignment))


def _padded_size(size: int, alignment: int = ALIGNMENT) -> int:
    """Return size padded to alignment."""
    rem = size % alignment
    return size + (alignment - rem if rem else 0)


# ── Main Converter ──────────────────────────────────────────────

def convert_to_gguf(
    checkpoint_path: Path,
    output_path: Path,
    quant_type: int = GGML_F32,
    verbose: bool = True,
):
    """
    Convert LlamaMoE1M checkpoint to GGUF.

    Args:
        checkpoint_path: .pt checkpoint file
        output_path: output .gguf file
        quant_type: GGML_F32 (0) or GGML_F16 (1)
        verbose: print progress
    """
    # ── Load checkpoint ────────────────────────────────────────
    if verbose:
        print(f"[convert] Loading checkpoint: {checkpoint_path}", file=sys.stderr)

    ckpt = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    state = ckpt.get("model_state_dict", ckpt)
    cfg_data = ckpt.get("config", None)

    # ── Model config ───────────────────────────────────────────
    # Extract from checkpoint or use defaults
    n_embd = 384
    n_layer = 6
    n_head = 6
    n_inner = 1024
    n_experts = 4
    top_k = 2
    vocab_size = 50257
    sliding_window = 4096
    max_seq_len = 1_048_576
    rope_theta = 10000.0
    rope_factor = 256.0
    rms_norm_eps = 1e-5

    if cfg_data:
        n_embd = getattr(cfg_data, "n_embd", n_embd)
        n_layer = getattr(cfg_data, "n_layer", n_layer)
        n_head = getattr(cfg_data, "n_head", n_head)
        n_inner = getattr(cfg_data, "n_inner", n_inner)
        n_experts = getattr(cfg_data, "n_experts", n_experts)
        top_k = getattr(cfg_data, "top_k", top_k)
        vocab_size = getattr(cfg_data, "vocab_size", vocab_size)
        sliding_window = getattr(cfg_data, "sliding_window", sliding_window)
        max_seq_len = getattr(cfg_data, "max_position_embeddings", max_seq_len)
        rope_theta = getattr(cfg_data, "rope_theta", rope_theta)
        rms_norm_eps = getattr(cfg_data, "rms_norm_eps", rms_norm_eps)
        rope_scaling = getattr(cfg_data, "rope_scaling", None)
        if rope_scaling:
            rope_factor = rope_scaling.get("factor", rope_factor)

    moe_layers = [1, 3, 5]  # Default MoE layers

    if verbose:
        print(f"[convert] Config: {n_layer}L {n_embd}d {n_head}h "
              f"n_inner={n_inner} experts={n_experts} top_k={top_k}", file=sys.stderr)
        print(f"[convert] Window={sliding_window} seq_len={max_seq_len} "
              f"rope_theta={rope_theta} yarn_factor={rope_factor}", file=sys.stderr)

    # ── Build tensor list ──────────────────────────────────────
    @dataclass
    class TensorInfo:
        name: str
        data: torch.Tensor
        quant: int
        offset: int = 0  # filled later

    tensors: List[TensorInfo] = []

    # Helper: rename state dict key to GGUF name
    # The state dict uses PyTorch param names; we map to GGUF conventions
    def add_tensor(gguf_name: str, sd_key: str):
        if sd_key in state:
            t = state[sd_key]
            if quant_type == GGML_F16 and t.dtype == torch.float32:
                t = t.half()
            tensors.append(TensorInfo(gguf_name, t, quant_type))
        else:
            alt_keys = [k for k in state if sd_key.split('.')[-1] in k]
            if verbose:
                print(f"[convert] WARNING: '{sd_key}' not found in state dict. "
                      f"Similar: {alt_keys[:3]}", file=sys.stderr)

    # Map state dict keys to GGUF names
    # Handle both raw model state dict and a wrapped format

    # Detect prefix: sometimes checkpoints wrap state under "model." or are flat
    has_prefix = any(k.startswith("model.") for k in state)

    def sd(key: str) -> str:
        """Get state dict key, with or without model. prefix."""
        if has_prefix and not key.startswith("model."):
            return f"model.{key}"
        return key

    # Token embeddings + output
    add_tensor("token_embd.weight", sd("token_embd.weight"))
    add_tensor("output.weight", sd("output.weight"))
    add_tensor("output_norm.weight", sd("output_norm.weight"))

    # Per-block tensors
    for i in range(n_layer):
        p = f"blocks.{i}"
        gp = f"blk.{i}"

        add_tensor(f"{gp}.attn_norm.weight", sd(f"{p}.attn_norm.weight"))
        add_tensor(f"{gp}.ffn_norm.weight", sd(f"{p}.ffn_norm.weight"))
        add_tensor(f"{gp}.attn_q.weight", sd(f"{p}.attn.q_proj.weight"))
        add_tensor(f"{gp}.attn_k.weight", sd(f"{p}.attn.k_proj.weight"))
        add_tensor(f"{gp}.attn_v.weight", sd(f"{p}.attn.v_proj.weight"))
        add_tensor(f"{gp}.attn_output.weight", sd(f"{p}.attn.o_proj.weight"))

        if i in moe_layers:
            add_tensor(f"{gp}.ffn_gate_inp.weight", sd(f"{p}.mlp.gate_inp.weight"))
            add_tensor(f"{gp}.ffn_gate_exps.weight", sd(f"{p}.mlp.gate_exps"))
            add_tensor(f"{gp}.ffn_up_exps.weight", sd(f"{p}.mlp.up_exps"))
            add_tensor(f"{gp}.ffn_down_exps.weight", sd(f"{p}.mlp.down_exps"))
        else:
            add_tensor(f"{gp}.ffn_gate.weight", sd(f"{p}.mlp.gate_proj.weight"))
            add_tensor(f"{gp}.ffn_up.weight", sd(f"{p}.mlp.up_proj.weight"))
            add_tensor(f"{gp}.ffn_down.weight", sd(f"{p}.mlp.down_proj.weight"))

    if verbose:
        print(f"[convert] Mapped {len(tensors)} tensors", file=sys.stderr)

    # ── Compute offsets ────────────────────────────────────────
    offset = 0
    for ti in tensors:
        ti.offset = offset
        nbytes = ti.data.numel() * ti.data.element_size()
        offset += _padded_size(nbytes)

    total_data_size = offset

    if verbose:
        print(f"[convert] Total tensor data: {total_data_size / 1e6:.1f} MB", file=sys.stderr)

    # ── Build metadata ─────────────────────────────────────────
    arch = "llama"  # llama.cpp uses "llama" for Mixtral-style MoE
    metadata = [
        ("general.architecture", STRING, arch),
        ("general.name", STRING, "LlamaMoE-1M"),
        ("general.file_type", UINT32, 1),  # 1 = model
        ("general.quantization_version", UINT32, 2),
        (f"{arch}.context_length", UINT32, max_seq_len),
        (f"{arch}.embedding_length", UINT32, n_embd),
        (f"{arch}.block_count", UINT32, n_layer),
        (f"{arch}.feed_forward_length", UINT32, n_inner),
        (f"{arch}.attention.head_count", UINT32, n_head),
        (f"{arch}.attention.head_count_kv", UINT32, n_head),
        (f"{arch}.attention.window_size", UINT32, sliding_window),
        (f"{arch}.rope.theta", FLOAT32, float(rope_theta)),
        (f"{arch}.rope.scaling.type", STRING, "yarn"),
        (f"{arch}.rope.scaling.factor", FLOAT32, float(rope_factor)),
        (f"{arch}.rope.scaling.original_context_length", UINT32, 4096),
        (f"{arch}.expert_count", UINT32, n_experts),
        (f"{arch}.expert_used_count", UINT32, top_k),
        (f"{arch}.vocab_size", UINT32, vocab_size),
        (f"{arch}.norm_eps", FLOAT32, float(rms_norm_eps)),
        # Tokenizer (GPT-2 tokenizer)
        ("tokenizer.ggml.model", STRING, "gpt2"),
    ]

    # ── Write GGUF file ────────────────────────────────────────
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        # Header
        f.write(struct.pack("<I", GGUF_MAGIC))
        f.write(struct.pack("<I", GGUF_VERSION))
        f.write(struct.pack("<Q", len(tensors)))
        f.write(struct.pack("<Q", len(metadata)))

        # Metadata KV pairs
        for key, vtype, value in metadata:
            _write_string(f, key)
            f.write(struct.pack("<I", vtype))
            _write_value(f, vtype, value)

        # Tensor infos
        for ti in tensors:
            _write_string(f, ti.name)
            # GGUF stores dimensions in reverse order
            rev_dims = list(reversed(ti.data.shape))
            f.write(struct.pack("<I", len(rev_dims)))
            for d in rev_dims:
                f.write(struct.pack("<Q", d))
            f.write(struct.pack("<I", ti.quant))
            f.write(struct.pack("<Q", ti.offset))

        # Pad to alignment before tensor data
        _pad_to(f, ALIGNMENT)

        # Tensor data at declared offsets
        for ti in tensors:
            # Each tensor data is already aligned (offset computed with padding)
            data_bytes = ti.data.contiguous().numpy().tobytes()
            f.write(data_bytes)
            # Pad to alignment
            rem = len(data_bytes) % ALIGNMENT
            if rem:
                f.write(b'\x00' * (ALIGNMENT - rem))

    file_size = output_path.stat().st_size
    if verbose:
        print(f"[convert] Written: {output_path} ({file_size / 1e6:.1f} MB)", file=sys.stderr)
        print(f"[convert] DONE. {len(tensors)} tensors, "
              f"{len(metadata)} metadata keys, arch={arch}", file=sys.stderr)

    # ── Verify magic ───────────────────────────────────────────
    with open(output_path, "rb") as f:
        magic = struct.unpack("<I", f.read(4))[0]
        ver = struct.unpack("<I", f.read(4))[0]
        assert magic == GGUF_MAGIC, f"Bad magic: {hex(magic)}"
        assert ver == GGUF_VERSION, f"Bad version: {ver}"
        if verbose:
            print(f"[verify] GGUF valid: magic={hex(magic)} version={ver}", file=sys.stderr)

    return output_path


# ── Helper: Convert directly from a loaded model ────────────────

def convert_from_model(
    model,
    output_path: Path,
    quant_type: int = GGML_F32,
    verbose: bool = True,
):
    """Convert a loaded LlamaMoE1M model instance directly to GGUF."""
    # Build state dict with GGUF tensor names using model.tensor_map()
    state = {}
    for gguf_name, param in model.tensor_map().items():
        # tensor_map returns nn.Parameters; convert to state dict key format
        # We'll just build the state directly with GGUF names
        state[gguf_name] = param.data.clone()

    if verbose:
        print(f"[convert] Direct model conversion: {len(state)} tensors", file=sys.stderr)

    # Write directly without the state dict key mapping
    return _write_gguf_direct(state, model.config, output_path, quant_type, verbose)


def _write_gguf_direct(state, config, output_path, quant_type, verbose):
    """Write GGUF from a dict with GGUF tensor names as keys."""
    from dataclasses import dataclass as dc

    @dc
    class TI:
        name: str
        data: torch.Tensor
        quant: int
        offset: int = 0

    tensors = []
    for name, data in state.items():
        if quant_type == GGML_F16 and data.dtype == torch.float32:
            data = data.half()
        tensors.append(TI(name, data, quant_type))

    # Compute offsets
    offset = 0
    for ti in tensors:
        ti.offset = offset
        offset += _padded_size(ti.data.numel() * ti.data.element_size())

    # Metadata
    arch = "llama"
    rc = config.rope_scaling or {}
    metadata = [
        ("general.architecture", STRING, arch),
        ("general.name", STRING, "LlamaMoE-1M"),
        ("general.file_type", UINT32, 1),
        ("general.quantization_version", UINT32, 2),
        (f"{arch}.context_length", UINT32, config.max_position_embeddings),
        (f"{arch}.embedding_length", UINT32, config.n_embd),
        (f"{arch}.block_count", UINT32, config.n_layer),
        (f"{arch}.feed_forward_length", UINT32, config.n_inner),
        (f"{arch}.attention.head_count", UINT32, config.n_head),
        (f"{arch}.attention.head_count_kv", UINT32, config.n_head),
        (f"{arch}.attention.window_size", UINT32, config.sliding_window),
        (f"{arch}.rope.theta", FLOAT32, float(config.rope_theta)),
        (f"{arch}.rope.scaling.type", STRING, "yarn"),
        (f"{arch}.rope.scaling.factor", FLOAT32, float(rc.get("factor", 256.0))),
        (f"{arch}.rope.scaling.original_context_length", UINT32, 4096),
        (f"{arch}.expert_count", UINT32, config.n_experts),
        (f"{arch}.expert_used_count", UINT32, config.top_k),
        (f"{arch}.vocab_size", UINT32, config.vocab_size),
        (f"{arch}.norm_eps", FLOAT32, float(config.rms_norm_eps)),
        ("tokenizer.ggml.model", STRING, "gpt2"),
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(struct.pack("<I", GGUF_MAGIC))
        f.write(struct.pack("<I", GGUF_VERSION))
        f.write(struct.pack("<Q", len(tensors)))
        f.write(struct.pack("<Q", len(metadata)))

        for key, vtype, value in metadata:
            _write_string(f, key)
            f.write(struct.pack("<I", vtype))
            _write_value(f, vtype, value)

        for ti in tensors:
            _write_string(f, ti.name)
            rev_dims = list(reversed(ti.data.shape))
            f.write(struct.pack("<I", len(rev_dims)))
            for d in rev_dims:
                f.write(struct.pack("<Q", d))
            f.write(struct.pack("<I", ti.quant))
            f.write(struct.pack("<Q", ti.offset))

        _pad_to(f, ALIGNMENT)

        for ti in tensors:
            data_bytes = ti.data.contiguous().numpy().tobytes()
            f.write(data_bytes)
            rem = len(data_bytes) % ALIGNMENT
            if rem:
                f.write(b'\x00' * (ALIGNMENT - rem))

    # Verify
    with open(output_path, "rb") as f:
        magic = struct.unpack("<I", f.read(4))[0]
        assert magic == GGUF_MAGIC

    if verbose:
        print(f"[convert] {output_path}: {output_path.stat().st_size/1e6:.1f}MB, "
              f"{len(tensors)} tensors, magic OK", file=sys.stderr)

    return output_path


# ── CLI ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="LlamaMoE-1M → GGUF converter")
    parser.add_argument("checkpoint", type=str, help=".pt checkpoint or model dir")
    parser.add_argument("--output", "-o", type=str, default=None,
                        help="Output .gguf file (default: <checkpoint>.gguf)")
    parser.add_argument("--f16", action="store_true",
                        help="Store as float16 (default: float32)")
    parser.add_argument("--direct", action="store_true",
                        help="Load model directly (not checkpoint) and convert")
    args = parser.parse_args()

    ckpt = Path(args.checkpoint)
    if not ckpt.exists():
        print(f"ERROR: {ckpt} not found", file=sys.stderr)
        sys.exit(1)

    out = Path(args.output) if args.output else ckpt.with_suffix(".gguf")
    qt = GGML_F16 if args.f16 else GGML_F32

    if args.direct:
        # Load model directly
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from model_llama import LlamaMoEConfig, LlamaMoE1M
        config = LlamaMoEConfig()
        model = LlamaMoE1M(config)
        print(f"[convert] Fresh LlamaMoE-1M: {model.count_parameters()['total']/1e6:.1f}M params",
              file=sys.stderr)
        convert_from_model(model, out, qt)
    else:
        convert_to_gguf(ckpt, out, qt)
