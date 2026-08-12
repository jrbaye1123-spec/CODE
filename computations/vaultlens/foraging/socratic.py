"""Socratic disambiguation: interactive prompts for debt resolution.

When the Foraging Engine cannot resolve a conflict autonomously, it generates
targeted questions derived from the conflicting claims' scope or jurisdiction
mismatch — never invented.
"""

from .debt import EpistemicDebt
from .engine import ForagingResult


def format_socratic_prompt(result: ForagingResult, debt: EpistemicDebt) -> str:
    """Format a Socratic disambiguation prompt for the user.

    Returns a human-readable prompt with the question and numbered options.
    The user's answer can be fed back into the Session Graph to re-resolve.
    """
    if not result.socratic_question:
        return ""

    lines = []
    lines.append("=" * 60)
    lines.append(f"EPISTEMIC DEBT: {debt.debt_id}")
    lines.append("=" * 60)
    lines.append(f"Query: {debt.query_text}")
    lines.append(f"Status: {debt.status}")
    lines.append(f"Trigger: {debt.trigger}")
    lines.append("")

    lines.append(result.socratic_question)
    lines.append("")

    for i, option in enumerate(result.socratic_options, 1):
        lines.append(f"  [{i}] {option}")

    lines.append("")
    lines.append(f"Enter choice [1-{len(result.socratic_options)}] or 'skip':")
    lines.append("=" * 60)

    return "\n".join(lines)


def apply_socratic_answer(debt: EpistemicDebt, choice: int,
                          session_graph=None) -> dict:
    """Apply a user's Socratic answer to resolve the debt.

    If a session_graph is provided, the answer is injected as a temporary
    condition node, allowing the Adjudicator to re-evaluate the query.

    Returns dict with: resolved (bool), action (str), context_update (dict)
    """
    if choice < 1 or not debt:
        return {"resolved": False, "action": "invalid_choice"}

    action_map = {
        1: "prefer_demand_side",
        2: "prefer_supply_side",
        3: "conservative_fallback",
    }

    action = action_map.get(choice, "unknown")

    context_update = {}
    if session_graph is not None and choice in (1, 2):
        condition = "demand_driven" if choice == 1 else "supply_driven"
        context_update = {
            "condition_node": condition,
            "action": "inject_scope_resolution",
            "debt_id": debt.debt_id,
        }

    return {
        "resolved": choice in (1, 2, 3),
        "action": action,
        "context_update": context_update,
    }
