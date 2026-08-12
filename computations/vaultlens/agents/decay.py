"""Epistemic Decay Engine: time-based confidence degradation for graph edges.

Knowledge has a half-life. Heuristic edges decay quickly. High-evidence,
peer-reviewed edges decay slowly. The decay engine applies temporal decay
and flags edges that need re-verification.

Key invariant: decay never drops an edge below its floor confidence.
Nullification requires explicit human action.
"""

import sqlite3
import time
from dataclasses import dataclass
from typing import Optional


# ── Decay configuration ────────────────────────────────

@dataclass
class DecayConfig:
    """Configuration for epistemic decay."""
    # Half-lives in days
    heuristic_half_life: int = 90          # Auto-extracted edges decay fast
    low_evidence_half_life: int = 180      # Low-confidence edges
    medium_evidence_half_life: int = 365   # Standard edges
    high_evidence_half_life: int = 1825    # High-confidence, well-evidenced (5 years)

    # Thresholds
    provisional_threshold: float = 0.4     # Below this → provisional
    review_threshold: float = 0.5          # Below this → needs review
    active_threshold: float = 0.6          # Minimum for active status

    # Floor (never drop below this from decay alone)
    absolute_floor: float = 0.1

    # Evidence count tiers
    high_evidence_min: int = 4             # 4+ pieces of evidence → high half-life
    medium_evidence_min: int = 2           # 2-3 pieces → medium half-life
    low_evidence_max: int = 1              # 0-1 pieces → low half-life


# ── Decay function ─────────────────────────────────────

def calculate_decay(confidence: float, evidence_count: int,
                    created_days_ago: float,
                    is_heuristic: bool = False,
                    config: DecayConfig = None) -> tuple[float, str]:
    """Calculate decayed confidence for an edge.

    Args:
        confidence: Original confidence (0-1)
        evidence_count: Number of supporting evidence items
        created_days_ago: Days since edge was created or last reinforced
        is_heuristic: Whether edge was auto-extracted (faster decay)
        config: Decay configuration

    Returns:
        (decayed_confidence, status_flag)
    """
    cfg = config or DecayConfig()

    # Select half-life based on evidence strength
    if is_heuristic:
        half_life = cfg.heuristic_half_life
    elif evidence_count >= cfg.high_evidence_min:
        half_life = cfg.high_evidence_half_life
    elif evidence_count >= cfg.medium_evidence_min:
        half_life = cfg.medium_evidence_half_life
    else:
        half_life = cfg.low_evidence_half_life

    # Decay formula: confidence * (0.5 ^ (days / half_life))
    if half_life <= 0:
        decayed = confidence
    else:
        decay_factor = 0.5 ** (created_days_ago / half_life)
        decayed = confidence * decay_factor

    # Apply floor
    decayed = max(decayed, cfg.absolute_floor)

    # Determine status flag
    if decayed < cfg.provisional_threshold:
        status = "provisional"
    elif decayed < cfg.review_threshold:
        status = "needs_review"
    elif decayed < cfg.active_threshold:
        status = "active_low"
    else:
        status = "active"

    return round(decayed, 4), status


# ── Decay application ──────────────────────────────────

class DecayEngine:
    """Applies temporal decay to graph edges in batch."""

    def __init__(self, db_path: str, config: DecayConfig = None):
        self.db_path = db_path
        self.config = config or DecayConfig()

    def apply_decay(self, dry_run: bool = False) -> dict:
        """Apply decay to all edges in the vault.

        Args:
            dry_run: If True, only report what would change (no writes)

        Returns:
            Dict with decay statistics
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        now = time.time()
        SECONDS_PER_DAY = 86400

        # Check if status column exists (added in v0.9)
        has_status = False
        try:
            conn.execute("SELECT status FROM edges LIMIT 1")
            has_status = True
        except sqlite3.OperationalError:
            pass

        if has_status:
            edges = conn.execute("""
                SELECT edge_id, confidence, relation, variant, source,
                       created_at, resolved
                FROM edges
                WHERE resolved = 1 AND (status IS NULL OR status NOT IN ('nullified', 'retracted'))
            """).fetchall()
        else:
            edges = conn.execute("""
                SELECT edge_id, confidence, relation, variant, source,
                       created_at, resolved
                FROM edges
                WHERE resolved = 1
            """).fetchall()

        stats = {
            "total_edges": len(edges),
            "decayed": 0,
            "unchanged": 0,
            "provisional": 0,
            "needs_review": 0,
            "details": [],
        }

        for edge in edges:
            eid = edge["edge_id"]
            confidence = edge["confidence"] or 1.0
            source = edge["source"] or "explicit"
            created_at = edge["created_at"] or ""

            # Parse creation date
            try:
                created_dt = None
                for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
                    try:
                        created_dt = time.mktime(time.strptime(created_at[:19], fmt))
                        break
                    except (ValueError, TypeError):
                        continue
                if created_dt is None:
                    created_dt = now - (365 * SECONDS_PER_DAY)  # Default: 1 year ago
            except Exception:
                created_dt = now - (365 * SECONDS_PER_DAY)

            created_days_ago = (now - created_dt) / SECONDS_PER_DAY

            # Estimate evidence count from source type
            is_heuristic = source in ("heuristic", "approved_jsonl", "approved_sidecar")
            evidence_count = 1 if is_heuristic else 3  # Rough estimate

            new_conf, status = calculate_decay(
                confidence, evidence_count, created_days_ago, is_heuristic, self.config
            )

            if new_conf < confidence:
                stats["decayed"] += 1
                detail = (
                    f"Edge {eid}: {confidence:.2f} → {new_conf:.2f} "
                    f"({created_days_ago:.0f} days, {status})"
                )
                stats["details"].append(detail)

                if status == "provisional":
                    stats["provisional"] += 1
                elif status == "needs_review":
                    stats["needs_review"] += 1

                if not dry_run:
                    conn.execute(
                        "UPDATE edges SET confidence = ?, status = ? WHERE edge_id = ?",
                        (new_conf, status, eid)
                    )
            else:
                stats["unchanged"] += 1

        if not dry_run:
            conn.commit()

        conn.close()
        return stats


# ── Edge reinforcement ─────────────────────────────────

def reinforce_edge(db_path: str, edge_id: str, boost: float = 0.1,
                   max_confidence: float = 1.0) -> bool:
    """Reinforce an edge: reset its decay clock and boost confidence.

    Called when a human reviews and confirms an edge.
    """
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT confidence FROM edges WHERE edge_id = ?", (edge_id,)
    ).fetchone()

    if not row:
        conn.close()
        return False

    new_conf = min(row[0] + boost, max_confidence)
    conn.execute(
        """UPDATE edges SET confidence = ?, status = 'active',
           created_at = datetime('now')
           WHERE edge_id = ?""",
        (new_conf, edge_id)
    )
    conn.commit()
    conn.close()
    return True
