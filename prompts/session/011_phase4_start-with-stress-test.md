# 011 — Phase 4: approved plan, include the stress test

- **Date:** 2026-09-14
- **Phase:** 4 (Evaluate & calibrate)
- **Tool:** Claude Code (Claude Opus 5)
- **Time spent:** ~1.0 h

## Prompt (verbatim)

```
this is good plan , and yes include stress test
```

## What the assistant did

1. **Ablation switches** added to `audit/engine.py` / `audit/mapping.py`, one per Phase 3 fix, defaults = final behaviour (tests confirm no output change).
2. **Step 1, scorecard and ablation** (`audit/evaluation.py`): H1 per-category table. The first Phase 3 run already flagged 58/58 with 0 false alarms. All fixes together changed 5 H1 category labels, 1 H1 total, and 20 of 3,942 submitted rows (5 flag flips).
3. **Step 2, stress test** (`audit/stress.py`): 22 planted error types (18 standard, H3 amendment trap, H5 multiplier trap, 2 deliberately hard). 2,040 plants across all five hospitals, 2,024 flagged, 1,840/1,840 standard+trap plants with the right category. A harness bug was found and fixed (a batch could borrow an ID that was itself being replaced). The look-alike type was repeated over 5 seeds: 1.2% silent misses.
4. **Step 3, failure types**, each verified with a concrete replay: (A) look-alike descriptions, (B) a wrong unit hides a price error, (C) knock-on findings from a broken line (INV-H1-000388: malformed date removes a same-day bundle), (D) daily-cap amount convention. Exposure counted in the submission (54 wrong-unit invoices, 40 pattern invoices, of which H1 shows 10/10 genuine, 28 cap invoices).
5. **Step 4, report** `docs/evaluation_report.md`. Every figure was re-derived from the result files before finalising; three draft figures were wrong and corrected (1,673 not 1,613; 400 not 500 plants; 24 not 34 untouched invoices).
6. No H1-specific tuning was done in this phase. `submission.csv` is unchanged.
