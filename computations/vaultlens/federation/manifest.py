"""Expert Manifest Registry: signed capability declarations for MOE nodes.

Each expert publishes a cryptographically signed manifest describing its
domains, legal boundaries, and endpoints. The Router reads ONLY these
manifests — it never probes underlying data.

Schema: manifest.v1
"""

import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ExpertCapabilities:
    """What an expert can handle."""
    domains: list[str] = field(default_factory=list)
    data_modalities: list[str] = field(default_factory=list)
    timeframe: str = ""
    languages: list[str] = field(default_factory=list)


@dataclass
class LegalBoundaries:
    """Legal constraints on an expert's data."""
    jurisdictions: list[str] = field(default_factory=list)
    classification_max: str = "CONFIDENTIAL"
    anonymization_required: bool = True
    cross_border_export_allowed: bool = False


@dataclass
class ExpertEndpoints:
    """Where to reach this expert (local or remote)."""
    query: str = ""       # URL or local vault_db path
    evidence: str = ""    # URL or local graph path


@dataclass
class ExpertManifest:
    """Signed capability declaration for a single MOE expert."""
    expert_id: str
    public_key: str = ""
    capabilities: ExpertCapabilities = field(default_factory=ExpertCapabilities)
    legal_boundaries: LegalBoundaries = field(default_factory=LegalBoundaries)
    endpoints: ExpertEndpoints = field(default_factory=ExpertEndpoints)
    hmac_signature: str = ""
    created_at: str = ""
    version: str = "manifest.v1"

    def to_dict(self) -> dict:
        return {
            "expert_id": self.expert_id,
            "public_key": self.public_key,
            "capabilities": {
                "domains": self.capabilities.domains,
                "data_modalities": self.capabilities.data_modalities,
                "timeframe": self.capabilities.timeframe,
                "languages": self.capabilities.languages,
            },
            "legal_boundaries": {
                "jurisdictions": self.legal_boundaries.jurisdictions,
                "classification_max": self.legal_boundaries.classification_max,
                "anonymization_required": self.legal_boundaries.anonymization_required,
                "cross_border_export_allowed": self.legal_boundaries.cross_border_export_allowed,
            },
            "endpoints": {
                "query": self.endpoints.query,
                "evidence": self.endpoints.evidence,
            },
            "hmac_manifest_signature": self.hmac_signature,
            "created_at": self.created_at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ExpertManifest":
        caps = d.get("capabilities", {})
        legal = d.get("legal_boundaries", {})
        eps = d.get("endpoints", {})
        return cls(
            expert_id=d.get("expert_id", ""),
            public_key=d.get("public_key", ""),
            capabilities=ExpertCapabilities(
                domains=caps.get("domains", []),
                data_modalities=caps.get("data_modalities", []),
                timeframe=caps.get("timeframe", ""),
                languages=caps.get("languages", []),
            ),
            legal_boundaries=LegalBoundaries(
                jurisdictions=legal.get("jurisdictions", []),
                classification_max=legal.get("classification_max", "CONFIDENTIAL"),
                anonymization_required=legal.get("anonymization_required", True),
                cross_border_export_allowed=legal.get("cross_border_export_allowed", False),
            ),
            endpoints=ExpertEndpoints(
                query=eps.get("query", ""),
                evidence=eps.get("evidence", ""),
            ),
            hmac_signature=d.get("hmac_manifest_signature", ""),
            created_at=d.get("created_at", ""),
            version=d.get("version", "manifest.v1"),
        )

    def sign(self, secret: str = "") -> str:
        """Sign the manifest with HMAC-SHA256."""
        canonical = json.dumps({
            "expert_id": self.expert_id,
            "capabilities": {
                "domains": sorted(self.capabilities.domains),
                "data_modalities": sorted(self.capabilities.data_modalities),
                "timeframe": self.capabilities.timeframe,
                "languages": sorted(self.capabilities.languages),
            },
            "legal_boundaries": {
                "jurisdictions": sorted(self.legal_boundaries.jurisdictions),
                "classification_max": self.legal_boundaries.classification_max,
            },
            "version": self.version,
        }, sort_keys=True)
        self.hmac_signature = hmac.new(
            (secret or os.environ.get("VAULTLENS_SECRET", "vaultlens")).encode(),
            canonical.encode(), hashlib.sha256
        ).hexdigest()[:32]
        return self.hmac_signature

    def verify(self, secret: str = "") -> bool:
        """Verify the manifest signature."""
        stored = self.hmac_signature
        computed = self.sign(secret)
        return hmac.compare_digest(stored, computed)


class ManifestRegistry:
    """Local registry of signed expert manifests.

    In production, this would be a distributed registry with JWT/Ed25519.
    For MVP: local JSON files + HMAC verification.
    """

    def __init__(self, registry_dir: str = ".vaultlens/experts/"):
        self.registry_dir = registry_dir
        self._manifests: dict[str, ExpertManifest] = {}
        self._loaded = False

    def register(self, manifest: ExpertManifest, secret: str = "") -> None:
        """Register a signed expert manifest."""
        manifest.sign(secret)
        self._manifests[manifest.expert_id] = manifest
        self._persist(manifest)

    def get(self, expert_id: str) -> Optional[ExpertManifest]:
        """Get a manifest by expert ID."""
        self._ensure_loaded()
        return self._manifests.get(expert_id)

    def get_all(self) -> list[ExpertManifest]:
        """Get all registered manifests."""
        self._ensure_loaded()
        return list(self._manifests.values())

    def find_by_domain(self, domain: str) -> list[ExpertManifest]:
        """Find experts covering a specific domain."""
        self._ensure_loaded()
        return [m for m in self._manifests.values()
                if domain.lower() in [d.lower() for d in m.capabilities.domains]]

    def find_by_jurisdiction(self, jurisdiction: str) -> list[ExpertManifest]:
        """Find experts in a specific legal jurisdiction."""
        self._ensure_loaded()
        return [m for m in self._manifests.values()
                if jurisdiction in m.legal_boundaries.jurisdictions]

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        os.makedirs(self.registry_dir, exist_ok=True)
        for fname in os.listdir(self.registry_dir):
            if fname.endswith(".manifest.json"):
                try:
                    with open(os.path.join(self.registry_dir, fname)) as f:
                        m = ExpertManifest.from_dict(json.load(f))
                        self._manifests[m.expert_id] = m
                except (json.JSONDecodeError, KeyError):
                    pass
        self._loaded = True

    def _persist(self, manifest: ExpertManifest) -> None:
        os.makedirs(self.registry_dir, exist_ok=True)
        fname = f"{manifest.expert_id}.manifest.json"
        with open(os.path.join(self.registry_dir, fname), "w") as f:
            json.dump(manifest.to_dict(), f, indent=2)
