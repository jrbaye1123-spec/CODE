# Curation Review Template

> Use this template for each knowledge engineer review decision.

---

## Note

**File:** `[path]`

**Title:** `[title]`

---

## Review Questions

1. **Where did this come from?**
   - Source: `[source-registry-id or URL]`
   - Source type: `[paper / book / internal-spec / synthesis / reference]`

2. **Who approved it?**
   - Reviewer: `@[name]`
   - Reviewed at: `YYYY-MM-DD`

3. **What is its scope?**
   - May be used by: `[triage / contradiction / guardian / all / none]`
   - Constraints: `[e.g., "Technical claims only, not policy authority"]`

4. **Is it index-eligible?**
   - Decision: `[verify / exception / quarantine / rewrite / delete]`
   - If exception: owner, expiry, reason

---

## Decision

| Field | Value |
|-------|-------|
| Decision | |
| provenance_status | |
| provenance_level | |
| reviewer | |
| reviewed_at | |
| exception_owner | (if exception) |
| exception_expires_at | (if exception) |
| exception_reason | (if exception) |

---

## Resulting Frontmatter

```yaml
provenance_status: [complete / exception / incomplete / quarantined]
provenance_level: [verified / exception / degraded / unknown]
source: "[source-registry-id]"
reviewer: "@[name]"
reviewed_at: YYYY-MM-DD
```
