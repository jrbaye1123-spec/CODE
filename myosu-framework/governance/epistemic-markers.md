# Epistemic Markers

All agent outputs must carry explicit epistemic markers visible at
normal reading speed. Markers persist through all downstream processing.

## Required Markers by Origin Type

### Extraction
- `extraction_confidence`: "high" | "medium" | "low"
- Source locator (DOI, URL, page)
- Verbatim quote where available

### Summarization
- `summarization_scope`: "full_document" | "section" | "abstract"
- Source locator
- "This is a summary, not a verbatim extraction"

### Synthesis
- `interpretive_threshold`: true (mandatory)
- `marker_text`: "⚠️ Interpretive Threshold — Beyond this point: agent-generated
  synthesis, inference, and framing. Not direct extraction from sources.
  Treat as provisional reasoning."
- `pattern_confidence`: "high" | "medium" | "low"
- `inference_confidence`: "high" | "medium" | "low" (if inference present)

### Speculation
- `speculation_flag`: true
- `confidence`: ≤ 0.5 enforced at write time
- "This is speculative. No direct evidential anchor."

## Marker Persistence

Epistemic markers must survive:
- Handoff between agents
- Linking and tagging in Obsidian
- Graph view
- Export (or explicit declaration of stripping)
- Downstream synthesis (markers carried forward in input_refs)
