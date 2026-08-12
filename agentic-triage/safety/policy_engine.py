"""Four-rule policy engine — the minimal gate for all agent actions.

Per Nullresearch strategy: four rules, not forty. Every additional gate
is a cost in researcher trust and must earn its place.

The four rules:
1. Any write outside the agent's own persistent memory (no vault writes, no external DB writes).
2. Any outbound network call whose destination was not in the original task specification.
3. Any shell command with side effects beyond stdout/stderr.
4. Any action that impersonates a human identity.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Callable
from datetime import datetime, timezone
import json
from pathlib import Path


class ActionType(Enum):
    """Categories of agent actions subject to policy gates."""
    FILE_READ = auto()           # Reading any file
    FILE_WRITE = auto()          # Writing any file
    VAULT_READ = auto()          # Reading from the vault
    VAULT_WRITE = auto()         # Writing to the vault (always gated - rule 1)
    MEMORY_READ = auto()         # Reading agent's own persistent memory
    MEMORY_WRITE = auto()        # Writing agent's own persistent memory
    NETWORK_OUTBOUND = auto()    # Outbound network call
    SHELL_COMMAND = auto()       # Shell command execution
    SHELL_READONLY = auto()      # Read-only shell command (no side effects)
    HUMAN_IMPERSONATION = auto() # Action impersonating human identity


@dataclass
class ActionRequest:
    """An action the agent wants to perform, subject to policy gating."""
    action_type: ActionType
    description: str
    target: str  # File path, URL, command, etc.
    session_id: str
    task_spec: dict = field(default_factory=dict)  # Original task specification
    metadata: dict = field(default_factory=dict)


@dataclass
class PolicyDecision:
    """Result of policy evaluation for a requested action."""
    allowed: bool
    rule_triggered: Optional[int] = None  # Which rule blocked it (1-4)
    reason: str = ""
    requires_approval: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class PolicyEngine:
    """Minimal four-rule policy engine for agent action gating.

    If an action triggers no rule, it is allowed.
    If it triggers any rule, the agent pauses and requests human sign-off.
    """

    def __init__(self, memory_path: str = "data/memory_store", log_path: str = "data/logs"):
        self.memory_path = Path(memory_path)
        self.log_path = Path(log_path)
        self.log_path.mkdir(parents=True, exist_ok=True)
        self._approval_callbacks: list[Callable] = []
        self.decision_log: list[PolicyDecision] = []

    def register_approval_callback(self, callback: Callable[[ActionRequest, PolicyDecision], None]):
        """Register a callback for when an action requires human approval."""
        self._approval_callbacks.append(callback)

    def evaluate(self, action: ActionRequest) -> PolicyDecision:
        """Evaluate an action against the four rules.

        Returns a PolicyDecision. Actions triggering any rule are blocked
        and require human approval.
        """
        # Rule 1: Any write outside agent's persistent memory
        if action.action_type == ActionType.VAULT_WRITE:
            decision = PolicyDecision(
                allowed=False, rule_triggered=1,
                reason="Rule 1: No vault writes. Agents read from vault but never write to it.",
                requires_approval=True,
            )
        elif action.action_type == ActionType.FILE_WRITE:
            # Allow writes only within agent's memory directory
            target_path = Path(action.target)
            if not str(target_path.resolve()).startswith(str(self.memory_path.resolve())):
                decision = PolicyDecision(
                    allowed=False, rule_triggered=1,
                    reason=f"Rule 1: Write target '{action.target}' is outside agent memory path.",
                    requires_approval=True,
                )
            else:
                decision = PolicyDecision(allowed=True, reason="Write within agent memory — allowed.")

        # Rule 2: Outbound network call to unapproved destination
        elif action.action_type == ActionType.NETWORK_OUTBOUND:
            allowed_destinations = action.task_spec.get("allowed_destinations", [])
            if allowed_destinations:
                target_approved = any(
                    domain in action.target for domain in allowed_destinations
                )
                if not target_approved:
                    decision = PolicyDecision(
                        allowed=False, rule_triggered=2,
                        reason=f"Rule 2: Network destination '{action.target}' not in task's allowed destinations.",
                        requires_approval=True,
                    )
                else:
                    decision = PolicyDecision(
                        allowed=True,
                        reason="Network call to approved destination — allowed.",
                    )
            else:
                decision = PolicyDecision(
                    allowed=True,
                    reason="No destination restrictions in task spec — allowed.",
                )

        # Rule 3: Shell command with side effects
        elif action.action_type == ActionType.SHELL_COMMAND:
            decision = PolicyDecision(
                allowed=False, rule_triggered=3,
                reason=f"Rule 3: Shell command '{action.target}' may have side effects. Use SHELL_READONLY for safe commands.",
                requires_approval=True,
            )

        # Rule 4: Human impersonation
        elif action.action_type == ActionType.HUMAN_IMPERSONATION:
            decision = PolicyDecision(
                allowed=False, rule_triggered=4,
                reason="Rule 4: No action may impersonate a human identity (email, publishing, forum posts).",
                requires_approval=True,
            )

        else:
            decision = PolicyDecision(allowed=True, reason="No rule triggered — allowed.")

        self.decision_log.append(decision)
        self._log_decision(action, decision)

        if decision.requires_approval:
            for callback in self._approval_callbacks:
                callback(action, decision)

        return decision

    def _log_decision(self, action: ActionRequest, decision: PolicyDecision):
        """Log policy decisions for audit trail."""
        log_entry = {
            "timestamp": decision.timestamp,
            "session_id": action.session_id,
            "action_type": action.action_type.name,
            "target": action.target,
            "description": action.description,
            "allowed": decision.allowed,
            "rule_triggered": decision.rule_triggered,
            "reason": decision.reason,
        }
        log_file = self.log_path / "policy_decisions.jsonl"
        with open(log_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")

    def get_recent_decisions(self, limit: int = 50) -> list[dict]:
        """Retrieve recent policy decisions for audit review."""
        log_file = self.log_path / "policy_decisions.jsonl"
        if not log_file.exists():
            return []
        decisions = []
        with open(log_file) as f:
            for line in f:
                decisions.append(json.loads(line))
        return decisions[-limit:]

    def is_action_safe(self, action: ActionRequest) -> bool:
        """Quick check: is this action automatically safe (no gates triggered)?"""
        decision = self.evaluate(action)
        return decision.allowed and not decision.requires_approval
