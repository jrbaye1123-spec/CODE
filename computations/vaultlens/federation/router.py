"""Federated Router: dispatches queries to domain experts without central RAG.

Flow:
1. Classify query intent locally (keyword heuristics for MVP)
2. Score expert manifests against query domains
3. Filter experts through policy engine (legal gates)
4. Produce a Federated Query Plan

Zero central RAG: the router only reads manifest metadata.
It never probes underlying vector indices or document stores.
"""

from dataclasses import dataclass, field
from typing import Optional

from .manifest import ExpertManifest, ManifestRegistry
from .policy import PolicyEngine, PolicyDecision


@dataclass
class ScoredExpert:
    """An expert scored against a query."""
    manifest: ExpertManifest
    score: float
    matched_domains: list[str] = field(default_factory=list)


@dataclass
class FederatedQueryPlan:
    """Result of routing: which experts to query, and why."""
    query: str
    strategy: str                     # 'single_expert', 'multi_expert', 'refused'
    experts: list[ScoredExpert] = field(default_factory=list)
    rejected_experts: list[dict] = field(default_factory=list)  # {expert_id, reason}
    policy_decision: Optional[PolicyDecision] = None
    routing_timestamp: str = ""


class FederatedRouter:
    """Routes queries to domain experts with policy enforcement."""

    def __init__(self, registry: ManifestRegistry, policy: PolicyEngine = None):
        self.registry = registry
        self.policy = policy or PolicyEngine()

    def route(self, query: str, legal_context: dict = None,
              min_score: float = 0.3) -> FederatedQueryPlan:
        """Route a query to eligible experts.

        Args:
            query: Natural language query
            legal_context: Dict with query_classification, jurisdictions,
                          user_roles, anonymization_applied, cross_border_requested
            min_score: Minimum domain overlap score to consider an expert

        Returns:
            FederatedQueryPlan with selected/rejected experts and strategy
        """
        legal_context = legal_context or {}
        import time

        # 1. Classify query domains (keyword heuristics for MVP)
        query_tags = self._classify_query(query)

        # 2. Score all manifests
        all_manifests = self.registry.get_all()
        candidates = []
        for manifest in all_manifests:
            score, matched = self._score_manifest(manifest, query_tags)
            if score >= min_score:
                candidates.append(ScoredExpert(
                    manifest=manifest, score=score, matched_domains=matched,
                ))

        if not candidates:
            return FederatedQueryPlan(
                query=query,
                strategy="refused",
                rejected_experts=[{
                    "expert_id": "all",
                    "reason": f"No expert matched query domains: {query_tags}",
                }],
                routing_timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            )

        # 3. Policy filtering
        filtered = []
        rejected = []
        for cand in candidates:
            ctx = {
                "proposed_experts": [cand.manifest.to_dict()],
                "query_classification": legal_context.get("query_classification", "UNCLASSIFIED"),
                "required_jurisdictions": legal_context.get("jurisdictions", []),
                "compilation_strategy": "stitch_summaries_only" if len(candidates) > 1 else "single_expert",
                "anonymization_applied": legal_context.get("anonymization_applied", False),
                "cross_border_requested": legal_context.get("cross_border_requested", False),
            }
            decision = self.policy.evaluate(ctx)
            if decision.allowed:
                filtered.append(cand)
            else:
                rejected.append({
                    "expert_id": cand.manifest.expert_id,
                    "reason": "; ".join(decision.deny_reasons),
                })

        # 4. Determine strategy
        if not filtered:
            strategy = "refused"
        elif len(filtered) == 1:
            strategy = "single_expert"
        else:
            strategy = "multi_expert"

        return FederatedQueryPlan(
            query=query,
            strategy=strategy,
            experts=filtered,
            rejected_experts=rejected,
            policy_decision=PolicyDecision(
                allowed=strategy != "refused",
                rules_applied=list(self.policy.rules.keys()),
                deny_reasons=[r["reason"] for r in rejected],
            ),
            routing_timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )

    def _classify_query(self, query: str) -> list[str]:
        """Classify query into domain tags using keyword heuristics.

        In production: use lightweight BERT classifier or LLM.
        For MVP: keyword matching against known domains.
        """
        q = query.lower()
        tags = []

        domain_keywords = {
            "economics": ["inflation", "demand", "supply", "gdp", "recession",
                         "monetary", "fiscal", "interest rate", "spending", "market"],
            "monetary_policy": ["rate hike", "central bank", "tightening", "qe",
                               "quantitative easing", "forward guidance", "fed"],
            "clinical": ["trial", "patient", "drug", "treatment", "dose",
                        "efficacy", "adverse", "cohort"],
            "legal": ["jurisdiction", "compliance", "regulation", "statute",
                     "liability", "contract", "gdpr"],
            "governance": ["proposal", "review", "approval", "audit", "hmac",
                          "signature", "manifest"],
            "data_science": ["embedding", "vector", "model", "training",
                            "inference", "dataset", "metric", "recall"],
        }

        for domain, keywords in domain_keywords.items():
            if any(kw in q for kw in keywords):
                tags.append(domain)

        return tags if tags else ["general"]

    def _score_manifest(self, manifest: ExpertManifest,
                        query_tags: list[str]) -> tuple[float, list[str]]:
        """Score a manifest against query domain tags.

        Returns (score, matched_domains).
        Score is Jaccard-like: |intersection| / max(|query_tags|, 1).
        """
        expert_domains = [d.lower() for d in manifest.capabilities.domains]
        matched = [t for t in query_tags if t.lower() in expert_domains
                   or "general" in expert_domains]

        if not matched and "general" not in expert_domains:
            return 0.0, []

        score = len(matched) / max(len(query_tags), 1)
        return min(score, 1.0), matched
