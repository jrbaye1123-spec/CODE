"""Vault curation — validates notes against structural AND epistemic indexing criteria.

Per Nullresearch strategy, a note is eligible for the agent-facing index only when:
(a) It has a date of last substantive revision
(b) It has at least one link to another indexed note or cited external source
(c) It has an explicit author attribution

PIVOT: Epistemic supply chain control. Structural criteria are necessary but
insufficient. A note must also pass epistemic admission before becoming
machine-facing. The knowledge engineer is the admission authority — not
support staff, but the named epistemic control point at the choke point
between raw vault content and the machine-facing index.

The risk is not "wrong answers." The risk is false legitimacy: ungoverned
content becoming index-eligible, appearing auditable, then being trusted
in execution. No content enters the index without governed source,
recorded derivation path, explicit admission approval, and machine-readable
provenance status.

Epistemic criteria (gated AFTER structural pass):
(d) Governed source or approved exception
(e) Recorded transformation or derivation path
(f) Explicit epistemic review with admission approval
(g) Machine-readable provenance status
(h) Clear escalation path if provenance is incomplete

The decision of what qualifies is made by a human knowledge engineer, not
the agent. This module provides tooling to assist that human decision and
enforces the hard gate at index build time."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
import json
import re
import frontmatter


@dataclass
class CurationResult:
    """Result of evaluating a note against curation criteria."""

    note_path: str
    title: str
    passes: bool

    # Structural criteria
    has_revision_date: bool = False
    revision_date: Optional[str] = None
    has_links: bool = False
    link_count: int = 0
    links: list[str] = field(default_factory=list)
    has_author: bool = False
    author: Optional[str] = None

    # Epistemic criteria (PIVOT: supply chain admission control)
    source_classification: str = "unknown"  # "governed", "derived", "quarantined", "unknown"
    has_derivation_path: bool = False
    derivation_path: Optional[str] = None  # What was this derived from, by whom, when
    epistemic_reviewed: bool = False
    admission_authority: Optional[str] = None  # Named knowledge engineer who approved
    admission_timestamp: Optional[str] = None
    provenance_status: str = "unknown"  # "verified", "degraded", "unknown"
    escalation_owner: Optional[str] = None  # Who is escalated to if provenance is incomplete

    # Shared
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class VaultCurator:
    """Tooling to assist the human knowledge engineer in curating the vault index.

    This does NOT make curation decisions — it surfaces the data so the 
    knowledge engineer can decide. The tool flags eligibility, the human confirms.
    """

    # Common frontmatter fields
    DATE_FIELDS = ["date", "last_revised", "updated", "modified", "revision_date", "last_modified"]
    AUTHOR_FIELDS = ["author", "authors", "attribution", "contributor", "created_by", "creator"]
    LINK_PATTERNS = [
        r"\[\[([^\]]+)\]\]",  # Wiki-style [[link]]
        r"\[([^\]]+)\]\(([^)]+)\)",  # Markdown [text](url)
        r"https?://[^\s\)]+",  # Raw URLs (excluding closing parens)
        r"@[a-zA-Z0-9_/-]+",  # @mentions/references
        r"#\^[a-zA-Z0-9]+",  # Block references
    ]

    # Patterns that suggest a note is a draft, not a finished artifact
    DRAFT_MARKERS = [
        r"(?i)\b(draft|wip|todo|stub|placeholder|incomplete|unfinished|work.?in.?progress)\b",
        r"(?i)\b(tbd|tbc|coming.?soon|needs.?work|rough.?notes?|brain.?dump)\b",
        r"^#+\s*(draft|wip|todo)",
    ]

    def evaluate_note(self, note_path: str | Path) -> CurationResult:
        """Evaluate a single note against the three curation criteria.

        Args:
            note_path: Path to a markdown note file.

        Returns:
            CurationResult with pass/fail and detailed criteria breakdown.
        """
        note_path = Path(note_path)
        if not note_path.exists():
            return CurationResult(
                note_path=str(note_path),
                title=note_path.stem,
                passes=False,
                failures=[f"File not found: {note_path}"],
            )

        content = note_path.read_text(encoding="utf-8", errors="replace")
        result = CurationResult(note_path=str(note_path), title=note_path.stem, passes=True)

        # Parse frontmatter if present
        try:
            post = frontmatter.loads(content)
            metadata = post.metadata or {}
            body = post.content
        except Exception:
            metadata = {}
            body = content

        # Criterion (a): Date of last substantive revision
        date_found = None
        for field in self.DATE_FIELDS:
            if field in metadata and metadata[field]:
                date_found = str(metadata[field])
                break

        if date_found:
            result.has_revision_date = True
            result.revision_date = date_found
        else:
            result.has_revision_date = False
            result.passes = False
            result.failures.append(
                "Missing revision date — no date/last_revised/updated field in frontmatter"
            )

        # Criterion (b): At least one link to another note or cited external source
        all_links = []
        for pattern in self.LINK_PATTERNS:
            matches = re.findall(pattern, body)
            if pattern == r"\[([^\]]+)\]\(([^)]+)\)":
                all_links.extend([m[1] for m in matches])
            else:
                all_links.extend(matches)

        # Filter out self-references and anchors
        note_name = note_path.stem
        all_links = [
            link for link in all_links
            if note_name.lower() not in link.lower()
            and not link.startswith("#")  # In-page anchors
        ]

        if all_links:
            result.has_links = True
            result.link_count = len(all_links)
            result.links = all_links[:20]  # Cap for display
        else:
            result.has_links = False
            result.passes = False
            result.failures.append("No links to other notes or external sources found")

        # Criterion (c): Explicit author attribution
        author_found = None
        for field in self.AUTHOR_FIELDS:
            if field in metadata and metadata[field]:
                author_found = str(metadata[field])
                break

        if author_found:
            result.has_author = True
            result.author = author_found
        else:
            result.has_author = False
            result.passes = False
            result.failures.append("Missing author attribution in frontmatter")

        # Warnings — draft markers present even if criteria pass
        for pattern in self.DRAFT_MARKERS:
            if re.search(pattern, body):
                result.warnings.append(f"Draft marker detected: {pattern}")
                break

        return result

    def evaluate_directory(
        self, vault_path: str | Path, file_pattern: str = "*.md"
    ) -> list[CurationResult]:
        """Evaluate all notes in a directory against curation criteria.

        Args:
            vault_path: Root of the vault or notes directory.
            file_pattern: Glob pattern for note files.

        Returns:
            List of CurationResults, sorted by pass/fail.
        """
        vault_path = Path(vault_path)
        results = []
        for note_file in sorted(vault_path.rglob(file_pattern)):
            result = self.evaluate_note(note_file)
            results.append(result)

        results.sort(key=lambda r: (not r.passes, r.title.lower()))
        return results

    def build_index(self, vault_path: str | Path, output_path: str = "data/vault_index/index.json") -> dict:
        """Build the machine-facing vault index from curated notes.

        HARD GATE: A note must pass BOTH structural criteria (date, links,
        author) AND epistemic admission (governed source, derivation path,
        epistemic review, provenance status). Only notes with
        provenance_status == "verified" are admitted to the index.

        If any previously-indexed entry is found with provenance_status: unknown
        or provenance_status: degraded, the build is PAUSED and the escalation
        owner is flagged. This is a release-blocking control, not a warning.

        Returns summary statistics about the index build.
        """
        all_results = self.evaluate_directory(vault_path)

        # Structural pass
        structurally_eligible = [r for r in all_results if r.passes]
        structurally_ineligible = [r for r in all_results if not r.passes]

        # Epistemic pass (hard gate)
        epistemically_eligible = [
            r for r in structurally_eligible
            if r.provenance_status == "verified"
            and r.source_classification in ("governed", "derived")
            and r.epistemic_reviewed
        ]
        epistemically_blocked = [
            r for r in structurally_eligible
            if r not in epistemically_eligible
        ]

        # Detect false legitimacy: entries that would have entered the old index
        degraded_entries = [
            r for r in epistemically_blocked
            if r.provenance_status in ("degraded", "unknown")
        ]
        if degraded_entries:
            # PIVOT: Hard stop. Do not build index. Escalate.
            escalation_targets = list(set(
                r.escalation_owner for r in degraded_entries if r.escalation_owner
            ))
            return {
                "build_status": "BLOCKED — EPISTEMIC GATE FAILED",
                "total_notes_scanned": len(all_results),
                "structurally_eligible": len(structurally_eligible),
                "epistemically_eligible": 0,
                "epistemically_blocked": len(epistemically_blocked),
                "degraded_entries": [
                    {
                        "path": r.note_path,
                        "title": r.title,
                        "provenance_status": r.provenance_status,
                        "source_classification": r.source_classification,
                        "escalation_owner": r.escalation_owner,
                    }
                    for r in degraded_entries
                ],
                "escalation_targets": escalation_targets,
                "index_path": None,
                "failures_by_reason": self._summarize_failures(
                    structurally_ineligible + epistemically_blocked
                ),
                "governance_action": (
                    "Index build paused. All dependent outputs flagged as "
                    "provenance: degraded. Epistemic control owner escalated. "
                    "Resolve degraded entries before rebuild."
                ),
            }

        # Build index from verified entries only
        index_entries = []
        for note in epistemically_eligible:
            index_entries.append({
                "path": note.note_path,
                "title": note.title,
                "author": note.author,
                "last_revised": note.revision_date,
                "link_count": note.link_count,
                "links": note.links[:10],
                "source_classification": note.source_classification,
                "derivation_path": note.derivation_path,
                "admission_authority": note.admission_authority,
                "admission_timestamp": note.admission_timestamp,
                "provenance_status": note.provenance_status,
            })

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(index_entries, indent=2, ensure_ascii=False))

        return {
            "build_status": "PASSED — EPISTEMIC GATE CLEARED",
            "total_notes_scanned": len(all_results),
            "structurally_eligible": len(structurally_eligible),
            "epistemically_eligible": len(epistemically_eligible),
            "epistemically_blocked": len(epistemically_blocked),
            "index_path": str(output.resolve()),
            "failures_by_reason": self._summarize_failures(
                structurally_ineligible + epistemically_blocked
            ),
        }

    def _summarize_failures(self, ineligible: list[CurationResult]) -> dict:
        """Summarize why notes failed curation (structural + epistemic)."""
        reasons = {
            "missing_date": 0, "missing_links": 0, "missing_author": 0,
            "multiple_structural": 0,
            # Epistemic failure reasons
            "ungoverned_source": 0, "missing_derivation": 0,
            "not_reviewed": 0, "provenance_unknown": 0,
            "provenance_degraded": 0,
        }
        for note in ineligible:
            # Structural
            has_date = note.has_revision_date
            has_links = note.has_links
            has_author = note.has_author
            structural_fail = 0
            if not has_date:
                structural_fail += 1
            if not has_links:
                structural_fail += 1
            if not has_author:
                structural_fail += 1

            if structural_fail >= 2:
                reasons["multiple_structural"] += 1
            elif structural_fail == 1:
                if not has_date:
                    reasons["missing_date"] += 1
                if not has_links:
                    reasons["missing_links"] += 1
                if not has_author:
                    reasons["missing_author"] += 1

            # Epistemic (only count if structural passed)
            if structural_fail == 0:
                if note.source_classification not in ("governed", "derived"):
                    reasons["ungoverned_source"] += 1
                if not note.has_derivation_path:
                    reasons["missing_derivation"] += 1
                if not note.epistemic_reviewed:
                    reasons["not_reviewed"] += 1
                if note.provenance_status == "unknown":
                    reasons["provenance_unknown"] += 1
                if note.provenance_status == "degraded":
                    reasons["provenance_degraded"] += 1

        return reasons
