"""Compare pipeline predictions with the H1 labels: invoice-level flags, expected totals, per category."""

import csv
from collections import Counter, defaultdict

from .loader import ROOT


def load_labels():
    with open(ROOT / "labels" / "hospital_1_labels.csv") as f:
        return {r["invoice_id"]: r for r in csv.DictReader(f)}


def scored_invoices(invoices):
    """One prediction per invoice_id: the last occurrence (a reused ID's label describes the reuse)."""
    by_id = {}
    for inv in invoices:
        by_id[inv["invoice_id"]] = inv
    return by_id


def compare(invoices, labels=None, verbose=True):
    labels = labels or load_labels()
    preds = scored_invoices(invoices)
    flag = Counter()
    total_ok = Counter()
    cat = defaultdict(Counter)
    misses = defaultdict(list)
    for iid, lab in labels.items():
        inv = preds[iid]
        truth = {c for c in lab["error_categories"].split("|") if c}
        pred = {c for c, _, _ in inv["findings"]}
        flag[(bool(pred), bool(truth))] += 1
        exp_ok = inv["expected_total_cents"] == int(lab["expected_total_cents"])
        total_ok[(bool(truth), exp_ok)] += 1
        for c in truth | pred:
            key = ("tp" if c in truth and c in pred else "fn" if c in truth else "fp")
            cat[c][key] += 1
            if key != "tp":
                misses[(c, key)].append(iid)
        if not exp_ok:
            misses[("expected_total", "wrong")].append(iid)
    tp, fp, fn, tn = flag[(True, True)], flag[(True, False)], flag[(False, True)], flag[(False, False)]
    report = {
        "invoice_flag": dict(tp=tp, fp=fp, fn=fn, tn=tn,
                             precision=tp / max(1, tp + fp), recall=tp / max(1, tp + fn)),
        "expected_total_exact": {
            "erroneous": f"{total_ok[(True, True)]}/{total_ok[(True, True)] + total_ok[(True, False)]}",
            "clean": f"{total_ok[(False, True)]}/{total_ok[(False, True)] + total_ok[(False, False)]}",
        },
        "categories": {c: dict(v) for c, v in sorted(cat.items())},
        "misses": misses,
    }
    if verbose:
        print("invoice flags:", {k: round(v, 3) if isinstance(v, float) else v for k, v in report["invoice_flag"].items()})
        print("expected total exact:", report["expected_total_exact"])
        print(f"{'category':40s} tp  fp  fn")
        for c, v in report["categories"].items():
            print(f"{c:40s}{v.get('tp', 0):3d} {v.get('fp', 0):3d} {v.get('fn', 0):3d}")
    return report
