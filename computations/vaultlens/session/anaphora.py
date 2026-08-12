"""Anaphora resolution: resolves pronouns and follow-up intent.

Before the LLM compiles a new TraversalPlan, this module resolves
references to previous context ("that", "it", "why?", "evidence?").
This enables sub-millisecond fast paths for pure follow-up queries.
"""

from .memory import SessionContext, ResolvedQuery


class AnaphoraResolver:
    """Resolves pronouns and follow-up intent against session context."""

    def __init__(self, session: SessionContext):
        self.session = session

    def resolve(self, raw_query: str) -> ResolvedQuery:
        """Resolve a raw query against session context.

        Returns a ResolvedQuery that tells the executor what to do:
        - new_query: full LLM planner needed
        - causal_expansion/evidential_expansion/etc: fast path, no LLM
        - followup_expansion: expand from focus nodes with last variants
        """
        query_lower = raw_query.lower().strip()

        # ── Pure variant follow-ups (fast path, no LLM) ──
        if query_lower in ("why?", "why", "what caused it?", "what caused that?",
                           "cause?", "causes?"):
            if self.session.last_focus_nodes:
                return ResolvedQuery(
                    intent="causal_expansion",
                    focus_nodes=self.session.last_focus_nodes,
                    variants=["causal"],
                    raw_query=raw_query,
                    is_followup=True,
                    skip_llm=True,
                )

        if query_lower in ("evidence?", "what supports that?", "proof?",
                           "what proves that?", "data?"):
            if self.session.last_focus_nodes:
                return ResolvedQuery(
                    intent="evidential_expansion",
                    focus_nodes=self.session.last_focus_nodes,
                    variants=["evidential"],
                    raw_query=raw_query,
                    is_followup=True,
                    skip_llm=True,
                )

        if query_lower in ("where did that come from?", "source?", "origin?",
                           "provenance?", "where is that from?"):
            if self.session.last_focus_nodes:
                return ResolvedQuery(
                    intent="provenance_expansion",
                    focus_nodes=self.session.last_focus_nodes,
                    variants=["provenance"],
                    raw_query=raw_query,
                    is_followup=True,
                    skip_llm=True,
                )

        if query_lower in ("when?", "when did that happen?", "before?",
                           "after?", "timeline?"):
            if self.session.last_focus_nodes:
                return ResolvedQuery(
                    intent="temporal_expansion",
                    focus_nodes=self.session.last_focus_nodes,
                    variants=["temporal"],
                    raw_query=raw_query,
                    is_followup=True,
                    skip_llm=True,
                )

        if query_lower in ("what is that part of?", "where does it belong?",
                           "hierarchy?", "structure?"):
            if self.session.last_focus_nodes:
                return ResolvedQuery(
                    intent="hierarchical_expansion",
                    focus_nodes=self.session.last_focus_nodes,
                    variants=["hierarchical"],
                    raw_query=raw_query,
                    is_followup=True,
                    skip_llm=True,
                )

        if query_lower in ("similar?", "what is similar?", "related?",
                           "what is like that?"):
            if self.session.last_focus_nodes:
                return ResolvedQuery(
                    intent="semantic_expansion",
                    focus_nodes=self.session.last_focus_nodes,
                    variants=["semantic"],
                    raw_query=raw_query,
                    is_followup=True,
                    skip_llm=True,
                )

        # ── Focus shift ("what about X?") — before pronoun check ──
        import re
        m = re.search(r"what about (.+)", query_lower.rstrip("?"))
        if m and self.session.last_focus_nodes:
            about_match = m.group(1).strip()
            return ResolvedQuery(
                intent="focus_shift",
                focus_nodes=self.session.last_focus_nodes,
                variants=self.session.last_variants,
                raw_query=raw_query,
                resolved_terms=[about_match],
                is_followup=True,
                skip_llm=False,
            )

        # ── Pronoun/anaphora resolution ────────────────
        import re
        pronouns = ["that", "it", "this", "those", "them", "these"]
        # Strip punctuation from query words before matching
        clean_words = [re.sub(r'[^\w]', '', w) for w in query_lower.split()]
        has_pronoun = any(p in clean_words for p in pronouns)

        if has_pronoun and self.session.last_focus_nodes:
            # Generic pronoun follow-up
            return ResolvedQuery(
                intent="followup_expansion",
                focus_nodes=self.session.last_focus_nodes,
                variants=self.session.last_variants,
                raw_query=raw_query,
                is_followup=True,
                skip_llm=False,  # LLM needed to interpret the full follow-up
            )

        # ── New query ──────────────────────────────────
        return ResolvedQuery(
            intent="new_query",
            focus_nodes=[],
            variants=[],
            raw_query=raw_query,
            is_followup=False,
            skip_llm=False,
        )
