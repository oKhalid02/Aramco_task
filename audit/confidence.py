"""Step 7: turn each invoice's evidence into a confidence and human-review reasons (Phase 2, D4).

Two numbers per invoice:
  confidence         probability the flag is right (flagged=1: really erroneous; flagged=0: really clean).
                     This is the submission's `confidence` column.
  amount_confidence  probability expected_total_cents is right. Equal to `confidence` except where H1 shows the
                     amount itself is unreliable (daily-cap cases). Used for the review queue only.

Each tier's number is a ceiling chosen before looking at the scored hospitals, then checked against H1:
the H1 accuracy of every tier must be at least its number (see `calibration_table`). H1 is the
development set, so its near-perfect accuracy is not used to push confidences higher.
"""

from collections import Counter, defaultdict

MECHANICAL = {
    "contract_number_mismatch", "duplicate_invoice_id", "invoice_total_mismatch", "line_total_arithmetic",
    "malformed_service_date", "service_date_out_of_window", "service_date_after_invoice_date",
}
UNTESTED = {"late_submission", "service_not_yet_contracted"}  # rule types with no H1 example

TIERS = {  # tier -> (confidence, meaning)
    "F1": (0.97, "flagged: at least one mechanical finding (header, dates, arithmetic)"),
    "F2": (0.93, "flagged: pricing/identification finding on a line matched without a tie-break"),
    "F3": (0.80, "flagged: findings rest only on tie-broken or rule-overridden matches"),
    "F4": (0.65, "flagged: only rule types never seen in H1"),
    "F5": (0.60, "flagged: the flag depends on an ambiguous clause's reading"),
    "C1": (0.97, "clean: every line matched without a tie-break"),
    "C2": (0.95, "clean: some line identified by its billed unit (tie-break)"),
    "C3": (0.85, "clean: some line identified by its billed price (its price check is then circular)"),
    "C4": (0.80, "clean: the LLM second opinion disagrees with a line's match"),
    "C5": (0.70, "clean: some line's service could not be resolved, so it was not priced"),
    "C6": (0.60, "clean: an alternative reading of an ambiguous clause would flag it"),
}
AMOUNT_CAP_CONFIDENCE = 0.20  # H1: expected total matched the label in 0/4 daily-cap cases (Laplace (0+1)/(4+2) ≈ 0.17)
REVIEW_BELOW = 0.85  # Phase 2 D4 said "initially 0.70"; 0.85 also queues tie-broken flags and LLM disagreements


def assess(inv):
    """Return (tier, confidence, reasons[]) for one invoice after the engine, sensitivity and LLM passes."""
    cats = {c for c, _, _ in inv["findings"]}
    lines = {li["line_id"]: li for li in inv["line_items"]}
    reasons = []
    for li in inv["line_items"]:
        if li["certainty"] == "ambiguous":
            reasons.append(f"line {li['line_no']}: '{li['description'].strip()}' matches {len(li['candidates'])} services; not priced")
        elif li["certainty"] == "price_tiebreak":
            reasons.append(f"line {li['line_no']}: '{li['description'].strip()}' identified only by its price")
        if li.get("llm_disagrees"):
            reasons.append(f"line {li['line_no']}: LLM second opinion disagrees ({li['llm_disagrees']})")
    if inv.get("sensitive_to"):
        reasons.append("result changes under alternative reading: " + "; ".join(inv["sensitive_to"]))
    if "daily_cap_exceeded" in cats:
        reasons.append("expected total follows the contract (excess over the cap unpaid); H1 labels paid less in 4/4 cap cases")

    if cats:
        if inv.get("sensitive_flag"):
            tier = "F5"
        elif cats & MECHANICAL:
            tier = "F1"
        elif cats <= UNTESTED:
            tier = "F4"
        else:
            supporting = [lines.get(lid) for c, lid, _ in inv["findings"] if c not in UNTESTED]
            weak = all(li is not None and (li["certainty"] in ("unit_tiebreak", "price_tiebreak")
                                           or li.get("rule_override") or li.get("llm_disagrees"))
                       for li in supporting)
            tier = "F3" if weak else "F2"
    else:
        certs = {li["certainty"] for li in inv["line_items"]}
        if inv.get("sensitive_flag"):
            tier = "C6"
        elif "ambiguous" in certs:
            tier = "C5"
        elif any(li.get("llm_disagrees") for li in inv["line_items"]):
            tier = "C4"
        elif "price_tiebreak" in certs:
            tier = "C3"
        elif "unit_tiebreak" in certs:
            tier = "C2"
        else:
            tier = "C1"
    return tier, TIERS[tier][0], reasons


def amount_confidence(inv):
    if any(c == "daily_cap_exceeded" for c, _, _ in inv["findings"]):
        return min(inv["confidence"], AMOUNT_CAP_CONFIDENCE)
    return inv["confidence"]


def review_type(inv):
    flag = inv["confidence"] < REVIEW_BELOW
    amount = inv["amount_confidence"] < REVIEW_BELOW
    return {(True, True): "flag and amount uncertain", (True, False): "flag uncertain",
            (False, True): "amount uncertain"}.get((flag, amount))


def amount_calibration(invoices_by_id, labels):
    """H1: amount confidence groups vs how often expected_total_cents equals the label."""
    stats = defaultdict(Counter)
    for iid, lab in labels.items():
        inv = invoices_by_id[iid]
        group = "cap" if inv["amount_confidence"] < inv["confidence"] else "other"
        stats[group]["n"] += 1
        stats[group]["right"] += inv["expected_total_cents"] == int(lab["expected_total_cents"])
    return dict(stats)


def calibration_table(invoices_by_id, labels):
    """H1: per tier, how many rows and how often the flag was right."""
    stats = defaultdict(Counter)
    for iid, lab in labels.items():
        inv = invoices_by_id[iid]
        right = bool(inv["findings"]) == (lab["is_erroneous"] == "1")
        stats[inv["tier"]]["n"] += 1
        stats[inv["tier"]]["right"] += right
    return {t: (TIERS[t][0], s["n"], s["right"]) for t, s in sorted(stats.items())}
