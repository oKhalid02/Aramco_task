# 007 — Phase 3: start implementation

- **Date:** 2026-09-14
- **Phase:** 3 (Implement)
- **Tool:** Claude Code (Claude Opus 5)
- **Time spent:** ~1.5 h active (plus a pause of ~2.5 h waiting for the Claude subscription session limit to reset)

## Prompt (verbatim)

```
thats greate lets start phase 3
```

## What the assistant did

- Closed Phase 2: D2 (order H1 → H4 → H5 → H3 → H2), D3, D4 and the D5 approach marked Agreed.
- Started implementation following the Phase 2 plan (see progress notes below).

## Progress notes

1. **Contracts → rules** (`audit/contracts.py`, `rules/`): a table parser (H1/H3/H4/H5) and a prose sentence-pattern parser (H2). Internal checks: number words vs digits, cap column vs caps section, amendment "old rate" vs Appendix B, every rule names a real service, every H2 sentence understood. 830/830 pass. The one early failure was a bug in the checker itself ("two hundred and forty"), fixed.
2. **LLM second reading of contracts** (`prompts/pipeline/contract_extraction_v1.md`, `audit/llm_extract_contracts.py`): all 5 contracts, **0 differences** from the parser. The diff was proven able to catch planted errors (1-cent rate, multiplier, cap, bundle).
3. **Description matcher** (`audit/mapping.py`): of 194 distinct description tokens, only "Ent" needed a hand-written abbreviation. H1: 11/12 unknown_service found by "no match", 0 false alarms.
4. **Engine** (`audit/engine.py`): first H1 run flagged 58/58 with 0 false alarms. Fixes driven by general rules, not by individual invoices:
   - bundles/history count lines billed in the wrong unit (the service was still delivered);
   - a date past the term end is reported as out of window only;
   - a loose match whose unit AND price fit nothing is an unknown service (all 11 true wrong-unit lines had plausible prices);
   - dropping fewer words is not evidence, so multi-candidate matches are ties (found by the LLM second opinion: "Emer Ortho").
5. **Label finding:** in 4/4 H1 daily-cap cases the labels pay *less* than the cap allows (3, 3, 3, 9 units). This is consistent with the labels keeping the pre-inflation quantity, which is not derivable from the data. Kept the contract reading, added a review reason.
6. **Data-majority check** (`audit/verify.py`): every service in every hospital agrees with our price on ≥96% of lines. Mismatches look like planted traps: H3 amendment rates used for 2024 dates, H5 wrong multipliers, ×2/×½/×3 prices.
7. **Ambiguity sensitivity:** A6 (cap+premium) and A4 (60-day rule) never trigger. Exclusion-window inclusivity is settled by H1 (4/4 cases on the boundary). A5 (which units count toward volume discounts) is live: counting mis-presented lines removes 5 threshold-boundary artefacts in H3/H5, and the contract says "Units … billed". Switched the primary reading; the 5 invoices are marked sensitive (confidence 0.60, review queue).
8. **Confidence tiers** (`audit/confidence.py`): no tier is overconfident on H1. Review threshold moved from 0.70 (D4 "initially") to 0.85. Review queue = 33 rows (5 reading-sensitive, 28 cap-amount cases).
9. **LLM mapping second opinion** (`prompts/pipeline/description_mapping_v1.md`): H1 79/80 agree (the 1 is explained by the unit+price rule), H4 125/125. The H5/H3/H2 run hit the **Claude subscription session limit** (429, "resets 2:10pm"); resumed after the reset. Final: H5 89/89, H3 97/97, H2 165/165 agree. Estimated usage for all LLM steps ≈ $5 of subscription allowance.
10. **Runnable repo:** `python3 -m audit` rebuilds everything in ~4 s from committed files; 12 unittest tests; README rewritten for reviewers (original brief kept at `docs/exercise_brief.md`).
