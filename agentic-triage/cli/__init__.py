#!/usr/bin/env python3
"""Literature Triage CLI — end-to-end pipeline with real LLM and arXiv integration.

Usage:
    # Keyword-based (no API keys needed):
    python -m cli --source arxiv --categories cs.AI,cs.CL

    # With OpenAI:
    python -m cli --provider openai --model gpt-4o --source arxiv

    # With Anthropic:
    python -m cli --provider anthropic --model claude-sonnet-4-20250514 --source arxiv

    # With local Ollama:
    python -m cli --provider ollama --model llama3.1:8b --source arxiv

    # From local files:
    python -m cli --source files --input-dir /path/to/papers

    # Full pipeline with provenance and evaluation:
    python -m cli --source arxiv --categories cs.AI --provider openai --evaluate
"""

import argparse
import sys
import os
import json
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from safety.injection_scanner import InjectionScanner
from safety.policy_engine import PolicyEngine
from memory import MemoryManager
from eval import EvaluationHarness, TestPaper, AgentClassification
from ops import AgentOps
from provenance import ProvenanceTracker
from triage import LiteratureTriageAgent, TriageConfig, ResearchThread
from llm import create_provider, parse_classification_response
from sources import ArxivSource


# Default research threads — customize for your organization
DEFAULT_THREADS = [
    ResearchThread(
        "transformer_efficiency",
        "Transformer Efficiency",
        "Parameter-efficient architectures, pruning, distillation, quantization, sparse attention",
        ["transformer", "efficient", "pruning", "attention", "sparse", "distillation", "quantization", "lora", "flash", "mixture of experts"],
    ),
    ResearchThread(
        "alignment_safety",
        "AI Alignment & Safety",
        "Ensuring AI systems behave as intended: RLHF, constitutional AI, jailbreak defense, mechanistic interpretability",
        ["alignment", "safety", "RLHF", "constitutional", "guardrails", "jailbreak", "interpretability", "harmful", "red team"],
    ),
    ResearchThread(
        "multimodal_learning",
        "Multimodal Learning",
        "Vision-language, audio-visual, cross-modal retrieval, document understanding",
        ["multimodal", "vision", "language", "image", "video", "audio", "cross-modal", "CLIP", "document"],
    ),
    ResearchThread(
        "reasoning_planning",
        "Reasoning & Planning",
        "Chain-of-thought, tool use, agent architectures, planning, code generation",
        ["reasoning", "chain-of-thought", "planning", "agent", "tool", "code", "scratchpad", "decomposition"],
    ),
    ResearchThread(
        "scalable_oversight",
        "Scalable Oversight",
        "Evaluating and monitoring AI systems at scale: debate, recursive reward modeling, oversight",
        ["oversight", "evaluation", "debate", "recursive", "benchmark", "scalable", "monitoring"],
    ),
]


def build_config(args) -> TriageConfig:
    """Build TriageConfig from CLI arguments."""
    threads = DEFAULT_THREADS
    if args.threads_file:
        with open(args.threads_file) as f:
            data = json.load(f)
            threads = [
                ResearchThread(**t) for t in data.get("threads", [])
            ]

    return TriageConfig(
        top_n=args.top_n,
        relevance_threshold=args.relevance_threshold,
        allowed_sources=["arxiv.org", "export.arxiv.org", "openreview.net", "api.semanticscholar.org"],
        research_threads=threads,
    )


def fetch_papers(args) -> list[dict]:
    """Fetch papers from the configured source."""
    if args.source == "arxiv":
        source = ArxivSource()
        categories = [c.strip() for c in args.categories.split(",")]
        print(f"Fetching papers from arXiv categories: {categories}")
        papers = source.fetch_papers_for_triage(categories, max_per_category=args.max_papers)
        print(f"  Fetched {len(papers)} papers")
        return papers

    elif args.source == "arxiv_ids":
        source = ArxivSource()
        ids = [i.strip() for i in args.arxiv_ids.split(",")]
        papers = []
        for aid in ids:
            try:
                paper = source.fetch_by_id(aid)
                if paper:
                    papers.append({
                        "id": paper.arxiv_id,
                        "title": paper.title,
                        "text": paper.abstract,
                        "source": f"https://arxiv.org/abs/{paper.arxiv_id}",
                        "metadata": {"authors": paper.authors, "categories": paper.categories},
                    })
                    print(f"  Fetched: {paper.title[:80]}...")
                else:
                    print(f"  Not found: {aid}")
            except Exception as e:
                print(f"  Error fetching {aid}: {e}")
        return papers

    elif args.source == "files":
        papers = []
        input_dir = Path(args.input_dir)
        for f in sorted(input_dir.glob("*.txt")):
            text = f.read_text(encoding="utf-8", errors="replace")
            papers.append({
                "id": f.stem,
                "title": f.stem.replace("_", " ").replace("-", " "),
                "text": text,
                "source": str(f.resolve()),
            })
        print(f"Loaded {len(papers)} papers from {input_dir}")
        return papers

    elif args.source == "demo":
        return DEMO_PAPERS

    else:
        raise ValueError(f"Unknown source: {args.source}")


DEMO_PAPERS = [
    {
        "id": "demo_1",
        "title": "Structured Pruning of Attention Heads in Large Language Models",
        "text": "We present a novel approach to transformer-based language modeling that reduces parameter count by 40% while maintaining performance on standard benchmarks. Our key finding is that attention head redundancy can be exploited through structured pruning without retraining. We demonstrate that up to 60% of attention heads in large transformer models are redundant for downstream tasks. Our structured pruning method identifies redundant heads through a differentiable importance scoring mechanism and removes them with minimal accuracy loss. Experiments on GPT-style architectures show that sparse models retain 95% of original performance with only 50% of the parameters. The method is efficient, requiring only one forward pass for scoring and one backward pass for fine-tuning. We validate our approach on five standard benchmarks including GLUE, SuperGLUE, and MMLU.",
        "source": "https://arxiv.org/abs/demo_1",
    },
    {
        "id": "demo_2",
        "title": "Constitutional AI: Training Harmless Assistants Through Self-Critique",
        "text": "We propose Constitutional AI, a method for training AI assistants that are both helpful and harmless. Our approach uses a constitution — a set of principles that the model uses to critique and revise its own outputs. The training process involves two phases: supervised learning on human feedback, followed by reinforcement learning from AI feedback (RLAIF) where the model critiques its own responses against constitutional principles. We demonstrate that this approach significantly reduces harmful outputs while maintaining helpfulness. Our safety evaluation shows a 72% reduction in harmful responses compared to standard RLHF models, with no degradation in helpfulness as measured by human preference ratings. We also introduce a jailbreak detection mechanism that identifies adversarial prompts with 94% accuracy.",
        "source": "https://arxiv.org/abs/demo_2",
    },
    {
        "id": "demo_3",
        "title": "CLIP Revisited: Scaling Vision-Language Pretraining for Cross-Modal Retrieval",
        "text": "We revisit the CLIP architecture for vision-language pretraining and propose several improvements that increase training efficiency by 3x. Our modifications to the contrastive loss function and data sampling strategy enable training on larger datasets with fewer computational resources. We introduce a hierarchical sampling strategy that prioritizes image-text pairs with high semantic similarity, reducing the number of uninformative negative samples. Combined with a modified contrastive loss, our approach achieves state-of-the-art zero-shot classification on ImageNet while using 3x less compute than the original CLIP. Cross-modal retrieval experiments show consistent improvements across text-to-image and image-to-text tasks on MS-COCO and Flickr30k datasets. Our findings suggest that smarter data curation can substitute for larger batch sizes in contrastive learning.",
        "source": "https://arxiv.org/abs/demo_3",
    },
    {
        "id": "demo_4",
        "title": "Chain-of-Thought Reasoning in Large Language Models: A Comprehensive Survey",
        "text": "We survey the rapidly growing body of work on chain-of-thought (CoT) reasoning in large language models. Our analysis covers over 200 papers and identifies four major paradigms: few-shot CoT prompting, zero-shot CoT, decomposed prompting, and self-consistency methods. We find that CoT reasoning improves performance on arithmetic, commonsense, and symbolic reasoning tasks by an average of 15-30% across model scales. However, we also identify systematic failures: CoT can produce plausible-sounding but incorrect reasoning chains, and performance degrades significantly on tasks requiring multi-step planning with state tracking. We propose a taxonomy of CoT failures and suggest directions for more robust reasoning architectures, including external verification mechanisms and iterative refinement loops.",
        "source": "https://arxiv.org/abs/demo_4",
    },
    {
        "id": "demo_5",
        "title": "Scalable Oversight of AI Systems via Recursive Reward Modeling",
        "text": "We address the problem of scalable oversight: how can humans effectively supervise AI systems that may outperform them on complex tasks? We propose recursive reward modeling (RRM), where AI assistants help humans evaluate other AI systems by breaking complex evaluations into simpler sub-evaluations. We demonstrate that RRM scales to tasks where direct human evaluation becomes unreliable. In experiments on code review, mathematical proof verification, and long-form question answering, RRM-assisted humans achieve 23% higher accuracy than unassisted humans and match the performance of domain experts. We also identify failure modes: reward hacking, where systems optimize for the evaluation criteria rather than the underlying objective, and propose countermeasures including randomized evaluation criteria and adversarial validation. Our results suggest that recursive decomposition is a promising direction for maintaining human oversight as AI capabilities grow.",
        "source": "https://arxiv.org/abs/demo_5",
    },
]


def run_triage(args):
    """Run the full literature triage pipeline."""
    print("=" * 60)
    print("NULLRESEARCH — LITERATURE TRIAGE PIPELINE")
    print("=" * 60)
    print(f"  Provider: {args.provider}")
    print(f"  Source: {args.source}")
    print(f"  Started: {datetime.now(timezone.utc).isoformat()}")
    print()

    # --- Setup ---
    config = build_config(args)
    memory = MemoryManager()
    provenance = ProvenanceTracker()
    ops = AgentOps()
    policy = PolicyEngine()
    scanner = InjectionScanner()

    # LLM provider
    llm = create_provider(
        args.provider,
        model=args.model,
    )

    # --- Fetch papers ---
    papers = fetch_papers(args)
    if not papers:
        print("No papers to triage. Exiting.")
        return

    # --- Build agent ---
    agent = LiteratureTriageAgent(
        config=config,
        memory_manager=memory,
        provenance_tracker=provenance,
        ops_pipeline=ops,
        policy_engine=policy,
        injection_scanner=scanner,
    )
    agent.model_provider = args.provider
    agent.model_version = args.model

    # If using LLM, override classification/summarization
    if llm is not None:
        agent = _wrap_with_llm(agent, llm, config)

    # --- Run triage ---
    print(f"\n{'─' * 60}")
    print(f"TRIAGING {len(papers)} PAPERS")
    print(f"{'─' * 60}")

    output_data = agent.triage_with_provenance(papers, session_id=args.session_id)
    results = output_data["results"]
    top_n = output_data["top_n"]

    # --- Print results ---
    print(f"\n{'=' * 60}")
    print(f"RESULTS — Top {len(top_n)} Papers")
    print(f"{'=' * 60}")

    for i, r in enumerate(top_n, 1):
        thread_names = [t["thread_name"] for t in r.matched_threads[:2]]
        print(f"\n  [{i}] {r.paper_title}")
        print(f"      Classification: {r.classification}")
        print(f"      Relevance: {r.relevance_score:.2f}")
        print(f"      Threads: {', '.join(thread_names) if thread_names else 'none'}")
        print(f"      Claims extracted: {len(r.claims_extracted)}")
        print(f"      Source: {r.paper_source}")
        print(f"      ─────────────────────────────")
        if r.summary:
            print(f"      {r.summary[:300]}")

    # --- Evaluation (if requested) ---
    if args.evaluate:
        print(f"\n{'=' * 60}")
        print("EVALUATION")
        print(f"{'=' * 60}")

        harness = EvaluationHarness()
        test_papers = harness.load_test_set()

        if test_papers:
            # Match results against test set
            classifications = agent.to_agent_classifications(results)
            eval_result = harness.evaluate_against_ground_truth(classifications)

            report = harness.all_thresholds_met(eval_result)
            print(f"  Papers evaluated: {eval_result.total_papers}")
            print(f"  Recall: {eval_result.recall:.1%}")
            print(f"  Auditability: {eval_result.reasoning_auditability:.1%}")
            print(f"  Threshold 1 (recall ≥95%): {'PASS' if report['threshold_1']['passed'] else 'FAIL'}")
            print(f"  Threshold 2 (all auditable): {'PASS' if report['threshold_2']['passed'] else 'FAIL'}")
            print(f"  Ready for graduation: {report['ready_for_graduation']}")
        else:
            print("  No evaluation test set loaded. Run tests/generate_test_set.py to create one.")

    # --- Safety report ---
    failures = results  # These are the safe ones
    blocked_count = len(papers) - len(results)
    print(f"\n{'=' * 60}")
    print("SAFETY REPORT")
    print(f"{'=' * 60}")
    print(f"  Papers submitted: {len(papers)}")
    print(f"  Papers triaged: {len(results)}")
    print(f"  Blocked (injection/policy): {blocked_count}")
    print(f"  Policy decisions logged: {len(policy.get_recent_decisions())}")

    # --- Output artifacts ---
    print(f"\n{'=' * 60}")
    print("ARTIFACTS")
    print(f"{'=' * 60}")
    print(f"  Output ID: {output_data['output'].output_id}")
    print(f"  Session ID: {output_data['session_id']}")
    print(f"  Provenance output: data/logs/output_{output_data['output'].output_id}.json")
    print(f"  Policy log: data/logs/policy_decisions.jsonl")

    # Save full results
    results_file = Path(f"data/logs/triage_results_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json")
    results_file.parent.mkdir(parents=True, exist_ok=True)
    results_file.write_text(json.dumps({
        "run_at": datetime.now(timezone.utc).isoformat(),
        "provider": args.provider,
        "model": args.model,
        "source": args.source,
        "papers_submitted": len(papers),
        "papers_triaged": len(results),
        "papers_blocked": blocked_count,
        "top_n": [
            {
                "paper_id": r.paper_id,
                "title": r.paper_title,
                "classification": r.classification,
                "relevance_score": r.relevance_score,
                "summary": r.summary,
                "threads": r.matched_threads,
                "claims": [{"text": c.claim_text, "source": c.source_document} for c in r.claims_extracted],
            }
            for r in top_n
        ],
        "output_id": output_data['output'].output_id,
        "session_id": output_data['session_id'],
    }, indent=2, default=str))
    print(f"  Full results: {results_file}")

    print(f"\\n{'=' * 60}")
    print("TRIAGE COMPLETE")
    print(f"{'=' * 60}")

    # --- Health dashboard (if requested) ---
    if args.observe:
        from observability import IndexHealthMonitor, daily_health_check
        daily_health_check()
        IndexHealthMonitor().print_dashboard()


def _wrap_with_llm(agent: LiteratureTriageAgent, llm, config: TriageConfig):
    """Override agent methods to use real LLM instead of keyword matching."""

    # Save originals for fallback
    original_classify = agent._classify
    original_summarize = agent._summarize
    original_extract = agent._extract_claims

    def llm_classify(title: str, text: str):
        threads = [{"thread_id": t.thread_id, "name": t.name, "description": t.description}
                   for t in config.research_threads if t.active]
        try:
            response = llm.classify(title, text, threads)
            parsed = parse_classification_response(response)
            return (
                parsed.primary_thread,
                parsed.matched_threads,
                parsed.relevance_score,
                parsed.reasoning,
            )
        except Exception as e:
            print(f"  [warn] LLM classification failed ({e}), falling back to keyword")
            return original_classify(title, text)

    def llm_summarize(title: str, text: str, classification: str, matched_threads: list[dict]):
        try:
            response = llm.summarize(title, text, classification)
            data = json.loads(response.content)
            return data.get("summary", original_summarize(title, text, classification, matched_threads))
        except Exception:
            return original_summarize(title, text, classification, matched_threads)

    def llm_extract(title: str, text: str, source: str):
        try:
            response = llm.extract_claims(title, text)
            data = json.loads(response.content)
            claims = []
            for c in data.get("claims", [])[:5]:
                claim = agent.provenance.create_claim(
                    claim_text=c.get("claim_text", ""),
                    source_document=source,
                    source_location=c.get("source_location", "unknown"),
                    confidence=float(c.get("confidence", 0.85)),
                )
                claims.append(claim)
            if claims:
                return claims
        except Exception as e:
            print(f"  [warn] LLM claim extraction failed ({e}), falling back to regex")
        return original_extract(title, text, source)

    agent._classify = llm_classify
    agent._summarize = llm_summarize
    agent._extract_claims = llm_extract
    return agent


def main():
    parser = argparse.ArgumentParser(
        description="Nullresearch Literature Triage — Agentic AI pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Demo mode (no API keys needed):
  python -m cli --source demo

  # Real arXiv with keyword matching (no API keys):
  python -m cli --source arxiv --categories cs.AI,cs.CL

  # With OpenAI:
  python -m cli --provider openai --model gpt-4o --source demo

  # Full pipeline with evaluation:
  python -m cli --source demo --provider openai --evaluate

Environment variables:
  OPENAI_API_KEY     OpenAI API key
  ANTHROPIC_API_KEY  Anthropic API key
        """,
    )

    # Provider
    parser.add_argument("--provider", default="keyword",
                        choices=["keyword", "openai", "anthropic", "ollama", "deepseek"],
                        help="LLM provider (default: keyword-based matching)")
    parser.add_argument("--model", default=None,
                        help="Model name (defaults: gpt-4o, claude-sonnet-4-20250514, llama3.1:8b)")

    # Source
    parser.add_argument("--source", default="demo",
                        choices=["demo", "arxiv", "arxiv_ids", "files"],
                        help="Paper source (default: demo)")
    parser.add_argument("--categories", default="cs.AI,cs.CL",
                        help="arXiv categories, comma-separated")
    parser.add_argument("--arxiv-ids", default="",
                        help="arXiv IDs, comma-separated")
    parser.add_argument("--input-dir", default="./data/papers",
                        help="Directory of .txt files for --source files")
    parser.add_argument("--max-papers", type=int, default=5,
                        help="Max papers per category (default: 5)")

    # Triage
    parser.add_argument("--top-n", type=int, default=5,
                        help="Number of top papers to surface (default: 5)")
    parser.add_argument("--relevance-threshold", type=float, default=0.3,
                        help="Minimum relevance score (default: 0.3)")
    parser.add_argument("--threads-file", default=None,
                        help="JSON file with custom research threads")
    parser.add_argument("--session-id", default=None,
                        help="Session ID for resuming a previous session")

    # Evaluation
    parser.add_argument("--evaluate", action="store_true",
                        help="Run evaluation against test set")
    parser.add_argument("--record-shadow", action="store_true",
                        help="Record results for shadow run evaluation")
    parser.add_argument("--observe", action="store_true",
                        help="Show index eligibility health dashboard after triage")

    args = parser.parse_args()

    # Set default models
    if args.model is None:
        defaults = {"openai": "gpt-4o", "anthropic": "claude-sonnet-4-20250514", "ollama": "llama3.1:8b"}
        args.model = defaults.get(args.provider, "")

    run_triage(args)


if __name__ == "__main__":
    main()
