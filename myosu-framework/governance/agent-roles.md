# Agent Roles

## Active Agents

| Agent | Role | Capabilities | Forbidden | Risk Tier |
|-------|------|-------------|-----------|-----------|
| retrieval | Retrieval | read_sources, write_source_cache, query_registries | synthesize, promote, export, execute_tools | 1 |
| extraction | Extraction | read_sources, write_agent_extractions, read_agent_extractions, handoff | write_my_thinking, synthesize, promote, export, execute_tools, web_access | 1 |
| summarization | Summarization | read_agent_extractions, write_agent_summaries, handoff | write_my_thinking, synthesize, promote, export | 1 |
| contradiction_detection | Contradiction Detection | read_agent_extractions, read_agent_summaries, write_agent_syntheses | write_my_thinking, promote, export, resolve_tensions | 2 |
| synthesis | Synthesis | read_agent_extractions, read_agent_summaries, read_agent_dissent, write_agent_syntheses | write_my_thinking, promote, export, execute_tools | 2 |
| promotion | Promotion | write_my_thinking, promote, ratify, annotate, reconstruct (human only) | synthesize, execute_tools | 2 |
| human | Human (John) | * (all) | none | 0 |

## Design Consideration: Retrieval Dissent Agent

Role: surface what the main retrieval pipeline excluded. Not yet implemented.
Capabilities: read_source_cache, query_registries, write_agent_dissent
Purpose: flag non-English, low-citation, non-traditional sources that were
ranked below the retrieval threshold. See Requirement 4.5.
