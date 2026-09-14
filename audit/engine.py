"""Step 5: check and re-price every invoice of one hospital against its rules.

All invoices of a hospital are processed together because several rules need history: cumulative
volume discounts (all patients, whole term), cross-invoice duplicates, bundles, caps and exclusion
windows. Ambiguous clauses are switchable through `readings` so step 6 can re-run under the
alternative reading.
"""

import itertools
from collections import defaultdict

from .mapping import Matcher
from .money import apply_discount, apply_multiplier, apply_uplift, to_fraction

DEFAULT_READINGS = {
    # A-numbers refer to docs/phase1_task_understanding.md §7.
    "exclusion_inclusive": True,  # "within N days" means |days apart| <= N
    "premium_threshold_on": "billed",  # A6: daily premium threshold tested on billed (vs capped) quantity
    "unit_basis_hour_item_accepts": (),  # A2: billed units also accepted for a "per hour, per item" service
    "deadline_rule": True,  # A4: enforce H2's 60-day submission clause
    # A5: which billed units count toward volume-discount utilisation ("Units of a Service billed").
    # H3/H5 evidence: counting mis-presented lines too removes 5 threshold-boundary artefacts.
    "cumulative_counts": "delivered",
    "cumulative_excludes_out_of_term": False,
    # Fixes made during Phase 3, switchable so the evaluation can measure what each one changed.
    "history_includes_mispresented": True,  # H1 label evidence (INV-H1-000847): a wrong-unit line still delivered
    "date_root_cause": True,  # H1 label evidence (INV-H1-000179/-000852): past-term date reported once
    "unit_price_unknown_rule": True,  # H1 label evidence (INV-H1-000236): loose match, unit+price fit nothing
    "matcher_tie_rule": "any_multiple",  # LLM second opinion ("Emer Ortho"); first run used "fewest_missing"
}

MONEY_CATEGORIES = {
    "unit_price_mismatch", "bundle_not_applied", "premium_omitted", "premium_incorrectly_applied",
    "volume_discount_omitted", "volume_discount_incorrectly_applied", "daily_cap_exceeded",
    "cross_invoice_duplicate", "exclusion_window_violation", "line_total_arithmetic",
    "invoice_total_mismatch",
}


class HospitalAudit:
    def __init__(self, hospital, rules, invoices, mapping_overrides=None, readings=None):
        self.hospital = hospital
        self.rules = rules
        self.invoices = invoices
        self.services = rules["services"]
        self.overrides = mapping_overrides or {}  # description -> {"service": name|None, "certainty": ...}
        self.readings = {**DEFAULT_READINGS, **(readings or {})}
        self.matcher = Matcher(self.services, tie_rule=self.readings["matcher_tie_rule"])
        self.bundle_of = defaultdict(list)
        for b in rules["bundles"]:
            self.bundle_of[b["a"]].append((b["b"], b["rate_a_cents"]))
            self.bundle_of[b["b"]].append((b["a"], b["rate_b_cents"]))
        self.exclusions_of = defaultdict(list)
        for e in rules["exclusions"]:
            self.exclusions_of[e["service"]].append((e["excluded_by"], e["days"]))

    # ------------------------------------------------------------ mapping

    def resolve(self, inv, li):
        override = self.overrides.get(li["description"])
        result = override or self.matcher.match(li["description"])
        certainty = result["certainty"]
        if certainty in ("exact", "strong", "llm"):
            return result["service"], certainty, result.get("candidates", [])
        if certainty == "ambiguous":
            candidates = result["candidates"]
            by_unit = [c for c in candidates if self.unit_ok(c, li["unit_basis_as_billed"])]
            if len(by_unit) == 1:
                return by_unit[0], "unit_tiebreak", candidates
            pool = by_unit or candidates
            by_price = [c for c in pool if li["unit_price_cents"] in self.plausible_prices(c, inv)]
            if len(by_price) == 1:
                return by_price[0], "price_tiebreak", candidates
            return None, "ambiguous", candidates
        return None, "none", []

    def unit_ok(self, service, billed_unit):
        unit = self.services[service]["unit"]
        return billed_unit == unit or (unit == "per_hour_per_item"
                                       and billed_unit in self.readings["unit_basis_hour_item_accepts"])

    def plausible_prices(self, service, inv):
        svc = self.services[service]
        rates = {r["rate_cents"] for r in svc["rates"]} | {rate for _, rate in self.bundle_of[service]}
        uplifts = [None] + [p for p in (self.rules["premiums"].get(service, {}).get("uplift_pct"),
                                         self.rules["weekend_uplifts"].get(service)) if p]
        discounts = [None] + [t["pct"] for t in self.rules["discounts"].get(service, [])]
        prices = set()
        for rate, up, disc in itertools.product(rates, uplifts, discounts):
            p = self.multiplied(rate, service, inv)
            p = apply_uplift(p, up) if up else p
            prices.add(apply_discount(p, disc) if disc else p)
        return prices

    def multiplied(self, rate, service, inv):
        fm = self.rules["facility_multipliers"].get(service)
        tm = self.rules["tier_multipliers"].get(service)
        if fm:
            rate = apply_multiplier(rate, to_fraction(fm[inv["facility_code"]]))
        if tm:
            rate = apply_multiplier(rate, to_fraction(tm[inv["plan_tier"]]))
        return rate

    # ------------------------------------------------------------ main pass

    def run(self):
        R = self.readings
        rules = self.rules
        seen_ids = set()
        rows = []  # every line with its resolution
        for inv in self.invoices:
            inv["findings"] = []  # (category, line_id|None, detail)
            inv["evidence"] = []
            inv["reused_id"] = inv["invoice_id"] in seen_ids
            seen_ids.add(inv["invoice_id"])
            for li in inv["line_items"]:
                service, certainty, candidates = self.resolve(inv, li)
                if (R["unit_price_unknown_rule"] and service and certainty != "exact"
                        and not self.unit_ok(service, li["unit_basis_as_billed"])
                        and li["unit_price_cents"] not in self.plausible_prices(service, inv)):
                    # A loose match whose unit AND price both fit nothing about the service: the text does not
                    # identify this service after all (H1: all 11 true wrong-unit lines had plausible prices).
                    service, certainty = None, "none"
                li["service"], li["certainty"], li["candidates"] = service, certainty, candidates
                li["delivered"] = bool(service and li["service_date_parsed"])
                li["priceable"] = li["delivered"] and self.unit_ok(service, li["unit_basis_as_billed"])
                rows.append((inv, li))

        # History indexes over delivered lines (a mis-presented unit does not mean the service was not
        # delivered), in contract order: Service Date, then line identifier.
        history = "delivered" if R["history_includes_mispresented"] else "priceable"
        ordered = sorted((r for r in rows if r[1][history]),
                         key=lambda r: (r[1]["service_date_parsed"], r[1]["line_id"]))
        by_day = defaultdict(list)  # (patient, service, date) -> [(inv, li)]
        by_patient_service = defaultdict(list)  # (patient, service) -> [date]
        for inv, li in sorted(ordered, key=lambda r: (r[0]["position"], r[1]["line_id"])):
            by_day[(inv["patient_id"], li["service"], li["service_date_parsed"])].append((inv, li))
        for inv, li in ordered:
            by_patient_service[(inv["patient_id"], li["service"])].append(li["service_date_parsed"])
        self._by_day_cache = by_day

        # Duplicates: the same Service, Patient and Service Date more than once -> later occurrences.
        for group in by_day.values():
            for inv, li in group[1:]:
                li["duplicate_of"] = group[0][1]["line_id"]

        # Cumulative utilisation (billed units of non-duplicate lines, before the line being priced).
        running = defaultdict(int)
        for inv, li in ordered:
            li["prior_units"] = running[li["service"]]
            counts = {
                "priceable": li["priceable"] and not li.get("duplicate_of"),
                "delivered": not li.get("duplicate_of"),
                "delivered_incl_duplicates": True,
            }[R["cumulative_counts"]]
            if R["cumulative_excludes_out_of_term"] and not (
                    rules["term_start"] <= li["service_date_parsed"].isoformat() <= rules["term_end"]):
                counts = False
            if counts:
                running[li["service"]] += li["quantity"]

        # Daily cap usage in line order within the day.
        for (patient, service, date), group in by_day.items():
            cap = rules["caps"].get(service)
            used = 0
            for inv, li in group:
                if li.get("duplicate_of") or not li["priceable"]:
                    li["payable_qty"] = li["quantity"]
                    continue
                li["payable_qty"] = li["quantity"] if cap is None else max(0, min(li["quantity"], cap - used))
                used += li["quantity"]
            li_total = sum(li["quantity"] for _, li in group if not li.get("duplicate_of"))
            capped_total = sum(li["payable_qty"] for _, li in group if not li.get("duplicate_of"))
            for _, li in group:
                li["day_qty_billed"], li["day_qty_capped"] = li_total, capped_total

        for inv in self.invoices:
            self.check_invoice(inv, by_day, by_patient_service)
        return self.invoices

    # ------------------------------------------------------------ per invoice

    def check_invoice(self, inv, by_day, by_patient_service):
        rules, R = self.rules, self.readings
        add = lambda cat, line=None, detail="": inv["findings"].append((cat, line, detail))

        if inv["contract_number"] != rules["contract_number"]:
            add("contract_number_mismatch", None, inv["contract_number"])
        if inv["reused_id"]:
            add("duplicate_invoice_id")
        billed_sum = sum(li["line_total_cents"] for li in inv["line_items"])
        if billed_sum != inv["invoice_total_cents"]:
            add("invoice_total_mismatch", None, f"lines sum {billed_sum}")
        if (R["deadline_rule"] and rules["submission_deadline_days"] and inv["invoice_date_parsed"]
                and inv["discharge_date_parsed"]
                and (inv["invoice_date_parsed"] - inv["discharge_date_parsed"]).days > rules["submission_deadline_days"]):
            add("late_submission", None, f"{(inv['invoice_date_parsed'] - inv['discharge_date_parsed']).days} days after discharge")

        term_start, term_end = rules["term_start"], rules["term_end"]
        expected_total = 0
        for li in inv["line_items"]:
            lid, date, service = li["line_id"], li["service_date_parsed"], li["service"]
            billed_unit, qty = li["unit_price_cents"], li["quantity"]
            if qty * billed_unit != li["line_total_cents"]:
                add("line_total_arithmetic", lid, f"{qty} x {billed_unit} != {li['line_total_cents']}")
            if li["certainty"] == "none":
                add("unknown_service", lid, li["description"])
            elif li["certainty"] == "ambiguous":
                inv["evidence"].append(("unresolved_mapping", lid, li["candidates"]))
            if li["certainty"] in ("strong", "unit_tiebreak", "price_tiebreak", "llm"):
                inv["evidence"].append((f"mapping_{li['certainty']}", lid, service))
            if date is None:
                add("malformed_service_date", lid, li["service_date"])
            else:
                out_of_term = not (term_start <= date.isoformat() <= term_end)
                if out_of_term:
                    add("service_date_out_of_window", lid, li["service_date"])
                if inv["invoice_date_parsed"] and date > inv["invoice_date_parsed"] and not (
                        out_of_term and R["date_root_cause"]):
                    # Reported only when the date is inside the term: a date past the term end is reported as
                    # out of window (its root cause), not twice (H1 labels: INV-H1-000179, -000852).
                    add("service_date_after_invoice_date", lid, li["service_date"])
                avail = service and self.services[service]["available_from"]
                if avail and date.isoformat() < avail:
                    add("service_not_yet_contracted", lid, f"{service} billable from {avail}")
            if service and not self.unit_ok(service, li["unit_basis_as_billed"]):
                add("wrong_unit_basis", lid, f"{li['unit_basis_as_billed']} vs {self.services[service]['unit']}")

            if not li["priceable"]:
                expected_total += qty * billed_unit
                continue
            if li.get("duplicate_of"):
                add("cross_invoice_duplicate", lid, f"repeats {li['duplicate_of']}")
                continue
            blocked = self.excluded(inv, li, by_patient_service)
            if blocked:
                add("exclusion_window_violation", lid, blocked)
                continue

            expected_unit, parts = self.price(inv, li, by_day)
            payable = li["payable_qty"]
            if payable < qty:
                add("daily_cap_exceeded", lid, f"{qty} billed, {payable} payable")
            if billed_unit != expected_unit:
                add(self.price_category(inv, li, parts, billed_unit), lid, f"billed {billed_unit}, expected {expected_unit}")
            expected_total += payable * expected_unit
        inv["expected_total_cents"] = expected_total

    def excluded(self, inv, li, by_patient_service):
        for other, days in self.exclusions_of.get(li["service"], []):
            for d in by_patient_service.get((inv["patient_id"], other), []):
                gap = abs((li["service_date_parsed"] - d).days)
                if gap < days or (gap == days and self.readings["exclusion_inclusive"]):
                    return f"{other} delivered {gap} days apart (window {days})"
        return None

    def price(self, inv, li, by_day, bundle=None, premium=None, weekend=None, discount=None):
        """Expected unit price. Each keyword forces an adjustment on (True) or off (False) for diagnosis."""
        rules, service, date = self.rules, li["service"], li["service_date_parsed"]
        svc = self.services[service]
        rate = [r for r in svc["rates"] if r["from"] is None or r["from"] <= date.isoformat()][-1]["rate_cents"]
        parts = {}
        partner_rate = None
        for partner, bundled in self.bundle_of.get(service, []):
            if by_day.get((inv["patient_id"], partner, date)):
                partner_rate = bundled
        parts["bundle"] = partner_rate is not None
        if (parts["bundle"] if bundle is None else bundle) and partner_rate is not None:
            rate = partner_rate
        rate = self.multiplied(rate, service, inv)

        prem = rules["premiums"].get(service)
        day_qty = li["day_qty_capped"] if self.readings["premium_threshold_on"] == "capped" else li["day_qty_billed"]
        parts["premium"] = bool(prem and day_qty > prem["threshold"])
        if (parts["premium"] if premium is None else premium) and prem:
            rate = apply_uplift(rate, prem["uplift_pct"])
        wk = rules["weekend_uplifts"].get(service)
        parts["weekend"] = bool(wk and date.weekday() >= 5)
        if (parts["weekend"] if weekend is None else weekend) and wk:
            rate = apply_uplift(rate, wk)

        tiers = [t for t in rules["discounts"].get(service, []) if li["prior_units"] > t["threshold"]]
        deepest = max((t["pct"] for t in tiers), key=to_fraction, default=None)
        parts["discount"] = deepest
        all_tiers = rules["discounts"].get(service, [])
        if discount is False:
            deepest = None
        elif discount is True and deepest is None and all_tiers:
            deepest = all_tiers[0]["pct"]
        if deepest:
            rate = apply_discount(rate, deepest)
        return rate, parts

    def price_category(self, inv, li, parts, billed):
        """Explain a unit-price difference by the single adjustment that would reproduce the billed price."""
        service = li["service"]
        tests = []
        if parts["bundle"]:
            tests.append(("bundle_not_applied", dict(bundle=False)))
        if self.rules["premiums"].get(service):
            tests.append(("premium_omitted" if parts["premium"] else "premium_incorrectly_applied",
                          dict(premium=not parts["premium"])))
        if self.rules["weekend_uplifts"].get(service):
            tests.append(("premium_omitted" if parts["weekend"] else "premium_incorrectly_applied",
                          dict(weekend=not parts["weekend"])))
        if self.rules["discounts"].get(service):
            if parts["discount"]:
                tests.append(("volume_discount_omitted", dict(discount=False)))
            else:
                for t in self.rules["discounts"][service]:
                    tests.append(("volume_discount_incorrectly_applied", dict(discount_pct=t["pct"])))
        for category, forced in tests:
            if "discount_pct" in forced:
                base, _ = self._price_with(inv, li, discount=False)
                candidate = apply_discount(base, forced["discount_pct"])
            else:
                candidate, _ = self._price_with(inv, li, **forced)
            if candidate == billed:
                return category
        return "unit_price_mismatch"

    def _price_with(self, inv, li, **forced):
        return self.price(inv, li, self._by_day_cache, **forced)
