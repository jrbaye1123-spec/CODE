"""
Vault RAG Engine — GPT2-MoE-1M Inference Pipeline
==================================================
Loads the YaRN-stretched GPT2-MoE-1M model (1M context window),
retrieves vault context via Kitadel + semantic embeddings,
and generates answers grounded in your notes.

Key advantage over the old gpt2-medium pipeline:
  - 1M token context vs 1024 — can fit entire vault sections
  - YaRN RoPE extrapolation from 4096-trained checkpoint
  - MoE routing for domain-specific knowledge

Usage:
    python3 vault_rag/inference.py "what is the spectral tail shape parameter?"
    python3 vault_rag/inference.py --chat
    python3 vault_rag/inference.py "query" --top-k 20 --max-context 50000
"""

import sys
import time
from pathlib import Path
from typing import Optional, List, Dict

import torch
import torch.nn.functional as F

# Project paths
PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from model import GPT2MoEConfig, GPT2MoE1M
from retriever import VaultRetriever


class VaultGPTMoE:
    """
    GPT2-MoE-1M model grounded in vault knowledge via RAG.
    1M context window = can ingest massive vault context.

    Query → retrieve vault context → MoE generates answer.
    """

    def __init__(self, checkpoint_path: Optional[str] = None,
                 yarn_factor: float = 256.0,
                 dtype: torch.dtype = torch.float16):
        """
        Args:
            checkpoint_path: Path to .pt checkpoint. Defaults to best.
            yarn_factor: YaRN scaling factor (256 = 4096→1M).
            dtype: fp16 for memory efficiency on CPU.
        """
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.dtype = dtype if self.device == "cuda" else torch.float32

        # ── Load checkpoint ──────────────────────────────────────────
        if checkpoint_path is None:
            checkpoint_path = str(PROJECT_DIR / "vault-gpt-moe-trained" / "checkpoint_best.pt")

        print(f"[vault-moe] Loading checkpoint: {checkpoint_path}", file=sys.stderr)
        ckpt = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
        base_config = ckpt["config"]

        # Apply YaRN scaling
        config = base_config
        config.rope_scaling = {"type": "yarn", "factor": yarn_factor}
        config.max_position_embeddings = 1_048_576
        config.n_positions = 1_048_576
        config.sliding_window = max(config.sliding_window, 512)
        config.global_attn_stride = max(config.global_attn_stride, 64)

        print(f"[vault-moe] YaRN factor={yarn_factor} → "
              f"max_pos={config.max_position_embeddings:,} "
              f"step={ckpt['global_step']} loss={ckpt['loss']:.4f}", file=sys.stderr)

        # Build model
        self.model = GPT2MoE1M(config)
        self.model.load_state_dict(ckpt["model_state_dict"], strict=False)
        self.model = self.model.to(self.dtype).to(self.device)
        self.model.eval()

        param_count = sum(p.numel() for p in self.model.parameters()) / 1e6
        print(f"[vault-moe] Ready. {param_count:.1f}M params, "
              f"1M context, {self.dtype}", file=sys.stderr)

        # ── Tokenizer ────────────────────────────────────────────────
        from transformers import AutoTokenizer
        self.tokenizer = AutoTokenizer.from_pretrained("gpt2")
        self.tokenizer.pad_token = self.tokenizer.eos_token

        # ── Vault retriever (Kitadel + semantic) ─────────────────────
        self.retriever = VaultRetriever()
        self.config = config

    # ── RAG Prompt Formatting ────────────────────────────────────────

    def _build_rag_prompt(self, query: str, context: str) -> str:
        """
        Build RAG prompt with vault context.
        With 1M context, we can fit much more vault content.
        """
        prompt = (
            f"You are a knowledgeable assistant with access to a personal "
            f"knowledge vault. Use the following context from the vault to "
            f"answer the question. If the context doesn't contain the answer, "
            f"say so honestly.\n"
            f"\n"
            f"=== VAULT CONTEXT ===\n"
            f"{context}\n"
            f"=== END CONTEXT ===\n"
            f"\n"
            f"Question: {query}\n"
            f"\n"
            f"Answer:"
        )
        return prompt

    # ── Generation ───────────────────────────────────────────────────

    @torch.no_grad()
    def _generate(self, input_ids: torch.Tensor, max_new_tokens: int = 256,
                  temperature: float = 0.7, top_k: int = 50) -> torch.Tensor:
        """
        Autoregressive generation with the MoE model.
        Uses logits_last_only for efficiency.
        For each new token, processes the last 4096 tokens as context
        (sliding window handles longer-range via global attention).
        """
        generated = input_ids.clone()
        total_len = generated.shape[1]

        for step in range(max_new_tokens):
            # Use last 4096 tokens as context for efficiency
            chunk_size = min(generated.shape[1], 4096)
            context_start = max(0, generated.shape[1] - chunk_size)
            context = generated[:, context_start:]
            pos_ids = torch.arange(context_start, generated.shape[1],
                                   device=self.device).unsqueeze(0)

            # Forward pass — only need last token logits
            logits, _ = self.model(context, position_ids=pos_ids,
                                   logits_last_only=True)
            next_logits = logits[:, -1, :] / temperature

            # Top-k sampling
            if top_k > 0:
                top_k_values, _ = torch.topk(next_logits, top_k)
                min_top_k = top_k_values[:, -1].unsqueeze(-1)
                next_logits[next_logits < min_top_k] = float("-inf")

            probs = F.softmax(next_logits, dim=-1)
            next_token = torch.multinomial(probs, num_samples=1)
            generated = torch.cat([generated, next_token], dim=-1)

        return generated

    def ask(self, query: str, top_k: int = 10, max_context_tokens: int = 50000,
            max_new_tokens: int = 256, temperature: float = 0.7) -> dict:
        """
        Full RAG pipeline: retrieve → prompt → generate.
        With 1M context, max_context_tokens can be very large.

        Returns:
            dict with keys: query, answer, sources, context_tokens, time_ms
        """
        t0 = time.time()

        # 1. Retrieve vault context
        print(f"[vault-moe] Retrieving context for: {query}", file=sys.stderr)
        context = self.retriever.retrieve_context(
            query, top_k=top_k, max_tokens=max_context_tokens
        )

        if not context.strip():
            context = "(No relevant vault context found.)"

        # 2. Build RAG prompt
        prompt = self._build_rag_prompt(query, context)

        # 3. Tokenize — 1M context means we can fit huge prompts
        input_ids = self.tokenizer.encode(prompt, return_tensors="pt").to(self.device)
        context_tokens = input_ids.shape[1]

        print(f"[vault-moe] Prompt: {context_tokens} tokens, "
              f"generating {max_new_tokens}...", file=sys.stderr)

        # 4. Generate
        generated = self._generate(
            input_ids,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
        )

        # 5. Decode only the generated part
        generated_ids = generated[0][context_tokens:]
        answer = self.tokenizer.decode(generated_ids, skip_special_tokens=True)

        elapsed = (time.time() - t0) * 1000

        # 6. Extract sources
        sources = []
        for line in context.split("\n"):
            if line.startswith("### ") and "(score:" in line:
                path = line.split("(score:")[0].replace("### ", "").strip()
                sources.append(path)

        return {
            "query": query,
            "answer": answer.strip(),
            "sources": sources[:top_k],
            "context_tokens": context_tokens,
            "generated_tokens": len(generated_ids),
            "time_ms": round(elapsed, 1),
        }

    # ── Batch ask ────────────────────────────────────────────────────

    def ask_batch(self, queries: list, **kwargs) -> list:
        """Run multiple queries through the RAG pipeline."""
        return [self.ask(q, **kwargs) for q in queries]

    # ── Interactive ──────────────────────────────────────────────────

    def chat(self):
        """Interactive RAG chat session."""
        print(f"\n{'='*60}")
        print(f"VAULT GPT-MoE-1M — YaRN Context Window")
        print(f"Ask questions about your vault. Type 'quit' to exit.")
        print(f"{'='*60}\n")

        while True:
            try:
                query = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n")
                break

            if query.lower() in ("quit", "exit", "q"):
                break
            if not query:
                continue

            result = self.ask(query)
            print(f"\nVaultGPT: {result['answer']}\n")
            print(f"  [Sources: {len(result['sources'])} notes, "
                  f"{result['context_tokens']} ctx tokens, "
                  f"{result['time_ms']:.0f}ms]\n")


# ── CLI ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Vault RAG inference (GPT2-MoE-1M)")
    parser.add_argument("query", nargs="?", help="Question to ask the vault")
    parser.add_argument("--checkpoint", default=None,
                        help="Path to checkpoint .pt file")
    parser.add_argument("--yarn-factor", type=float, default=256.0,
                        help="YaRN scaling factor (default: 256)")
    parser.add_argument("--top-k", type=int, default=10,
                        help="Number of vault notes to retrieve")
    parser.add_argument("--max-context", type=int, default=50000,
                        help="Max context tokens from vault (1M window!)")
    parser.add_argument("--max-new", type=int, default=256,
                        help="Max new tokens to generate")
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--chat", action="store_true",
                        help="Interactive chat mode")
    parser.add_argument("--no-context", action="store_true",
                        help="Skip vault retrieval (raw generation)")
    args = parser.parse_args()

    vault_gpt = VaultGPTMoE(
        checkpoint_path=args.checkpoint,
        yarn_factor=args.yarn_factor,
    )

    if args.chat:
        vault_gpt.chat()
    elif args.query:
        result = vault_gpt.ask(
            args.query,
            top_k=args.top_k,
            max_context_tokens=args.max_context,
            max_new_tokens=args.max_new,
            temperature=args.temperature,
        )
        print(f"\nQ: {result['query']}")
        print(f"\nA: {result['answer']}")
        print(f"\n───")
        print(f"Sources ({len(result['sources'])} notes):")
        for s in result['sources']:
            print(f"  • {s}")
        print(f"Context: {result['context_tokens']} tokens | "
              f"Generated: {result['generated_tokens']} tokens | "
              f"{result['time_ms']:.0f}ms")
    else:
        parser.print_help()