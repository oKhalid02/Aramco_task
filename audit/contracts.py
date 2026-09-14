"""Deterministic contract parsers -> one common rule format (see rules/hospital_N.json).

H1, H3, H4, H5 are Markdown tables; H2 is templated prose. Every parser also records
`checks`: internal consistency tests (e.g. number words vs digits, cap column vs cap section)
that feed the extraction verification report.
"""

import json
import re
from pathlib import Path

from .money import gbp_to_cents

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS = ROOT / "contracts"

UNIT_CODES = {
    "per hour": "per_hour",
    "per visit": "per_visit",
    "per day of service": "per_day",
    "per night of occupancy": "per_night",
    "per procedure": "per_procedure",
    "per item supplied": "per_item",
    "per unit dispensed": "per_unit_dispensed",
    "per test": "per_test",
    "per hour, per item": "per_hour_per_item",
}

NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
    "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100, "thousand": 1000,
}


def words_to_int(words: str) -> int:
    """'two hundred and forty' -> 240, 'twenty-four' -> 24."""
    total, current = 0, 0
    for w in re.split(r"[\s\-]+", words.lower().replace(" and ", " ")):
        if not w:
            continue
        v = NUMBER_WORDS[w]
        if v == 100:
            current = (current or 1) * 100
        elif v == 1000:
            total += (current or 1) * 1000
            current = 0
        else:
            current += v
    return total + current


class RuleSet:
    def __init__(self, hospital: str):
        self.data = {
            "hospital": hospital,
            "contract_number": None,
            "term_start": None,
            "term_end": None,
            "services": {},  # name -> {unit, rates: [{from, rate_cents}], available_from}
            "caps": {},  # name -> max units per patient per service day
            "premiums": {},  # name -> {threshold, uplift_pct}
            "weekend_uplifts": {},  # name -> pct
            "discounts": {},  # name -> [{threshold, pct}] ascending
            "bundles": [],  # {a, b, rate_a_cents, rate_b_cents}
            "exclusions": [],  # {service, days, excluded_by}
            "facility_multipliers": {},  # name -> {facility: "1.1"}
            "tier_multipliers": {},  # name -> {tier: "0.95"}
            "submission_deadline_days": None,
            "sources": [],
        }
        self.checks = []  # (ok: bool, message)

    def check(self, ok: bool, message: str):
        self.checks.append({"ok": bool(ok), "message": message})

    def add_service(self, name, unit_text, rate_cents, available_from=None):
        unit = UNIT_CODES[unit_text.strip()]
        self.check(name not in self.data["services"], f"service listed once: {name}")
        self.data["services"][name] = {
            "unit": unit,
            "rates": [{"from": None, "rate_cents": rate_cents}],
            "available_from": available_from,
        }

    def set_cap(self, name, value, source):
        existing = self.data["caps"].get(name)
        if existing is not None:
            self.check(existing == value, f"cap for {name} consistent ({existing} vs {value} in {source})")
        self.data["caps"][name] = value

    def add_discount(self, name, threshold, pct):
        tiers = self.data["discounts"].setdefault(name, [])
        tiers.append({"threshold": threshold, "pct": pct})
        tiers.sort(key=lambda t: t["threshold"])

    def add_bundle(self, a, b, rate_a, rate_b):
        for bundle in self.data["bundles"]:
            if {bundle["a"], bundle["b"]} == {a, b}:
                same = (bundle["a"], bundle["rate_a_cents"], bundle["rate_b_cents"]) in (
                    (a, rate_a, rate_b), (b, rate_b, rate_a))
                self.check(same, f"bundle {a} + {b} stated consistently")
                return
        self.data["bundles"].append({"a": a, "b": b, "rate_a_cents": rate_a, "rate_b_cents": rate_b})

    def finish(self):
        names = set(self.data["services"])
        referenced = set(self.data["caps"]) | set(self.data["premiums"]) | set(self.data["weekend_uplifts"]) \
            | set(self.data["discounts"]) | set(self.data["facility_multipliers"]) | set(self.data["tier_multipliers"])
        for b in self.data["bundles"]:
            referenced |= {b["a"], b["b"]}
        for e in self.data["exclusions"]:
            referenced |= {e["service"], e["excluded_by"]}
        unknown = sorted(referenced - names)
        self.check(not unknown, f"every rule references a contracted service (unknown: {unknown})")
        if self.data["facility_multipliers"]:
            self.check(set(self.data["facility_multipliers"]) == names, "facility multiplier for every service")
            self.check(set(self.data["tier_multipliers"]) == names, "plan-tier multiplier for every service")
        return self


# ---------------------------------------------------------------- Markdown tables

def parse_header(md: str, rules: RuleSet):
    number = re.search(r"\*\*Contract number:\*\* (\S+)", md).group(1)
    start = re.search(r"\*\*Effective from:\*\* (.+)", md).group(1).strip()
    end = re.search(r"\*\*Effective to:\*\* (.+)", md).group(1).strip()
    rounding = re.search(r"\*\*Rounding convention:\*\* (.+)", md).group(1).strip()
    rules.check(rounding == "half_up_cent", f"rounding convention is half_up_cent ({rounding})")
    if rules.data["contract_number"]:
        rules.check(rules.data["contract_number"] == number, f"contract number consistent across documents ({number})")
    rules.data["contract_number"] = number
    rules.data["term_start"] = iso_date(start)
    rules.data["term_end"] = iso_date(end)


MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], start=1)}


def iso_date(text: str) -> str:
    day, month, year = text.split()
    return f"{int(year):04d}-{MONTHS[month.lower()]:02d}-{int(day):02d}"


def markdown_tables(md: str):
    """Yield (heading, header_cells, rows) for every pipe table, with the nearest heading above it."""
    heading, lines = "", md.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("#"):
            heading = line.lstrip("#").strip()
        if line.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[-| ]+\|$", lines[i + 1]):
            header = cells(line)
            rows = []
            i += 2
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(cells(lines[i]))
                i += 1
            yield heading, header, rows
            continue
        i += 1


def cells(line: str):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def table_int(text: str) -> int:
    """'more than 6 items' -> 6, 'eighty (80)' -> 80 (checks the words), '24 hours' -> 24."""
    m = re.search(r"\((\d+)\)", text)
    if m:
        return int(m.group(1))
    return int(re.search(r"\d+", text).group(0))


def table_pct(text: str) -> str:
    return re.search(r"(\d+(?:\.\d+)?)%", text).group(1)


def check_words(rules: RuleSet, text: str, where: str):
    """Where a figure is written as 'eighty (80)', the words must agree with the digits."""
    for words, digits in re.findall(r"([a-z][a-z\- ]*?) \((\d+)%?\)", text):
        tokens = re.sub(r"\s*percent$", "", words.strip()).split()
        kept = []
        for token in reversed(tokens):  # trailing run of number words, e.g. "of two hundred and forty"
            if token != "and" and not all(p in NUMBER_WORDS for p in token.split("-")):
                break
            kept.insert(0, token)
        words = " ".join(kept)
        if words:
            rules.check(words_to_int(words) == int(digits), f"number words match digits: '{words} ({digits})' in {where}")


def classify(heading: str, header):
    h, first = heading.lower(), header[0].lower()
    if "facility code" in first:
        return None
    if "facility multiplier" in h:
        return "facility"
    if "plan-tier" in h:
        return "tier"
    if "substituted rates" in h:
        return "amend_rates"
    if "additional services" in h:
        return "amend_added"
    if "premium" in h:
        return "premiums"
    if "business-day" in h:
        return "weekend"
    if "discount" in h:
        return "discounts"
    if "cap" in h or "limit" in h:
        return "caps"
    if "bundle" in h:
        return "bundles"
    if "exclusion" in h:
        return "exclusions"
    if "rate" in h:
        return "rates"
    raise ValueError(f"unclassified table under heading {heading!r}: {header}")


def col(header, *needles):
    for i, name in enumerate(header):
        if all(n in name.lower() for n in needles):
            return i
    raise KeyError(f"{needles} not in {header}")


def parse_tables(md: str, rules: RuleSet, source: str):
    rules.data["sources"].append(source)
    parse_header(md, rules)
    check_words(rules, md, source)
    for heading, header, rows in markdown_tables(md):
        kind = classify(heading, header)
        if kind is None:
            continue
        for row in rows:
            name = row[0]
            if kind == "rates":
                rules.add_service(name, row[col(header, "unit")], gbp_to_cents(row[col(header, "rate")]))
                if any("cap" in c.lower() for c in header):
                    cap = row[col(header, "cap")]
                    if cap not in ("—", "-", ""):
                        rules.set_cap(name, table_int(cap), f"{source} rate table")
            elif kind == "caps":
                rules.set_cap(name, table_int(row[1]), f"{source} caps section")
            elif kind == "premiums":
                rules.check(name not in rules.data["premiums"], f"one premium per service: {name}")
                rules.data["premiums"][name] = {"threshold": table_int(row[1]), "uplift_pct": table_pct(row[2])}
            elif kind == "weekend":
                rules.data["weekend_uplifts"][name] = table_pct(row[1])
            elif kind == "discounts":
                rules.add_discount(name, table_int(row[1]), table_pct(row[2]))
            elif kind == "bundles":
                a, b = row[col(header, "service a")], row[col(header, "service b")]
                ra, rb = row[col(header, "rate a")], row[col(header, "rate b")]
                rules.add_bundle(a, b, gbp_to_cents(ra), gbp_to_cents(rb))
            elif kind == "exclusions":
                rules.data["exclusions"].append({"service": name, "days": table_int(row[1]), "excluded_by": row[2]})
            elif kind == "facility":
                rules.data["facility_multipliers"][name] = dict(zip(header[1:], row[1:]))
            elif kind == "tier":
                rules.data["tier_multipliers"][name] = dict(zip(header[1:], row[1:]))
            elif kind == "amend_rates":
                svc = rules.data["services"].get(name)
                rules.check(svc is not None, f"amended service exists in Appendix B: {name}")
                old = gbp_to_cents(row[col(header, "to 31 december 2024")])
                new = gbp_to_cents(row[col(header, "from 1 january 2025")])
                rules.check(svc["rates"][0]["rate_cents"] == old,
                            f"amendment 'rate to 31 Dec 2024' equals Appendix B for {name}")
                rules.check(UNIT_CODES[row[col(header, "unit")]] == svc["unit"], f"amendment unit unchanged for {name}")
                svc["rates"].append({"from": "2025-01-01", "rate_cents": new})
            elif kind == "amend_added":
                rules.add_service(name, row[col(header, "unit")], gbp_to_cents(row[col(header, "rate")]),
                                  available_from="2025-01-01")


# ---------------------------------------------------------------- H2 prose

PROSE_CLAUSE = re.compile(
    r"^(\d+\.\d+) In respect of (.+?), the Provider shall invoice the Payer at the rate of "
    r"(GBP [\d,]+\.\d\d) (per [a-z ,]+?)\. (.*)$", re.M)
N = r"([a-z][a-z\- ]*?) \((\d+)\)"
PCT = r"([a-z][a-z\- ]*?) percent \((\d+)%\)"
PROSE_RULES = {
    "cap": re.compile(rf"The Provider shall not bill more than {N} [a-z]+ of this Service for a Patient on a single Service Day\."),
    "weekend": re.compile(rf"Where the Service Date of this Service does not fall on a Business Day, the rate applicable to it shall be increased by {PCT}\."),
    "premium": re.compile(rf"Where the aggregate quantity of this Service delivered to a Patient on a single Service Day exceeds {N} [a-z]+, the rate applicable to that Service Day shall be increased by {PCT}\."),
    "discount": re.compile(rf"Where cumulative utilisation of this Service exceeds {N} [a-z]+, counted cumulatively across the whole term of this Agreement and aggregated across all Patients, a discount of {PCT} shall be applied to each subsequent Unit\."),
    "exclusion": re.compile(rf"This Service is not billable where ([A-Z][A-Za-z ]+?) has been delivered to the same Patient within {N} days of the Service Date\."),
    "bundle": re.compile(r"Where this Service and ([A-Z][A-Za-z ]+?) are both delivered to the same Patient on the same Service Day, the two shall be billed as a bundle, this Service at (GBP [\d,]+\.\d\d) per [a-z ]+ and ([A-Z][A-Za-z ]+?) at (GBP [\d,]+\.\d\d) per [a-z ]+, in substitution for their standalone rates\."),
}
PROSE_BOILERPLATE = [
    r"The description applied by the Provider on any invoice shall not of itself vary the rate applicable to this Service; the rate follows the Service actually delivered\.",
    r"Any quantity billed for this Service must be expressed on the unit basis stated in this clause and on no other basis\.",
    r"The rate stated in this clause is inclusive of all consumables, staffing and overhead attributable to the Service, and no separate charge shall be raised in respect of them\.",
    r"The Provider shall be able to demonstrate, from its clinical record, the quantity billed for this Service on any Service Day\.",
    r"Where an invoice presents this Service on a unit basis other than the one stated in this clause, the line item shall be treated as incorrectly presented and shall be returned to the Provider\.",
    r"The Provider shall present this Service on its invoices under a description sufficient to identify it as ([A-Za-z ]+), and shall not present it under a description that identifies a different contracted Service\.",
]


def parse_prose(md: str, rules: RuleSet, source: str):
    rules.data["sources"].append(source)
    parse_header(md, rules)
    clauses = PROSE_CLAUSE.findall(md)
    for number, name, rate, unit, rest in clauses:
        rules.add_service(name, unit, gbp_to_cents(rate))
        remaining = rest

        def words(w, d, what):
            rules.check(words_to_int(w) == int(d), f"clause {number}: {what} words '{w}' match ({d})")
            return int(d)

        for kind, pattern in PROSE_RULES.items():
            for m in pattern.finditer(rest):
                g = m.groups()
                if kind == "cap":
                    rules.set_cap(name, words(g[0], g[1], "cap"), f"clause {number}")
                elif kind == "weekend":
                    rules.data["weekend_uplifts"][name] = str(words(g[0], g[1], "uplift"))
                elif kind == "premium":
                    rules.data["premiums"][name] = {"threshold": words(g[0], g[1], "threshold"),
                                                   "uplift_pct": str(words(g[2], g[3], "uplift"))}
                elif kind == "discount":
                    rules.add_discount(name, words(g[0], g[1], "threshold"), str(words(g[2], g[3], "discount")))
                elif kind == "exclusion":
                    rules.data["exclusions"].append({"service": name, "days": words(g[1], g[2], "window"),
                                                     "excluded_by": g[0]})
                elif kind == "bundle":
                    other, rate_self, other2, rate_other = g
                    rules.check(other == other2, f"clause {number}: bundle names the same partner twice")
                    rules.add_bundle(name, other, gbp_to_cents(rate_self), gbp_to_cents(rate_other))
            remaining = pattern.sub("", remaining)
        for i, pattern in enumerate(PROSE_BOILERPLATE):
            m = re.search(pattern, remaining)
            if i == len(PROSE_BOILERPLATE) - 1 and m:
                rules.check(m.group(1) == name, f"clause {number}: description clause names its own service")
            remaining = re.sub(pattern, "", remaining)
        rules.check(not remaining.strip(), f"clause {number}: every sentence understood (left: {remaining.strip()!r})")

    rules.check(len(clauses) == len(re.findall(r"In respect of ", md)), "every 'In respect of' clause parsed")
    money_lines = [l for l in md.split("\n") if ("GBP " in l or "%" in l) and "In respect of" not in l]
    rules.check(not money_lines, f"no GBP/% figures outside service clauses ({money_lines[:2]})")
    m = re.search(rf"submitted no later than {N} days after the discharge date", md)
    if m:
        rules.data["submission_deadline_days"] = int(m.group(2))
        rules.check(words_to_int(m.group(1)) == int(m.group(2)), "submission deadline words match digits")


# ---------------------------------------------------------------- per hospital

def build(hospital: int) -> RuleSet:
    rules = RuleSet(f"H{hospital}")
    folder = CONTRACTS / f"hospital_{hospital}"
    read = lambda name: (folder / name).read_text()
    if hospital == 1:
        parse_tables(read("provider_services_agreement.md"), rules, "provider_services_agreement.md")
    elif hospital == 2:
        parse_prose(read("master_services_agreement.md"), rules, "master_services_agreement.md")
    elif hospital == 3:
        # Precedence (base 1.3): amendment > Appendix B > base. Appendix B first so the
        # amendment can layer dated rates on top; the base agreement holds the rule tables.
        parse_tables(read("appendix_b_rate_schedule.md"), rules, "appendix_b_rate_schedule.md")
        parse_tables(read("base_agreement.md"), rules, "base_agreement.md")
        parse_tables(read("amendment_no_1.md"), rules, "amendment_no_1.md")
    elif hospital == 4:
        md = read("conditional_reimbursement_agreement.md")
        parse_tables(md, rules, "conditional_reimbursement_agreement.md")
        rules.check("_None._" in md.split("## 10.")[1].split("## 11.")[0], "H4 §10 states no weekend uplifts")
    elif hospital == 5:
        parse_tables(read("network_reimbursement_agreement.md"), rules, "network_reimbursement_agreement.md")
    return rules.finish()


def write_all(out_dir: Path = ROOT / "rules"):
    out_dir.mkdir(exist_ok=True)
    summary = {}
    for h in range(1, 6):
        rules = build(h)
        (out_dir / f"hospital_{h}.json").write_text(json.dumps(rules.data, indent=2, sort_keys=True) + "\n")
        summary[h] = rules
    return summary


if __name__ == "__main__":
    for h, rules in write_all().items():
        d = rules.data
        failed = [c["message"] for c in rules.checks if not c["ok"]]
        print(f"H{h} {d['contract_number']}: services={len(d['services'])} caps={len(d['caps'])} "
              f"premiums={len(d['premiums'])} weekend={len(d['weekend_uplifts'])} "
              f"discounts={len(d['discounts'])} bundles={len(d['bundles'])} exclusions={len(d['exclusions'])} "
              f"facility_mult={len(d['facility_multipliers'])} tier_mult={len(d['tier_multipliers'])} "
              f"deadline={d['submission_deadline_days']} | checks {len(rules.checks) - len(failed)}/{len(rules.checks)} ok")
        for f in failed:
            print("   FAILED:", f)
