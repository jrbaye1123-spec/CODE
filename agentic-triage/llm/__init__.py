"""LLM provider abstraction — swappable backends for classification and summarization.

Supports OpenAI, Anthropic, and local/Ollama providers.
The triage agent calls this instead of keyword matching when a real LLM is configured.
"""

from dataclasses import dataclass, field
from typing import Optional, Protocol
import json
import os
import time


@dataclass
class LLMResponse:
    """Normalized response from any LLM provider."""
    content: str
    model: str
    provider: str
    latency_ms: float
    token_count: int
    cost_estimate: float
    raw_response: Optional[dict] = None


@dataclass
class ClassificationOutput:
    """Structured classification output from the LLM."""
    primary_thread: str
    relevance_score: float
    matched_threads: list[dict]  # [{thread_id, thread_name, score, reasoning}]
    reasoning: str
    summary: str
    key_claims: list[dict]  # [{claim_text, source_location, confidence}]


class LLMProvider(Protocol):
    """Protocol that all LLM providers must implement."""

    def classify(self, paper_title: str, paper_text: str, threads: list[dict], prompt_version: str = "v1") -> LLMResponse:
        """Classify a paper against research threads."""
        ...

    def summarize(self, paper_title: str, paper_text: str, classification: str, prompt_version: str = "v1") -> LLMResponse:
        """Generate a structured summary."""
        ...

    def extract_claims(self, paper_title: str, paper_text: str, prompt_version: str = "v1") -> LLMResponse:
        """Extract claims with source locations."""
        ...


class OpenAIProvider:
    """OpenAI-compatible provider (GPT-4, GPT-4o, etc.)."""

    def __init__(self, model: str = "gpt-4o", api_key: Optional[str] = None):
        self.model = model
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.provider_name = "openai"
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
            except ImportError:
                raise ImportError("openai package required: pip install openai")
        return self._client

    def classify(self, paper_title: str, paper_text: str, threads: list[dict], prompt_version: str = "v1") -> LLMResponse:
        start = time.time()
        thread_descriptions = "\n".join(
            f"- {t['thread_id']}: {t['name']} — {t.get('description', '')}"
            for t in threads
        )

        system_prompt = (
            "You are a research literature triage agent. Classify academic papers "
            "against active research threads. Output valid JSON only."
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
    "reasoning": "Explanation of classification decision",
    "summary": "Structured summary of the paper in 3-5 sentences",
    "key_claims": [
        {{"claim_text": "...", "source_location": "abstract/paragraph N", "confidence": 0.0-1.0}}
    ]
}}"""

        client = self._get_client()
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
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
            raw_response=response.model_dump() if hasattr(response, 'model_dump') else None,
        )

    def summarize(self, paper_title: str, paper_text: str, classification: str, prompt_version: str = "v1") -> LLMResponse:
        start = time.time()
        client = self._get_client()
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "Summarize academic papers concisely. Output JSON only."},
                {"role": "user", "content": f"Summarize this paper classified as '{classification}':\n\nTitle: {paper_title}\n\n{paper_text[:6000]}\n\nReturn: {{\"summary\": \"3-5 sentence structured summary\", \"key_findings\": [\"finding 1\", \"finding 2\"], \"methodology\": \"brief description\"}}"},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        elapsed = (time.time() - start) * 1000
        content = response.choices[0].message.content or "{}"

        return LLMResponse(
            content=content, model=self.model, provider=self.provider_name,
            latency_ms=elapsed,
            token_count=response.usage.total_tokens if response.usage else 0,
            cost_estimate=self._estimate_cost(response.usage),
        )

    def extract_claims(self, paper_title: str, paper_text: str, prompt_version: str = "v1") -> LLMResponse:
        start = time.time()
        client = self._get_client()
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "Extract key claims from academic papers with source locations. Output JSON only."},
                {"role": "user", "content": f"Extract up to 5 key claims from this paper:\n\nTitle: {paper_title}\n\n{paper_text[:8000]}\n\nReturn: {{\"claims\": [{{\"claim_text\": \"...\", \"source_location\": \"section/paragraph\", \"confidence\": 0.0-1.0}}]}}"},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        elapsed = (time.time() - start) * 1000

        return LLMResponse(
            content=response.choices[0].message.content or "{}",
            model=self.model, provider=self.provider_name,
            latency_ms=elapsed,
            token_count=response.usage.total_tokens if response.usage else 0,
            cost_estimate=self._estimate_cost(response.usage),
        )

    def _estimate_cost(self, usage) -> float:
        if not usage:
            return 0.0
        # GPT-4o pricing: ~$5/1M input, ~$15/1M output
        input_cost = (usage.prompt_tokens or 0) * 5.0 / 1_000_000
        output_cost = (usage.completion_tokens or 0) * 15.0 / 1_000_000
        return round(input_cost + output_cost, 6)


class AnthropicProvider:
    """Anthropic Claude provider."""

    def __init__(self, model: str = "claude-sonnet-4-20250514", api_key: Optional[str] = None):
        self.model = model
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.provider_name = "anthropic"
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError("anthropic package required: pip install anthropic")
        return self._client

    def classify(self, paper_title: str, paper_text: str, threads: list[dict], prompt_version: str = "v1") -> LLMResponse:
        start = time.time()
        thread_descriptions = "\n".join(
            f"- {t['thread_id']}: {t['name']} — {t.get('description', '')}"
            for t in threads
        )
        client = self._get_client()
        response = client.messages.create(
            model=self.model,
            max_tokens=2000,
            temperature=0.1,
            system="You are a research literature triage agent. Output valid JSON only.",
            messages=[{"role": "user", "content": f"""Classify this paper against these threads and return JSON:

Threads:
{thread_descriptions}

Paper: {paper_title}
{paper_text[:8000]}

Return JSON: {{"primary_thread": "...", "relevance_score": 0.0-1.0, "matched_threads": [...], "reasoning": "...", "summary": "...", "key_claims": [...]}}"""}],
        )
        elapsed = (time.time() - start) * 1000
        content = response.content[0].text if response.content else "{}"

        return LLMResponse(
            content=content, model=self.model, provider=self.provider_name,
            latency_ms=elapsed,
            token_count=response.usage.input_tokens + response.usage.output_tokens if response.usage else 0,
            cost_estimate=self._estimate_cost(response.usage),
        )

    def summarize(self, paper_title: str, paper_text: str, classification: str, prompt_version: str = "v1") -> LLMResponse:
        start = time.time()
        client = self._get_client()
        response = client.messages.create(
            model=self.model, max_tokens=1000, temperature=0.1,
            system="Summarize academic papers. Output JSON only.",
            messages=[{"role": "user", "content": f"Summarize: {paper_title} ({classification})\n\n{paper_text[:6000]}\n\nReturn JSON with summary, key_findings, methodology."}],
        )
        elapsed = (time.time() - start) * 1000
        return LLMResponse(
            content=response.content[0].text if response.content else "{}",
            model=self.model, provider=self.provider_name, latency_ms=elapsed,
            token_count=response.usage.input_tokens + response.usage.output_tokens if response.usage else 0,
            cost_estimate=self._estimate_cost(response.usage),
        )

    def extract_claims(self, paper_title: str, paper_text: str, prompt_version: str = "v1") -> LLMResponse:
        start = time.time()
        client = self._get_client()
        response = client.messages.create(
            model=self.model, max_tokens=1500, temperature=0.1,
            system="Extract key claims with source locations. Output JSON only.",
            messages=[{"role": "user", "content": f"Extract up to 5 claims: {paper_title}\n\n{paper_text[:8000]}\n\nReturn JSON with claims array (claim_text, source_location, confidence)."}],
        )
        elapsed = (time.time() - start) * 1000
        return LLMResponse(
            content=response.content[0].text if response.content else "{}",
            model=self.model, provider=self.provider_name, latency_ms=elapsed,
            token_count=response.usage.input_tokens + response.usage.output_tokens if response.usage else 0,
            cost_estimate=self._estimate_cost(response.usage),
        )

    def _estimate_cost(self, usage) -> float:
        if not usage:
            return 0.0
        return round((usage.input_tokens * 3.0 + usage.output_tokens * 15.0) / 1_000_000, 6)


class OllamaProvider:
    """Local Ollama provider for offline/private classification."""

    def __init__(self, model: str = "llama3.1:8b", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url
        self.provider_name = "ollama"

    def classify(self, paper_title: str, paper_text: str, threads: list[dict], prompt_version: str = "v1") -> LLMResponse:
        start = time.time()
        thread_descriptions = "\n".join(
            f"- {t['thread_id']}: {t['name']}"
            for t in threads
        )
        response = self._call_ollama(f"""Classify this paper against research threads. Return JSON only.

Threads:
{thread_descriptions}

Paper: {paper_title}
{paper_text[:4000]}

Return: {{"primary_thread": "thread_id", "relevance_score": 0.0-1.0, "matched_threads": [{{"thread_id": "...", "thread_name": "...", "score": 0.0-1.0, "reasoning": "..."}}], "reasoning": "...", "summary": "...", "key_claims": [{{"claim_text": "...", "source_location": "...", "confidence": 0.0-1.0}}]}}""")
        elapsed = (time.time() - start) * 1000
        return LLMResponse(
            content=response.get("response", "{}"),
            model=self.model, provider=self.provider_name,
            latency_ms=elapsed, token_count=0, cost_estimate=0.0,
        )

    def summarize(self, paper_title: str, paper_text: str, classification: str, prompt_version: str = "v1") -> LLMResponse:
        start = time.time()
        response = self._call_ollama(f"Summarize this paper in JSON. Title: {paper_title}\nClassification: {classification}\n\n{paper_text[:4000]}\n\nReturn JSON with summary, key_findings, methodology.")
        elapsed = (time.time() - start) * 1000
        return LLMResponse(
            content=response.get("response", "{}"),
            model=self.model, provider=self.provider_name,
            latency_ms=elapsed, token_count=0, cost_estimate=0.0,
        )

    def extract_claims(self, paper_title: str, paper_text: str, prompt_version: str = "v1") -> LLMResponse:
        start = time.time()
        response = self._call_ollama(f"Extract up to 5 key claims from this paper in JSON. Title: {paper_title}\n\n{paper_text[:4000]}\n\nReturn: {{\"claims\": [{{\"claim_text\": \"...\", \"source_location\": \"...\", \"confidence\": 0.0-1.0}}]}}")
        elapsed = (time.time() - start) * 1000
        return LLMResponse(
            content=response.get("response", "{}"),
            model=self.model, provider=self.provider_name,
            latency_ms=elapsed, token_count=0, cost_estimate=0.0,
        )

    def _call_ollama(self, prompt: str) -> dict:
        import urllib.request, urllib.error
        data = json.dumps({
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1},
        }).encode()
        req = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read())
        except urllib.error.URLError:
            return {"response": '{"error": "Ollama not running"}'}


def parse_classification_response(response: LLMResponse) -> ClassificationOutput:
    """Parse LLM classification response into structured ClassificationOutput."""
    try:
        data = json.loads(response.content)
    except json.JSONDecodeError:
        # Try to extract JSON from text
        import re
        match = re.search(r'\{.*\}', response.content, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
            except json.JSONDecodeError:
                data = {}
        else:
            data = {}

    return ClassificationOutput(
        primary_thread=data.get("primary_thread", "unclassified"),
        relevance_score=float(data.get("relevance_score", 0.0)),
        matched_threads=data.get("matched_threads", []),
        reasoning=data.get("reasoning", "No reasoning provided."),
        summary=data.get("summary", response.content[:200]),
        key_claims=data.get("key_claims", []),
    )


def create_provider(provider_type: str = "keyword", **kwargs):
    """Factory for LLM providers.

    Args:
        provider_type: "openai", "anthropic", "ollama", "deepseek", or "keyword"
        **kwargs: Passed to provider constructor (model, api_key, base_url, etc.)

    Returns:
        LLMProvider instance or None for keyword-based fallback.
    """
    if provider_type == "openai":
        return OpenAIProvider(**kwargs)
    elif provider_type == "anthropic":
        return AnthropicProvider(**kwargs)
    elif provider_type == "ollama":
        return OllamaProvider(**kwargs)
    elif provider_type == "deepseek":
        from .deepseek_provider import DeepSeekProvider
        return DeepSeekProvider(**kwargs)
    elif provider_type == "keyword":
        return None  # Signal to use keyword-based fallback
    else:
        raise ValueError(f"Unknown provider: {provider_type}")
