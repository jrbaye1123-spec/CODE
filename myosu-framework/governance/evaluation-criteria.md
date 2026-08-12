# Evaluation Criteria

Quality-of-judgment metrics for each agent role.

## Retrieval Agent
- [ ] Source diversity: top-30 results include ≥ 3 intellectual traditions
- [ ] Non-English coverage: ≥ 10% of top-30 are non-English (where relevant)
- [ ] Precision: ≥ 80% of retrieved sources are relevant to query
- [ ] Recall: known key sources appear in top-30

## Extraction Agent
- [ ] Verbatim fidelity: extracted quotes match source text
- [ ] Attribution: every extracted claim links to source locator
- [ ] Confidence accuracy: reported confidence matches actual fidelity

## Contradiction Detection Agent
- [ ] Preservation: contradictions are flagged, not resolved
- [ ] Precision: flagged contradictions are genuine (not false positives)
- [ ] Recall: known contradictory source pairs are detected

## Synthesis Agent
- [ ] Interpretive threshold marker: present on every synthesis output
- [ ] Tension preservation: contradictory inputs produce tension entries
- [ ] Non-resolution: agent does not assign resolution_status="resolved"
- [ ] Epistemic honesty: confidence reflects source quality, not output fluency

## Overall System
- [ ] Authorship drift: < 25% (warning), < 40% (critical)
- [ ] Provenance integrity: violation rate < 5% (warning), < 15% (critical)
- [ ] Review load: backlog < max_pending_items
- [ ] Firebreak integrity: zero unpromoted agent content in /my-thinking/
