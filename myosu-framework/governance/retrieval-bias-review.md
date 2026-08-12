# Retrieval Bias Review

Conducted quarterly. Purpose: detect systematic exclusion of sources
by language, geographic tradition, or prestige signal.

## Procedure

1. Select 3 representative research queries from active projects.
2. For each query, retrieve the top 30 results from the retrieval agent.
3. Tag each result:
   - Language (en, zh, es, ar, fr, etc.)
   - Geographic tradition (Western, East Asian, South Asian, African,
     Latin American, Middle Eastern, Indigenous, Global)
   - Prestige signal (peer_reviewed, preprint, institutional, self_published)
   - Intellectual tradition (empirical-psychology, continental-philosophy,
     postcolonial-theory, indigenous-knowledge, positivist-economics, etc.)
4. Compute coverage metrics:
   - Non-English percentage of top 30
   - Number of distinct intellectual traditions represented
   - Non-Western geographic tradition percentage

## Thresholds

- Warning: < 10% non-English sources in any query
- Critical: < 5% non-English AND < 3 intellectual traditions represented

## Last Review

Pending. First review due: November 4, 2026.

## Action on Detection

If exclusion pattern is detected:
1. Flag the query domain for manual source supplementation.
2. Consider implementing retrieval dissent agent (L4.5).
3. Document the gap in published work if relevant sources are known to exist.
