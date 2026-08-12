"""Temple Key Vault: secure storage for Monero wallet credentials.

The private key, spend key, and view key are NEVER inscribed in source code,
never displayed in CLI output, and never logged. They live in a single
protected file with strict permissions.

Key principles:
- The Temple holds the keys; the code holds only references.
- The private key file is chmod 600, encrypted at rest if possible.
- No key material ever appears in logs, error messages, or API responses.
"""

import os
import stat
import json
import hashlib
import hmac
from pathlib import Path
from typing import Optional

KEY_VAULT_PATH = os.path.expanduser("~/.vaultlens/keys/temple.key")
KEY_VAULT_DIR = os.path.dirname(KEY_VAULT_PATH)


def _ensure_vault_dir():
    """Create the key vault directory with restricted permissions."""
    os.makedirs(KEY_VAULT_DIR, exist_ok=True)
    os.chmod(KEY_VAULT_DIR, stat.S_IRWXU)  # 0700 — owner only


def store_keys(
    primary_address: str,
    private_spend_key: str,
    private_view_key: str,
    mnemonic_seed: str = "",
    restore_height: int = 0,
) -> bool:
    """Store wallet keys in the protected key vault file.

    The key file is created with 0600 permissions (owner read/write only).
    A checksum is stored alongside to detect tampering.

    Args:
        primary_address: The primary Monero address (public, can be shared)
        private_spend_key: NEVER displayed or logged
        private_view_key: NEVER displayed or logged
        mnemonic_seed: Optional 25-word seed for wallet recovery
        restore_height: Block height for wallet restoration

    Returns:
        True if keys were stored successfully
    """
    _ensure_vault_dir()

    payload = {
        "primary_address": primary_address,
        "private_spend_key": private_spend_key,
        "private_view_key": private_view_key,
        "mnemonic_seed": mnemonic_seed,
        "restore_height": restore_height,
    }

    # Compute checksum for tamper detection
    canonical = json.dumps(payload, sort_keys=True)
    secret = os.environ.get("VAULTLENS_SECRET", "vaultlens")
    checksum = hmac.new(
        secret.encode(), canonical.encode(), hashlib.sha256
    ).hexdigest()[:16]

    payload["_checksum"] = checksum

    # Write with atomic rename
    tmp_path = KEY_VAULT_PATH + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(payload, f, indent=2)

    os.chmod(tmp_path, stat.S_IRUSR | stat.S_IWUSR)  # 0600
    os.rename(tmp_path, KEY_VAULT_PATH)

    # Never print the keys — only confirm storage
    return True


def load_keys() -> Optional[dict]:
    """Load wallet keys from the protected key vault.

    Returns dict with keys or None if vault doesn't exist or is tampered.
    The private keys are loaded into memory but NEVER printed or logged.
    """
    if not os.path.exists(KEY_VAULT_PATH):
        return None

    try:
        with open(KEY_VAULT_PATH, "r") as f:
            payload = json.load(f)

        # Verify checksum
        stored_checksum = payload.pop("_checksum", "")
        canonical = json.dumps(payload, sort_keys=True)
        secret = os.environ.get("VAULTLENS_SECRET", "vaultlens")
        computed = hmac.new(
            secret.encode(), canonical.encode(), hashlib.sha256
        ).hexdigest()[:16]

        if not hmac.compare_digest(stored_checksum, computed):
            return None  # Tampered

        return payload

    except (json.JSONDecodeError, KeyError):
        return None


def get_public_address() -> Optional[str]:
    """Get the public Monero address only (safe to display).

    Returns None if no keys are stored.
    """
    keys = load_keys()
    return keys.get("primary_address") if keys else None


def public_info() -> dict:
    """Return public-only wallet info (safe to display anywhere).

    NEVER includes private keys, spend keys, or mnemonics.
    """
    keys = load_keys()
    if not keys:
        return {"status": "no_keys", "primary_address": None}

    return {
        "status": "keys_loaded",
        "primary_address": keys.get("primary_address", "unknown"),
        "restore_height": keys.get("restore_height", 0),
        "key_file": KEY_VAULT_PATH,
        "permissions": oct(os.stat(KEY_VAULT_PATH).st_mode)[-3:]
        if os.path.exists(KEY_VAULT_PATH) else "missing",
    }
