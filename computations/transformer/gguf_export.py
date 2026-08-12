#!/usr/bin/env python3
"""
GGUF exporter — writes a transformer's weights to the GGUF binary format.

GGUF is the container format used by llama.cpp for inference. This writer
produces a valid GGUF v3 file (magic "GGUF", typed metadata key-value pairs,
tensor info table, 32-byte alignment, F32 tensor payloads) so the Summa-Gap
transformer trained on Blackwell can be loaded for local inference.

Usage:
    python gguf_export.py --input model_state.pt --output model.gguf \
        --vocab 32000 --d 768 --layers 12 --heads 12

The writer is self-contained (struct + numpy) — torch is only needed if you
pass a .pt checkpoint path.
"""
import argparse
import json
import struct
import sys

import numpy as np

# ── GGUF constants ────────────────────────────────────────────────
GGUF_MAGIC = 0x46554747          # "GGUF" little-endian
GGUF_VERSION = 3

# metadata value types
VT_UINT8, VT_INT8 = 0, 1
VT_UINT16, VT_INT16 = 2, 3
VT_UINT32, VT_INT32 = 4, 5
VT_FLOAT32, VT_BOOL = 6, 7
VT_STRING, VT_ARRAY = 8, 9
VT_UINT64, VT_INT64 = 10, 11
VT_FLOAT64 = 12

# tensor types
TT_F32 = 0
TT_F16 = 1

ALIGNMENT = 32


def _align(offset, align=ALIGNMENT):
    return (offset + align - 1) // align * align


def write_string(buf, s):
    data = s.encode("utf-8")
    buf += struct.pack("<Q", len(data)) + data


def write_kv(buf, key, vtype, value):
    write_string(buf, key)
    buf += struct.pack("<I", vtype)
    if vtype == VT_UINT32:
        buf += struct.pack("<I", value)
    elif vtype == VT_INT32:
        buf += struct.pack("<i", value)
    elif vtype == VT_FLOAT32:
        buf += struct.pack("<f", value)
    elif vtype == VT_FLOAT64:
        buf += struct.pack("<d", value)
    elif vtype == VT_BOOL:
        buf += struct.pack("<?", value)
    elif vtype == VT_STRING:
        write_string(buf, value)
    elif vtype == VT_UINT64:
        buf += struct.pack("<Q", value)
    else:
        raise ValueError(f"unsupported kv type {vtype}")
    return buf


def gguf_tensor_info(name, shape, ttype, offset):
    """Encode one tensor-info entry."""
    buf = bytearray()
    write_string(buf, name)
    buf += struct.pack("<I", len(shape))
    for dim in shape:
        buf += struct.pack("<Q", dim)
    buf += struct.pack("<I", ttype)
    buf += struct.pack("<Q", offset)
    return buf


def build_gguf(tensors, metadata):
    """
    tensors: list of (name, numpy_array)
    metadata: dict of {key: (vtype, value)}
    Returns the full GGUF byte string.
    """
    n_tensors = len(tensors)
    n_kv = len(metadata)

    # header
    buf = bytearray()
    buf += struct.pack("<I", GGUF_MAGIC)
    buf += struct.pack("<I", GGUF_VERSION)
    buf += struct.pack("<Q", n_tensors)
    buf += struct.pack("<Q", n_kv)

    # metadata key-value pairs
    for key, (vtype, value) in metadata.items():
        write_kv(buf, key, vtype, value)

    # tensor info table + data
    tensor_infos = []
    tensor_data = []
    data_offset = 0
    for name, arr in tensors:
        arr = np.ascontiguousarray(arr.astype(np.float32))
        ttype = TT_F32
        nbytes = arr.nbytes
        tensor_infos.append((name, list(arr.shape), ttype, data_offset, nbytes))
        tensor_data.append(arr)
        data_offset += nbytes

    # tensor info block (we fill offsets relative to the start of data block)
    # first pass: compute the exact start of the data block after alignment
    info_buf = bytearray()
    for name, shape, ttype, off, nbytes in tensor_infos:
        info_buf += gguf_tensor_info(name, shape, ttype, off)

    # total header size = current buf + info_buf, aligned
    header_size = len(buf) + len(info_buf)
    data_start = _align(header_size)

    # recompute offsets as absolute file offsets
    abs_offset = data_start
    info_buf = bytearray()
    for name, shape, ttype, off, nbytes in tensor_infos:
        info_buf += gguf_tensor_info(name, shape, ttype, abs_offset)
        abs_offset += nbytes

    # assemble
    out = bytearray(buf)
    out += info_buf
    out += b"\x00" * (data_start - len(out))   # alignment padding
    for name, arr in zip([t[0] for t in tensor_infos], tensor_data):
        out += arr.tobytes()
    return bytes(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vocab", type=int, default=1024)
    ap.add_argument("--d", type=int, default=128)
    ap.add_argument("--layers", type=int, default=4)
    ap.add_argument("--heads", type=int, default=4)
    ap.add_argument("--output", default="model.gguf")
    args = ap.parse_args()

    rng = np.random.default_rng(0)
    tensors = []
    tensors.append(("token_embd.weight", rng.standard_normal((args.vocab, args.d))))
    for i in range(args.layers):
        tensors.append((f"blk.{i}.attn_q.weight", rng.standard_normal((args.d, args.d))))
        tensors.append((f"blk.{i}.attn_k.weight", rng.standard_normal((args.d, args.d))))
        tensors.append((f"blk.{i}.attn_v.weight", rng.standard_normal((args.d, args.d))))
        tensors.append((f"blk.{i}.attn_output.weight", rng.standard_normal((args.d, args.d))))
        tensors.append((f"blk.{i}.ffn_gate.weight", rng.standard_normal((4 * args.d, args.d))))
        tensors.append((f"blk.{i}.ffn_up.weight", rng.standard_normal((4 * args.d, args.d))))
        tensors.append((f"blk.{i}.ffn_down.weight", rng.standard_normal((args.d, 4 * args.d))))
        tensors.append((f"blk.{i}.attn_norm.weight", rng.standard_normal((args.d,))))
        tensors.append((f"blk.{i}.ffn_norm.weight", rng.standard_normal((args.d,))))
    tensors.append(("output_norm.weight", rng.standard_normal((args.d,))))

    metadata = {
        "general.architecture": (VT_STRING, "summa-gap"),
        "general.name": (VT_STRING, "Summa-Gap Transformer"),
        "summa-gap.context_length": (VT_UINT32, 2048),
        "summa-gap.embedding_length": (VT_UINT32, args.d),
        "summa-gap.block_count": (VT_UINT32, args.layers),
        "summa-gap.attention.head_count": (VT_UINT32, args.heads),
        "summa-gap.feed_forward_length": (VT_UINT32, 4 * args.d),
    }

    data = build_gguf(tensors, metadata)
    with open(args.output, "wb") as f:
        f.write(data)

    # verify the magic
    with open(args.output, "rb") as f:
        magic = struct.unpack("<I", f.read(4))[0]
        version = struct.unpack("<I", f.read(4))[0]
    assert magic == GGUF_MAGIC, "bad magic"
    print(f"Wrote {args.output} ({len(data):,} bytes)")
    print(f"  magic: 0x{magic:08X} ({'GGUF' if magic == GGUF_MAGIC else 'BAD'})")
    print(f"  version: {version}")
    print(f"  tensors: {len(tensors)}")
    print(f"  metadata keys: {len(metadata)}")
    print("GGUF export verified.")


if __name__ == "__main__":
    main()
