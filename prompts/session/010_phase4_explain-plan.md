# 010 — Phase 4: explain the plan before starting

- **Date:** 2026-09-14
- **Phase:** 4 (Evaluate & calibrate), planning only
- **Tool:** Claude Code (Claude Opus 5)
- **Time spent:** ~0.1 h

## Prompt (verbatim)

```
before going to phase 4 , explain what you will do in it
```

## What the assistant did

- Explained the Phase 4 plan against deliverable 3 (per-category performance on H1, plus an error analysis of 3–4 systematic failure types with examples).
- Flagged the core difficulty: H1 is near-perfect *because* it was the development set, so it cannot show real failure modes by itself.
- Proposed four steps: (1) H1 scorecard including "first run vs final" to expose what was tuned on H1; (2) a stress test that plants known errors into invoices of every hospital, so detection can be measured where no labels exist; (3) a failure-type analysis; (4) the calibration check and report. Proposed a freeze: no H1-specific tuning from here on.
- Gave a time estimate and asked for approval, including whether to run the stress test.

## Outputs

- `prompts/session/010_phase4_explain-plan.md` (this file). No code changed.

## Decisions / follow-ups

- Waiting for the user's go-ahead on the Phase 4 plan and on the stress test.
