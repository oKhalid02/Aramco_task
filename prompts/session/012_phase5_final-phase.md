# 012 — Phase 5: final phase

- **Date:** 2026-09-14
- **Phase:** 5 (Package & write up)
- **Tool:** Claude Code (Claude Opus 5)
- **Time spent:** ~0.5 h

## Prompt (verbatim)

```
good, do the final phase
```

## What the assistant did

1. Checked the last open facts for the decision log. A4 (60-day rule), A7 (duplicate on a capped service) and A10 (added service before its date) never occur in the data.
2. Wrote `docs/decision_log.md` (deliverable 5): 14 clause ambiguities, 7 label conventions inferred from H1, 7 method decisions, each with the decision and its evidence or effect.
3. Wrote `docs/next_steps.md`: six prioritised follow-ups tied to the four failure types, with effort estimates.
4. Rewrote `README.md` for reviewers: reproduce, deliverables map, how it works, results, repository map, time used (~4.6 h), AI disclosure.
5. Corrected a count repeated in earlier chat summaries: the LLM mapping second opinion covered **556** descriptions (not 555).
6. Committed on a new branch `submission` (not `main`; nothing pushed, because `origin` is the exercise author's repository). Verified that a fresh clone reproduces `submission.csv` byte for byte and passes the tests.
