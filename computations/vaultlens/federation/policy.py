"""Embedded Policy Engine: enforces legal framework without OPA server.

For MVP, policy rules are Python predicates. In production, these would
be OPA Rego policies evaluated by an OPA sidecar. The interface is the
same: evaluate query context against rules, return allow/deny + traces.

Policy runs TWICE: once during routing (filter experts), once during
compilation (validate final answer before signing).
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PolicyDecision:
    """Result of evaluating a policy rule set against a query context."""
    allowed: bool
    rules_applied: list[str] = field(default_factory=list)
    deny_reasons: list[str] = field(default_factory=list)
    policy_trace: str = ""


class PolicyEngine:
    """Embedded policy evaluator for VaultLens federal queries.

    Rules are Python predicates that receive a context dict and return
    (allowed: bool, reason: str).
    """

    def __init__(self):
        self.rules: dict[str, callable] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register built-in policy rules."""

        # Rule: data sovereignty — PII queries must stay in declared jurisdictions
        def rule_jurisdiction_lock(ctx: dict) -> tuple[bool, str]:
            experts = ctx.get("proposed_experts", [])
            required = ctx.get("required_jurisdictions", [])
            if not required:
                return True, ""
            for expert in experts:
                legal = expert.get("legal_boundaries", {})
                expert_juris = legal.get("jurisdictions", [])
                if not set(required).issubset(set(expert_juris)):
                    return False, (
                        f"Expert '{expert.get('expert_id', '?')}' lacks required "
                        f"jurisdiction(s): {set(required) - set(expert_juris)}"
                    )
            return True, "jurisdiction_lock: passed"

        self.rules["jurisdiction_lock"] = rule_jurisdiction_lock

        # Rule: multi-expert queries require stitch_summaries_only strategy
        def rule_multi_expert_strategy(ctx: dict) -> tuple[bool, str]:
            experts = ctx.get("proposed_experts", [])
            strategy = ctx.get("compilation_strategy", "")
            if len(experts) > 1:
                if strategy not in ("stitch_summaries_only", "multi_expert_isolated"):
                    return False, (
                        f"Multi-expert query ({len(experts)} experts) requires "
                        f"'stitch_summaries_only' strategy, got '{strategy}'"
                    )
            return True, "multi_expert_strategy: passed"

        self.rules["multi_expert_strategy"] = rule_multi_expert_strategy

        # Rule: classification ceiling — expert must handle query classification
        def rule_classification_ceiling(ctx: dict) -> tuple[bool, str]:
            experts = ctx.get("proposed_experts", [])
            query_class = ctx.get("query_classification", "UNCLASSIFIED")
            classifications = {
                "UNCLASSIFIED": 0, "INTERNAL": 1, "CONFIDENTIAL": 2,
                "RESTRICTED": 3, "TOP_SECRET": 4,
            }
            q_level = classifications.get(query_class, 0)
            for expert in experts:
                legal = expert.get("legal_boundaries", {})
                max_class = legal.get("classification_max", "CONFIDENTIAL")
                e_level = classifications.get(max_class, 0)
                if q_level > e_level:
                    return False, (
                        f"Query classification '{query_class}' (L{q_level}) exceeds "
                        f"expert '{expert.get('expert_id', '?')}' max '{max_class}' (L{e_level})"
                    )
            return True, "classification_ceiling: passed"

        self.rules["classification_ceiling"] = rule_classification_ceiling

        # Rule: anonymization required for sensitive queries
        def rule_anonymization(ctx: dict) -> tuple[bool, str]:
            experts = ctx.get("proposed_experts", [])
            query_class = ctx.get("query_classification", "UNCLASSIFIED")
            if query_class in ("CONFIDENTIAL", "RESTRICTED"):
                for expert in experts:
                    legal = expert.get("legal_boundaries", {})
                    if legal.get("anonymization_required", True):
                        if not ctx.get("anonymization_applied", False):
                            return False, (
                                f"Query '{query_class}' requires anonymization but "
                                f"none applied for expert '{expert.get('expert_id', '?')}'"
                            )
            return True, "anonymization: passed"

        self.rules["anonymization"] = rule_anonymization

        # Rule: cross-border export control
        def rule_cross_border(ctx: dict) -> tuple[bool, str]:
            experts = ctx.get("proposed_experts", [])
            if ctx.get("cross_border_requested", False):
                for expert in experts:
                    legal = expert.get("legal_boundaries", {})
                    if not legal.get("cross_border_export_allowed", False):
                        return False, (
                            f"Cross-border export requested but expert "
                            f"'{expert.get('expert_id', '?')}' forbids it"
                        )
            return True, "cross_border: passed"

        self.rules["cross_border"] = rule_cross_border

    def evaluate(self, context: dict, rule_names: list[str] = None) -> PolicyDecision:
        """Evaluate policy rules against a query context.

        Args:
            context: Query context with proposed_experts, query_classification, etc.
            rule_names: Specific rules to evaluate (None = all)

        Returns:
            PolicyDecision with allow/deny and trace
        """
        names = rule_names or list(self.rules.keys())
        applied = []
        denials = []
        trace_parts = []

        for name in names:
            rule_fn = self.rules.get(name)
            if rule_fn is None:
                continue
            allowed, reason = rule_fn(context)
            applied.append(name)
            trace_parts.append(f"[{name}] {'ALLOW' if allowed else 'DENY'}: {reason}")
            if not allowed:
                denials.append(reason)

        allowed = len(denials) == 0
        return PolicyDecision(
            allowed=allowed,
            rules_applied=applied,
            deny_reasons=denials,
            policy_trace="\n".join(trace_parts),
        )
