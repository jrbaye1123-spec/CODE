# Curation Workflow

> The governed path from raw source to machine-facing output.
> There is exactly one path. If a note cannot travel it, it does not become index-eligible.

---

## The Path

```
1. RAW SOURCE
   ├── safety scan (InjectionScanner)
   ├── source record created (Source Registry)
   └── vault intake

2. VAULT NOTE
   ├── frontmatter created
   ├── provenance_status: incomplete
   └── links to source registry entry

3. CURATION REVIEW
   ├── knowledge engineer reviews
   ├── answers: where, who, when, scope
   └── decision: verify / exception / quarantine / rewrite / delete

4. EPISTEMIC GATE
   ├── curation.gate runs in enforce mode
   ├── parse check → field check → status check → exception check
   └── pass → index admission / fail → block + report

5. INDEX ADMISSION
   ├── note enters machine-facing index
   ├── gate report stored as audit artifact
   └── observability snapshot taken

6. AGENT RETRIEVAL
   ├── agent reads from index (not raw vault)
   ├── provenance level checked at retrieval time
   └── output carries provenance label

7. PROVENANCE-LABELED OUTPUT
   ├── every claim traces to source
   ├── output header carries provenance_level
   └── observability log updated
```

---

## Review Decisions

| Decision | Meaning | Result |
|----------|---------|--------|
| **Verify** | Source and reviewer known; approve | provenance_status: complete |
| **Exception** | Time-boxed use allowed | provenance_status: exception, output degraded |
| **Quarantine** | Not index-eligible | Move out of index path |
| **Rewrite** | Too ungoverned | Needs new source or reconstruction |
| **Delete/Archive** | No longer useful or too risky | Remove from active vault |

---

## Knowledge Engineer Review Questions

For each candidate note:

1. Where did this come from? (trace to source registry)
2. Who approved it? (reviewer attribution)
3. When was it reviewed? (timestamp)
4. What is its scope? (which outputs may use it)
5. Is it index-eligible? (gate decision)

---

## Cadence

| Frequency | Action |
|-----------|--------|
| Per note | Review, decision, gate |
| Daily | Gate health check (observability) |
| Weekly | Exception register review |
| Monthly | Source registry audit |
| Quarterly | Graduation threshold review (eval) |
