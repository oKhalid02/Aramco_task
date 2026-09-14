# 001 — Phase 1: understand the task

- **Date:** 2026-09-13
- **Phase:** 1 (Understand)
- **Tool:** Claude Code (Claude Opus 5)
- **Time spent:** ~0.5 h (reading + profiling)

## Prompt (verbatim)

```
i have a task i want you to help me with. see this repo https://github.com/majedzahrani3/insurance_auditing .
i read the repo and i understod the main things but yet see it and explain it to me. 
i want to complete this in phases. phase 1 :understand the task and the problem , phase 2: design the solutions , phase 3: implementing the solution. and if you see we have to make more phases thats ok 
lastly see the deliverbales and make sure you are capturing each prompt like this one.
```

## What the assistant did

- Read the README, all 7 contract documents (H2 read with boilerplate filtered out), and the H5 rate-table PDF.
- Checked that .md and .txt contracts carry identical numbers, and that the PDF matches but garbles numbers when extracted.
- Profiled invoices and line items per hospital: counts, contract numbers, facilities, tiers, unit bases, malformed dates, date ranges, distinct descriptions.
- Analysed H1 labels: category counts, how `expected_total_cents` relates to billed per category, and how duplicate invoice IDs behave in CSV vs JSONL.
- Proposed 5 phases (added *Evaluate & calibrate* and *Package & write up*).
- Set up this prompt-logging convention.

## Outputs

- `docs/phase1_task_understanding.md`
- `prompts/README.md`
- `prompts/session/001_phase1_understand-task.md` (this file)

## Decisions / follow-ups

- Use `.md` contracts, not PDFs (PDF extraction corrupts numbers).
- Prefer JSONL over CSV (keeps duplicate-ID invoices apart).
- 13 ambiguities logged (A1–A13 in the Phase 1 doc), to be decided in Phase 2.
