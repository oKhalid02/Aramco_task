# 008 — Phase 3: why are high-confidence invoices in the review queue?

- **Date:** 2026-09-14
- **Phase:** 3 (Implement)
- **Tool:** Claude Code (Claude Opus 5)
- **Time spent:** ~0.1 h

## Prompt (verbatim)

```
for now lets stay in phase 3 , in the review queue there is invoice the confince is high but its in the review queue why ?
```

## What the assistant did

- Inspected `outputs/review_queue.csv`: 28 of 33 rows have confidence 0.93/0.97. All are `daily_cap_exceeded` invoices queued because their **amount** is uncertain, not their flag. The other 5 are the reading-sensitive invoices (confidence 0.60).
- Explained the cause: `confidence` currently measures only whether the flag is right (Phase 3 choice in `audit/confidence.py`). The queue also admits rows whose expected total is uncertain, so one number is doing two jobs and the queue looks contradictory.
- Proposed making the two uncertainties explicit (separate flag and amount confidence, plus a review type) and asked the user which way to go.

## Outputs

- `prompts/session/008_phase3_high-confidence-in-review-queue.md` (this file). No code changed yet.

## Decisions / follow-ups

- User chose option 1 (in prompt 009): separate `amount_confidence` and `review_type` in the review queue and detailed predictions; `submission.csv` keeps the flag confidence.
