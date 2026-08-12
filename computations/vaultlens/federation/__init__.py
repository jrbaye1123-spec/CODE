# VaultLens v0.6 — Federated Multi-Expert Architecture
from .manifest import ExpertManifest, ManifestRegistry, ExpertCapabilities, LegalBoundaries
from .policy import PolicyEngine, PolicyDecision
from .router import FederatedRouter, FederatedQueryPlan, ScoredExpert
from .synthesizer import MultiExpertSynthesizer, ExpertResponseEnvelope, FederatedAnswerEnvelope
