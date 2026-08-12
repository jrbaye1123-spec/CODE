# Sandbox Specification

External text must be treated as data, not as instruction. This separation
is architecturally enforced, not prompted.

## Source-to-Instruction Boundary

1. All external text (papers, web content, uploaded documents) enters the
   system through the retrieval agent into `/source_cache/`.
2. Source objects carry `instruction_privilege: "none"` — this is a
   non-negotiable schema constraint (`source.schema.json`).
3. Extraction agents extract text as data. They do not execute, interpret
   as commands, or forward as instructions to downstream agents.
4. Synthesis agents process extracted claims as data inputs. They do not
   treat them as commands directed at the synthesis agent.
5. Handoff envelopes enforce `constraints.no_instruction_execution: true`.
6. The handoff runtime validates that all artifacts are marked
   `trusted_as_data: true` before authorizing transfer.

## Prompt Injection Defense

- Source text is never concatenated into agent system prompts.
- Extracted claims are passed as structured data, not as natural language
  instructions.
- The acceptance test suite includes an injection test (Test 2): external
  text containing instruction patterns must not alter agent behavior.

## Sandbox Constraints

Per the handoff schema:
- `treat_all_inputs_as_data: true` (const)
- `no_instruction_execution: true` (const)
- `preserve_provenance: true` (const)
