# 002 — Phase 1: check my understanding

- **Date:** 2026-09-13
- **Phase:** 1 (Understand)
- **Tool:** Claude Code (Claude Opus 5)
- **Time spent:** ~0.1 h

## Prompt (verbatim)

```
keep us in phase 1 for now , so what of i understand yet we have 5 hosiptals each have a contract some of them are clean like hospital 1 and there are lables for it and some of them are not like the rest , so the goal is to make the rest hospital like hospital 1 so we can calculate each inovice and make sure its clean and correct. also of what i see each hoisptal have his roles so each contract have diffrent fileds than the other . lastly the main goal of this job is to catch the wrong invoice with wrong amount of money to flag them . is my understanding of the problem right ?
```

## What the assistant did

- Reviewed the user's summary point by point against the data.
- Checked: how many H1 wrong invoices still have the correct money (17 of 58), and whether invoice columns differ between hospitals (they don't; one layout for all 5).
- Added §9 "Common misreadings" to the Phase 1 doc.

## Outputs

- `docs/phase1_task_understanding.md` (added §9)
- `prompts/session/002_phase1_check-understanding.md` (this file)

## Decisions / follow-ups

- Corrections agreed: H1 is *labelled*, not *clean*. Contracts share the same rule types but differ in values and a few extras. Invoice fields are identical across hospitals. Not every error is about money.
- Still in Phase 1; no design work started.
