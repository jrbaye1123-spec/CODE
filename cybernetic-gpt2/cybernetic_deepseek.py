"""Cybernetic DeepSeek — Observer heads injected into pre-trained reasoning model.

Usage:
    # Download model yourself first:
    # huggingface-cli download deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B --local-dir ~/models/deepseek-r1-1.5b
    
    # Then run with your local path:
    python cybernetic_deepseek.py --model-path ~/models/deepseek-r1-1.5b
    
    # Or let it auto-download (slower, needs auth token):
    python cybernetic_deepseek.py
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import sys
import os
import argparse
from pathlib import Path
from typing import Optional

from transformers import AutoModelForCausalLM, AutoTokenizer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from moe_observer import MoEObserverBlock


class CyberneticDeepSeek(nn.Module):
    """DeepSeek-R1 with cybernetic observer heads in the residual stream."""

    def __init__(self, model_path: str, load_in_4bit: bool = True,
                 n_observer_experts: int = 8, k_active: int = 2):
        super().__init__()

        print(f"Loading: {model_path}")
        print(f"  4-bit: {load_in_4bit}")
        print(f"  Observer experts: {n_observer_experts}, Active: {k_active}")

        # Load base model
        load_kwargs = {
            "torch_dtype": torch.float16,
            "device_map": "auto",
            "trust_remote_code": True,
        }
        if load_in_4bit:
            load_kwargs["load_in_4bit"] = True

        self.base_model = AutoModelForCausalLM.from_pretrained(model_path, **load_kwargs)
        self.tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)

        # Architecture params
        base_cfg = self.base_model.config
        self.hidden_size = base_cfg.hidden_size
        self.num_layers = base_cfg.num_hidden_layers
        self.num_heads = base_cfg.num_attention_heads

        print(f"  Hidden: {self.hidden_size}, Layers: {self.num_layers}, Heads: {self.num_heads}")

        # Observer config
        from model import CyberneticGPT2Config
        obs_cfg = CyberneticGPT2Config(
            n_embd=self.hidden_size, n_head=self.num_heads,
            n_layer=1, block_size=8192,
            vocab_size=self.tokenizer.vocab_size,
        )

        # Inject observer blocks
        self.observer_blocks = nn.ModuleList([
            MoEObserverBlock(obs_cfg, n_experts=n_observer_experts, k_active=k_active)
            for _ in range(self.num_layers)
        ])

        self.n_observer_experts = n_observer_experts
        self.k_active = k_active

        print(f"  Injected {self.num_layers} MoE observer blocks")
        print(f"  Total experts: {self.num_layers * n_observer_experts}")
        print(f"  Active per pass: {self.num_layers * k_active}")

    def forward(self, input_ids, attention_mask=None, labels=None, **kwargs):
        B, T = input_ids.shape
        device = input_ids.device

        hidden_states = self.base_model.get_input_embeddings()(input_ids)
        layer_energies = []

        for i, layer in enumerate(self.base_model.model.layers):
            layer_out = layer(hidden_states, attention_mask=attention_mask)
            hidden_states = layer_out[0]

            # Cybernetic steering
            steering, energy, _ = self.observer_blocks[i](hidden_states)
            hidden_states = hidden_states + 0.05 * steering
            layer_energies.append(energy.item() if isinstance(energy, torch.Tensor) else energy)

        hidden_states = self.base_model.model.norm(hidden_states)
        logits = self.base_model.lm_head(hidden_states)

        loss = None
        if labels is not None:
            ce = F.cross_entropy(
                logits[..., :-1, :].contiguous().view(-1, logits.size(-1)),
                labels[..., 1:].contiguous().view(-1), ignore_index=-100)
            avg_e = sum(layer_energies) / max(len(layer_energies), 1)
            loss = ce + 0.01 * avg_e

        return {"logits": logits, "loss": loss, "energies": layer_energies}

    @torch.no_grad()
    def generate(self, prompt: str, max_new: int = 80, temp: float = 0.7, top_p: float = 0.9) -> dict:
        device = next(self.parameters()).device
        inputs = self.tokenizer(prompt, return_tensors="pt").to(device)
        ids = inputs["input_ids"]
        energies = []

        for _ in range(max_new):
            out = self.forward(ids, attention_mask=torch.ones_like(ids))
            logits = out["logits"][:, -1, :] / temp

            if top_p < 1.0:
                s, si = torch.sort(logits, descending=True)
                c = torch.cumsum(F.softmax(s, dim=-1), dim=-1)
                remove = c > top_p
                remove[..., 1:] = remove[..., :-1].clone()
                remove[..., 0] = False
                logits[remove.scatter(1, si, remove)] = float('-inf')

            probs = F.softmax(logits, dim=-1)
            next_tok = torch.multinomial(probs, 1)
            ids = torch.cat([ids, next_tok], dim=-1)
            energies.append(sum(out["energies"]) / max(len(out["energies"]), 1))

            if next_tok.item() == self.tokenizer.eos_token_id:
                break

        text = self.tokenizer.decode(ids[0], skip_special_tokens=True)
        return {"text": text, "energies": energies}


def main():
    parser = argparse.ArgumentParser(description="Cybernetic DeepSeek")
    parser.add_argument("--model-path", default=None, help="Local path to model")
    parser.add_argument("--prompt", default="Explain cybernetic governance in AI systems.", help="Prompt")
    parser.add_argument("--max-tokens", type=int, default=80)
    args = parser.parse_args()

    model_path = args.model_path or "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B"

    print("=" * 60)
    print("  CYBERNETIC DEEPSEEK")
    print("=" * 60)

    model = CyberneticDeepSeek(model_path, load_in_4bit=True)
    print()

    result = model.generate(args.prompt, max_new=args.max_tokens)
    print(f"Prompt:   {args.prompt}")
    print(f"Response: {result['text'][len(args.prompt):][:300]}")
    print(f"Tokens:   {len(result['energies'])}")
    if result['energies']:
        print(f"Energy:   {sum(result['energies'])/len(result['energies']):.4f}")
    print("=" * 60)


if __name__ == "__main__":
    main()
