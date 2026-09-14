# Phase 1 — Understanding the Task and the Problem

_Status: complete (2026-09-13). Everything here comes from reading the package; nothing has been built yet._

## 1. The task in one paragraph

An insurer (Meridian) pays five hospitals, and each hospital has its own contract. Each hospital sends
invoices, and each invoice has line items (service, date, quantity, unit, price). Some invoices break
their contract: wrong price, a missing or wrongly applied adjustment, a quantity over a cap, a duplicate
bill, bad dates or header data. For **hospitals 2–5** we must say, per invoice, whether it is wrong, a
label for what is wrong, what the total *should* be, and how confident we are. Hospital 1 comes with
answers (labels) for development and is not scored.

## 2. What we are given

| Input | Size | Notes |
|---|---|---|
| `contracts/hospital_N/` | 5 contracts, 7 documents | .md and .txt carry identical numbers (verified). PDFs duplicate the md; PDF text extraction garbles numbers (`1.05 1 0.95` → `1.051 0.95`), so **use .md**. |
| `invoices/hospital_N_invoices.jsonl` | 840–1,132 invoices per hospital | Same data as the CSVs, with line items nested. **Better source**: see §6.4. |
| `invoices/*_invoices.csv` / `*_line_items.csv` | ~12.5 lines per invoice | Money is integer cents. Quantities 1–40. |
| `labels/hospital_1_labels.csv` | 913 rows | `invoice_id, is_erroneous, error_categories (pipe-separated), expected_total_cents, ambiguity_sensitive` |
| `submission_template.csv` | header only | `invoice_id, flagged, error_category, expected_total_cents, billed_total_cents, confidence` |

## 3. How we are assessed

- Coverage of all 4 scored hospitals is **not** expected. Doing 2 hospitals well, plus an honest account
  of what was skipped and why, beats a thin pass over all 4.
- **Calibration is measured.** A confident wrong answer costs more than an honest "unsure". A wrongly
  extracted rate spreads to every invoice that uses it.
- Rows for invoices we believe are **clean** are scored too.
- Time cap: **6–8 hours total**. At the cap, stop and write up what would come next.
- The label file has an `ambiguity_sensitive` column. It is 0 for every H1 row, which suggests the scored
  hospitals contain invoices whose correct answer depends on how an ambiguous clause is read.

### Deliverables
1. A runnable repo (README, pinned dependencies) that reproduces `submission.csv`.
2. `submission.csv`.
3. Evaluation report: per-category performance on H1, plus an error analysis grouped by the 3–4
   **failure types** of our approach, with one example each.
4. **Prompts as versioned files**, showing iteration → see `prompts/`.
5. One-page decision log: assumptions, unresolved ambiguities, and what we decided about each.

## 4. The five contracts: same rules, different presentation

All five share the same calculation core (§3.1/3.2 in each): **whole cents, round half-up after every
step**, adjustment order **bundle → facility multiplier → plan-tier multiplier → premium/uplift →
volume discount**, line total = unit rate × quantity, invoice total = sum of line totals.

| Hospital | Scored | Presentation | What is special |
|---|---|---|---|
| **H1** Northgate | no (labelled) | One document, clean tables | The reference. 107 services. |
| **H2** St. Auben | yes | **Prose only, no tables.** ~70 services spread through 800 lines, mixed with filler articles repeated 5× each | Rates and rules sit inside sentences. "Service Day" runs **07:00–06:59** (the data has dates only). New rule: invoice must be submitted **≤ 60 days after discharge** (13.1). Clause 4.2 gives the unit basis as "per hour, per item". |
| **H3** Rivermead | yes | **Three documents**: Base Agreement (rules), Appendix B (rates), Amendment No. 1 | Precedence: amendment > appendix > base. **7 rates change for Service Dates on or after 2025-01-01** (by service date, not invoice date). **2 services only billable from 2025-01-01.** |
| **H4** Calderwood | yes | One document, tables, cross-referenced sections | Closest to H1. Explicit wording on the cap/premium interaction (5.3), cap enforcement across invoices (6.2), and "not applied on the line where the threshold is first crossed" (8.4). Non-business-day uplifts: **none**. |
| **H5** Pelham | yes | Tables + a PDF of the rate tables | **Facility multipliers** (F-MAIN/F-NORTH/F-COAST) and **plan-tier multipliers** per service, so rounding after each step matters. It is the only hospital with more than one facility in its data. |

## 5. The error categories (from H1 labels)

H1: **58 of 913 invoices are wrong (6.4%)**; 40 of those have 2–3 categories at once. Grouped by the
kind of check needed:

| Family | Categories (H1 count) | Needs |
|---|---|---|
| Invoice header | `contract_number_mismatch` (5), `duplicate_invoice_id` (5) | Compare against contract / other invoices |
| Dates | `malformed_service_date` (6), `service_date_after_invoice_date` (5), `service_date_out_of_window` (5) | Parse dates, contract term |
| Arithmetic | `line_total_arithmetic` (6), `invoice_total_mismatch` (6) | Pure arithmetic, no contract needed |
| Service identification | `unknown_service` (12), `wrong_unit_basis` (11) | **Map free-text description → contracted service** |
| Pricing (single line) | `unit_price_mismatch` (10), `premium_omitted` (3), `premium_incorrectly_applied` (6) | Rate + day-of-week/daily aggregate rules |
| Pricing (cross-line / cross-invoice) | `bundle_not_applied` (5), `daily_cap_exceeded` (4), `exclusion_window_violation` (4), `cross_invoice_duplicate` (4), `volume_discount_omitted` (4), `volume_discount_incorrectly_applied` (4) | Patient history across invoices; **running utilisation across all patients over the whole term** |

## 6. What the H1 labels teach us

1. **Clean invoice ⇒ `expected_total == billed_total`** (855/855).
2. **Header/date/identification errors don't change the expected total.** On single-error invoices,
   `contract_number_mismatch`, `duplicate_invoice_id`, `malformed_service_date`,
   `service_date_after_invoice_date`, `service_date_out_of_window`, `unknown_service` and
   `wrong_unit_basis` all have expected == billed. The invoice is flagged, but no amount is re-priced.
3. **Pricing errors do change it**: expected goes down for caps, bundles, duplicates and missing discounts,
   and up for a missing premium.
4. **Duplicate invoice IDs**: two different invoices share one ID. In the CSV their line items get
   merged under that ID. The **JSONL keeps them apart**, and `line_id` encodes the original invoice
   (`H1-L00068-xx` vs `H1-L00155-xx`). The label (one row per ID) describes the **later/reused** invoice.
5. **Descriptions are messy**: abbreviations, word-order changes, noise codes (`/NG-3022`). Some fit more
   than one contracted service: `Visit Amb Hm` could be *Ambulatory Cardiac Home Visit* or *Ambulatory
   Infectious Home Visit*. 474–544 distinct descriptions per hospital.
6. Only ~6% of invoices are wrong, so "flag nothing" is already ~94% accurate. Precision/recall per
   category is what counts.

## 7. Traps and ambiguities found so far (these feed the decision log)

| # | Where | Issue |
|---|---|---|
| A1 | All | **Description → service mapping.** Resolving an ambiguous description by the billed price is circular: if the price is the error, we map to the wrong service and miss it. |
| A2 | H2 4.2, H3 App. B, H4 §3, H5 Table 1 | Unit basis **"per hour, per item"** on one telemetry service each; data has `per_hour_per_item`. Is `per_hour` alone a wrong unit basis? |
| A3 | H2 2.2 / 2.4 | Service Day is 07:00–06:59, but we only have dates. Treat as a calendar day? Business Day = the day the Service Day *starts*. |
| A4 | H2 13.1 | "Submitted ≤ 60 days after discharge": a rule with no H1 category. Flag it, and under what label? |
| A5 | All | Cumulative volume discounts run across **all patients and the whole term**. Do erroneous lines (duplicates, out-of-term, wrong contract, unknown service) count toward utilisation? |
| A6 | H4 5.3 / 6.1 | A premium may be payable on a quantity that is itself capped. Is the premium threshold tested on the billed quantity or the capped one? Is the excess paid at 0? |
| A7 | H4 11.3 → 6.2 | A duplicate service is treated through the daily cap. Remove the duplicate line, or only the excess over the cap? |
| A8 | H4 8.2 | "Applied last … except as provided in 8.3", but 8.3 contains no exception. Read as no exception. |
| A9 | H5 1.2 | Facility multiplier uses the "facility code recorded on a line item", but facility is only on the invoice. Use the invoice's. |
| A10 | H3 A1.3 | Services added from 2025-01-01, billed for earlier dates: `unknown_service` or a date error? |
| A11 | All | Invoices quoting another hospital's contract number: price them under the quoted contract or the hospital's own? (H1 labels: expected == billed, so just flag.) |
| A12 | Duplicates | A daily cap "per Patient per Service Day" across invoices: which invoice gets the excess? Presumably the later one in line-id order. |
| A13 | H2 | Filler articles repeat each sentence 5× in varied wording, which is noise for LLM extraction. The rate clauses are highly templated, so deterministic parsing looks feasible. |

## 8. Questions Phase 2 must answer

1. **Sequencing**: which hospitals first, and which do we explicitly skip?
2. **Architecture**: contract → structured rule table (how: parser, LLM, manual?) → pricing engine →
   checks → submission. How is each extraction verified?
3. **Description mapping**: deterministic (token/abbreviation matching) vs LLM, how ties are handled,
   and how uncertainty flows into `confidence`.
4. **Confidence model**: how to turn check type + mapping certainty + ambiguity exposure into a calibrated number.
5. A decision for each ambiguity A1–A13.

## 9. Common misreadings (checked against the data)

| Tempting reading | What is actually true |
|---|---|
| "Hospital 1 is the clean one" | H1 is **labelled**, not clean: 58 of its 913 invoices are wrong. It is the answer key used to test the checker. Its *contract* is the easiest to read (tables), which is a separate point. |
| "Each contract has different fields" | The **invoice data has identical columns for all 5 hospitals**. The contracts use the **same rule types** and the same calculation order and rounding. They differ in services, rates, which rules apply to which service, presentation, and a few extras (H5 multipliers, H3 dated rate changes, H2 60-day rule and 07:00 Service Day). |
| "The goal is to catch invoices with the wrong amount" | Only partly. In H1, **17 of 58 wrong invoices have the correct money** (bad date, wrong contract number, reused ID, unknown service, wrong unit). They must be flagged too, with expected = billed. |
| "Output is flagged / not flagged" | Each row also needs the expected total, an error label and a **calibrated confidence**. Rows for clean invoices are scored as well. |

## 10. Proposed phases

| Phase | Goal | Output |
|---|---|---|
| 1. Understand | Read everything, list rules, categories, traps | this document |
| 2. Design | Sequencing, architecture, mapping strategy, confidence model, ambiguity decisions | `docs/phase2_design.md`, first decision-log entries |
| 3. Implement | Contract extraction → pricing engine → checks → `submission.csv` | code + tests |
| 4. Evaluate & calibrate | Score on H1, per-category metrics, failure-type analysis, confidence calibration; loops back into 3 | evaluation report |
| 5. Package & write up | README reproduction, pinned deps, decision log, "what I'd do next", prompt log complete | final repo |
