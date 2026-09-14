# Phase 2 — Solution Design

_Status: **closed 2026-09-14** — plan approved by the user; all decisions Agreed (details may be refined in Phase 3/4 and logged in the decision log)._

## Guiding principles (Agreed 2026-09-14)

1. **Exact where exact is possible.** Contracts are read by code parsers and invoices are priced by code.
2. **LLM only where the text is genuinely fuzzy, or as a second opinion.** Its outputs are saved to
   files, so the pipeline reruns without an API key.
3. **Every uncertainty lowers confidence and is visible.** An unsure prediction gets a low confidence
   and goes to a human-review queue with the reason. A confident wrong answer is the worst outcome.
4. **Never pick a service by its billed price** (circular: it hides exactly the errors we are looking for).
5. **One command reproduces `submission.csv`**, with pinned dependencies.

---

## D1. Contract extraction — **Agreed 2026-09-14**

Code parsers produce the rules. An LLM reads the same contracts independently as a cross-check.

Evidence (2026-09-13):
- H1, H3, H4, H5 are Markdown tables, which a table parser reads exactly.
- H2 prose is templated: a regex found **76 service clauses**, and **12 sentence patterns cover 100%**
  of their sentences. No GBP or % figure appears outside those clauses.
- The fuzzy text is in the **invoice descriptions** (`Svc Preop Ent Steril`, `Intens - Nutr Support`,
  look-alikes not in the contract), so that is where the LLM goes (D3).

Rejected: LLM as the primary extractor (silent wrong rates, not reproducible). LLM computing
invoice labels (can't do 60k lines of exact running arithmetic).

## D4. Confidence and human review — **Agreed 2026-09-14**

`confidence` = our probability that the row is right: for `flagged=1`, that the invoice really is wrong;
for `flagged=0`, that it really is clean.

Each invoice collects **evidence signals**:

| Signal | Lowers confidence when… |
|---|---|
| Check type | The error comes from a judgement check (pricing, mapping) rather than a mechanical one (arithmetic, dates, header) |
| Mapping certainty | Any line's description → service match was weak, LLM-resolved, or a tie |
| Extraction status | A service used on the invoice failed the extraction cross-checks (step 3) |
| Ambiguity sensitivity | The verdict or total **changes** under the alternative reading of an ambiguous clause (step 6) |
| Untested feature | The result depends on something H1 can't test (H5 multipliers, H3 amendment, H2 60-day rule) |

**Calibration:** group H1 invoices by their evidence pattern, measure how often we're actually right in
each group, and use that rate as the confidence. Patterns that never occur in H1 get a cautious,
documented cap.

**Human review:** every invoice below a threshold (initially 0.70) goes to `review_queue.csv` with
its reasons (e.g. *"line 4: 'Visit Amb Hm' matches 2 services"*, *"total depends on reading of H4 §5.3"*).

## D2. Sequencing — **Agreed 2026-09-14**

Build and prove the engine on **H1** (labelled) first, then **H4 → H5 → H3 → H2**. Each hospital is
submitted only if its extraction passes step 3. The order puts closest-to-H1 first and most untestable
features last:

| Order | Hospital | Why here |
|---|---|---|
| 1 | H4 | Tables, same features as H1. Lowest risk. |
| 2 | H5 | Tables. Multipliers are mechanical, and the data-majority check can verify them. |
| 3 | H3 | Three documents plus date-switched rates. Small extra logic. |
| 4 | H2 | Parser proven, but the 07:00 Service Day and 60-day rule are unverifiable ambiguities. |

If time runs out, stop at the last completed hospital and write down what the next one needed.

## D3. Description → service mapping — **Agreed 2026-09-14**

Normalise (strip `/NG-xxxx` codes, punctuation, filler nouns) → expand abbreviations (`Preop`,
`Ent`→Otolaryngologic, `Rtn`, `Spclst` …) → match against **that hospital's** service list →
certainty level: `exact` / `strong` / `llm` / `ambiguous` / `none`. Only `ambiguous` and unmatched
descriptions go to the LLM (it chooses from the service list or answers "none"). Answers are cached in
`mappings/hospital_N.csv`. Accuracy is measured on H1, where the labels expose `unknown_service` and
pricing errors.

## D5. Ambiguity rulings — **Agreed approach 2026-09-14**

Each ambiguity A1–A13 gets a **primary reading** (used for the prediction) and an **alternative**
(used only to test sensitivity, step 6). Both go in the decision log.

## D6. How the LLM steps get run — **Agreed 2026-09-14: Option B** (`claude -p` script on the subscription)

**Smoke test (2026-09-14):** the Claude Code v2.1.270 binary bundled with the VS Code extension ran
`claude -p … --output-format json --json-schema …` on the subscription login. It returned
schema-valid output (`"Assisted  Urol Hm Vst"` → *Assisted Urologic Home Visit*, certainty high),
model `claude-opus-5`. **Estimated usage ≈ $0.33 for one tiny call** (client-side estimate, drawn from
subscription limits, not billed): the default Claude Code context is heavy. Implications for Phase 3:
- **Batch**: send all uncertain descriptions of a hospital in one call, not one call per description.
- Replace the default context with our own (`--system-prompt`), and give the model no tools. It only needs to read and answer.
- Pin the model (`--model claude-opus-5`) and record it with every saved output.
- Script locates the binary via `CLAUDE_BIN`, falling back to `claude` on the PATH. Nothing gets installed.

Background:

Facts (checked 2026-09-14, official docs):
- A paid Claude subscription (Pro/Max) **does not include API access**. The Claude API is a separate
  pay-as-you-go product (Claude Console), with no free tier.
- Claude Code's scripted mode (`claude -p`) **does** run on the subscription login. Only `--bare` mode
  requires an API key. Usage counts against the subscription's limits.
- This machine currently has no `ANTHROPIC_API_KEY` and no `claude` command on the PATH (the VS Code extension bundles its own).

| Option | Cost | Re-runnable by others | Notes |
|---|---|---|---|
| **A. Claude Code as the LLM** (steps run in the assistant session, from the versioned prompt files) | Subscription only | From cached outputs | Zero setup |
| **B. Script calling `claude -p`** with the prompt files, `--output-format json --json-schema` | Subscription only | Yes, with Claude Code installed | Needs the CLI installed on the PATH |
| C. Anthropic API (Python SDK) | Pay-as-you-go; likely a few dollars at this volume (estimate) | Yes, with an API key | Cleanest code path, but costs money |

**Proposed:** whichever option runs the LLM, the design stays the same: **versioned prompt files in
`prompts/pipeline/` → outputs saved to committed files → the pipeline reads only the saved files.**
Reviewers reproduce `submission.csv` with no LLM access at all. Start with **B** (a real, repeatable
script on the subscription). Fall back to **A** if installing the CLI costs time. The README
discloses the model, date and prompt version used.

---

## The plan, step by step

| Step | What happens | Output |
|---|---|---|
| 0. Setup | Project layout, pinned dependencies, one run command | `README`, `requirements.txt` |
| 1. Load invoices | Read JSONL (keeps reused IDs apart); parse dates, and keep malformed ones as findings | in-memory invoices |
| 2. Parse contracts | Parsers → common rule format: services (unit, rate, valid dates), caps, premiums, weekend uplifts, bundles, discounts, exclusions, multipliers, invoice rules | `rules/hospital_N.json` |
| 3. Verify extraction | (a) LLM second reader, diffed against the parser; (b) data-majority price check; (c) count checks (e.g. H2 = 76 services). Unresolved services → marked uncertain | `verification/` report |
| 4. Map descriptions | Matcher → LLM for leftovers → cached, each with a certainty level | `mappings/hospital_N.csv` |
| 5. Check invoices | Per hospital, in service-date order (running totals): header → dates → service & unit → arithmetic → pricing (bundle → facility → tier → premium → discount, rounding each step) → caps, exclusions, cross-invoice duplicates | categories + expected total |
| 6. Ambiguity test | Re-run affected invoices under the alternative readings; mark any whose answer changes | ambiguity flags |
| 7. Confidence | Evidence signals → calibrated confidence; low ones → review queue with reasons | `confidence`, `review_queue.csv` |
| 8. Evaluate on H1 | Per-category precision/recall, calibration table, 3–4 failure types with examples; loop back to 4–7 | `docs/evaluation_report.md` |
| 9. Run & write up | Hospitals in D2 order → submission; decision log; "what I'd do next" | `submission.csv`, `docs/decision_log.md` |

## Rough time budget (cap 6–8 h)

| Work | Hours |
|---|---|
| Phases 1–2 (so far ~0.9) | ~1.0 |
| Steps 0–3 (setup, parsers, verification) | ~1.0 |
| Step 4 (mapping) | ~1.0–1.5 |
| Steps 5–7 (engine, ambiguity, confidence) on H1 | ~1.5–2.0 |
| Step 8 (evaluate & fix loop) | ~1.0 |
| Step 9 (other hospitals + write-up) | ~1.0–1.5 |
| **Total** | **~6.5–8.0**, tight, hence the D2 cut-lines |
