# 003 — Phase 2: user proposes LLM extraction of contracts

- **Date:** 2026-09-13
- **Phase:** 2 (Design)
- **Tool:** Claude Code (Claude Opus 5)
- **Time spent:** ~0.2 h

## Prompt (verbatim)

```
thats perfect i got the full picture lets go now to phase 2 , i will suggest a solution and tell how is it if you have other solution tell. this phase to figure out the best solution , so after seeing the contracts i think the best way to solve this is by extracting the data from the contract by LLM and transfer it to something look like the labled table in hoisptal 1 what do you think ?
```

## What the assistant did

- Separated two readings of "like the labelled table": H1's contract tables (rules) vs H1's labels (answers).
- Experiment 1: tested whether H2's prose contract parses with fixed patterns. Result: 76 service clauses, 12 sentence patterns, 100% coverage, 0 leftover sentences.
- Experiment 2: sampled 30 H1 invoice descriptions to see where the fuzziness really is (abbreviations, dropped words, noise codes, look-alike services not in the contract).
- Recommended: deterministic contract parsing; LLM as cross-check for extraction and as the fallback for description → service mapping, with results cached.

## Outputs

- `docs/phase2_design.md` (D1 proposed, pipeline sketch)
- `prompts/session/003_phase2_llm-extraction-proposal.md` (this file)

## Decisions / follow-ups

- D1 is **Proposed**, waiting for the user's agreement.
- Next: D2 sequencing, D3 mapping details, D4 confidence, D5 ambiguity rulings.
