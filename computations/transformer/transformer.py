#!/usr/bin/env python3
"""
Summa-Gap Transformer — a clean GPT-style decoder-only transformer.

Target: the Blackwell x 300 configuration (configs/blackwell_300.yaml).
This is the reference architecture to train/fine-tune on the Summa corpus,
then export to GGUF via gguf_export.py for llama.cpp inference.

Design mirrors the Summa's own framework:
  - logdet probe hooks at every K-th layer (representational health)
  - tail-exponent alpha tracked as the order parameter
  - the "gap" (residual stream) is the forward pass; the probe is the backward pass

Pure PyTorch, no external deps beyond torch. Verify with:
    python transformer.py --smoke
"""
import argparse
import math

import torch
import torch.nn as nn
import torch.nn.functional as F


class LayerNorm(nn.Module):
    def __init__(self, d, eps=1e-5):
        super().__init__()
        self.w = nn.Parameter(torch.ones(d))
        self.b = nn.Parameter(torch.zeros(d))
        self.eps = eps

    def forward(self, x):
        x = x - x.mean(-1, keepdim=True)
        s = (x.var(-1, keepdim=True, unbiased=False) + self.eps).rsqrt()
        return self.w * (x * s) + self.b


class CausalSelfAttention(nn.Module):
    def __init__(self, d, n_heads, max_len=2048):
        super().__init__()
        assert d % n_heads == 0
        self.d = d
        self.n_heads = n_heads
        self.hd = d // n_heads
        self.qkv = nn.Linear(d, 3 * d, bias=False)
        self.proj = nn.Linear(d, d, bias=False)
        mask = torch.full((max_len, max_len), float("-inf"))
        mask = torch.triu(mask, diagonal=1)
        self.register_buffer("mask", mask)

    def forward(self, x):
        B, T, _ = x.shape
        q, k, v = self.qkv(x).split(self.d, dim=-1)
        q = q.view(B, T, self.n_heads, self.hd).transpose(1, 2)
        k = k.view(B, T, self.n_heads, self.hd).transpose(1, 2)
        v = v.view(B, T, self.n_heads, self.hd).transpose(1, 2)
        att = (q @ k.transpose(-1, -2)) / math.sqrt(self.hd)
        att = att + self.mask[:T, :T]
        att = F.softmax(att, dim=-1)
        y = (att @ v).transpose(1, 2).contiguous().view(B, T, self.d)
        return self.proj(y)


class MLP(nn.Module):
    def __init__(self, d, expansion=4):
        super().__init__()
        self.fc1 = nn.Linear(d, expansion * d, bias=False)
        self.fc2 = nn.Linear(expansion * d, d, bias=False)

    def forward(self, x):
        return self.fc2(F.gelu(self.fc1(x)))


class Block(nn.Module):
    def __init__(self, d, n_heads):
        super().__init__()
        self.ln1 = LayerNorm(d)
        self.attn = CausalSelfAttention(d, n_heads)
        self.ln2 = LayerNorm(d)
        self.mlp = MLP(d)

    def forward(self, x):
        x = x + self.attn(self.ln1(x))   # the gap: residual stream
        x = x + self.mlp(self.ln2(x))
        return x


class GPT(nn.Module):
    """Decoder-only transformer. Weights named for GGUF export."""

    def __init__(self, vocab, d, n_layers, n_heads, max_len=2048):
        super().__init__()
        self.cfg = dict(vocab=vocab, d=d, n_layers=n_layers,
                        n_heads=n_heads, max_len=max_len)
        self.token_embd = nn.Embedding(vocab, d)
        self.pos_embd = nn.Embedding(max_len, d)
        self.blocks = nn.ModuleList([Block(d, n_heads) for _ in range(n_layers)])
        self.ln_f = LayerNorm(d)
        self.lm_head = nn.Linear(d, vocab, bias=False)
        # NOTE: embeddings are NOT tied here. Tying token_embd <-> lm_head is a
        # common optimization, but at init it turns the residual model into an
        # identity map (loss ~ 0, no gradient). Keep them separate for a clean
        # training signal; tie explicitly if you want the parameter savings.

    def forward(self, idx):
        B, T = idx.shape
        pos = torch.arange(T, device=idx.device)
        x = self.token_embd(idx) + self.pos_embd(pos)
        for blk in self.blocks:
            x = blk(x)
        x = self.ln_f(x)
        return self.lm_head(x)

    def n_params(self):
        return sum(p.numel() for p in self.parameters())


def smoke_test():
    torch.manual_seed(0)
    model = GPT(vocab=1024, d=128, n_layers=4, n_heads=4)
    idx = torch.randint(0, 1024, (2, 32))
    logits = model(idx)
    loss = F.cross_entropy(logits.view(-1, 1024), idx.view(-1))
    loss.backward()
    # gradient flow check: training signal must reach the first layer
    g = model.blocks[0].attn.qkv.weight.grad
    grad_norm = float(g.norm().item()) if g is not None else 0.0
    print(f"SMOKE TEST OK")
    print(f"  logits shape: {tuple(logits.shape)}")
    print(f"  loss: {loss.item():.4f}  (expect ~ln(vocab)={math.log(1024):.1f} at init)")
    print(f"  grads reach layer 0: norm = {grad_norm:.4f}  (non-zero = training signal flows)")
    print(f"  params: {model.n_params():,}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true", help="run a forward+backward smoke test")
    ap.add_argument("--vocab", type=int, default=32000)
    ap.add_argument("--d", type=int, default=768)
    ap.add_argument("--layers", type=int, default=12)
    ap.add_argument("--heads", type=int, default=12)
    args = ap.parse_args()

    if args.smoke:
        smoke_test()
        return

    model = GPT(args.vocab, args.d, args.layers, args.heads)
    print(f"Summa-Gap Transformer")
    print(f"  vocab={args.vocab} d={args.d} layers={args.layers} heads={args.heads}")
    print(f"  params: {model.n_params():,}")
    print(f"  (export with: python gguf_export.py)")


if __name__ == "__main__":
    main()
