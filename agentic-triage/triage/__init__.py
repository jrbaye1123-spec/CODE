"""Literature Triage Agent — classifies, scores, and summarizes incoming papers.

The highest-priority workflow at Nullresearch. Given a queue of new papers/preprints:
1. Classify each against active research threads
2. Assign relevance scores with reasoning
3. Surface the top-N with structured summaries

This is the FOUNDATION that all other workflows depend on.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import json
import hashlib
import uuid
import time

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from safety.injection_scanner import InjectionScanner, InjectionBlockedError
from safety.policy_engine import PolicyEngine, ActionType, ActionRequest
from memory import MemoryManager
from eval import AgentClassification
from provenance import ProvenanceTracker, Claim, AttributionLedger, AttributionEntry
from ops import AgentOps, PromptVersion, ModelRun


@dataclass
class ResearchThread:
    """An active research thread for classification."""
    thread_id: str
    name: str
    description: str
    keywords: list[str]
    active: bool = True


@dataclass
class TriageConfig:
    """Configuration for the Literature Triage workflow."""
    top_n: int = 10  # Number of top papers to surface
    relevance_threshold: float = 0.5  # Minimum relevance score to include
    max_paper_length_chars: int = 100_000  # Truncate papers beyond this
    allowed_sources: list[str] = field(default_factory=lambda: [
        "arxiv.org", "export.arxiv.org",
        "openreview.net", "api.openreview.net",
        "api.semanticscholar.org",
    ])
    research_threads: list[ResearchThread] = field(default_factory=list)


@dataclass
class TriageResult:
    """Output of triaging a single paper."""
    paper_id: str
    paper_title: str
    paper_source: str
    classification: str  # Primary research thread
    relevance_score: float  # 0.0 to 1.0
    matched_threads: list[dict]  # [{thread_id, thread_name, score, reasoning}]
    summary: str
    claims_extracted: list[Claim]
    reasoning_trace: str
    triaged_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class LiteratureTriageAgent:
    """Agent that classifies, scores, and summarizes incoming papers.

    Runs inside the safety boundary: all paper content passes injection
    scanning before entering agent context. All actions pass the policy engine.
    """

    def __init__(
        self,
        config: TriageConfig,
        memory_manager: MemoryManager,
        provenance_tracker: ProvenanceTracker,
        ops_pipeline: AgentOps,
        policy_engine: PolicyEngine,
        injection_scanner: InjectionScanner,
    ):
        self.config = config
        self.memory = memory_manager
        self.provenance = provenance_tracker
        self.ops = ops_pipeline
        self.policy = policy_engine
        self.scanner = injection_scanner
        self.agent_id = "literature_triage_v1"
        self.model_provider = "default"
        self.model_version = "1.0"

    def triage_paper(
        self, paper_id: str, paper_title: str, paper_text: str, paper_source: str
    ) -> TriageResult:
        """Triage a single paper through the full pipeline.

        Steps:
        1. Safety scan — content passes injection defense
        2. Policy check — verify source is in allowed destinations
        3. Classify against research threads
        4. Extract claims with provenance
        5. Generate structured summary
        6. Log run in AgentOps

        Args:
            paper_id: Unique identifier (arxiv ID, DOI, etc.)
            paper_title: Title of the paper
            paper_text: Full content of the paper
            paper_source: URL or source identifier

        Returns:
            TriageResult with classification, relevance, summary, and claims.

        Raises:
            InjectionBlockedError: If paper content fails safety scan.
        """
        session_id = str(uuid.uuid4())[:8]
        start_time = time.time()

        # --- Step 1: Safety scan ---
        scan_result = self.scanner.scan(paper_text, source=paper_source)
        if not scan_result.passed:
            raise InjectionBlockedError(
                f"Paper '{paper_title}' from {paper_source} blocked: "
                f"risk={scan_result.risk_score:.2f}"
            )

        # --- Step 2: Policy check ---
        action = ActionRequest(
            action_type=ActionType.NETWORK_OUTBOUND,
            description=f"Read paper: {paper_title}",
            target=paper_source,
            session_id=session_id,
            task_spec={"allowed_destinations": self.config.allowed_sources},
        )
        decision = self.policy.evaluate(action)
        if not decision.allowed:
            raise PermissionError(f"Policy blocked paper source: {decision.reason}")

        # --- Step 3: Truncate if too long ---
        if len(paper_text) > self.config.max_paper_length_chars:
            paper_text = paper_text[:self.config.max_paper_length_chars]

        # --- Step 4: Classify against research threads ---
        classification, matched_threads, relevance_score, reasoning = self._classify(
            paper_title, paper_text
        )

        # --- Step 5: Extract claims with provenance ---
        claims = self._extract_claims(paper_title, paper_text, paper_source)

        # --- Step 6: Generate structured summary ---
        summary = self._summarize(paper_title, paper_text, classification, matched_threads)

        # --- Step 7: Build reasoning trace ---
        reasoning_trace = self._build_reasoning_trace(
            paper_title, classification, relevance_score, matched_threads, reasoning
        )

        # --- Step 8: Log in AgentOps ---
        run = ModelRun(
            run_id=f"run_{uuid.uuid4().hex[:12]}",
            workflow="literature_triage",
            prompt_version_id=self._get_active_prompt_version(),
            model_provider=self.model_provider,
            model_version=self.model_version,
            input_hash=hashlib.sha256(paper_text.encode()).hexdigest()[:16],
            output_hash=hashlib.sha256(classification.encode()).hexdigest()[:16],
            latency_ms=(time.time() - start_time) * 1000,
            token_count=len(paper_text.split()),
            cost_estimate=self._estimate_cost(paper_text),
        )
        self.ops.log_run(run)

        return TriageResult(
            paper_id=paper_id,
            paper_title=paper_title,
            paper_source=paper_source,
            classification=classification,
            relevance_score=relevance_score,
            matched_threads=matched_threads,
            summary=summary,
            claims_extracted=claims,
            reasoning_trace=reasoning_trace,
        )

    def triage_queue(self, papers: list[dict]) -> list[TriageResult]:
        """Triage a queue of papers.

        Args:
            papers: List of dicts with keys: id, title, text, source

        Returns:
            List of TriageResults sorted by relevance score descending.
        """
        results = []
        failures = []

        for paper in papers:
            try:
                result = self.triage_paper(
                    paper_id=paper["id"],
                    paper_title=paper["title"],
                    paper_text=paper["text"],
                    paper_source=paper["source"],
                )
                results.append(result)
            except (InjectionBlockedError, PermissionError) as e:
                failures.append({
                    "paper_id": paper.get("id", "unknown"),
                    "title": paper.get("title", "unknown"),
                    "error": str(e),
                })

        # Sort by relevance, filter below threshold
        results.sort(key=lambda r: r.relevance_score, reverse=True)
        results = [r for r in results if r.relevance_score >= self.config.relevance_threshold]

        # Record failures
        session = self.memory.get_session("triage_queue") if self.memory._active_sessions else None
        if session:
            session.set_variable("triage_failures", failures)

        return results[:self.config.top_n]

    def get_top_n(self, results: list[TriageResult], n: Optional[int] = None) -> list[TriageResult]:
        """Return the top-N results by relevance score."""
        n = n or self.config.top_n
        sorted_results = sorted(results, key=lambda r: r.relevance_score, reverse=True)
        return sorted_results[:n]

    def to_agent_classifications(self, results: list[TriageResult]) -> list[AgentClassification]:
        """Convert triage results to the format expected by the evaluation harness."""
        return [
            AgentClassification(
                paper_id=r.paper_id,
                agent_version=self.agent_id,
                model_provider=self.model_provider,
                model_version=self.model_version,
                classification=r.classification,
                relevance_score=r.relevance_score,
                relevant_threads=[t["thread_id"] for t in r.matched_threads],
                reasoning_trace=r.reasoning_trace,
            )
            for r in results
        ]

    # --- Internal methods ---

    def _classify(self, title: str, text: str) -> tuple[str, list[dict], float, str]:
        """Classify a paper against active research threads.

        In production, this calls the LLM. Here we provide the classification
        logic with a structured output contract. The actual LLM call is a
        separate integration point.
        """
        threads = [t for t in self.config.research_threads if t.active]
        if not threads:
            return "unclassified", [], 0.0, "No active research threads configured."

        # Score each thread based on keyword matches and semantic relevance
        text_lower = (title + " " + text[:5000]).lower()
        matched = []

        for thread in threads:
            keyword_hits = sum(
                1 for kw in thread.keywords
                if kw.lower() in text_lower
            )
            keyword_score = keyword_hits / max(len(thread.keywords), 1)

            if keyword_score > 0:
                matched.append({
                    "thread_id": thread.thread_id,
                    "thread_name": thread.name,
                    "score": min(keyword_score * 1.5, 1.0),  # Boost for keyword matches
                    "reasoning": (
                        f"Matched {keyword_hits}/{len(thread.keywords)} keywords "
                        f"from thread '{thread.name}'"
                    ),
                })

        matched.sort(key=lambda m: m["score"], reverse=True)

        if not matched:
            return "unclassified", [], 0.0, (
            f"No research threads matched. Paper title: '{title}'. "
            f"Consider adding new research threads or reviewing paper manually."
        )

        primary = matched[0]
        classification = primary["thread_id"]
        relevance_score = primary["score"]
        reasoning = primary["reasoning"]

        return classification, matched[:5], relevance_score, reasoning

    def _extract_claims(
        self, title: str, text: str, source: str
    ) -> list[Claim]:
        """Extract claims from the paper with provenance attached.

        Each claim is a tuple of (claim_text, source_document, source_location).
        """
        claims = []

        # Extract key claims from abstract/introduction (first 3000 chars)
        abstract_text = text[:3000]

        # Simple claim extraction: sentences that look like findings
        import re
        sentences = re.split(r'(?<=[.!?])\s+', abstract_text)
        claim_patterns = [
            r'(?i)\b(we find|we show|we demonstrate|we prove|we establish|we present|our results)\b',
            r'(?i)\b(this (paper|work|study) (presents|introduces|proposes|demonstrates))\b',
            r'(?i)\b(the (key|main|primary) (finding|result|contribution|insight))\b',
            r'(?i)\b(we (argue|conclude|propose|suggest|hypothesize))\b',
        ]

        for i, sentence in enumerate(sentences[:20]):  # Max 20 claims
            sentence = sentence.strip()
            if len(sentence) < 30 or len(sentence) > 500:
                continue

            is_claim = any(re.search(pattern, sentence) for pattern in claim_patterns)
            if not is_claim:
                continue

            claim = self.provenance.create_claim(
                claim_text=sentence,
                source_document=source,
                source_location=f"abstract, sentence {i + 1}",
                confidence=0.85,
            )
            claims.append(claim)

        return claims

    def _summarize(
        self, title: str, text: str, classification: str, matched_threads: list[dict]
    ) -> str:
        """Generate a structured summary of the paper.

        In production, this calls an LLM. Here we provide a template-based
        summary that the evaluation harness can validate.
        """
        thread_names = [t["thread_name"] for t in matched_threads[:3]]
        thread_str = ", ".join(thread_names) if thread_names else "no specific threads"

        # Extract first paragraph as proxy for abstract
        paragraphs = text.split("\n\n")
        first_para = paragraphs[0][:500] if paragraphs else text[:500]

        return (
            f"Paper: {title}\n"
            f"Classification: {classification}\n"
            f"Relevant threads: {thread_str}\n"
            f"Summary: {first_para}..."
        )

    def _build_reasoning_trace(
        self,
        title: str,
        classification: str,
        relevance_score: float,
        matched_threads: list[dict],
        reasoning: str,
    ) -> str:
        """Build a human-readable, auditable reasoning trace."""
        lines = [
            f"Literature Triage Reasoning Trace",
            f"=================================",
            f"Paper: {title}",
            f"Classification: {classification}",
            f"Relevance Score: {relevance_score:.2f}",
            f"",
            f"Thread Matching:",
        ]
        for t in matched_threads:
            lines.append(f"  - {t['thread_name']} (score: {t['score']:.2f}): {t['reasoning']}")

        lines.append(f"")
        lines.append(f"Primary reasoning: {reasoning}")
        lines.append(f"")
        lines.append(f"Audit: This trace was generated by {self.agent_id}")
        lines.append(f"Model: {self.model_provider}/{self.model_version}")
        lines.append(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")

        return "\n".join(lines)

    def _get_active_prompt_version(self) -> str:
        """Get the active prompt version for logging."""
        active = self.ops.get_active_prompt("literature_triage")
        return active.version_id if active else "unknown"

    def _estimate_cost(self, text: str) -> float:
        """Estimate inference cost based on token count."""
        # Rough estimate: ~$0.01 per 1K tokens for classification
        token_count = len(text.split())
        return round(token_count * 0.01 / 1000, 6)

    # --- Full workflow with provenance output ---

    def triage_with_provenance(
        self, papers: list[dict], session_id: Optional[str] = None
    ) -> dict:
        """Run full triage and produce provenance-tracked output.

        This is the end-to-end workflow that produces an AgentOutput
        with every claim carrying source provenance.
        """
        if session_id:
            session = self.memory.resume_session(session_id, "literature_triage")
        else:
            session = self.memory.create_session(
                task_id=str(uuid.uuid4())[:8],
                task_description=f"Triage {len(papers)} papers",
            )

        results = self.triage_queue(papers)

        all_claims = []
        for r in results:
            all_claims.extend(r.claims_extracted)

        sources = list(set(r.paper_source for r in results))

        output = self.provenance.create_output(
            workflow="literature_triage",
            session_id=session.session_id,
            summary=f"Triaged {len(results)} papers. Top result: {results[0].paper_title if results else 'none'}",
            claims=all_claims,
            sources_consulted=sources,
            agent_version=self.agent_id,
            model_provider=self.model_provider,
            model_version=self.model_version,
        )

        # Record attribution entries for each source
        attribution_ledger = AttributionLedger()
        for r in results:
            # Extract author from paper metadata if available
            contributor = "unknown"
            entry = AttributionEntry(
                entry_id=f"attr_{uuid.uuid4().hex[:12]}",
                output_id=output.output_id,
                contributor=contributor,
                source_document=r.paper_source,
                contribution_weight=round(1.0 / max(len(results), 1), 4),
                claims_derived=[c.claim_id for c in r.claims_extracted],
            )
            attribution_ledger.record_attribution(entry)

        # Save session checkpoint for resumption
        self.memory.save_session_checkpoint(session.session_id)
        self.memory.close_session(session.session_id)

        return {
            "output": output,
            "results": results,
            "top_n": self.get_top_n(results),
            "session_id": session.session_id,
        }
