"""Phase 4, step 1: H1 scorecard and ablation of the fixes made while developing on H1.

Usage: python -m audit.evaluation   -> outputs/evaluation/scorecard.md, ablation.md
"""

import json
from collections import Counter

from .contracts import ROOT
from .engine import HospitalAudit
from .evaluate import compare, load_labels, scored_invoices
from .loader import load

OUT = ROOT / "outputs" / "evaluation"

FIXES = {
    "history_includes_mispresented": ("A wrong-unit line still counts as delivered (bundles, history)", "H1 labels", False),
    "date_root_cause": ("A date past the term end is reported as out of window only", "H1 labels", False),
    "unit_price_unknown_rule": ("Loose match whose unit and price fit nothing -> unknown service", "H1 labels", False),
    "matcher_tie_rule": ("Several services fit a description -> tie (not fewest dropped words)", "LLM second opinion", "fewest_missing"),
    "cumulative_counts": ("Wrong-unit lines count toward volume-discount utilisation", "H3/H5 data majority", "priceable"),
}


def rules_for(h):
    return json.loads((ROOT / "rules" / f"hospital_{h}.json").read_text())


def outcomes(h, readings=None):
    invoices = HospitalAudit(h, rules_for(h), load(h), readings=readings).run()
    by_id = scored_invoices(invoices)
    return invoices, {i: (bool(v["findings"]), v["expected_total_cents"], frozenset(c for c, _, _ in v["findings"]))
                      for i, v in by_id.items()}


def scorecard():
    invoices, _ = outcomes(1)
    labels = load_labels()
    report = compare(invoices, labels, verbose=False)
    by_id = scored_invoices(invoices)
    total_by_cat = Counter()
    exact_by_cat = Counter()
    for iid, lab in labels.items():
        for c in filter(None, lab["error_categories"].split("|")):
            total_by_cat[c] += 1
            exact_by_cat[c] += by_id[iid]["expected_total_cents"] == int(lab["expected_total_cents"])
    rows = ["| Category | Labelled | Found | False alarms | Missed | Precision | Recall | Expected total exact |",
            "|---|---|---|---|---|---|---|---|"]
    for c, v in report["categories"].items():
        tp, fp, fn = v.get("tp", 0), v.get("fp", 0), v.get("fn", 0)
        rows.append(f"| `{c}` | {total_by_cat[c]} | {tp} | {fp} | {fn} | {tp / max(1, tp + fp):.2f} | "
                    f"{tp / max(1, tp + fn):.2f} | {exact_by_cat[c]}/{total_by_cat[c]} |")
    f = report["invoice_flag"]
    head = (f"**Invoice level (H1, 913 invoices):** {f['tp']} erroneous found, {f['fp']} false alarms, {f['fn']} missed, "
            f"{f['tn']} clean confirmed. Expected total exact: erroneous {report['expected_total_exact']['erroneous']}, "
            f"clean {report['expected_total_exact']['clean']}.")
    return head + "\n\n" + "\n".join(rows) + "\n", report


def ablation():
    base_h1 = compare(outcomes(1)[0], verbose=False)
    base_other = {h: outcomes(h)[1] for h in (2, 3, 4, 5)}
    configs = [("Final pipeline", {})]
    configs += [(f"without: {desc}", {key: off}) for key, (desc, _, off) in FIXES.items()]
    configs.append(("First Phase 3 run (all five off)", {key: off for key, (_, _, off) in FIXES.items()}))
    rows = ["| Configuration | Evidence for the fix | H1 false alarms | H1 missed | H1 category errors | "
            "H1 totals wrong | H2–H5 invoices that change | …of which flag flips |",
            "|---|---|---|---|---|---|---|---|"]
    for name, readings in configs:
        r = compare(outcomes(1, readings)[0], verbose=False)
        cat_errors = sum(v.get("fp", 0) + v.get("fn", 0) for v in r["categories"].values())
        wrong_totals = len(r["misses"].get(("expected_total", "wrong"), []))
        changed = flips = 0
        for h in (2, 3, 4, 5):
            other = outcomes(h, readings)[1] if readings else base_other[h]
            for iid, o in other.items():
                if o != base_other[h][iid]:
                    changed += 1
                    flips += o[0] != base_other[h][iid][0]
        evidence = next((ev for key, (desc, ev, _) in FIXES.items() if name.endswith(desc)), "")
        rows.append(f"| {name} | {evidence} | {r['invoice_flag']['fp']} | {r['invoice_flag']['fn']} | {cat_errors} | "
                    f"{wrong_totals} | {changed} | {flips} |")
    return "\n".join(rows) + "\n"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    card, _ = scorecard()
    (OUT / "scorecard.md").write_text(card)
    abl = ablation()
    (OUT / "ablation.md").write_text(abl)
    print(card)
    print(abl)


if __name__ == "__main__":
    main()
