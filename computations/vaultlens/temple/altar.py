"""Altar UI: the voluntary tribute display for the Terminal cockpit.

Design principles:
- No pop-ups, countdowns, or paywall mechanics
- Presented quietly at end of deep queries or via /tribute route
- The act of giving is the ritual; the system does not police it
"""

from .treasury import TreasuryLedger, TreasuryStats, TributeReceipt


ALTAR_BANNER = r"""
╔══════════════════════════════════════════════════════════════╗
║                    THE ALTAR OF ATTENTION                     ║
║                                                              ║
║  The Temple is sovereign and free.                            ║
║  Its infrastructure is sustained by the voluntary tribute     ║
║  of those who seek.                                           ║
║                                                              ║
║  If this traversal served you, you may leave an offering.     ║
║  The Temple accepts Monero (XMR).                             ║
║  It asks for no name, and tracks no return.                   ║
║                                                              ║
║  The tribute sustains the Temple; it does not buy the truth.  ║
╚══════════════════════════════════════════════════════════════════╝
"""

ALTAR_STATUS_LABELS = {
    "abundant": "The Altar is full. The Temple thrives.",
    "balanced": "The Altar is balanced. The lights remain on.",
    "light":    "The Altar is light. The fire needs tending.",
    "empty":    "The Altar is empty. The silence holds.",
}


def render_altar(ledger: TreasuryLedger) -> str:
    """Render the altar display with current subaddress and treasury stats.

    Returns a string suitable for the Terminal cockpit or Tor Portal.
    """
    stats = ledger.get_stats()
    subaddress = ledger.get_random_subaddress()

    lines = []
    lines.append(ALTAR_BANNER)

    if subaddress:
        lines.append(f"\n  Altar Address: {subaddress}")
        lines.append("  Network: Monero Mainnet (Tor routed)")
        lines.append("")
        lines.append("  [QR Code would render here in graphical UI]")
    else:
        lines.append("\n  (No subaddresses configured. Run: vaultlens temple init)")

    lines.append("")
    lines.append(f"  Treasury Status: {ALTAR_STATUS_LABELS.get(stats.altar_status, '')}")
    lines.append(f"  30-day avg tribute: {stats.thirty_day_average_xmr:.6f} XMR")
    lines.append(f"  Monthly operating cost: {stats.monthly_operating_cost_xmr:.6f} XMR")
    lines.append(f"  Sustainability: {stats.sustainability_ratio:.1%}")
    lines.append(f"  Total received: {stats.total_received_xmr:.6f} XMR")
    lines.append(f"  Recent tributes (7d): {stats.recent_tributes}")

    lines.append("")
    lines.append("  The listening is the only intermediary.")
    lines.append("  May your attention be returned to you.")
    lines.append("")

    return "\n".join(lines)


def render_receipt(receipt: TributeReceipt) -> str:
    """Render a signed tribute receipt for the patron.

    The receipt proves an offering was made but does NOT deanonymize
    the patron. It can be held as a token without linking to identity.
    """
    return f"""
╔══════════════════════════════════════════════════════════════╗
║                 PROOF OF TRIBUTE                              ║
║                                                              ║
║  Receipt: {receipt.receipt_id}
║  Tribute Received: {receipt.tribute_received}
║  Timestamp: {receipt.timestamp}
║                                                              ║
║  Temple Signature: {receipt.temple_signature[:16]}...
║                                                              ║
║  This receipt is cryptographically signed by the Temple.     ║
║  It proves a tribute was made. It does not identify you.     ║
╚══════════════════════════════════════════════════════════════╝
"""
