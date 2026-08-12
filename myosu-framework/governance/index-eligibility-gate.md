# Index Eligibility Gate

> **The epistemic supply chain is not a documentation problem. It is a release-blocking control plane between raw vault content and machine-facing legitimacy.**

---

## Pivot

Knowledge engineering is the release gate for machine-facing truth. Stop ungoverned admission now. A small, governed index is safer than a large, plausible one.

---

## Board Rule

**No ungoverned content becomes index-eligible.**

Metric form:

> Index Eligibility Rate = 100%. Any unvetted index entry degrades provenance and pauses dependent workflows.

---

## Exception Process

Gates fail through exceptions, not through ignorance. Delivery pressure will not ask "Should we bypass the gate?" It will ask "Can we make a tiny exception just for this demo, this client, this launch?"

| Step | Rule |
|---|---|
| 1. Request | Someone names the content, the reason, the owner, and the expiry. |
| 2. Classify | Entry is marked `provenance: degraded` or `provenance: exception`. |
| 3. Constrain | Outputs using it must carry degraded provenance and cannot be used for high-stakes actions. |
| 4. Timebox | Exception expires automatically; no permanent ungoverned entries. |
| 5. Audit | Every exception is logged and reviewed by the epistemic control owner. |

Hard rule:

> **Exceptions are allowed. Silent ungoverned index eligibility is not.**

---

## Minimum Viable Gate

If only three things are implemented, implement these:

1. **Quarantine all new raw content by default.**
   New content enters as `raw` or `quarantined`, never directly index-eligible.

2. **Block index ingestion unless `vetted`.**
   The index only accepts entries with complete provenance and approved status.

3. **Pause on violation.**
   If `unvetted_index_count > 0`, flag dependent outputs as `provenance: degraded` and pause the affected workflow.

---

## Architecture

```
raw content → quarantine → vetted → index-eligible → agent readable
                  ↑                          ↓
              exception               provenance: degraded
              (timeboxed,            (pauses workflow)
               audited)
```

The governed path is the default. The ungoverned path is loud, blocked, and expensive to ignore.

---

## Related

- [[index-eligibility-implementation]] — DS Cloud engineering blueprint: bucket policies, index hooks, nightly queries
- [[epistemic-supply-chain]] — Concept note on the knowledge engineer as control point
- [[vault-architecture]] — Vault directory structure and quarantine design
- [[pipeline-spec]] — Agent pipeline specification
- [[retrieval-contract]] — Agent epistemic boundary and input contract
