"""End-to-end run: rules -> engine -> ambiguity sensitivity -> LLM second opinion -> confidence -> outputs.

Reads only committed files (contracts, invoices, rules, saved LLM outputs); never calls an LLM.
"""

import csv
import json
from collections import Counter

from .confidence import TIERS, amount_calibration, amount_confidence, assess, calibration_table, review_type
from .contracts import ROOT, write_all
from .engine import HospitalAudit
from .evaluate import compare, load_labels, scored_invoices
from .loader import load

SCORED = [4, 5, 3, 2]  # Phase 2, D2 order
ALTERNATIVE_READINGS = {
    # name -> readings. Exclusion-window inclusivity is not tested: H1 labels settle it (4/4 on the boundary).
    "A5: only correctly-presented units count toward volume discounts": {"cumulative_counts": "priceable"},
    "A6: premium threshold tested on the capped quantity": {"premium_threshold_on": "capped"},
    "A4: no 60-day submission rule": {"deadline_rule": False},
}


def outcome(inv):
    return bool(inv["findings"]), inv["expected_total_cents"], frozenset(c for c, _, _ in inv["findings"])


def attach_llm_opinion(hospital, invoices):
    path = ROOT / "mappings" / f"llm_hospital_{hospital}.json"
    if not path.exists():
        return False
    opinions = {r["description"]: r for r in json.loads(path.read_text())["output"]["results"]}
    for inv in invoices:
        for li in inv["line_items"]:
            op = opinions.get(li["description"])
            if op is None or li["certainty"] == "exact":
                continue
            if li["certainty"] == "none":
                if op["verdict"] != "none" and li.get("rule_override"):
                    continue  # text-only opinion vs our unit+price evidence: explained, not a disagreement
                agrees = op["verdict"] == "none"
            elif li["certainty"] == "strong":
                agrees = op["verdict"] == "match" and op["service"] == li["service"]
            elif li["certainty"] == "ambiguous":
                agrees = op["verdict"] == "ambiguous"
            else:  # tie-broken: the text alone is expected to be ambiguous, or to name our choice
                agrees = (op["verdict"] == "ambiguous" and set(li["candidates"]) <= set(op["candidates"]) | {li["service"]}) \
                    or (op["verdict"] == "match" and op["service"] == li["service"])
            if not agrees:
                li["llm_disagrees"] = f"LLM: {op['verdict']} {op['service'] or op['candidates']}"
    return True


def run_hospital(hospital):
    rules = json.loads((ROOT / "rules" / f"hospital_{hospital}.json").read_text())
    invoices = HospitalAudit(hospital, rules, load(hospital)).run()
    for inv in invoices:
        for li in inv["line_items"]:
            li["rule_override"] = li["certainty"] == "none" and bool(li["candidates"])
    base = {id(inv): outcome(inv) for inv in invoices}
    for name, readings in ALTERNATIVE_READINGS.items():
        alt = HospitalAudit(hospital, rules, load(hospital), readings=readings).run()
        for inv, other in zip(invoices, alt):
            if outcome(other) != base[id(inv)]:
                inv.setdefault("sensitive_to", []).append(name)
                inv["sensitive_flag"] = inv.get("sensitive_flag") or outcome(other)[0] != base[id(inv)][0]
    has_llm = attach_llm_opinion(hospital, invoices)
    for inv in invoices:
        inv["tier"], inv["confidence"], inv["reasons"] = assess(inv)
        inv["amount_confidence"] = amount_confidence(inv)
        inv["review_type"] = review_type(inv)
        inv["llm_opinion"] = has_llm
    return invoices


def row(inv):
    cats = []
    for c, _, _ in inv["findings"]:
        if c not in cats:
            cats.append(c)
    return {
        "invoice_id": inv["invoice_id"],
        "flagged": 1 if cats else 0,
        "error_category": "|".join(cats),
        "expected_total_cents": inv["expected_total_cents"],
        "billed_total_cents": inv["invoice_total_cents"],
        "confidence": f"{inv['confidence']:.2f}",
    }


def main():
    write_all()
    out = ROOT / "outputs"
    out.mkdir(exist_ok=True)
    submission, review, details = [], [], []
    for h in [1] + SCORED:
        invoices = run_hospital(h)
        by_id = scored_invoices(invoices)
        for iid, inv in by_id.items():
            r = row(inv)
            extra = {"amount_confidence": f"{inv['amount_confidence']:.2f}", "review_type": inv["review_type"] or ""}
            details.append({"hospital": f"H{h}", **r, **extra, "tier": inv["tier"], "llm_mapping_opinion": inv["llm_opinion"],
                            "findings": "; ".join(f"{c}@{lid or 'invoice'}: {d}" for c, lid, d in inv["findings"]),
                            "reasons": " | ".join(inv["reasons"])})
            if h != 1:
                submission.append(r)
                if inv["review_type"]:
                    review.append({"hospital": f"H{h}", **r, **extra, "why_review": " | ".join(inv["reasons"]) or TIERS[inv["tier"]][1],
                                   "findings": details[-1]["findings"]})
        tiers = Counter(inv["tier"] for inv in by_id.values())
        print(f"H{h}: {len(by_id)} invoices, flagged {sum(1 for i in by_id.values() if i['findings'])}, tiers {dict(sorted(tiers.items()))}")
        if h == 1:
            labels = load_labels()
            compare(invoices, labels)
            print("calibration on H1 (tier: stated confidence, rows, flag right):")
            for t, (conf, n, right) in calibration_table(by_id, labels).items():
                print(f"   {t} {conf:.2f}  n={n:4d}  right={right / n:.3f}  {'OK' if right / n >= conf else 'OVERCONFIDENT'}")
            print("amount on H1 (group: rows, expected total exact):",
                  {g: f"{s['right']}/{s['n']}" for g, s in amount_calibration(by_id, labels).items()})

    fields = ["invoice_id", "flagged", "error_category", "expected_total_cents", "billed_total_cents", "confidence"]
    with open(ROOT / "submission.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(submission)
    with open(out / "review_queue.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["hospital"] + fields + ["amount_confidence", "review_type", "why_review", "findings"])
        w.writeheader()
        w.writerows(sorted(review, key=lambda r: (r["review_type"], float(r["confidence"]), float(r["amount_confidence"]))))
    with open(out / "predictions_detailed.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["hospital"] + fields + ["amount_confidence", "review_type", "tier", "llm_mapping_opinion", "findings", "reasons"])
        w.writeheader()
        w.writerows(details)
    print(f"submission.csv: {len(submission)} rows; outputs/review_queue.csv: {len(review)} rows")


if __name__ == "__main__":
    main()
