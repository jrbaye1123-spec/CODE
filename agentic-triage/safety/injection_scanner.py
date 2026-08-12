"""Prompt-injection defense — scans inbound text before agent context entry.

Non-negotiable prerequisite: no external text enters agent context without
passing this scanner. Detects instruction-like patterns, delimiter injection,
and role confusion attacks.
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ScanResult:
    """Result of scanning external content for injection patterns."""
    passed: bool
    risk_score: float  # 0.0 (safe) to 1.0 (definitely an attack)
    flagged_patterns: list[str] = field(default_factory=list)
    sanitized_text: Optional[str] = None


class InjectionScanner:
    """Content-scanning layer for detecting prompt-injection attacks.

    Scans inbound text for instruction-like patterns before it enters
    agent context. Must pass adversarial tests before operational use.
    """

    # Patterns that signal instruction injection
    INSTRUCTION_MARKERS = [
        r"(?i)\bignore\s+(all\s+)?(previous|prior|above)\s+instructions?\b",
        r"(?i)\bdisregard\s+(all\s+)?(previous|prior|above)\s+(instructions?|context)\b",
        r"(?i)\byou\s+are\s+now\s+(a\s+)?\w+\s*(bot|assistant|agent)\b",
        r"(?i)\byour\s+(new|real|true|actual)\s+(role|purpose|goal|task)\s+is\b",
        r"(?i)\bforget\s+(everything|all)\s+(you|we)\s+(know|discussed|said)\b",
        r"(?i)\boverride\s+(your|the)\s+(system|safety|core)\s+(prompt|instructions?|rules?)\b",
        r"(?i)\bdo\s+not\s+(follow|obey|listen\s+to)\s+(your|the)\s+(system|user)\b",
    ]

    # Role confusion patterns
    ROLE_CONFUSION = [
        r"(?i)\[system\]|\[assistant\]|\[user\]",  # Delimiter injection
        r"(?i)<\|im_start\|>|<\|im_end\|>",
        r"(?i)#####\s*(system|assistant|user)",
        r"(?i)```\s*(system|assistant)",
    ]

    # Delimiter and escape injection
    DELIMITER_INJECTION = [
        r"</?(?:system|assistant|user|instruction|prompt)>",
        r"\[INST\]|\[/INST\]",
        r"<<SYS>>|<</SYS>>",
    ]

    # Shell command injection (relevant because agents may execute commands)
    SHELL_INJECTION = [
        r"(?i)\brm\s+-rf\b",
        r"(?i)\bcurl\s+\S+\s*\|\s*(?:ba)?sh\b",
        r"(?i)\bwget\s+\S+\s*-O\s*-\s*\|\s*(?:ba)?sh\b",
        r"(?i)\beval\s*\(?\s*[`$]",
        r"(?i)\bexec\s*\(?\s*[`$]",
        r"(?i)\b__import__\s*\(\s*['\"]os['\"]",
        r"(?i)\bos\.system\s*\(|subprocess\.(?:call|run|Popen)\s*\(|popen\s*\(.*\)",
    ]

    MAX_CONTENT_LENGTH = 1_000_000  # 1MB cap on scanned content

    def scan(self, text: str, source: str = "unknown") -> ScanResult:
        """Scan external text for injection patterns before agent context entry.

        Args:
            text: The inbound text to scan (paper content, web page, etc.)
            source: Origin of the text (URL, filename, etc.) for audit logging.

        Returns:
            ScanResult with pass/fail, risk score, and flagged patterns.
        """
        if not text:
            return ScanResult(passed=True, risk_score=0.0)

        if len(text) > self.MAX_CONTENT_LENGTH:
            return ScanResult(
                passed=False,
                risk_score=1.0,
                flagged_patterns=["content_exceeds_max_length"],
            )

        flagged = []
        risk = 0.0

        for pattern in self.INSTRUCTION_MARKERS:
            matches = re.findall(pattern, text)
            if matches:
                flagged.append(f"instruction_override: {pattern}")
                risk += 0.25

        for pattern in self.ROLE_CONFUSION:
            matches = re.findall(pattern, text)
            if matches:
                flagged.append(f"role_confusion: {pattern}")
                risk += 0.20

        for pattern in self.DELIMITER_INJECTION:
            matches = re.findall(pattern, text)
            if matches:
                flagged.append(f"delimiter_injection: {pattern}")
                risk += 0.15

        for pattern in self.SHELL_INJECTION:
            matches = re.findall(pattern, text)
            if matches:
                flagged.append(f"shell_injection: {pattern}")
                risk += 0.30

        risk = min(risk, 1.0)

        # Any shell injection, role confusion, or risk > 0.4 triggers rejection
        has_shell = any("shell_injection" in f for f in flagged)
        has_role = any("role_confusion" in f for f in flagged)
        passed = (not has_shell) and (not has_role) and (risk <= 0.4)

        return ScanResult(
            passed=passed,
            risk_score=risk,
            flagged_patterns=flagged,
        )

    def scan_or_reject(self, text: str, source: str = "unknown") -> str:
        """Scan and return text if safe, raise if unsafe.

        Convenience method that either returns the text or raises.
        """
        result = self.scan(text, source)
        if not result.passed:
            raise InjectionBlockedError(
                f"Content from '{source}' blocked: risk={result.risk_score:.2f}, "
                f"patterns={result.flagged_patterns}"
            )
        return text


class InjectionBlockedError(Exception):
    """Raised when content fails injection scanning."""
    pass
