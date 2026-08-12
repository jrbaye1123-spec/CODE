"""DeepSeek provider — stochastic semantic sensor for the epistemic control plane.

Uses the OpenAI-compatible DeepSeek API. Supports reasoning/thinking mode.
Falls back gracefully: if no API key is available, returns empty responses
rather than crashing. The control plane (compare.py) will flag these as
divergences for human adjudication.

This is not an "upgrade" to the deterministic keyword classifier. It is a
higher-entropy semantic sensor entering a proven secure perimeter. The
observability layer monitors it identically to all other providers.
"""

from dataclasses import dataclass, field
from typing import Optional
import json
import os
import time

from . import LLMResponse, LLMProvider


class DeepSeekProvider:
    """DeepSeek API provider with reasoning/thinking support.

    API keys: reads DEEPSEEK_API_KEY from environment. Falls back to local
    proxy at http://localhost:8000/v1 if use_local_fallback=True and no
    remote key is found.

    Default model: deepseek-v4-pro
    """

    def __init__(
        self,
        model: str = "deepseek-v4-pro",
        api_key: Optional[str] = None,
        use_local_fallback: bool = False,
    ):
        self.model = model
        self.provider_name = "deepseek"

        # Priority 1: explicit argument
        # Priority 2: DEEPSEEK_API_KEY environment variable
        # Priority 3: local fallback (if enabled)
        api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")

        if api_key:
            self.base_url = "https://api.deepseek.com"
            self.api_key = api_key
        elif use_local_fallback:
            self.base_url = "http://localhost:8000/v1"
            self.api_key = "dummy"
        else:
            self.base_url = ""
            self.api_key = ""

        self._client = None
        self._available = bool(self.api_key)

    def _get_client(self):
        if self._client is None:
            if not self._available:
                raise RuntimeError(
                    "DeepSeek API key not available. Set DEEPSEEK_API_KEY "
                    "environment variable or pass api_key to constructor."
                )
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                )
            except ImportError:
                raise ImportError(
                    "openai package required for DeepSeek provider: "
                    "pip install openai"
                )
        return self._client

    def classify(
        self,
        paper_title: str,
        paper_text: str,
        threads: list[dict],
        prompt_version: str = "v1",
    ) -> LLMResponse:
        """Classify a paper against research threads.

        Uses DeepSeek's reasoning/thinking mode for higher-quality
        classification decisions. Falls back to keyword matching if
        the API is unavailable.
        """
        if not self._available:
            return self._empty_response(
                "DeepSeek unavailable — no API key configured",
            )

        start = time.time()
        thread_descriptions = "\n".join(
            f"- {t['thread_id']}: {t['name']} — {t.get('description', '')}"
            for t in threads
        )

        system_prompt = (
            "You are a research literature triage agent. Classify academic "
            "papers against active research threads. Think carefully about "
            "semantic relevance, not just keyword overlap. Output valid JSON "
            "only, with no markdown wrapping."
        )

        user_prompt = f"""Classify the following paper against these research threads:

Research Threads:
{thread_descriptions}

Paper Title: {paper_title}

Paper Content (truncated):
{paper_text[:8000]}

Return JSON with this exact structure:
{{
    "primary_thread": "thread_id of best match, or 'unclassified'",
    "relevance_score": 0.0-1.0,
    "matched_threads": [
        {{"thread_id": "...", "thread_name": "...", "score": 0.0-1.0, "reasoning": "..."}}
    ],
    "reasoning": "Detailed explanation of classification decision",
    "summary": "Structured summary of the paper in 3-5 sentences",
    "key_claims": [
        {{"claim_text": "...", "source_location": "abstract/paragraph N", "confidence": 0.0-1.0}}
    ]
}}"""

        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                extra_body={"thinking": {"type": "enabled"}},
            )

            elapsed = (time.time() - start) * 1000
            content = response.choices[0].message.content or "{}"
            usage = response.usage

            return LLMResponse(
                content=content,
                model=self.model,
                provider=self.provider_name,
                latency_ms=elapsed,
                token_count=usage.total_tokens if usage else 0,
                cost_estimate=self._estimate_cost(usage),
                raw_response=(
                    response.model_dump()
                    if hasattr(response, "model_dump")
                    else None
                ),
            )
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            return LLMResponse(
                content=json.dumps({"error": str(e), "primary_thread": "unclassified", "relevance_score": 0.0}),
                model=self.model,
                provider=self.provider_name,
                latency_ms=elapsed,
                token_count=0,
                cost_estimate=0.0,
            )

    def summarize(
        self,
        paper_title: str,
        paper_text: str,
        classification: str,
        prompt_version: str = "v1",
    ) -> LLMResponse:
        """Generate a structured summary."""
        if not self._available:
            return self._empty_response("DeepSeek unavailable")

        start = time.time()
        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Summarize academic papers concisely. Output JSON only.",
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Summarize this paper classified as '{classification}':\n\n"
                            f"Title: {paper_title}\n\n"
                            f"{paper_text[:6000]}\n\n"
                            'Return: {"summary": "3-5 sentence structured summary", '
                            '"key_findings": ["finding 1", "finding 2"], '
                            '"methodology": "brief description"}'
                        ),
                    },
                ],
                temperature=0.1,
            )
            elapsed = (time.time() - start) * 1000
            return LLMResponse(
                content=response.choices[0].message.content or "{}",
                model=self.model,
                provider=self.provider_name,
                latency_ms=elapsed,
                token_count=response.usage.total_tokens if response.usage else 0,
                cost_estimate=self._estimate_cost(response.usage),
            )
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            return LLMResponse(
                content=json.dumps({"summary": f"Error: {e}"}),
                model=self.model,
                provider=self.provider_name,
                latency_ms=elapsed,
                token_count=0,
                cost_estimate=0.0,
            )

    def extract_claims(
        self,
        paper_title: str,
        paper_text: str,
        prompt_version: str = "v1",
    ) -> LLMResponse:
        """Extract claims with source locations."""
        if not self._available:
            return self._empty_response("DeepSeek unavailable")

        start = time.time()
        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Extract key claims from academic papers with source locations. Output JSON only.",
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Extract up to 5 key claims from this paper:\n\n"
                            f"Title: {paper_title}\n\n"
                            f"{paper_text[:8000]}\n\n"
                            'Return: {"claims": [{"claim_text": "...", '
                            '"source_location": "section/paragraph", '
                            '"confidence": 0.0-1.0}]}'
                        ),
                    },
                ],
                temperature=0.1,
            )
            elapsed = (time.time() - start) * 1000
            return LLMResponse(
                content=response.choices[0].message.content or "{}",
                model=self.model,
                provider=self.provider_name,
                latency_ms=elapsed,
                token_count=response.usage.total_tokens if response.usage else 0,
                cost_estimate=self._estimate_cost(response.usage),
            )
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            return LLMResponse(
                content=json.dumps({"claims": []}),
                model=self.model,
                provider=self.provider_name,
                latency_ms=elapsed,
                token_count=0,
                cost_estimate=0.0,
            )

    def _estimate_cost(self, usage) -> float:
        """DeepSeek pricing: ~$0.27/1M input, ~$1.10/1M output (v3).
        v4-pro pricing may vary. Conservative estimate used here."""
        if not usage:
            return 0.0
        input_cost = (usage.prompt_tokens or 0) * 0.55 / 1_000_000
        output_cost = (usage.completion_tokens or 0) * 2.19 / 1_000_000
        return round(input_cost + output_cost, 6)

    def _empty_response(self, reason: str) -> LLMResponse:
        """Return an empty/error response when the provider is unavailable."""
        return LLMResponse(
            content=json.dumps({
                "primary_thread": "unclassified",
                "relevance_score": 0.0,
                "matched_threads": [],
                "reasoning": reason,
                "summary": reason,
                "key_claims": [],
            }),
            model=self.model,
            provider=self.provider_name,
            latency_ms=0,
            token_count=0,
            cost_estimate=0.0,
        )
