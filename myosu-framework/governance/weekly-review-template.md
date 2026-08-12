# Weekly Governance Review — {{date:YYYY-MM-DD}}

> Run: `python governance/cli.py weekly` and fill in below.

---

## 1. Authorship Drift

- Drift %: _____ (warning: 25%, critical: 40%)
- Agent synthesis allowed this week: _____
- Promotions allowed this week: _____
- Firebreak attempts blocked: _____
- Status: [ ] OK [ ] WARNING [ ] CRITICAL

**If warning or critical:**
- What % of promotions used ratification mode? _____
- Did I reconstruct, annotate, or compose — or just click "ratify"?
- Action: _____

---

## 2. Review Backlog

- Pending review: _____
- Flagged: _____
- Total backlog: _____ (threshold: 100)
- Status: [ ] OK [ ] OVERLOADED

**If overloaded:**
- Am I approving claims I haven't meaningfully reviewed?
- Action: _____

---

## 3. Quarantine Count

- Total quarantined: _____
- Top reasons:
  - W-002 (missing provenance): _____
  - W-001/W-001b (firebreak violation): _____
  - W-003 (missing threshold marker): _____
  - W-004 (agent assigned stable_finding): _____
  - SYN-004 (agent resolved tension): _____
- Status: [ ] OK [ ] REVIEW NEEDED

**Any quarantined note older than 7 days?** [ ] Yes [ ] No
**If yes:** rehabilitate or delete this week.

---

## 4. Exceptions

- Open exceptions: _____
- Any expiring this week? [ ] Yes [ ] No
- Any undocumented workarounds? [ ] Yes [ ] No

**If undocumented workarounds exist:**
- Document them NOW in `/governance/logs/exceptions.md`
- Action: _____

---

## 5. Quick Sanity Checks

- [ ] Ran `python governance/cli.py test`? All phases pass?
- [ ] Any S1 incidents this week?
- [ ] Any agent behavior change I didn't log?
- [ ] Any new source or dependency I didn't register?
- [ ] Did I read at least one note's full provenance frontmatter this week?

---

## 6. Reflection (one sentence each)

What was the most important thing my agents surfaced this week?

What did they miss that I had to find myself?

Am I still the author of meaning, or am I becoming a curator?

---

## 7. Dashboard Snapshot

```
Provenance integrity:  ___% violation rate
Quarantine count:      ___
Authorship drift:      ___%
Review backlog:        ___
Review load health:    ___
Open exceptions:       ___
Open incidents:        ___
Firebreak status:      ___
```

---

**Signed:** John
**Next review:** {{date+7d:YYYY-MM-DD}}
