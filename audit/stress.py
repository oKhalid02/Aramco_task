"""Phase 4, step 2: stress test by planting known errors into invoices the pipeline currently rates clean.

For every hospital and error type, up to N clean invoices (distinct patients) receive one planted error
each. All plants of one type go into one fresh copy of the hospital's data, the full engine runs, and
we record: flagged? right category? right expected total? side effects on untouched invoices?
Planted prices are derived from the engine's own price calculation, so they are exactly what a
hospital would bill if it made that specific mistake.

Usage: python -m audit.stress   -> outputs/evaluation/stress_results.csv, stress_summary.md
"""

import copy
import csv
import datetime
import json
import random
from collections import Counter, defaultdict

from .confidence import assess
from .contracts import ROOT
from .engine import HospitalAudit
from .evaluate import load_labels, scored_invoices
from .loader import load, parse_date
from .money import apply_discount, apply_uplift

OUT = ROOT / "outputs" / "evaluation"
PER_TYPE = 20
SEED = 20260914
UNITS = ["per_hour", "per_visit", "per_day", "per_night", "per_procedure", "per_item", "per_unit_dispensed", "per_test"]
PRICE_FACTORS = [0.5, 0.75, 1.25, 1.5, 1.75, 2, 3]  # the ratios seen in H1's labelled unit_price_mismatch lines


class Planter:
    def __init__(self, hospital, rng):
        self.h, self.rng = hospital, rng
        self.rules = json.loads((ROOT / "rules" / f"hospital_{hospital}.json").read_text())
        self.base_audit = HospitalAudit(hospital, self.rules, load(hospital))
        self.base = self.base_audit.run()
        self.by_day = self.base_audit._by_day_cache
        labels = load_labels() if hospital == 1 else None
        reused = Counter(inv["invoice_id"] for inv in self.base)
        self.clean = [inv for inv in self.base
                      if not inv["findings"] and reused[inv["invoice_id"]] == 1
                      and all(li["priceable"] and not li.get("duplicate_of") for li in inv["line_items"])
                      and (labels is None or labels[inv["invoice_id"]]["is_erroneous"] == "0")]
        self.other_contracts = [json.loads((ROOT / "rules" / f"hospital_{o}.json").read_text())
                                for o in range(1, 6) if o != hospital]

    # ------------------------------------------------------------ helpers

    def targets(self, predicate):
        """Clean invoices with at least one line satisfying predicate, one per patient, shuffled."""
        pool = [(inv, [li for li in inv["line_items"] if predicate(inv, li)]) for inv in self.clean]
        pool = [(inv, lines) for inv, lines in pool if lines]
        self.rng.shuffle(pool)
        seen, picked = set(), []
        for inv, lines in pool:
            if inv["patient_id"] not in seen:
                seen.add(inv["patient_id"])
                picked.append((inv, self.rng.choice(lines)))
        return picked

    def price(self, inv, li, **forced):
        return self.base_audit.price(inv, li, self.by_day, **forced)[0]

    @staticmethod
    def find(invs, base_inv, base_li=None):
        inv = invs[base_inv["position"]]
        if base_li is None:
            return inv, None
        return inv, next(l for l in inv["line_items"] if l["line_id"] == base_li["line_id"])

    @staticmethod
    def reprice(inv, li, unit_price=None, quantity=None):
        if unit_price is not None:
            li["unit_price_cents"] = unit_price
        if quantity is not None:
            li["quantity"] = quantity
        li["line_total_cents"] = li["quantity"] * li["unit_price_cents"]
        inv["invoice_total_cents"] = sum(l["line_total_cents"] for l in inv["line_items"])

    @staticmethod
    def set_date(li, text):
        li["service_date"] = text
        li["service_date_parsed"] = parse_date(text)

    def add_line(self, inv, template, description, service_date, unit_price, unit=None):
        n = len(inv["line_items"]) + 1
        prefix = inv["line_items"][0]["line_id"].rsplit("-", 1)[0]
        line = {"line_id": f"{prefix}-{n:02d}", "invoice_id": inv["invoice_id"], "line_no": n,
                "service_date": service_date, "service_date_parsed": parse_date(service_date),
                "description": description, "quantity": template["quantity"],
                "unit_basis_as_billed": unit or template["unit_basis_as_billed"],
                "unit_price_cents": unit_price, "line_total_cents": 0}
        inv["line_items"].append(line)
        self.reprice(inv, line)
        return line

    def in_term(self, d):
        return self.rules["term_start"] <= d.isoformat() <= self.rules["term_end"]

    # ------------------------------------------------------------ error types
    # Each returns a list of plants: (base_invoice, apply(invs) -> detail dict)

    def plant_all(self, kind):
        return getattr(self, f"p_{kind}")()

    def p_unit_price_mismatch(self):
        def make(inv, li):
            factor = self.rng.choice(PRICE_FACTORS)
            def apply(invs):
                i, l = self.find(invs, inv, li)
                self.reprice(i, l, unit_price=round(l["unit_price_cents"] * factor))
                return {"line": li, "detail": f"price x{factor}"}
            return apply
        return [(inv, make(inv, li)) for inv, li in self.targets(lambda i, l: True)]

    def p_wrong_unit_plus_price(self):
        def make(inv, li):
            unit = self.rng.choice([u for u in UNITS if u != li["unit_basis_as_billed"]])
            def apply(invs):
                i, l = self.find(invs, inv, li)
                l["unit_basis_as_billed"] = unit
                self.reprice(i, l, unit_price=l["unit_price_cents"] * 2)
                return {"line": li, "detail": f"unit {unit} and price x2 on the same line",
                        "truth": ["wrong_unit_basis", "unit_price_mismatch"]}
            return apply
        return [(inv, make(inv, li)) for inv, li in self.targets(lambda i, l: l["unit_basis_as_billed"] != "per_hour_per_item")]

    def p_line_total_arithmetic(self):
        def make(inv, li):
            delta = self.rng.choice([1, -1]) * li["unit_price_cents"]
            def apply(invs):
                i, l = self.find(invs, inv, li)
                l["line_total_cents"] += delta
                i["invoice_total_cents"] = sum(x["line_total_cents"] for x in i["line_items"])
                return {"line": li, "detail": f"line total off by one unit ({delta:+d})"}
            return apply
        return [(inv, make(inv, li)) for inv, li in self.targets(lambda i, l: True)]

    def p_invoice_total_mismatch(self):
        def make(inv):
            delta = self.rng.choice([-100000, -25000, 50000, 100000])
            def apply(invs):
                i, _ = self.find(invs, inv)
                i["invoice_total_cents"] += delta
                return {"detail": f"invoice total {delta:+d}"}
            return apply
        return [(inv, make(inv)) for inv, _ in self.targets(lambda i, l: True)]

    def p_contract_number_mismatch(self):
        def make(inv):
            other = self.rng.choice(self.other_contracts)["contract_number"]
            def apply(invs):
                self.find(invs, inv)[0]["contract_number"] = other
                return {"detail": other}
            return apply
        return [(inv, make(inv)) for inv, _ in self.targets(lambda i, l: True)]

    def p_duplicate_invoice_id(self):
        picked = self.targets(lambda i, l: i["position"] > 10)[:PER_TYPE]
        planted = {inv["position"] for inv, _ in picked}  # never borrow an ID that is itself being replaced
        def make(inv):
            earlier = self.rng.choice([o for o in self.base[: inv["position"]] if o["position"] not in planted])["invoice_id"]
            def apply(invs):
                self.find(invs, inv)[0]["invoice_id"] = earlier
                return {"detail": f"reuses {earlier}"}
            return apply
        return [(inv, make(inv)) for inv, _ in picked]

    def p_malformed_service_date(self):
        def make(inv, li):
            def apply(invs):
                self.set_date(self.find(invs, inv, li)[1], "31/02/2024")
                return {"line": li, "detail": "31/02/2024"}
            return apply
        return [(inv, make(inv, li)) for inv, li in self.targets(lambda i, l: True)]

    def p_service_date_out_of_window(self):
        end = datetime.date.fromisoformat(self.rules["term_end"])
        def make(inv, li):
            d = li["service_date_parsed"]
            new = d + datetime.timedelta(days=7 * ((end - d).days // 7 + self.rng.randint(1, 20)))  # same weekday
            def apply(invs):
                self.set_date(self.find(invs, inv, li)[1], new.isoformat())
                return {"line": li, "detail": new.isoformat()}
            return apply
        return [(inv, make(inv, li)) for inv, li in self.targets(lambda i, l: True)]

    def p_service_date_after_invoice_date(self):
        def make(inv, li):
            new = li["service_date_parsed"] + datetime.timedelta(
                days=7 * ((inv["invoice_date_parsed"] - li["service_date_parsed"]).days // 7 + 1))
            def apply(invs):
                self.set_date(self.find(invs, inv, li)[1], new.isoformat())
                return {"line": li, "detail": f"{new.isoformat()} > invoice {inv['invoice_date']}"}
            return apply
        picked = self.targets(lambda i, l: self.in_term(l["service_date_parsed"] + datetime.timedelta(
            days=7 * ((i["invoice_date_parsed"] - l["service_date_parsed"]).days // 7 + 1))))
        return [(inv, make(inv, li)) for inv, li in picked]

    def p_wrong_unit_basis(self):
        def make(inv, li):
            unit = self.rng.choice([u for u in UNITS if u != li["unit_basis_as_billed"]])
            def apply(invs):
                self.find(invs, inv, li)[1]["unit_basis_as_billed"] = unit
                return {"line": li, "detail": f"{li['unit_basis_as_billed']} -> {unit}"}
            return apply
        return [(inv, make(inv, li)) for inv, li in self.targets(lambda i, l: l["unit_basis_as_billed"] != "per_hour_per_item")]

    def _foreign_services(self):
        mine = set(self.rules["services"])
        return sorted({s for r in self.other_contracts for s in r["services"]} - mine)

    def p_unknown_service(self):
        foreign = self._foreign_services()
        def make(inv, li):
            name = self.rng.choice(foreign)
            def apply(invs):
                self.find(invs, inv, li)[1]["description"] = name
                return {"line": li, "detail": f"description '{name}' (not in this contract)"}
            return apply
        return [(inv, make(inv, li)) for inv, li in self.targets(lambda i, l: True)]

    def p_unknown_service_lookalike(self):
        """A non-contract service whose name differs from a contract service only in the specialty word,
        written with that word dropped: the realistic hard case (cf. INV-H1-000236)."""
        mine = {tuple(s.split()): s for s in self.rules["services"]}
        pairs = []
        for f in self._foreign_services():
            w = f.split()
            for m in mine:
                if len(m) == len(w) and m[0] == w[0] and m[2:] == tuple(w[2:]) and m[1] != w[1]:
                    pairs.append((f, " ".join([w[0]] + w[2:])))
        def make(inv, li, desc):
            def apply(invs):
                self.find(invs, inv, li)[1]["description"] = desc
                return {"line": li, "detail": f"description '{desc}' (specialty dropped from a non-contract service)",
                        "truth": ["unknown_service"]}
            return apply
        plants = []
        for inv, li in self.targets(lambda i, l: True):
            if pairs:
                plants.append((inv, make(inv, li, self.rng.choice(pairs)[1])))
        return plants

    def p_daily_cap_exceeded(self):
        caps = self.rules["caps"]
        def make(inv, li):
            qty = caps[li["service"]] + self.rng.randint(1, 5)
            def apply(invs):
                i, l = self.find(invs, inv, li)
                self.reprice(i, l, quantity=qty)
                return {"line": li, "detail": f"quantity {li['quantity']} -> {qty} (cap {caps[li['service']]})",
                        "contract_total": inv["invoice_total_cents"] + (caps[li["service"]] - li["quantity"]) * li["unit_price_cents"]}
            return apply
        return [(inv, make(inv, li)) for inv, li in self.targets(lambda i, l: l["service"] in caps and l["quantity"] <= caps[l["service"]])]

    def p_cross_invoice_duplicate(self):
        by_patient = defaultdict(list)
        for inv in self.base:
            by_patient[inv["patient_id"]].append(inv)
        def make(inv, src_inv, src_li):
            def apply(invs):
                i, _ = self.find(invs, inv)
                self.add_line(i, src_li, src_li["description"], src_li["service_date"], src_li["unit_price_cents"])
                return {"detail": f"copies {src_li['line_id']} from {src_inv['invoice_id']}"}
            return apply
        plants, seen = [], set()
        pool = self.clean[:]
        self.rng.shuffle(pool)
        for inv in pool:
            if inv["patient_id"] in seen:
                continue
            earlier = [o for o in by_patient[inv["patient_id"]] if o["position"] < inv["position"] and not o["findings"]]
            candidates = [(o, l) for o in earlier for l in o["line_items"] if l["priceable"]
                          and inv["invoice_date_parsed"] and l["service_date_parsed"] <= inv["invoice_date_parsed"]]
            if candidates:
                seen.add(inv["patient_id"])
                o, l = self.rng.choice(candidates)
                plants.append((inv, make(inv, o, l)))
        return plants

    def p_exclusion_window_violation(self):
        plants, seen = [], set()
        delivered = defaultdict(list)  # (patient, service) -> dates
        for inv in self.base:
            for li in inv["line_items"]:
                if li["delivered"]:
                    delivered[(inv["patient_id"], li["service"])].append(li["service_date_parsed"])
        pool = self.clean[:]
        self.rng.shuffle(pool)
        for inv in pool:
            if inv["patient_id"] in seen:
                continue
            options = []
            for e in self.rules["exclusions"]:
                for d in delivered[(inv["patient_id"], e["excluded_by"])]:
                    new = d + datetime.timedelta(days=self.rng.randint(0, e["days"]))
                    if (self.in_term(new) and new <= inv["invoice_date_parsed"]
                            and new not in delivered[(inv["patient_id"], e["service"])]):
                        options.append((e, new))
            if not options:
                continue
            seen.add(inv["patient_id"])
            e, new = self.rng.choice(options)
            svc = self.rules["services"][e["service"]]
            rate = self.base_audit.multiplied(svc["rates"][-1 if new.isoformat() >= "2025-01-01" else 0]["rate_cents"],
                                              e["service"], inv)
            if self.rules["weekend_uplifts"].get(e["service"]) and new.weekday() >= 5:
                rate = apply_uplift(rate, self.rules["weekend_uplifts"][e["service"]])
            def apply(invs, inv=inv, e=e, new=new, rate=rate, unit=svc["unit"]):
                i, _ = self.find(invs, inv)
                template = {"quantity": 1, "unit_basis_as_billed": unit}
                self.add_line(i, template, e["service"], new.isoformat(), rate)
                return {"detail": f"adds {e['service']} on {new} (excluded by {e['excluded_by']} within {e['days']} days)"}
            plants.append((inv, apply))
        return plants[:PER_TYPE]

    def _price_plants(self, predicate, forced, label):
        def make(inv, li):
            new = forced(inv, li)
            def apply(invs):
                i, l = self.find(invs, inv, li)
                self.reprice(i, l, unit_price=new)
                return {"line": li, "detail": f"{label}: {li['unit_price_cents']} -> {new}"}
            return apply
        return [(inv, make(inv, li)) for inv, li in self.targets(lambda i, l: predicate(i, l) and forced(i, l) != l["unit_price_cents"])]

    def _parts(self, inv, li):
        return self.base_audit.price(inv, li, self.by_day)[1]

    def p_bundle_not_applied(self):
        return self._price_plants(lambda i, l: self._parts(i, l)["bundle"],
                                  lambda i, l: self.price(i, l, bundle=False), "standalone rate")

    def p_premium_omitted(self):
        return self._price_plants(lambda i, l: self._parts(i, l)["premium"] or self._parts(i, l)["weekend"],
                                  lambda i, l: self.price(i, l, premium=False, weekend=False), "uplift removed")

    def p_premium_incorrectly_applied(self):
        def due_none(i, l):
            p = self._parts(i, l)
            return not p["premium"] and not p["weekend"] and (
                l["service"] in self.rules["weekend_uplifts"] or l["service"] in self.rules["premiums"])
        def forced(i, l):
            return self.price(i, l, weekend=True) if l["service"] in self.rules["weekend_uplifts"] else self.price(i, l, premium=True)
        return self._price_plants(due_none, forced, "uplift added")

    def p_volume_discount_omitted(self):
        return self._price_plants(lambda i, l: self._parts(i, l)["discount"],
                                  lambda i, l: self.price(i, l, discount=False), "discount removed")

    def p_volume_discount_incorrectly_applied(self):
        tiers = self.rules["discounts"]
        return self._price_plants(lambda i, l: l["service"] in tiers and not self._parts(i, l)["discount"],
                                  lambda i, l: apply_discount(self.price(i, l, discount=False), tiers[l["service"]][0]["pct"]),
                                  "discount added")

    def p_amendment_rate_by_invoice_date(self):
        if self.h != 3:
            return []
        amended = {n for n, s in self.rules["services"].items() if len(s["rates"]) > 1}
        alt_rules = copy.deepcopy(self.rules)
        for n in amended:
            s = alt_rules["services"][n]
            s["rates"] = [{"from": None, "rate_cents": self.rules["services"][n]["rates"][1]["rate_cents"]}]
        alt = HospitalAudit(3, alt_rules, [])
        alt._by_day_cache = self.by_day
        return self._price_plants(lambda i, l: l["service"] in amended and l["service_date"] < "2025-01-01",
                                  lambda i, l: alt.price(i, l, self.by_day)[0], "2025 amendment rate on a 2024 date")

    def p_wrong_multiplier(self):
        if self.h != 5:
            return []
        def forced(i, l):
            other = [f for f in ("F-MAIN", "F-NORTH", "F-COAST") if f != i["facility_code"]]
            for f in other:
                p = self.base_audit.price({**i, "facility_code": f}, l, self.by_day)[0]
                if p != l["unit_price_cents"]:
                    return p
            return l["unit_price_cents"]
        return self._price_plants(lambda i, l: True, forced, "another facility's multiplier")


KINDS = [
    ("unit_price_mismatch", "unit_price_mismatch"), ("wrong_unit_plus_price", None),
    ("line_total_arithmetic", "line_total_arithmetic"), ("invoice_total_mismatch", "invoice_total_mismatch"),
    ("contract_number_mismatch", "contract_number_mismatch"), ("duplicate_invoice_id", "duplicate_invoice_id"),
    ("malformed_service_date", "malformed_service_date"), ("service_date_out_of_window", "service_date_out_of_window"),
    ("service_date_after_invoice_date", "service_date_after_invoice_date"), ("wrong_unit_basis", "wrong_unit_basis"),
    ("unknown_service", "unknown_service"), ("unknown_service_lookalike", None),
    ("daily_cap_exceeded", "daily_cap_exceeded"), ("cross_invoice_duplicate", "cross_invoice_duplicate"),
    ("exclusion_window_violation", "exclusion_window_violation"), ("bundle_not_applied", "bundle_not_applied"),
    ("premium_omitted", "premium_omitted"), ("premium_incorrectly_applied", "premium_incorrectly_applied"),
    ("volume_discount_omitted", "volume_discount_omitted"),
    ("volume_discount_incorrectly_applied", "volume_discount_incorrectly_applied"),
    ("amendment_rate_by_invoice_date", "unit_price_mismatch"), ("wrong_multiplier", "unit_price_mismatch"),
]

AMOUNT_UNCHANGED = {"contract_number_mismatch", "duplicate_invoice_id", "malformed_service_date",
                    "service_date_out_of_window", "service_date_after_invoice_date", "wrong_unit_basis",
                    "unknown_service", "unknown_service_lookalike"}


def outcome_map(invoices):
    return {inv["position"]: (bool(inv["findings"]), inv["expected_total_cents"],
                              frozenset(c for c, _, _ in inv["findings"])) for inv in invoices}


def run():
    from .pipeline import attach_llm_opinion  # local import: pipeline imports this package's modules
    OUT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    results = []
    for h in (1, 2, 3, 4, 5):
        planter = Planter(h, rng)
        baseline = outcome_map(planter.base)
        for kind, truth in KINDS:
            plants = planter.plant_all(kind)[:PER_TYPE]
            if not plants:
                continue
            invs = load(h)
            details = {}
            for base_inv, apply in plants:
                details[base_inv["position"]] = apply(invs)
            audited = HospitalAudit(h, planter.rules, invs).run()
            for inv in audited:
                for li in inv["line_items"]:
                    li["rule_override"] = li["certainty"] == "none" and bool(li["candidates"])
            attach_llm_opinion(h, audited)
            spill = sum(1 for inv in audited if inv["position"] not in details
                        and outcome_map([inv])[inv["position"]] != baseline[inv["position"]])
            for base_inv, _ in plants:
                inv = audited[base_inv["position"]]
                d = details[base_inv["position"]]
                tier, conf, _ = assess(inv)
                truth_cats = d.get("truth") or [truth]
                found = {c for c, _, _ in inv["findings"]}
                original_total = base_inv["invoice_total_cents"]
                line = d.get("line")
                after = next((l for l in inv["line_items"] if line and l["line_id"] == line["line_id"]), None)
                results.append({
                    "hospital": f"H{h}", "error_type": kind, "invoice_id": inv["invoice_id"],
                    "planted_line": line["line_id"] if line else "", "detail": d["detail"],
                    "line_match_before": line["certainty"] if line else "",
                    "line_match_after": after["certainty"] if after else "",
                    "flagged": int(bool(found)), "category_found": int(set(truth_cats) <= found),
                    "extra_categories": "|".join(sorted(found - set(truth_cats))),
                    "expected_total": inv["expected_total_cents"], "original_total": original_total,
                    "contract_total": d.get("contract_total", ""),
                    "total_equals_original": int(inv["expected_total_cents"] == original_total),
                    "tier": tier, "confidence": conf, "spillover_in_batch": spill,
                })
    fields = list(results[0])
    with open(OUT / "stress_results.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(results)
    return results


def summarise(results):
    by_type = defaultdict(list)
    for r in results:
        by_type[r["error_type"]].append(r)
    lines = ["| Planted error | Planted | Flagged | Right category | Total = original | Hospitals | Extra categories seen |",
             "|---|---|---|---|---|---|---|"]
    for kind, _ in KINDS:
        rs = by_type.get(kind)
        if not rs:
            continue
        n = len(rs)
        extra = Counter(c for r in rs for c in r["extra_categories"].split("|") if c)
        lines.append(f"| `{kind}` | {n} | {sum(r['flagged'] for r in rs)} | {sum(r['category_found'] for r in rs)} | "
                     f"{sum(r['total_equals_original'] for r in rs)} | "
                     f"{', '.join(sorted({r['hospital'] for r in rs}))} | "
                     f"{', '.join(f'{c} ({k})' for c, k in extra.most_common(3)) or '—'} |")
    per_h = defaultdict(lambda: [0, 0, 0])
    for r in results:
        per_h[r["hospital"]][0] += 1
        per_h[r["hospital"]][1] += r["flagged"]
        per_h[r["hospital"]][2] += r["category_found"]
    lines += ["", "| Hospital | Planted | Flagged | Right category |", "|---|---|---|---|"]
    lines += [f"| {h} | {a} | {b} ({b / a:.1%}) | {c} ({c / a:.1%}) |" for h, (a, b, c) in sorted(per_h.items())]
    missed = [r for r in results if not r["flagged"]]
    lines += ["", f"**Missed plants ({len(missed)}), by the planted line's match after the error:** "
              + ", ".join(f"{k or 'invoice-level'}: {v}" for k, v in Counter(r['line_match_after'] for r in missed).most_common())]
    to_review = sum(1 for r in missed if r["confidence"] < 0.85)
    lines += [f"**Missed plants that land in the review queue (confidence < 0.85):** {to_review}/{len(missed)}"]
    tiers = defaultdict(lambda: [0, 0])
    for r in results:
        tiers[r["tier"]][0] += 1
    lines += ["", "**Tier of each planted invoice after the run** (C = called clean, i.e. missed): "
              + ", ".join(f"{t}: {n[0]}" for t, n in sorted(tiers.items()))]
    text = "\n".join(lines) + "\n"
    (OUT / "stress_summary.md").write_text(text)
    return text


def lookalike_seeds(seeds=(1, 2, 3, 4, 5)):
    """The hardest planted type, repeated over several seeds to estimate its silent-miss rate."""
    from .pipeline import attach_llm_opinion
    outcome = Counter()
    for seed in seeds:
        rng = random.Random(seed)
        for h in (1, 2, 3, 4, 5):
            planter = Planter(h, rng)
            plants = planter.plant_all("unknown_service_lookalike")[:PER_TYPE]
            invs = load(h)
            for base_inv, apply in plants:
                apply(invs)
            audited = HospitalAudit(h, planter.rules, invs).run()
            for inv in audited:
                for li in inv["line_items"]:
                    li["rule_override"] = li["certainty"] == "none" and bool(li["candidates"])
            attach_llm_opinion(h, audited)
            for base_inv, _ in plants:
                inv = audited[base_inv["position"]]
                _, conf, _ = assess(inv)
                cats = {c for c, _, _ in inv["findings"]}
                outcome["found as unknown_service" if "unknown_service" in cats else
                        "flagged under another category" if cats else
                        "missed, sent to review (confidence < 0.85)" if conf < 0.85 else
                        "missed silently (clean at confidence >= 0.85)"] += 1
    n = sum(outcome.values())
    text = (f"**Look-alike unknown services over {len(seeds)} seeds ({n} plants):** "
            + "; ".join(f"{k}: {v} ({v / n:.1%})" for k, v in outcome.most_common()) + "\n")
    (OUT / "lookalike_seeds.md").write_text(text)
    return text


if __name__ == "__main__":
    print(summarise(run()))
    print(lookalike_seeds())
