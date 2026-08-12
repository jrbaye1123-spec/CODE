"""Treasury Ledger: privacy-preserving tribute accounting for the Sovereign Node.

Design principles:
- No surveillance: the system never links a transaction to a user session
- No turnstile: tribute is voluntary, the gate remains open
- Monero-native: subaddresses, ring signatures, stealth addresses
- Internal only: the ledger tracks operational costs, never user identity

The tribute sustains the Temple; it does not buy the truth.
"""

import hashlib
import hmac
import json
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional


# ── Schema ─────────────────────────────────────────────

TREASURY_SCHEMA = """
CREATE TABLE IF NOT EXISTS treasury (
    tx_hash TEXT PRIMARY KEY,
    subaddress_index INTEGER,
    amount_atomic BIGINT,
    block_height INTEGER,
    received_at TIMESTAMP DEFAULT (datetime('now')),
    confirmations INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS tribute_receipts (
    receipt_id TEXT PRIMARY KEY,
    tx_hash TEXT,
    issued_at TIMESTAMP DEFAULT (datetime('now')),
    temple_signature TEXT,
    FOREIGN KEY (tx_hash) REFERENCES treasury(tx_hash)
);

CREATE TABLE IF NOT EXISTS operational_costs (
    cost_id TEXT PRIMARY KEY,
    category TEXT,
    description TEXT,
    amount_xmr REAL,
    recorded_at TIMESTAMP DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS subaddress_pool (
    address_index INTEGER PRIMARY KEY,
    subaddress TEXT UNIQUE,
    label TEXT,
    created_at TIMESTAMP DEFAULT (datetime('now')),
    active INTEGER DEFAULT 1
);
"""


# ── Data classes ────────────────────────────────────────

@dataclass
class TributeReceipt:
    """A one-time signed receipt proving tribute was received.

    The receipt proves an offering was made but does NOT reveal which
    user made the payment. Even the Temple cannot deanonymize Monero
    transactions due to stealth addresses and ring signatures.
    """
    receipt_id: str
    tx_hash: str
    tribute_received: bool = True
    timestamp: str = ""
    temple_signature: str = ""

    def to_dict(self) -> dict:
        return {
            "receipt_id": self.receipt_id,
            "tx_hash": self.tx_hash,
            "tribute_received": self.tribute_received,
            "timestamp": self.timestamp,
            "temple_signature": self.temple_signature,
        }

    def sign(self, secret: str = "") -> str:
        """Sign the receipt with HMAC-SHA256."""
        secret = secret or os.environ.get("VAULTLENS_SECRET", "vaultlens")
        canonical = json.dumps({
            "receipt_id": self.receipt_id,
            "tx_hash": self.tx_hash,
            "timestamp": self.timestamp,
        }, sort_keys=True)
        self.temple_signature = hmac.new(
            secret.encode(), canonical.encode(), hashlib.sha256
        ).hexdigest()[:32]
        return self.temple_signature


@dataclass
class TreasuryStats:
    """Aggregated treasury metrics for the Dashboard."""
    total_received_xmr: float
    pending_xmr: float
    thirty_day_average_xmr: float
    monthly_operating_cost_xmr: float
    sustainability_ratio: float
    altar_status: str          # 'abundant', 'balanced', 'light', 'empty'
    recent_tributes: int
    oldest_pending_hours: float


class TreasuryLedger:
    """Privacy-preserving tribute accounting system."""

    def __init__(self, db_path: str = ".vaultlens/treasury.db",
                 secret: Optional[str] = None):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.executescript(TREASURY_SCHEMA)
        self.conn.commit()
        self.secret = secret

    # ── Transaction recording ──────────────────────────

    def record_tribute(self, tx_hash: str, subaddress_index: int,
                       amount_atomic: int, block_height: int) -> TributeReceipt:
        """Record a received tribute transaction.

        Called by the monero-wallet-rpc listener when a transaction is
        detected. Does NOT link to any user session.
        """
        self.conn.execute(
            """INSERT OR REPLACE INTO treasury
               (tx_hash, subaddress_index, amount_atomic, block_height, status)
               VALUES (?, ?, ?, ?, 'confirmed')""",
            (tx_hash, subaddress_index, amount_atomic, block_height)
        )
        self.conn.commit()

        # Generate receipt
        receipt_id = f"rcpt_{hashlib.sha256((tx_hash + str(uuid.uuid4())).encode()).hexdigest()[:12]}"
        receipt = TributeReceipt(
            receipt_id=receipt_id,
            tx_hash=tx_hash,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )
        receipt.sign(self.secret)

        self.conn.execute(
            "INSERT INTO tribute_receipts (receipt_id, tx_hash, temple_signature) "
            "VALUES (?, ?, ?)",
            (receipt_id, tx_hash, receipt.temple_signature)
        )
        self.conn.commit()

        return receipt

    # ── Subaddress pool ────────────────────────────────

    def get_random_subaddress(self) -> Optional[str]:
        """Return a random active subaddress for the altar display.

        Does NOT track which user receives which subaddress.
        """
        rows = self.conn.execute(
            "SELECT subaddress FROM subaddress_pool WHERE active = 1 "
            "ORDER BY RANDOM() LIMIT 1"
        ).fetchone()
        return rows[0] if rows else None

    def add_subaddress(self, address: str, label: str = "") -> int:
        """Add a new subaddress to the pool."""
        idx = self.conn.execute(
            "SELECT COALESCE(MAX(address_index), -1) + 1 FROM subaddress_pool"
        ).fetchone()[0]
        self.conn.execute(
            "INSERT INTO subaddress_pool (address_index, subaddress, label) "
            "VALUES (?, ?, ?)",
            (idx, address, label or f"altar-{idx}")
        )
        self.conn.commit()
        return idx

    # ── Cost recording ─────────────────────────────────

    def record_cost(self, category: str, description: str,
                    amount_xmr: float) -> None:
        """Record an operational cost for sustainability tracking."""
        cost_id = f"cost_{uuid.uuid4().hex[:8]}"
        self.conn.execute(
            "INSERT INTO operational_costs (cost_id, category, description, "
            "amount_xmr) VALUES (?, ?, ?, ?)",
            (cost_id, category, description, amount_xmr)
        )
        self.conn.commit()

    # ── Treasury statistics ────────────────────────────

    def get_stats(self) -> TreasuryStats:
        """Compute treasury metrics for the Dashboard."""
        XMR_ATOMIC = 1e12

        total = self.conn.execute(
            "SELECT COALESCE(SUM(amount_atomic), 0) FROM treasury "
            "WHERE status = 'confirmed'"
        ).fetchone()[0] / XMR_ATOMIC

        pending = self.conn.execute(
            "SELECT COALESCE(SUM(amount_atomic), 0) FROM treasury "
            "WHERE status = 'pending'"
        ).fetchone()[0] / XMR_ATOMIC

        thirty_day = self.conn.execute(
            "SELECT COALESCE(SUM(amount_atomic), 0) FROM treasury "
            "WHERE status = 'confirmed' AND received_at >= datetime('now', '-30 days')"
        ).fetchone()[0] / XMR_ATOMIC / 30.0

        monthly_cost = self.conn.execute(
            "SELECT COALESCE(SUM(amount_xmr), 0) FROM operational_costs "
            "WHERE recorded_at >= datetime('now', '-30 days')"
        ).fetchone()[0]

        recent = self.conn.execute(
            "SELECT COUNT(*) FROM treasury "
            "WHERE received_at >= datetime('now', '-7 days')"
        ).fetchone()[0]

        sustainability = (thirty_day * 30) / max(monthly_cost, 0.0001)
        if sustainability >= 1.5:
            status = "abundant"
        elif sustainability >= 1.0:
            status = "balanced"
        elif sustainability >= 0.3:
            status = "light"
        else:
            status = "empty"

        return TreasuryStats(
            total_received_xmr=round(total, 6),
            pending_xmr=round(pending, 6),
            thirty_day_average_xmr=round(thirty_day, 6),
            monthly_operating_cost_xmr=round(monthly_cost, 6),
            sustainability_ratio=round(sustainability, 2),
            altar_status=status,
            recent_tributes=recent,
            oldest_pending_hours=0.0,
        )

    def close(self):
        self.conn.commit()
        self.conn.close()
