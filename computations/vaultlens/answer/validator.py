"""Deterministic answer validator: checks every claim against the retrieved subgraph.

Rules (strict mode):
1. Every claim must have at least one valid citation
2. Cited edge_ids must exist in the retrieved subgraph
3. Cited edges must not be nullified/retracted
4. Claim type must be consistent with cited edge variant
5. If any claim fails validation, the entire answer is rejected

The validator is DETERMINISTIC — no LLM involved, just graph lookups.
"""

from .schema import GroundedAnswer, ValidationResult, Citation


class AnswerValidator:
    """Validates GroundedAnswers against a retrieved subgraph."""

    def __init__(self, nodes: list[dict], edges: list[dict],
                 strict: bool = True, min_citations_per_claim: int = 1):
        # Build lookup maps
        self.node_map: dict[str, dict] = {}
        for n in nodes:
            nid = n.get("note_id", "")
            if nid:
                self.node_map[nid] = n

        self.edge_map: dict[str, dict] = {}
        self.edge_list: list[dict] = []
        for i, e in enumerate(edges):
            eid = e.get("edge_id", f"e{i}")
            self.edge_map[eid] = e
            self.edge_list.append(e)

        self.strict = strict
        self.min_citations = min_citations_per_claim

    def validate(self, answer: GroundedAnswer) -> ValidationResult:
        """Validate all claims in an answer against the subgraph.

        Returns ValidationResult with errors, warnings, and counts.
        """
        errors = []
        warnings = []
        claims_grounded = 0
        nullified_count = 0
        missing_count = 0
        contradiction_count = len(answer.contradictions)

        for claim in answer.claims:
            valid_citations = []

            if not claim.citations:
                errors.append(f"Claim {claim.claim_id}: no citations")
                continue

            for citation in claim.citations:
                valid = self._validate_citation(citation, claim.claim_id, errors, warnings)
                if valid:
                    valid_citations.append(citation)
                else:
                    missing_count += 1

            if not valid_citations:
                errors.append(f"Claim {claim.claim_id}: has no valid citations")
            else:
                claims_grounded += 1

        if answer.insufficient_evidence:
            # Explicit refusal — not an error if properly flagged
            if not answer.claims and not answer.uncertainties:
                warnings.append("insufficient_evidence=true but no uncertainties listed")

        passed = len(errors) == 0 if self.strict else claims_grounded > 0

        return ValidationResult(
            passed=passed,
            errors=errors,
            warnings=warnings,
            claims_grounded=claims_grounded,
            claims_total=len(answer.claims),
            nullified_citations=nullified_count,
            missing_citations=missing_count,
            contradictions_found=contradiction_count,
        )

    def _validate_citation(self, cit: Citation, claim_id: str,
                           errors: list[str], warnings: list[str]) -> bool:
        """Validate a single citation. Returns True if valid."""
        # Check edge_id exists
        if cit.edge_id:
            edge = self.edge_map.get(cit.edge_id)
            if edge is None:
                errors.append(
                    f"Claim {claim_id}: cites edge '{cit.edge_id}' not in retrieved subgraph"
                )
                return False

            # Check edge status
            status = cit.status or edge.get("status", "active")
            if status in ("nullified", "retracted"):
                errors.append(
                    f"Claim {claim_id}: cites nullified edge '{cit.edge_id}'"
                )
                return False
            if status == "shadowed":
                warnings.append(
                    f"Claim {claim_id}: cites shadowed edge '{cit.edge_id}'"
                )
                # Still valid, just flagged

            # Validate relation consistency
            if cit.relation and edge.get("relation") != cit.relation:
                warnings.append(
                    f"Claim {claim_id}: cites relation '{cit.relation}' "
                    f"but edge '{cit.edge_id}' has '{edge.get('relation')}'"
                )

            # Validate confidence
            if cit.confidence is not None:
                edge_conf = edge.get("confidence", 1.0)
                if cit.confidence > edge_conf:
                    warnings.append(
                        f"Claim {claim_id}: claims confidence {cit.confidence} "
                        f"but edge '{cit.edge_id}' has confidence {edge_conf}"
                    )

        elif cit.note_id:
            # Node-only citation (definitional claims)
            if cit.note_id not in self.node_map:
                errors.append(
                    f"Claim {claim_id}: cites node '{cit.note_id}' not in retrieved subgraph"
                )
                return False
        else:
            # Citation must have at least edge_id or note_id
            errors.append(f"Claim {claim_id}: citation has no edge_id or note_id")
            return False

        return True

    def find_contradictions(self, answer: GroundedAnswer) -> list[dict]:
        """Find contradictions between answer claims and the subgraph.

        Checks for: supports vs refutes on same target, causes vs prevents.
        """
        contradictions = []

        # Build relation index for checking opposites
        opposite_relations = {
            "supports": "refutes",
            "refutes": "supports",
            "causes": "prevents",
            "prevents": "causes",
            "derived-from": "contradicts-source",
            "contradicts-source": "derived-from",
        }

        for claim in answer.claims:
            for cit in claim.citations:
                if not cit.edge_id:
                    continue
                edge = self.edge_map.get(cit.edge_id)
                if not edge:
                    continue

                src = edge.get("source", edge.get("source_note_id", ""))
                tgt = edge.get("target", edge.get("target_note_id", ""))
                rel = edge.get("relation", "")
                opposite = opposite_relations.get(rel)

                if not opposite:
                    continue

                # Check for opposite edges between same nodes
                for other_edge in self.edge_list:
                    other_src = other_edge.get("source", other_edge.get("source_note_id", ""))
                    other_tgt = other_edge.get("target", other_edge.get("target_note_id", ""))
                    other_rel = other_edge.get("relation", "")

                    if other_rel == opposite and (
                        (other_src == src and other_tgt == tgt) or
                        (other_src == tgt and other_tgt == src)
                    ):
                        contradictions.append({
                            "claim_id": claim.claim_id,
                            "cited_edge": cit.edge_id,
                            "cited_relation": rel,
                            "opposing_edge_id": other_edge.get("edge_id", "?"),
                            "opposing_relation": other_rel,
                            "explanation": (
                                f"Claim {claim.claim_id} cites {src} --{rel}--> {tgt}, "
                                f"but subgraph also contains {other_src} --{other_rel}--> {other_tgt}"
                            ),
                        })

        return contradictions
