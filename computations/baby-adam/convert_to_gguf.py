#!/usr/bin/env python3
"""
convert_to_gguf.py — Convert Baby Adam E checkpoints to GGUF format.

GGUF is the file format used by llama.cpp for model inference.
This converter maps BabyAdamE's tensor names to the GGUF naming convention
and writes a valid GGUF binary file.

GGUF specification:
  - Magic: "GGUF" (0x47475546)
  - Version 3
  - Tensor count, metadata KV count
  - Metadata key-value pairs (architecture, config, tokenizer, etc.)
  - Tensor info (name, dimensions, type, offset)
  - Tensor data (raw bytes)

For Baby Adam E, we use a custom architecture tag "babyadame" since the
architecture (character-level, RoPE, Pre-LN, SwiGLU, MoE, KS norm) is not
a standard llama.cpp architecture. The GGUF file is valid and can be read
by any GGUF-compatible tool, but inference requires a custom C++ backend.

Usage:
    python convert_to_gguf.py checkpoint.pt [--output model.gguf] [--quantize]
"""

import argparse
import struct
import json
import sys
import os
import math
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from collections import OrderedDict

import torch
import numpy as np


# ═══════════════════════════════════════════════════════════════════════
# GGUF FORMAT CONSTANTS
# ═══════════════════════════════════════════════════════════════════════

GGUF_MAGIC = 0x46554747  # "GGUF" in little-endian

GGUF_VERSION = 3

# GGUF value types
GGUF_TYPE_UINT8   = 0
GGUF_TYPE_INT8    = 1
GGUF_TYPE_UINT16  = 2
GGUF_TYPE_INT16   = 3
GGUF_TYPE_UINT32  = 4
GGUF_TYPE_INT32   = 5
GGUF_TYPE_FLOAT32 = 6
GGUF_TYPE_BOOL    = 7
GGUF_TYPE_STRING  = 8
GGUF_TYPE_ARRAY   = 9
GGUF_TYPE_UINT64  = 10
GGUF_TYPE_INT64   = 11
GGUF_TYPE_FLOAT64 = 12

# GGML tensor types
GGML_TYPE_F32  = 0
GGML_TYPE_F16  = 1
GGML_TYPE_Q4_0 = 2
GGML_TYPE_Q4_1 = 3
GGML_TYPE_Q5_0 = 6
GGML_TYPE_Q5_1 = 7
GGML_TYPE_Q8_0 = 8
GGML_TYPE_Q8_1 = 9
GGML_TYPE_Q2_K = 10
GGML_TYPE_Q3_K = 11
GGML_TYPE_Q4_K = 12
GGML_TYPE_Q5_K = 13
GGML_TYPE_Q6_K = 14
GGML_TYPE_Q8_K = 15
GGML_TYPE_IQ2_XXS = 16
GGML_TYPE_IQ2_XS  = 17
GGML_TYPE_IQ3_XXS = 18
GGML_TYPE_IQ1_S   = 19
GGML_TYPE_IQ4_NL  = 20
GGML_TYPE_IQ3_S   = 21
GGML_TYPE_IQ2_S   = 22
GGML_TYPE_IQ4_XS  = 23
GGML_TYPE_I8      = 24
GGML_TYPE_I16     = 25
GGML_TYPE_I32     = 26
GGML_TYPE_I64     = 27
GGML_TYPE_F64     = 28
GGML_TYPE_IQ1_M   = 29
GGML_TYPE_BF16    = 30

GGML_QNT_VERSION = 2

# Alignment for tensor data
GGUF_DEFAULT_ALIGNMENT = 32


# ═══════════════════════════════════════════════════════════════════════
# GGUF WRITER
# ═══════════════════════════════════════════════════════════════════════

class GGUFWriter:
    """Write GGUF format binary files."""

    def __init__(self, path: str, arch: str = "babyadame"):
        self.path = path
        self.arch = arch
        self.metadata: OrderedDict[str, Tuple[int, Any]] = OrderedDict()
        self.tensors: OrderedDict[str, Tuple[np.ndarray, int]] = OrderedDict()
        self.alignment = GGUF_DEFAULT_ALIGNMENT

    def add_metadata_bool(self, key: str, value: bool):
        self.metadata[key] = (GGUF_TYPE_BOOL, value)

    def add_metadata_uint32(self, key: str, value: int):
        self.metadata[key] = (GGUF_TYPE_UINT32, value)

    def add_metadata_uint64(self, key: str, value: int):
        self.metadata[key] = (GGUF_TYPE_UINT64, value)

    def add_metadata_int32(self, key: str, value: int):
        self.metadata[key] = (GGUF_TYPE_INT32, value)

    def add_metadata_float32(self, key: str, value: float):
        self.metadata[key] = (GGUF_TYPE_FLOAT32, value)

    def add_metadata_string(self, key: str, value: str):
        self.metadata[key] = (GGUF_TYPE_STRING, value)

    def add_metadata_array(self, key: str, values: List[Any], element_type: int):
        self.metadata[key] = (GGUF_TYPE_ARRAY, (element_type, values))

    def add_tensor(
        self,
        name: str,
        tensor: torch.Tensor,
        quant_type: int = GGML_TYPE_F32,
    ):
        """Add a tensor to the GGUF file."""
        if quant_type == GGML_TYPE_F32:
            data = tensor.detach().cpu().float().numpy()
        elif quant_type == GGML_TYPE_F16:
            data = tensor.detach().cpu().half().numpy().view(np.uint16)
        elif quant_type == GGML_TYPE_BF16:
            data = tensor.detach().cpu().bfloat16().numpy().view(np.uint16)
        else:
            raise ValueError(f"Unsupported quant type: {quant_type}")

        self.tensors[name] = (data, quant_type)

    def _write_string(self, f, s: str):
        """Write a GGUF string: uint64 length + UTF-8 bytes."""
        encoded = s.encode('utf-8')
        f.write(struct.pack('<Q', len(encoded)))
        f.write(encoded)

    def _write_value(self, f, value_type: int, value: Any):
        """Write a typed GGUF value."""
        if value_type == GGUF_TYPE_UINT8:
            f.write(struct.pack('<B', value))
        elif value_type == GGUF_TYPE_INT8:
            f.write(struct.pack('<b', value))
        elif value_type == GGUF_TYPE_UINT16:
            f.write(struct.pack('<H', value))
        elif value_type == GGUF_TYPE_INT16:
            f.write(struct.pack('<h', value))
        elif value_type == GGUF_TYPE_UINT32:
            f.write(struct.pack('<I', value))
        elif value_type == GGUF_TYPE_INT32:
            f.write(struct.pack('<i', value))
        elif value_type == GGUF_TYPE_UINT64:
            f.write(struct.pack('<Q', value))
        elif value_type == GGUF_TYPE_INT64:
            f.write(struct.pack('<q', value))
        elif value_type == GGUF_TYPE_FLOAT32:
            f.write(struct.pack('<f', value))
        elif value_type == GGUF_TYPE_FLOAT64:
            f.write(struct.pack('<d', value))
        elif value_type == GGUF_TYPE_BOOL:
            f.write(struct.pack('<?', value))
        elif value_type == GGUF_TYPE_STRING:
            self._write_string(f, value)
        elif value_type == GGUF_TYPE_ARRAY:
            element_type, values = value
            f.write(struct.pack('<I', element_type))
            f.write(struct.pack('<Q', len(values)))
            for v in values:
                # Assume homogeneous array — write natively based on element_type
                if element_type == GGUF_TYPE_INT32:
                    f.write(struct.pack('<i', v))
                elif element_type == GGUF_TYPE_FLOAT32:
                    f.write(struct.pack('<f', v))
                elif element_type == GGUF_TYPE_UINT32:
                    f.write(struct.pack('<I', v))
                elif element_type == GGUF_TYPE_STRING:
                    self._write_string(f, v)
                else:
                    self._write_value(f, element_type, v)
        else:
            raise ValueError(f"Unknown GGUF type: {value_type}")

    def write(self):
        """Write the complete GGUF file."""
        with open(self.path, 'wb') as f:
            # ── Header ──
            f.write(struct.pack('<I', GGUF_MAGIC))
            f.write(struct.pack('<I', GGUF_VERSION))
            f.write(struct.pack('<Q', len(self.tensors)))
            f.write(struct.pack('<Q', len(self.metadata)))

            # ── Metadata (key-value pairs) ──
            for key, (value_type, value) in self.metadata.items():
                self._write_string(f, key)
                f.write(struct.pack('<I', value_type))
                self._write_value(f, value_type, value)

            # ── Tensor info ──
            # First pass: collect sizes to compute offsets
            offset = f.tell()
            tensor_infos = []

            for name, (data, quant_type) in self.tensors.items():
                # String name
                name_encoded = name.encode('utf-8')
                name_len = 8 + len(name_encoded)  # uint64 length + bytes

                # n_dims (4 bytes) + dims array
                n_dims = len(data.shape)
                dims_size = 4 + n_dims * 8  # uint32 count + uint64 per dim

                # type (4 bytes) + offset (8 bytes)
                type_offset_size = 4 + 8

                total_info_size = name_len + dims_size + type_offset_size
                tensor_infos.append((name, data, quant_type, offset, n_dims, total_info_size))

                # Align to 32 bytes
                offset += total_info_size
                # Tensor data will start after all infos, aligned
                data_size = data.nbytes
                # We'll compute the aligned data offset after the info block

            # Total size of info block
            info_end = offset

            # Now compute aligned data offsets
            data_offset = info_end
            final_tensor_infos = []

            for name, data, quant_type, info_off, n_dims, info_size in tensor_infos:
                # Align data_offset
                if data_offset % self.alignment != 0:
                    data_offset += self.alignment - (data_offset % self.alignment)

                final_tensor_infos.append((
                    name, data, quant_type, info_off, data_offset, n_dims
                ))
                data_offset += data.nbytes

            # Write tensor infos
            for name, data, quant_type, info_off, data_off, n_dims in final_tensor_infos:
                self._write_string(f, name)
                f.write(struct.pack('<I', n_dims))
                for dim in reversed(data.shape):  # GGUF uses reverse dimension order
                    f.write(struct.pack('<Q', dim))
                f.write(struct.pack('<I', quant_type))
                f.write(struct.pack('<Q', data_off))

            # ── Pad to alignment ──
            pos = f.tell()
            if pos % self.alignment != 0:
                pad = self.alignment - (pos % self.alignment)
                f.write(b'\x00' * pad)

            # ── Tensor data ──
            for name, data, quant_type, info_off, data_off, n_dims in final_tensor_infos:
                # Pad to alignment if needed
                pos = f.tell()
                if pos < data_off:
                    f.write(b'\x00' * (data_off - pos))
                f.write(data.tobytes())

        file_size = os.path.getsize(self.path)
        print(f"GGUF written: {self.path}")
        print(f"  Architecture: {self.arch}")
        print(f"  Tensors: {len(self.tensors)}")
        print(f"  Metadata keys: {len(self.metadata)}")
        print(f"  File size: {file_size:,} bytes ({file_size / 1024**2:.1f} MB)")


# ═══════════════════════════════════════════════════════════════════════
# TENSOR NAME MAPPING — BabyAdamE → GGUF convention
# ═══════════════════════════════════════════════════════════════════════

def map_tensor_name(name: str, cfg: dict) -> Optional[str]:
    """
    Map BabyAdamE state_dict keys to GGUF tensor names.

    GGUF naming convention (llama.cpp style):
      token_embd.weight
      blk.{i}.attn_norm.weight
      blk.{i}.attn_q.weight
      blk.{i}.attn_k.weight
      blk.{i}.attn_v.weight
      blk.{i}.attn_output.weight
      blk.{i}.ffn_norm.weight
      blk.{i}.ffn_gate.weight     (w1 for SwiGLU)
      blk.{i}.ffn_up.weight       (w3 for SwiGLU)
      blk.{i}.ffn_down.weight     (w2 for SwiGLU)
      blk.{i}.ffn_gate_inp.weight (MoE router)
      blk.{i}.ffn_gate.{e}.weight (MoE expert e gate)
      blk.{i}.ffn_up.{e}.weight   (MoE expert e up)
      blk.{i}.ffn_down.{e}.weight (MoE expert e down)
      output_norm.weight
      output.weight
    """

    # Token embedding
    if name == 'token_embed.weight':
        return 'token_embd.weight'

    # Output head (tied with embedding — may be same tensor)
    if name == 'lm_head.weight':
        return 'output.weight'

    # Final layer norm
    if name == 'ln_final.weight':
        return 'output_norm.weight'

    # Transformer blocks
    # Pattern: blocks.{i}.ln1.weight, blocks.{i}.ln2.weight
    # blocks.{i}.attn.q_proj.weight, etc.
    # blocks.{i}.ffn.router.router.weight (prophet router)
    # blocks.{i}.ffn.experts.{e}.w1.weight, etc.

    parts = name.split('.')

    if parts[0] == 'blocks':
        try:
            layer_idx = int(parts[1])
        except ValueError:
            return None

        sub = '.'.join(parts[2:])

        # Layer norms (may be KS anisotropic)
        if sub == 'ln1.weight':
            return f'blk.{layer_idx}.attn_norm.weight'
        if sub == 'ln2.weight':
            return f'blk.{layer_idx}.ffn_norm.weight'
        if sub == 'ln1.log_a' or sub == 'ln1.log_b':
            return None  # KS params not needed for inference
        if sub == 'ln2.log_a' or sub == 'ln2.log_b':
            return None
        if sub.startswith('ln1.radial_proj') or sub.startswith('ln1.angular_proj'):
            return None
        if sub.startswith('ln2.radial_proj') or sub.startswith('ln2.angular_proj'):
            return None

        # Attention
        if sub == 'attn.q_proj.weight':
            return f'blk.{layer_idx}.attn_q.weight'
        if sub == 'attn.k_proj.weight':
            return f'blk.{layer_idx}.attn_k.weight'
        if sub == 'attn.v_proj.weight':
            return f'blk.{layer_idx}.attn_v.weight'
        if sub == 'attn.out_proj.weight':
            return f'blk.{layer_idx}.attn_output.weight'

        # FFN / MoE
        if sub == 'ffn.router.router.weight':
            return f'blk.{layer_idx}.ffn_gate_inp.weight'

        # Prophet router threshold net
        if sub.startswith('ffn.router.threshold_net'):
            return None  # Prophet-specific, not needed for vanilla inference

        # MoE experts
        if 'ffn.experts' in sub:
            # ffn.experts.{e}.w1.weight → blk.{i}.ffn_gate.{e}.weight
            expert_parts = sub.split('.')
            try:
                expert_idx = int(expert_parts[2])
            except (ValueError, IndexError):
                return None

            param = '.'.join(expert_parts[3:])
            if param == 'w1.weight':
                return f'blk.{layer_idx}.ffn_gate.{expert_idx}.weight'
            if param == 'w3.weight':
                return f'blk.{layer_idx}.ffn_up.{expert_idx}.weight'
            if param == 'w2.weight':
                return f'blk.{layer_idx}.ffn_down.{expert_idx}.weight'

        return None

    # Logit manifold (auxiliary, not core architecture)
    if name.startswith('logit_manifold'):
        return None

    return None


# ═══════════════════════════════════════════════════════════════════════
# MAIN CONVERSION
# ═══════════════════════════════════════════════════════════════════════

def convert(
    checkpoint_path: str,
    output_path: str,
    quantize: bool = False,
    metadata_overrides: Optional[dict] = None,
):
    """Convert a Baby Adam E checkpoint to GGUF format."""

    print(f"Loading checkpoint: {checkpoint_path}")
    checkpoint = torch.load(checkpoint_path, map_location='cpu', weights_only=False)

    # Extract config
    if 'config' in checkpoint:
        cfg = checkpoint['config']
        if hasattr(cfg, '__dict__'):
            cfg_dict = vars(cfg)
        elif isinstance(cfg, dict):
            cfg_dict = cfg
        else:
            cfg_dict = {}
    else:
        # Default BabyAdamE config
        cfg_dict = {
            'vocab_size': 256,
            'd_model': 256,
            'n_layers': 6,
            'n_heads': 8,
            'd_ff': 1024,
            'max_seq_len': 512,
            'n_experts': 4,
            'n_activated': 2,
            'moe_enabled': True,
            'rope_theta': 10000.0,
            'dropout': 0.1,
        }

    # Extract state dict
    if 'model_state_dict' in checkpoint:
        state_dict = checkpoint['model_state_dict']
    else:
        # Assume the checkpoint IS the state dict (or wrapped)
        state_dict = {k: v for k, v in checkpoint.items()
                      if isinstance(v, torch.Tensor)}

    print(f"Config: d_model={cfg_dict.get('d_model', '?')}, "
          f"n_layers={cfg_dict.get('n_layers', '?')}, "
          f"n_experts={cfg_dict.get('n_experts', '?')}")

    # Create GGUF writer
    writer = GGUFWriter(output_path, arch="babyadame")

    # ── Write metadata ──

    # General
    writer.add_metadata_string("general.architecture", "babyadame")
    writer.add_metadata_string("general.name", "BabyAdamE")
    writer.add_metadata_string("general.description",
        "Baby Adam E — Extended architecture with LogDet/Logit/Ledger, "
        "Berry phase, Connes spectral triple, WDW constraint, "
        "KS anisotropic scaling, Prophet router, MP shrinkage")
    writer.add_metadata_string("general.license", "CC0")

    # File info
    writer.add_metadata_uint32("general.file_type", 1)  # 1 = model

    # Quantization
    writer.add_metadata_uint32("general.quantization_version", GGML_QNT_VERSION)

    # Model config
    n_layers = cfg_dict.get('n_layers', 6)
    n_heads = cfg_dict.get('n_heads', 8)
    n_experts = cfg_dict.get('n_experts', 4)
    n_activated = cfg_dict.get('n_activated', 2)
    d_model = cfg_dict.get('d_model', 256)
    d_ff = cfg_dict.get('d_ff', 1024)
    vocab_size = cfg_dict.get('vocab_size', 256)
    max_seq_len = cfg_dict.get('max_seq_len', 512)

    writer.add_metadata_uint32("babyadame.block_count", n_layers)
    writer.add_metadata_uint32("babyadame.embedding_length", d_model)
    writer.add_metadata_uint32("babyadame.feed_forward_length", d_ff)
    writer.add_metadata_uint32("babyadame.attention.head_count", n_heads)
    writer.add_metadata_uint32("babyadame.attention.head_count_kv", n_heads)
    writer.add_metadata_float32("babyadame.rope.theta",
                                 cfg_dict.get('rope_theta', 10000.0))
    writer.add_metadata_bool("babyadame.rope.use_neox_style", False)

    # MoE config
    writer.add_metadata_uint32("babyadame.expert_count", n_experts)
    writer.add_metadata_uint32("babyadame.expert_used_count", n_activated)

    # Context
    writer.add_metadata_uint32("babyadame.context_length", max_seq_len)

    # Vocab
    writer.add_metadata_uint32("babyadame.vocab_size", vocab_size)

    # Architecture flags
    writer.add_metadata_bool("babyadame.use_pre_norm", True)
    writer.add_metadata_bool("babyadame.use_swiglu", True)
    writer.add_metadata_bool("babyadame.use_moe", cfg_dict.get('moe_enabled', True))
    writer.add_metadata_bool("babyadame.use_ks_norm", cfg_dict.get('ks_enabled', True))
    writer.add_metadata_bool("babyadame.use_prophet_router",
                              cfg_dict.get('prophet_stopping', False))

    # Tokenizer (character-level ASCII)
    writer.add_metadata_string("tokenizer.ggml.model", "ascii")
    # Build ASCII token list
    tokens = [chr(i) for i in range(256)]
    writer.add_metadata_array("tokenizer.ggml.tokens", tokens, GGUF_TYPE_STRING)
    scores = [-1000.0] * 256  # All valid, equal score
    writer.add_metadata_array("tokenizer.ggml.scores", scores, GGUF_TYPE_FLOAT32)
    writer.add_metadata_uint32("tokenizer.ggml.token_type_count", 1)
    writer.add_metadata_array("tokenizer.ggml.token_type",
                               [1] * 256, GGUF_TYPE_INT32)  # 1 = normal
    writer.add_metadata_uint32("tokenizer.ggml.bos_token_id", 0)  # NUL
    writer.add_metadata_uint32("tokenizer.ggml.eos_token_id", 0)  # NUL

    # Training info if available
    if 'step' in checkpoint:
        writer.add_metadata_uint32("babyadame.training_step", checkpoint['step'])
    if 'train_losses' in checkpoint and checkpoint['train_losses']:
        writer.add_metadata_float32("babyadame.training_loss",
                                     checkpoint['train_losses'][-1])

    # Boll
    writer.add_metadata_string("general.url",
        "https://github.com/nousresearch/hermes-agent")
    writer.add_metadata_uint32("babyadame.file_version", 1)

    # Override metadata if requested
    if metadata_overrides:
        for k, v in metadata_overrides.items():
            if isinstance(v, bool):
                writer.add_metadata_bool(k, v)
            elif isinstance(v, int):
                writer.add_metadata_uint32(k, v)
            elif isinstance(v, float):
                writer.add_metadata_float32(k, v)
            elif isinstance(v, str):
                writer.add_metadata_string(k, v)

    # ── Map and add tensors ──
    mapped_count = 0
    skipped_count = 0

    for name, tensor in state_dict.items():
        gguf_name = map_tensor_name(name, cfg_dict)

        if gguf_name is None:
            skipped_count += 1
            continue

        # Determine quantization
        if quantize:
            # For initial release, use F16
            quant_type = GGML_TYPE_F16
        else:
            quant_type = GGML_TYPE_F32

        writer.add_tensor(gguf_name, tensor, quant_type)
        mapped_count += 1

    print(f"\nTensor mapping:")
    print(f"  Mapped: {mapped_count}")
    print(f"  Skipped: {skipped_count}")

    # ── Write ──
    writer.write()

    # ── Verify (basic) ──
    with open(output_path, 'rb') as f:
        magic = struct.unpack('<I', f.read(4))[0]
        if magic != GGUF_MAGIC:
            print("ERROR: Invalid GGUF magic number!")
            return False
        version = struct.unpack('<I', f.read(4))[0]
        print(f"\nVerification: magic=0x{magic:08X}, version={version} ✓")

    return True


# ═══════════════════════════════════════════════════════════════════════
# GGUF READER (for verification)
# ═══════════════════════════════════════════════════════════════════════

def inspect_gguf(path: str):
    """Read and display GGUF file header info."""
    with open(path, 'rb') as f:
        magic = struct.unpack('<I', f.read(4))[0]
        if magic != GGUF_MAGIC:
            print(f"ERROR: Not a GGUF file (magic=0x{magic:08X})")
            return

        version = struct.unpack('<I', f.read(4))[0]
        n_tensors = struct.unpack('<Q', f.read(8))[0]
        n_metadata = struct.unpack('<Q', f.read(8))[0]

        print(f"GGUF File: {path}")
        print(f"  Version: {version}")
        print(f"  Tensors: {n_tensors}")
        print(f"  Metadata: {n_metadata}")
        print()

        # Read metadata
        print("Metadata:")
        for _ in range(n_metadata):
            key_len = struct.unpack('<Q', f.read(8))[0]
            key = f.read(key_len).decode('utf-8')
            val_type = struct.unpack('<I', f.read(4))[0]

            type_names = {
                0: 'uint8', 1: 'int8', 2: 'uint16', 3: 'int16',
                4: 'uint32', 5: 'int32', 6: 'float32', 7: 'bool',
                8: 'string', 9: 'array', 10: 'uint64', 11: 'int64',
            }
            type_name = type_names.get(val_type, f'unknown({val_type})')

            if val_type == GGUF_TYPE_STRING:
                s_len = struct.unpack('<Q', f.read(8))[0]
                s = f.read(s_len).decode('utf-8', errors='replace')
                print(f"  {key}: {type_name} = {s[:80]}")
            elif val_type == GGUF_TYPE_UINT32:
                v = struct.unpack('<I', f.read(4))[0]
                print(f"  {key}: {type_name} = {v}")
            elif val_type == GGUF_TYPE_UINT64:
                v = struct.unpack('<Q', f.read(8))[0]
                print(f"  {key}: {type_name} = {v}")
            elif val_type == GGUF_TYPE_INT32:
                v = struct.unpack('<i', f.read(4))[0]
                print(f"  {key}: {type_name} = {v}")
            elif val_type == GGUF_TYPE_FLOAT32:
                v = struct.unpack('<f', f.read(4))[0]
                print(f"  {key}: {type_name} = {v}")
            elif val_type == GGUF_TYPE_BOOL:
                v = struct.unpack('<?', f.read(1))[0]
                print(f"  {key}: {type_name} = {v}")
            elif val_type == GGUF_TYPE_ARRAY:
                elem_type = struct.unpack('<I', f.read(4))[0]
                arr_len = struct.unpack('<Q', f.read(8))[0]
                print(f"  {key}: array[{arr_len}] of {type_names.get(elem_type, f'type({elem_type})')}")
                # Skip array data
                for _ in range(arr_len):
                    if elem_type == GGUF_TYPE_STRING:
                        s_len = struct.unpack('<Q', f.read(8))[0]
                        f.read(s_len)
                    elif elem_type == GGUF_TYPE_INT32:
                        f.read(4)
                    elif elem_type == GGUF_TYPE_FLOAT32:
                        f.read(4)
                    elif elem_type == GGUF_TYPE_UINT32:
                        f.read(4)
                    else:
                        # Skip unknown
                        f.read(4)
            else:
                f.read(4)  # Skip unknown

        # Read tensor infos
        print(f"\nTensors:")
        for i in range(min(n_tensors, 20)):  # Show first 20
            name_len = struct.unpack('<Q', f.read(8))[0]
            name = f.read(name_len).decode('utf-8')
            n_dims = struct.unpack('<I', f.read(4))[0]
            dims = []
            for _ in range(n_dims):
                dims.append(struct.unpack('<Q', f.read(8))[0])
            quant_type = struct.unpack('<I', f.read(4))[0]
            offset = struct.unpack('<Q', f.read(8))[0]

            quant_names = {
                0: 'F32', 1: 'F16', 2: 'Q4_0', 10: 'Q2_K', 11: 'Q3_K',
                12: 'Q4_K', 13: 'Q5_K', 14: 'Q6_K', 30: 'BF16',
            }
            qname = quant_names.get(quant_type, f'type({quant_type})')

            # GGUF stores dims reversed
            shape = list(reversed(dims))
            print(f"  {name}: {qname} {shape} @ 0x{offset:08X}")

        if n_tensors > 20:
            print(f"  ... and {n_tensors - 20} more tensors")


# ═══════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Convert Baby Adam E checkpoint to GGUF format"
    )
    parser.add_argument(
        'checkpoint', type=str,
        help='Path to .pt checkpoint file'
    )
    parser.add_argument(
        '--output', '-o', type=str, default=None,
        help='Output GGUF path (default: <checkpoint_name>.gguf)'
    )
    parser.add_argument(
        '--quantize', '-q', action='store_true',
        help='Quantize to F16 (default: F32)'
    )
    parser.add_argument(
        '--inspect', '-i', action='store_true',
        help='Inspect an existing GGUF file'
    )
    parser.add_argument(
        '--metadata', type=str, default=None,
        help='JSON string of metadata overrides'
    )

    args = parser.parse_args()

    # Inspection mode
    if args.inspect:
        inspect_gguf(args.checkpoint)
        return

    # Conversion mode
    if args.output is None:
        base = os.path.splitext(os.path.basename(args.checkpoint))[0]
        args.output = f"{base}.gguf"

    metadata = None
    if args.metadata:
        metadata = json.loads(args.metadata)

    success = convert(
        args.checkpoint,
        args.output,
        quantize=args.quantize,
        metadata_overrides=metadata,
    )

    if success:
        # Quick inspect of the result
        print("\n" + "=" * 60)
        inspect_gguf(args.output)

    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
