# 006 — Phase 2: choose option B for the LLM steps

- **Date:** 2026-09-14
- **Phase:** 2 (Design)
- **Tool:** Claude Code (Claude Opus 5)
- **Time spent:** ~0.1 h

## Prompt (verbatim)

```
go with B
```

## What the assistant did

- Found the Claude Code CLI already on the machine, bundled with the VS Code extension (v2.1.270), so nothing was installed.
- Smoke-tested option B from the scratchpad: `claude -p` with `--output-format json --json-schema` on the subscription login. It returned schema-valid output with the correct mapping (`"Assisted  Urol Hm Vst"` → Assisted Urologic Home Visit), model `claude-opus-5`.
- Noted the estimated usage (~$0.33 for one tiny call, from subscription limits). This drove the design implications: batch calls, custom system prompt, no tools, pinned model.
- Marked D6 as Agreed (option B) in the design doc.

## Smoke-test prompt (kept for transparency)

```
Contract services: ["Ambulatory Cardiac Home Visit", "Ambulatory Infectious Home Visit", "Assisted Urologic Home Visit"]. Invoice description: "Assisted  Urol Hm Vst". Which contract service does it refer to? Answer "none" if none fits.
```

Schema: `{"service": string, "certainty": "high"|"medium"|"low"}`

## Outputs

- `docs/phase2_design.md` (D6 → Agreed, with smoke-test results and implications)
- `prompts/session/006_phase2_choose-option-b.md` (this file)

## Decisions / follow-ups

- D6 Agreed: option B.
- Still waiting for approval of the overall plan and the D2 hospital order (4 → 5 → 3 → 2).
