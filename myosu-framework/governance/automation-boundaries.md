# Automation Boundaries

## Fully Automated
- Retrieval of sources from authorized databases
- Extraction of verbatim quotes with source attribution
- Provenance metadata generation (handoff_chain, timestamps)
- Audit logging (hash-chained, append-only)
- Quarantine decisions for provenance failures
- Firebreak enforcement (agent → /my-thinking/ blocked)
- Epistemic marker validation (threshold marker presence)

## Human-in-the-Loop Required
- Agent synthesis review before vault insertion
- Promotion of agent content to human-author spaces
- Publication approval (pre-publication provenance audit)
- Rehabilitation of quarantined notes
- Classification of dual-use research
- Exception approval and registration
- Retirement of agent roles

## Human-Over-the-Loop (Override)
- Override of any agent-generated claim in the vault
- Correction or removal of claims with full downstream trace
- Resetting interaction profile
- Freezing vault sections from agent retrieval
- Override of review load throttle

## Irreversible Actions (Human Confirmation Required)
- Deletion of vault content
- External communication of research findings
- API writes to external systems
- Export without provenance
- Granting collaborator access
