# Index Eligibility Gate — DS Cloud Implementation Doctrine

> **The epistemic supply chain is a binary state machine for knowledge:**
> **State A (Quarantine):** Raw, transformable, not executable.
> **State B (Index):** Vetted, provenance-complete, executable.

Companion to [[index-eligibility-gate]]. This is the engineering specification.

---

## The Three-Item MVG Implementation

### 1. Quarantine by Default

```
DS Cloud bucket policy:
  - Any new .md or .json upload lands with system-tag `status: quarantine`
  - No indexer watches this bucket
  - Separate quarantine bucket from index bucket
```

The raw bucket is write-only from the agent's perspective. The index bucket is read-only. Content crosses the boundary only through the knowledge engineer's explicit approval action.

### 2. Block the Index

```
RAG/index pipeline check:
  - Verify metadata field `epistemic_status = approved` before ingestion
  - If missing: fail loudly
    - Slack/Teams alert: "Ingestion blocked: Missing provenance"
    - Log the block with document ID, timestamp, and reason
  - No silent ingestion. No default approval.
```

The indexer is the enforcement point. It does not guess. It does not warn and continue. It blocks.

### 3. Pause on Violation

```
Nightly query:
  SELECT * FROM index WHERE provenance_level = 'unvetted'

If count > 0:
  - Flip global feature flag
  - Append '⚠️ PROVENANCE DEGRADED' to all output headers
  - Pause dependent workflows (triage, contradiction, guardian)
  - Clear only when count returns to 0 and epistemic control owner signs off
```

The pause is automatic. The unpause requires human sign-off. No silent degradation.

---

## State Machine

```
                    knowledge engineer
                    approval action
                         │
    ┌─────────┐         ▼          ┌──────────┐
    │ RAW     │ ────────────────── │ INDEX    │
    │ bucket  │                    │ bucket   │
    │         │                    │          │
    │ status: │                    │ status:  │
    │ quarant.│                    │ approved │
    └─────────┘                    └──────────┘
         │                              │
         │ exception path               │ violation path
         ▼                              ▼
    ┌─────────┐                    ┌──────────┐
    │ timebox │                    │ PAUSE    │
    │ degraded│                    │ degraded │
    │ provenance                   │ flag on  │
    │ expires │                    │ workflows│
    └─────────┘                    │ halted   │
                                   └──────────┘
```

Only two stable states. Exceptions are transient and visible.

---

## The Unwritten Rule

> **Data is input. Knowledge is approved input. The index must never confuse the two.**

---

## Leadership One-Pager

| Field | Answer |
|-------|--------|
| **The Problem** | Demos look good with dirty data until they break in production. |
| **The Solution** | A hard admission gate. |
| **The Rule** | Index Eligibility Rate = 100%. |
| **The Exception** | Explicit, timeboxed, and visibly degraded. |
| **The Cost** | Zero velocity loss — most cleanup happens during the natural review cycle, not as a panic retrofit. |

---

## Engineering Checklist

- [ ] Separate raw bucket from index bucket in DS Cloud
- [ ] Apply quarantine tag policy on raw bucket upload
- [ ] Implement `epistemic_status` metadata field check in index pipeline
- [ ] Configure Slack/Teams alert on ingestion block
- [ ] Schedule nightly unvetted-index-count query
- [ ] Implement global provenance-degraded feature flag
- [ ] Wire flag to output headers and workflow pause
- [ ] Implement unpause requiring epistemic control owner sign-off
- [ ] Exception request form: content, reason, owner, expiry
- [ ] Exception audit log with review cadence

---

## Related

- [[index-eligibility-gate]] — Operational rules and exception process
- [[epistemic-supply-chain]] — Concept: knowledge engineer as control point
- [[vault-architecture]] — Quarantine directory design
- [[pipeline-spec]] — Agent pipeline with provenance checks
- [[provenance-log-schema]] — degraded provenance flag format
