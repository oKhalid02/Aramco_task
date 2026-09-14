# 005 — Phase 2: is there a free API key with a Claude subscription?

- **Date:** 2026-09-14
- **Phase:** 2 (Design)
- **Tool:** Claude Code (Claude Opus 5)
- **Time spent:** ~0.1 h

## Prompt (verbatim)

```
for the API key iam alredy sub with Claude , there is free api key right ?
```

## What the assistant did

- Checked the official docs instead of answering from memory:
  - Claude support article: paid subscriptions don't include API or Console access; the API is billed separately, pay-as-you-go.
  - Claude Code headless docs: `claude -p` works with the subscription login; only `--bare` mode needs `ANTHROPIC_API_KEY`.
- Checked the machine: no `ANTHROPIC_API_KEY`, no `ant` CLI, no `claude` command on the PATH.
- Added D6 (how the LLM steps get run: options A/B/C) to the design doc.

## Outputs

- `docs/phase2_design.md` (added D6)
- `prompts/session/005_phase2_api-key-question.md` (this file)

## Decisions / follow-ups

- No free API key. Proposed: run the LLM steps on the subscription via a `claude -p` script (B), falling back to this session (A). Outputs are always cached to files, so reviewers need no LLM.
- Still waiting for approval of the overall plan and the D2 hospital order.
