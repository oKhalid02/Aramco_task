# What I Would Do Next

_Time used: about 4.6 of the 6–8 hour cap (per-prompt estimates in `prompts/session/`). In priority
order, by expected effect on the scored output._

1. **Resolve the daily-cap amount convention (failure type D).** Ask the payer whether excess units are
   paid up to the cap (contract text) or the line reverts to a lower quantity (H1 labels). Affects 28
   submitted amounts. *~0.2 h once answered.*
2. **Price wrong-unit lines under each plausible unit (failure type B).** If no unit reconciles the
   billed price, also report `unit_price_mismatch`. Affects 54 submitted invoices, where a second price
   error would currently go unseen. *~0.5 h, then re-run the stress test.*
3. **Look-alike descriptions (failure type A).** Iterate the mapping prompt to v2: show the billed unit
   and price next to each candidate and ask whether the line can be that service at all, with the
   verdict feeding confidence. Also rank matches by which words were dropped (a missing *specialty* is
   riskier than a missing *service noun*). Target: the 1.2% silent-miss rate. *~1 h including an LLM run.*
4. **Knock-on findings (failure type C).** When a line cannot be dated or identified, mark findings on
   other lines that depend on it (same-day bundle partner, discount threshold) as "consequential"
   rather than independent errors, and lower their confidence. Affects up to 40 submitted invoices.
   *~0.5 h.*
5. **Measure false alarms on H2–H5.** Sample ~50 flagged and ~50 clean invoices across H2–H5 for a
   quick human check, to calibrate the tiers on real data instead of on the development set.
   *~1 h of reviewer time.*
6. **Specific categories for trap errors.** Emit `amendment_rate_misapplied` and `multiplier_mismatch`
   alongside `unit_price_mismatch`, if the scoring taxonomy accepts them.
