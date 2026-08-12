"""Epistemic Debt Ledger: tracks every refused/suspended/escalated query.

When the Adjudicator blocks an answer, a debt ticket is created.
The Foraging Engine works to resolve these debts through investigation.
"""

import hashlib
import json
import os
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Literal, Optional

DebtTrigger = Literal["refuse", "suspend", "escalate_human", "conflict_unresolved"]
DebtStatus = Literal["open", "investigating", "partially_resolved", "resolved", "unresolvable"]
ForagingStrategy = Literal["scope_bridge", "counterfactual", "socratic", "proposal", "none"]


@dataclass
class EpistemicDebt:
    """A knowledge gap that blocks answer synthesis."""
    debt_id: str
    query_id: str = ""
    query_text: str = ""
    created_at: str = ""
    trigger: DebtTrigger = "refuse"
    conflict_id: Optional[str] = None
    missing_evidence_type: Optional[str] = None
    status: DebtStatus = "open"
    resolution_strategy: Optional[ForagingStrategy] = None
    investigation_notes: list[str] = field(default_factory=list)
    resolved_at: Optional[str] = None
    session_id: str = ""

    def to_dict(self) -> dict:
        return {
            "debt_id": self.debt_id, "query_id": self.query_id,
            "query_text": self.query_text, "created_at": self.created_at,
            "trigger": self.trigger, "conflict_id": self.conflict_id,
            "missing_evidence_type": self.missing_evidence_type,
            "status": self.status, "resolution_strategy": self.resolution_strategy,
            "investigation_notes": self.investigation_notes,
            "resolved_at": self.resolved_at, "session_id": self.session_id,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "EpistemicDebt":
        return cls(**{k: v for k, v in d.items()
                      if k in cls.__dataclass_fields__})


# ── SQLite ledger ──────────────────────────────────────

DEBT_SCHEMA = """
CREATE TABLE IF NOT EXISTS epistemic_debt (
    debt_id TEXT PRIMARY KEY,
    query_id TEXT,
    query_text TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    trigger TEXT NOT NULL,
    conflict_id TEXT,
    missing_evidence_type TEXT,
    status TEXT DEFAULT 'open',
    resolution_strategy TEXT,
    investigation_notes TEXT,
    resolved_at TEXT,
    session_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_debt_status ON epistemic_debt(status);
CREATE INDEX IF NOT EXISTS idx_debt_query ON epistemic_debt(query_id);
"""


class DebtLedger:
    """Persistent ledger of epistemic debt tickets."""

    def __init__(self, db_path: str = ".vaultlens/debt_ledger.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.executescript(DEBT_SCHEMA)
        self.conn.commit()

    def create(self, debt: EpistemicDebt) -> str:
        """Record a new debt. Returns debt_id."""
        if not debt.created_at:
            debt.created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        if not debt.debt_id:
            debt.debt_id = f"debt_{hashlib.sha256(os.urandom(8)).hexdigest()[:8]}"

        self.conn.execute(
            """INSERT OR REPLACE INTO epistemic_debt
               (debt_id, query_id, query_text, created_at, trigger, conflict_id,
                missing_evidence_type, status, resolution_strategy,
                investigation_notes, session_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (debt.debt_id, debt.query_id, debt.query_text, debt.created_at,
             debt.trigger, debt.conflict_id, debt.missing_evidence_type,
             debt.status, debt.resolution_strategy,
             json.dumps(debt.investigation_notes), debt.session_id)
        )
        self.conn.commit()
        return debt.debt_id

    def get(self, debt_id: str) -> Optional[EpistemicDebt]:
        row = self.conn.execute(
            "SELECT * FROM epistemic_debt WHERE debt_id = ?", (debt_id,)
        ).fetchone()
        if not row:
            return None
        return EpistemicDebt(
            debt_id=row[0], query_id=row[1], query_text=row[2],
            created_at=row[3], trigger=row[4], conflict_id=row[5],
            missing_evidence_type=row[6], status=row[7],
            resolution_strategy=row[8],
            investigation_notes=json.loads(row[9] or "[]"),
            resolved_at=row[10], session_id=row[11],
        )

    def list_by_status(self, status: DebtStatus = "open") -> list[EpistemicDebt]:
        rows = self.conn.execute(
            "SELECT * FROM epistemic_debt WHERE status = ? ORDER BY created_at DESC",
            (status,)
        ).fetchall()
        return [EpistemicDebt(
            debt_id=r[0], query_id=r[1], query_text=r[2], created_at=r[3],
            trigger=r[4], conflict_id=r[5], missing_evidence_type=r[6],
            status=r[7], resolution_strategy=r[8],
            investigation_notes=json.loads(r[9] or "[]"),
            resolved_at=r[10], session_id=r[11],
        ) for r in rows]

    def list_all(self) -> list[EpistemicDebt]:
        rows = self.conn.execute(
            "SELECT * FROM epistemic_debt ORDER BY created_at DESC LIMIT 100"
        ).fetchall()
        return [EpistemicDebt(
            debt_id=r[0], query_id=r[1], query_text=r[2], created_at=r[3],
            trigger=r[4], conflict_id=r[5], missing_evidence_type=r[6],
            status=r[7], resolution_strategy=r[8],
            investigation_notes=json.loads(r[9] or "[]"),
            resolved_at=r[10], session_id=r[11],
        ) for r in rows]

    def update_status(self, debt_id: str, status: DebtStatus,
                      notes: list[str] = None,
                      strategy: ForagingStrategy = None) -> None:
        """Update debt status and optionally add investigation notes."""
        existing = self.get(debt_id)
        if not existing:
            return
        if notes:
            existing.investigation_notes.extend(notes)
        if status in ("resolved", "unresolvable") and not existing.resolved_at:
            existing.resolved_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        self.conn.execute(
            """UPDATE epistemic_debt SET status = ?, resolution_strategy = ?,
               investigation_notes = ?, resolved_at = ?
               WHERE debt_id = ?""",
            (status, strategy or existing.resolution_strategy,
             json.dumps(existing.investigation_notes),
             existing.resolved_at, debt_id)
        )
        self.conn.commit()

    def stats(self) -> dict:
        """Return debt statistics."""
        total = self.conn.execute("SELECT COUNT(*) FROM epistemic_debt").fetchone()[0]
        by_status = {}
        for row in self.conn.execute(
            "SELECT status, COUNT(*) FROM epistemic_debt GROUP BY status"
        ):
            by_status[row[0]] = row[1]
        by_trigger = {}
        for row in self.conn.execute(
            "SELECT trigger, COUNT(*) FROM epistemic_debt GROUP BY trigger"
        ):
            by_trigger[row[0]] = row[1]
        return {"total": total, "by_status": by_status, "by_trigger": by_trigger}

    def close(self):
        self.conn.commit()
        self.conn.close()
