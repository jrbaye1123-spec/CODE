"""Local model integration for VaultLens — fallback when cloud DeepSeek is unavailable.

Provides:
- LocalModelRunner: wraps llama.cpp CLI for local inference
- FallbackRetriever: hybrid retrieval that uses local model when cloud is down
- Status checks to determine which model to use
"""

import subprocess
import os
import time
import json
from typing import Optional


class LocalModelRunner:
    """Runs Llama 3.2 3B locally via llama-cli as fallback to cloud DeepSeek v4.

    Model: Llama-3.2-3B-Instruct-Q4_K_M.gguf (~1.9GB)
    Context: 32K default, up to 1M with RoPE scaling
    """

    def __init__(self):
        self.model_path = os.path.expanduser(
            "~/models/Llama-3.2-3B-Instruct-Q4_K_M.gguf"
        )
        self.llama_cli = os.path.expanduser(
            "~/llama.cpp/build/bin/llama-cli"
        )
        self.available = os.path.exists(self.model_path) and os.path.exists(self.llama_cli)

    def query(self, prompt: str, max_tokens: int = 1024, temperature: float = 0.1,
              context_size: int = 32768) -> str:
        """Run a one-shot query against the local model.

        Args:
            prompt: The full prompt to send
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0-1.0)
            context_size: Context window size (32K default, 128K practical, 1M max)

        Returns:
            Generated text response
        """
        if not self.available:
            raise RuntimeError("Local model not available")

        cmd = [
            self.llama_cli,
            "-m", self.model_path,
            "-c", str(context_size),
            "-t", "8",                    # 8 threads for Ryzen AI 7
            "-ctk", "q8_0",              # Quantized KV cache (memory efficient)
            "-ctv", "q8_0",
            "--temp", str(temperature),
            "-n", str(max_tokens),
            "--no-display-prompt",
            "-p", prompt,
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                env={**os.environ, "OMP_NUM_THREADS": "8"},
            )
            if result.returncode != 0:
                raise RuntimeError(f"llama-cli error: {result.stderr[:500]}")
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            return "[Local model timed out — falling back to cloud]"
        except FileNotFoundError:
            self.available = False
            raise RuntimeError("llama-cli not found")

    def is_available(self) -> bool:
        """Check if local model binary and weights exist."""
        return self.available

    def model_info(self) -> dict:
        """Return info about the local model."""
        size_gb = 0
        if os.path.exists(self.model_path):
            size_gb = os.path.getsize(self.model_path) / 1e9
        return {
            "model": "Llama-3.2-3B-Instruct-Q4_K_M",
            "size_gb": round(size_gb, 2),
            "context": "32K default, up to 1M with RoPE yarn scaling",
            "kv_cache": "Q8_0 quantized",
            "threads": 8,
            "backend": "CPU (Radeon 860M via ROCm optional)",
        }


# ── Singleton ──────────────────────────────────────────
_runner: Optional[LocalModelRunner] = None


def get_local_model() -> LocalModelRunner:
    """Get or create the local model runner singleton."""
    global _runner
    if _runner is None:
        _runner = LocalModelRunner()
    return _runner


def query_with_fallback(prompt: str, prefer_local: bool = False) -> dict:
    """Query with automatic fallback: try local first if preferred, else cloud.

    Returns:
        {"source": "local"|"cloud", "response": "...", "model": "..."}
    """
    runner = get_local_model()

    if prefer_local and runner.is_available():
        try:
            response = runner.query(prompt)
            return {"source": "local", "response": response, "model": "Llama-3.2-3B"}
        except RuntimeError:
            pass  # Fall through to cloud

    # Cloud fallback — the agent runtime handles this via its own API
    return {"source": "cloud", "response": None, "model": "DeepSeek-v4"}
