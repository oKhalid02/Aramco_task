# Decision Log

_Deliverable 5. Assumptions, ambiguities and what was decided. "Effect" says whether the choice changes
any output. Clause references: A-numbers in [phase1_task_understanding.md](phase1_task_understanding.md) §7._

## Ambiguous clauses

| # | Where | Ambiguity | Decision | Evidence / effect |
|---|---|---|---|---|
| A1 | All | Which contracted service a free-text description means | Every token must fit a different word of the service. Ties are broken by billed unit, then billed price (lower confidence). Never pick by price alone. | H1: 12/12 unknown services found. LLM second opinion agreed on all 556 uncertain descriptions except 1, which is explained. Residual risk: failure type A. |
| A2 | H2 4.2, H3, H4, H5 | Unit "per hour, per item" | Only `per_hour_per_item` is correct | **No effect:** those services are always billed that way |
| A3 | H2 2.2/2.4 | Service Day runs 07:00–06:59, but data has dates only | Service Day = the service date; Business Day = its weekday | Unverifiable; no alternative computable |
| A4 | H2 13.1 | Invoice ≤ 60 days after discharge: a rule with no H1 category | Enforced as `late_submission` | **No effect:** no invoice exceeds 60 days |
| A5 | All | Which units count toward cumulative volume discounts ("Units … billed") | All billed lines with a known service and date, including wrong-unit lines. Duplicates excluded. | Counting only correctly-presented lines creates 5 findings exactly at a discount threshold (H3, H5). Those 5 invoices are marked sensitive (confidence 0.60, review). |
| A6 | H4 5.3 | Premium threshold on billed vs capped quantity | Billed quantity | **No effect:** no contract has a service with both a cap and a premium |
| A7 | H4 11.3 → 6.2 | Duplicate service treated as a cap question | Later duplicate is not payable (removed) | **No effect:** no duplicate is on a capped service |
| A8 | H4 8.2 | "Applied last … except as provided in 8.3", but 8.3 states no exception | No exception | Standard order used |
| A9 | H5 1.2 | Facility "recorded on a line item", but facility is only on the invoice | Invoice facility applies to all its lines | Data majority: ≥97% of H5 prices agree |
| A10 | H3 A1.3 | Added services billed before 2025-01-01 | Flag `service_not_yet_contracted` | **No effect:** never occurs |
| A11 | All | Invoice quoting another hospital's contract number | Flag, and price under the hospital's own contract | H1 labels: expected total unchanged |
| A12 | All | Daily cap across several lines or invoices | Excess falls on the later line (line order) | **No effect:** no same-day repeats except duplicates |
| A13 | H2 | Filler articles around the rate clauses | Parse only "In respect of" clauses; check no figure lies outside them | 306/306 parser checks; LLM reading 0 differences |
| — | All | "Within N days" exclusion windows: ≤ N or < N | Inclusive (≤ N) | H1 labels: all 4 exclusion errors are exactly N days apart |

## Label conventions inferred from H1 (and applied to H2–H5)

| Topic | Decision | Evidence |
|---|---|---|
| Expected total for non-money errors (dates, contract number, reused ID, unknown service, wrong unit) | Line kept at billed amount; invoice flagged | H1 single-error invoices: expected = billed |
| **Daily cap amount** | **Contract: pay cap × rate.** The labels pay fewer units (3, 3, 3, 9), likely the pre-error quantity, which isn't in the data. Unresolved. | H1 0/4 amounts. Amount confidence 0.20, "amount uncertain" in the review queue (28 invoices). |
| Reused invoice ID | Row describes the later invoice; read from JSONL (the CSV merges both invoices' lines) | H1 labels |
| Past-term service date | Report `service_date_out_of_window` only, not also "after invoice date" | H1: INV-H1-000179, -000852 |
| Wrong-unit line | Still counts as delivered (bundle partner, history) | H1: INV-H1-000847 |
| Loose match whose unit and price fit nothing | `unknown_service` (not `wrong_unit_basis`) | H1: INV-H1-000236; all 11 true wrong-unit lines had plausible prices |
| Category names | H1 vocabulary. H3 amendment and H5 multiplier errors are reported as `unit_price_mismatch`; the specific cause is in `outputs/predictions_detailed.csv`. | Grader taxonomy unknown |

## Method decisions

| Decision | Reason |
|---|---|
| Contracts parsed by code; LLM used only as an independent second reader | Exact and reproducible. An extraction error would spread silently to every invoice. |
| Sources: `.md` contracts, JSONL invoices | `.md` = `.txt` (verified); PDF text extraction garbles numbers |
| `confidence` = probability the **flag** is right; separate `amount_confidence` in review outputs | The template has one column. Mixing the two made the review queue contradictory (prompt 008). |
| Confidence tiers are fixed ceilings, checked (not fitted) on H1; review threshold 0.85 (plan said 0.70) | H1 is the development set; 0.70 missed tie-broken flags |
| All four scored hospitals submitted | A shared engine, and every contract passed all three verification checks. Order of work was H4 → H5 → H3 → H2. |
| LLM steps via `claude -p` on the subscription; outputs committed | No API key needed to reproduce. The session limit was hit once (2026-09-14) and runs resumed after reset. |
| Pipeline prompts not iterated (both still v1) | v1 contract extraction matched the parser exactly. Failure type A suggests a v2 mapping prompt (see next steps). |
