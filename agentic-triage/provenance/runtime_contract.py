"""Runtime Provenance Contract — tells agents what they may do with each index entry.

This is the consumption-side counterpart to the epistemic gate. The gate
controls what enters the index. This contract controls how downstream agents
may USE indexed content, based on its provenance level.

Per the pivoted framework:
  - verified:     Normal use. Full trust.
  - exception:    Use with warning. Time-boxed legitimacy.
  - incomplete:   Do not use for high-stakes outputs.
  - unknown:      Quarantine. Block retrieval if possible.
  - expired:      Treat as unvetted.

Agent output must carry provenance degradation in its metadata so that
downstream consumers (and humans) can see the epistemic risk at a glance.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class ProvenanceLevel(Enum):
    """Epistemic trust level of a vault index entry."""
    VERIFIED = "verified"        # Governed source, reviewed, complete provenance
    EXCEPTION = "exception"      # Time-boxed exception with owner and expiry
    INCOMPLETE = "incomplete"    # Missing some provenance fields
    UNKNOWN = "unknown"          # No provenance metadata
    EXPIRED = "expired"          # Exception has lapsed
    PARSE_FAILED = "parse_failed"  # Frontmatter unreadable — ungovernable


@dataclass
class ProvenanceAssessment:
    """Result of assessing an index entry's provenance for agent consumption."""

    entry_path: str
    entry_title: str
    level: ProvenanceLevel
    usable: bool                        # Can the agent use this entry?
    requires_warning: bool              # Must the agent flag its output?
    warning_label: str = ""             # What to display in output metadata
    reason: str = ""                    # Human-readable explanation
    assessed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ─── Behavior rules per provenance level ───

PROVENANCE_BEHAVIOR = {
    ProvenanceLevel.VERIFIED: {
        "usable": True,
        "requires_warning": False,
        "label": "provenance: verified",
        "description": "Governed source. Full provenance chain intact. Normal use.",
    },
    ProvenanceLevel.EXCEPTION: {
        "usable": True,
        "requires_warning": True,
        "label": "provenance: exception",
        "description": "Time-boxed exception. Use with caution. Check expiry.",
    },
    ProvenanceLevel.INCOMPLETE: {
        "usable": True,      # Can read, but must not base high-stakes claims on it
        "requires_warning": True,
        "label": "provenance: incomplete",
        "description": "Missing provenance fields. Do not use for high-stakes outputs.",
    },
    ProvenanceLevel.UNKNOWN: {
        "usable": False,
        "requires_warning": True,
        "label": "provenance: unknown",
        "description": "No provenance metadata. Block retrieval if possible.",
    },
    ProvenanceLevel.EXPIRED: {
        "usable": False,
        "requires_warning": True,
        "label": "provenance: expired",
        "description": "Exception has lapsed. Treat as unvetted.",
    },
    ProvenanceLevel.PARSE_FAILED: {
        "usable": False,
        "requires_warning": True,
        "label": "provenance: parse_failed",
        "description": "Frontmatter unreadable. Ungovernable content.",
    },
}


def classify_provenance(entry: dict) -> ProvenanceAssessment:
    """Classify a single index entry's provenance level for agent consumption.

    Args:
        entry: A dict from the vault index JSON. Expected keys:
               path, title, provenance_status, source_classification,
               reviewer, reviewed_at, exception_expires_at.

    Returns:
        ProvenanceAssessment with level, usability, and warning requirements.
    """
    path = entry.get("path", "unknown")
    title = entry.get("title", path)

    status = entry.get("provenance_status", "")
    source = entry.get("source_classification", "")
    reviewer = entry.get("reviewer", "")
    reviewed_at = entry.get("reviewed_at", "")
    expires_at = entry.get("exception_expires_at", "")

    # Parse failed — no provenance_status at all
    if not status:
        return ProvenanceAssessment(
            entry_path=path,
            entry_title=title,
            level=ProvenanceLevel.PARSE_FAILED,
            usable=False,
            requires_warning=True,
            warning_label="provenance: parse_failed",
            reason="No provenance_status field. Frontmatter unreadable or absent.",
        )

    # Verified — complete provenance
    if status == "verified":
        missing = []
        if not source:
            missing.append("source_classification")
        if not reviewer:
            missing.append("reviewer")
        if not reviewed_at:
            missing.append("reviewed_at")

        if missing:
            return ProvenanceAssessment(
                entry_path=path,
                entry_title=title,
                level=ProvenanceLevel.INCOMPLETE,
                usable=True,
                requires_warning=True,
                warning_label="provenance: incomplete",
                reason=f"Verified status but missing fields: {', '.join(missing)}.",
            )

        return ProvenanceAssessment(
            entry_path=path,
            entry_title=title,
            level=ProvenanceLevel.VERIFIED,
            usable=True,
            requires_warning=False,
            warning_label="provenance: verified",
            reason="Full provenance chain intact. Governed source.",
        )

    # Exception — time-boxed legitimacy
    if status == "exception":
        # Check expiry
        if expires_at:
            try:
                expiry = datetime.fromisoformat(
                    str(expires_at).replace("Z", "+00:00")
                )
                if expiry < datetime.now(timezone.utc):
                    return ProvenanceAssessment(
                        entry_path=path,
                        entry_title=title,
                        level=ProvenanceLevel.EXPIRED,
                        usable=False,
                        requires_warning=True,
                        warning_label="provenance: expired",
                        reason=f"Exception expired at {expires_at}. Treat as unvetted.",
                    )
            except (ValueError, TypeError):
                return ProvenanceAssessment(
                    entry_path=path,
                    entry_title=title,
                    level=ProvenanceLevel.INCOMPLETE,
                    usable=True,
                    requires_warning=True,
                    warning_label="provenance: incomplete",
                    reason="Exception status but expiry date unparseable.",
                )

        # Check required exception fields
        missing_exc = []
        for f in ["exception_owner", "exception_expires_at", "exception_reason"]:
            if not entry.get(f):
                missing_exc.append(f)
        if missing_exc:
            return ProvenanceAssessment(
                entry_path=path,
                entry_title=title,
                level=ProvenanceLevel.INCOMPLETE,
                usable=True,
                requires_warning=True,
                warning_label="provenance: incomplete",
                reason=f"Exception missing required fields: {', '.join(missing_exc)}.",
            )

        return ProvenanceAssessment(
            entry_path=path,
            entry_title=title,
            level=ProvenanceLevel.EXCEPTION,
            usable=True,
            requires_warning=True,
            warning_label="provenance: exception",
            reason=f"Time-boxed exception. Expires {expires_at}. Owner: {entry.get('exception_owner', 'unknown')}.",
        )

    # Unknown or unrecognized status
    return ProvenanceAssessment(
        entry_path=path,
        entry_title=title,
        level=ProvenanceLevel.UNKNOWN,
        usable=False,
        requires_warning=True,
        warning_label="provenance: unknown",
        reason=f"Unrecognized provenance_status: '{status}'.",
    )


def assess_batch(entries: list[dict]) -> dict:
    """Assess a batch of index entries and return aggregate provenance state.

    Args:
        entries: List of index entry dicts from the vault index JSON.

    Returns:
        Dict with per-entry assessments, aggregate counts, and a summary
        degradation level for output metadata.
    """
    assessments = [classify_provenance(e) for e in entries]

    counts = {level: 0 for level in ProvenanceLevel}
    for a in assessments:
        counts[a.level] += 1

    # Determine overall degradation level
    has_unusable = any(not a.usable for a in assessments)
    has_warnings = any(a.requires_warning for a in assessments)

    if has_unusable:
        overall = "degraded"
    elif has_warnings:
        overall = "warning"
    else:
        overall = "clean"

    return {
        "assessed_at": datetime.now(timezone.utc).isoformat(),
        "total_entries": len(entries),
        "counts": {level.value: count for level, count in counts.items()},
        "overall_provenance": overall,
        "requires_warning": has_warnings,
        "assessments": [
            {
                "path": a.entry_path,
                "title": a.entry_title,
                "level": a.level.value,
                "usable": a.usable,
                "warning_label": a.warning_label,
                "reason": a.reason,
            }
            for a in assessments
        ],
        "degradation_header": (
            "⚠️  PROVENANCE DEGRADED — Some sources are unvetted, expired, or "
            "incomplete. Claims derived from degraded sources carry reduced "
            "confidence. See provenance log for details."
        ) if overall != "clean" else "",
    }


def degradation_header(batch_assessment: dict) -> str:
    """Return the provenance degradation header for agent output, if any.

    Args:
        batch_assessment: Result from assess_batch().

    Returns:
        A warning string to embed in output metadata, or empty string if clean.
    """
    return batch_assessment.get("degradation_header", "")
