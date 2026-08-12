"""Evaluation harness — measures Literature Triage against graduation thresholds.

Per Nullresearch strategy, graduation from experimental to operational requires:
1. Recall > 95% on a held-out test set of 30 papers with expert ground-truth labels
2. Reasoning trace is human-readable and auditable
3. Stable performance across two consecutive model/provider versions
4. Human reviewer agrees with agent classifications > 90% over a two-week shadow run
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import json


@dataclass
class TestPaper:
    """A single test paper with ground-truth labels."""
    paper_id: str
    title: str
    source: str  # arxiv ID, URL, or local path
    ground_truth: dict  # {"relevant_threads": [...], "relevance_score": float, "classification": str}
    labeled_by: str  # Expert who provided labels
    labeled_at: str


@dataclass
class AgentClassification:
    """Output from the Literature Triage agent for one paper."""
    paper_id: str
    agent_version: str
    model_provider: str
    model_version: str
    classification: str
    relevance_score: float
    relevant_threads: list[str]
    reasoning_trace: str  # Human-readable justification
    classified_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class EvaluationResult:
    """Results of evaluating agent output against ground truth."""
    total_papers: int
    correct_classifications: int
    recall: float
    thread_match_rate: float
    reasoning_auditability: float  # 0-1, how many traces pass audit
    details: list[dict] = field(default_factory=list)


class EvaluationHarness:
    """Measures triage agent performance against the four graduation thresholds."""

    def __init__(self, test_set_path: str = "data/test_set", results_path: str = "data/logs"):
        self.test_set_path = Path(test_set_path)
        self.results_path = Path(results_path)
        self.test_set_path.mkdir(parents=True, exist_ok=True)
        self.results_path.mkdir(parents=True, exist_ok=True)

    # --- Test Set Management ---

    def load_test_set(self) -> list[TestPaper]:
        """Load the held-out test set of papers with expert labels."""
        test_file = self.test_set_path / "test_set.jsonl"
        if not test_file.exists():
            return []

        papers = []
        with open(test_file) as f:
            for line in f:
                data = json.loads(line)
                papers.append(TestPaper(**data))
        return papers

    def add_test_paper(self, paper: TestPaper):
        """Add a paper to the test set (expert-labeled ground truth)."""
        test_file = self.test_set_path / "test_set.jsonl"
        with open(test_file, "a") as f:
            f.write(json.dumps({
                "paper_id": paper.paper_id,
                "title": paper.title,
                "source": paper.source,
                "ground_truth": paper.ground_truth,
                "labeled_by": paper.labeled_by,
                "labeled_at": paper.labeled_at,
            }) + "\n")

    def test_set_size(self) -> int:
        """Current size of the test set."""
        return len(self.load_test_set())

    def test_set_ready(self) -> bool:
        """Check if we have the minimum 30 labeled papers."""
        return self.test_set_size() >= 30

    # --- Evaluation Methods ---

    def evaluate_against_ground_truth(
        self, classifications: list[AgentClassification]
    ) -> EvaluationResult:
        """Compare agent classifications against expert ground-truth labels.

        This computes THRESHOLD 1: Recall > 95%
        """
        test_papers = {p.paper_id: p for p in self.load_test_set()}
        total = len(classifications)
        correct = 0
        thread_matches = 0
        auditable = 0
        details = []

        for cls in classifications:
            truth = test_papers.get(cls.paper_id)
            if not truth:
                details.append({
                    "paper_id": cls.paper_id,
                    "error": "No ground truth available",
                    "match": False,
                })
                continue

            classification_match = (
                cls.classification == truth.ground_truth.get("classification", "")
            )
            if classification_match:
                correct += 1

            # Thread match: how many ground-truth threads did agent identify?
            truth_threads = set(truth.ground_truth.get("relevant_threads", []))
            agent_threads = set(cls.relevant_threads)
            thread_match = 1.0  # Default when no truth threads
            if truth_threads:
                thread_match = len(truth_threads & agent_threads) / len(truth_threads)
            thread_matches += thread_match

            # Is the reasoning trace auditable?
            if cls.reasoning_trace and len(cls.reasoning_trace) > 20:
                auditable += 1

            details.append({
                "paper_id": cls.paper_id,
                "title": truth.title,
                "classification_match": classification_match,
                "agent_classification": cls.classification,
                "truth_classification": truth.ground_truth.get("classification"),
                "thread_match": thread_match,
                "auditable": len(cls.reasoning_trace) > 20 if cls.reasoning_trace else False,
            })

        recall = correct / total if total > 0 else 0.0
        thread_match_rate = thread_matches / total if total > 0 else 0.0
        reasoning_auditability = auditable / total if total > 0 else 0.0

        return EvaluationResult(
            total_papers=total,
            correct_classifications=correct,
            recall=recall,
            thread_match_rate=thread_match_rate,
            reasoning_auditability=reasoning_auditability,
            details=details,
        )

    def check_threshold_1(self, result: EvaluationResult) -> tuple[bool, str]:
        """THRESHOLD 1: Recall > 95%"""
        passed = result.recall >= 0.95
        msg = (
            f"THRESHOLD 1 {'PASSED' if passed else 'FAILED'}: "
            f"Recall = {result.recall:.1%} (target: ≥95%)"
        )
        return passed, msg

    def check_threshold_2(self, result: EvaluationResult) -> tuple[bool, str]:
        """THRESHOLD 2: Reasoning trace is human-readable and auditable."""
        passed = result.reasoning_auditability >= 1.0
        msg = (
            f"THRESHOLD 2 {'PASSED' if passed else 'FAILED'}: "
            f"Auditable = {result.reasoning_auditability:.0%} (target: 100%)"
        )
        return passed, msg

    def check_threshold_3(
        self, results_v1: EvaluationResult, results_v2: EvaluationResult
    ) -> tuple[bool, str]:
        """THRESHOLD 3: Stable performance across two model/provider versions."""
        recall_delta = abs(results_v1.recall - results_v2.recall)
        passed = recall_delta <= 0.05  # Within 5 percentage points
        msg = (
            f"THRESHOLD 3 {'PASSED' if passed else 'FAILED'}: "
            f"Recall delta = {recall_delta:.1%} (target: ≤5%)"
        )
        return passed, msg

    def check_threshold_4(
        self, shadow_run_results: list[dict]
    ) -> tuple[bool, str]:
        """THRESHOLD 4: Human agreement > 90% over two-week shadow run."""
        if not shadow_run_results:
            return False, "THRESHOLD 4 FAILED: No shadow run data available."

        total = len(shadow_run_results)
        agreements = sum(1 for r in shadow_run_results if r.get("human_agrees", False))
        agreement_rate = agreements / total if total > 0 else 0.0
        passed = agreement_rate >= 0.90
        msg = (
            f"THRESHOLD 4 {'PASSED' if passed else 'FAILED'}: "
            f"Human agreement = {agreement_rate:.1%} over {total} reviews (target: ≥90%)"
        )
        return passed, msg

    def all_thresholds_met(
        self,
        result: EvaluationResult,
        prev_result: Optional[EvaluationResult] = None,
        shadow_run_results: Optional[list[dict]] = None,
    ) -> dict:
        """Check all four graduation thresholds. Returns detailed report."""
        t1, t1_msg = self.check_threshold_1(result)
        t2, t2_msg = self.check_threshold_2(result)

        t3_passed = None
        t3_msg = ""
        if prev_result:
            t3_passed, t3_msg = self.check_threshold_3(prev_result, result)
        else:
            t3_msg = "THRESHOLD 3 PENDING: Need results from a second model version."

        t4_passed = None
        t4_msg = ""
        if shadow_run_results:
            t4_passed, t4_msg = self.check_threshold_4(shadow_run_results)
        else:
            t4_msg = "THRESHOLD 4 PENDING: Need two-week shadow run data."

        all_met = all([
            t1, t2,
            t3_passed if t3_passed is not None else True,
            t4_passed if t4_passed is not None else True,
        ])

        return {
            "all_passed": all_met,
            "threshold_1": {"passed": t1, "message": t1_msg},
            "threshold_2": {"passed": t2, "message": t2_msg},
            "threshold_3": {"passed": t3_passed, "message": t3_msg},
            "threshold_4": {"passed": t4_passed, "message": t4_msg},
            "ready_for_graduation": all_met and t3_passed is not None and t4_passed is not None,
        }

    def record_shadow_review(
        self,
        paper_id: str,
        agent_classification: str,
        agent_reasoning: str,
        human_agrees: bool,
        human_notes: str = "",
    ):
        """Record a single human review during the shadow run."""
        shadow_file = self.results_path / "shadow_run.jsonl"
        with open(shadow_file, "a") as f:
            f.write(json.dumps({
                "paper_id": paper_id,
                "agent_classification": agent_classification,
                "agent_reasoning": agent_reasoning,
                "human_agrees": human_agrees,
                "human_notes": human_notes,
                "reviewed_at": datetime.now(timezone.utc).isoformat(),
            }) + "\n")
