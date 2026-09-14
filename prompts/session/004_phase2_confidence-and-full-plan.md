# 004 — Phase 2: confidence principle and full step-by-step plan

- **Date:** 2026-09-14
- **Phase:** 2 (Design)
- **Tool:** Claude Code (Claude Opus 5)
- **Time spent:** ~0.2 h

## Prompt (verbatim)

```
i think that great idea we extract the data with parser and then validate it with LLM is great idea , but still we want to make sure of one thing its making sure about the outcome becuase if the predication in not sure the confidnce is low it ok to be checked by real person. last thing explain the final sloution to me in step by step format so that i make sure iam ok with the solutin plan
```

## What the assistant did

- Marked D1 (parser extraction + LLM cross-check) as Agreed.
- Turned the user's principle ("unsure → low confidence → human checks it") into D4: evidence signals, calibration on H1, and a `review_queue.csv` with reasons.
- Proposed D2 sequencing (H1 → H4 → H5 → H3 → H2, gated by extraction verification), D3 mapping method, and the D5 approach (primary + alternative reading per ambiguity, with a sensitivity re-run).
- Wrote the full 10-step plan (steps 0–9) and a rough time budget against the 6–8 h cap.

## Outputs

- `docs/phase2_design.md` (rewritten: principles, D1–D5, step-by-step plan, time budget)
- `prompts/session/004_phase2_confidence-and-full-plan.md` (this file)

## Decisions / follow-ups

- Agreed: D1; the D4 principle.
- Waiting for approval: D2 sequencing, D3 mapping, D4 details, D5 approach, overall plan.
- Open question for the user: API key access for the LLM steps (cross-check and mapping fallback).
