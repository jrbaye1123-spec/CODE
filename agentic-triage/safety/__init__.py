"""Safety boundary — prompt-injection defense and four-rule policy engine.

This layer gates ALL agent actions. It must be operational before any
external-reading agent runs. Per Nullresearch strategy: if injection defense
fails, the agent is compromised and no other control matters.
"""

from .injection_scanner import InjectionScanner
from .policy_engine import PolicyEngine, ActionType

__all__ = ["InjectionScanner", "PolicyEngine", "ActionType"]
