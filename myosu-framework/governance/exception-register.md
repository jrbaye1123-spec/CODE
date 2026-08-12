# Exception Register

> Time-boxed exceptions to the index eligibility gate.
> Exceptions are allowed. Silent ungoverned index eligibility is not.

---

## Active Exceptions

```json
{
  "exceptions": []
}
```

---

## Exception Record Schema

| Field | Required | Description |
|-------|----------|-------------|
| `exception_id` | Yes | Unique identifier |
| `file` | Yes | Path to the excepted note |
| `reason` | Yes | Why the exception is needed |
| `owner` | Yes | @person responsible |
| `requested_at` | Yes | YYYY-MM-DD |
| `expires_at` | Yes | YYYY-MM-DD (hard deadline) |
| `scope` | Yes | What outputs may use this |
| `status` | Yes | active, expired, revoked |
| `reviewed_by` | Yes | @knowledge-engineer |

---

## Hard Rules

1. Every exception has an owner. No anonymous exceptions.
2. Every exception expires. No permanent exceptions.
3. Expired exceptions block the note from the index.
4. Outputs using excepted sources are marked `provenance: degraded`.
5. The exception register is reviewed weekly by the epistemic control owner.
