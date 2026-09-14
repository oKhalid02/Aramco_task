"""Regression tests. Run: python -m unittest discover -s tests"""

import csv
import json
import unittest
from fractions import Fraction

from audit.contracts import ROOT, build, words_to_int
from audit.engine import HospitalAudit
from audit.evaluate import compare
from audit.loader import load
from audit.mapping import Matcher
from audit.money import apply_discount, apply_uplift, gbp_to_cents, round_half_up


class Money(unittest.TestCase):
    def test_half_up(self):
        self.assertEqual(round_half_up(Fraction(5, 2)), 3)
        self.assertEqual(round_half_up(Fraction(249, 100)), 2)
        self.assertEqual(round_half_up(Fraction(-5, 2)), -3)

    def test_adjustments(self):
        self.assertEqual(apply_uplift(20000, "20"), 24000)
        self.assertEqual(apply_discount(151975, "20"), 121580)  # INV-H1-000657 line 2
        self.assertEqual(apply_discount(112825, "10"), 101543)  # 101542.5 rounds up

    def test_gbp(self):
        self.assertEqual(gbp_to_cents("GBP 1,301.25"), 130125)


class Contracts(unittest.TestCase):
    EXPECTED_SERVICES = {1: 108, 2: 76, 3: 120, 4: 98, 5: 84}

    def test_every_contract_parses_with_all_checks_passing(self):
        for h, n in self.EXPECTED_SERVICES.items():
            rules = build(h)
            self.assertEqual(len(rules.data["services"]), n, f"H{h}")
            self.assertEqual([c["message"] for c in rules.checks if not c["ok"]], [], f"H{h}")

    def test_number_words(self):
        self.assertEqual(words_to_int("two hundred and forty"), 240)
        self.assertEqual(words_to_int("twenty-four"), 24)

    def test_h3_amendment_by_service_date(self):
        svc = build(3).data["services"]["Intensive Ophthalmic Laboratory Panel"]
        self.assertEqual(svc["rates"], [{"from": None, "rate_cents": 41825}, {"from": "2025-01-01", "rate_cents": 39725}])

    def test_saved_rules_match_parser(self):
        for h in self.EXPECTED_SERVICES:
            saved = json.loads((ROOT / "rules" / f"hospital_{h}.json").read_text())
            self.assertEqual(saved, json.loads(json.dumps(build(h).data)), f"rules/hospital_{h}.json is stale")


class Mapping(unittest.TestCase):
    def setUp(self):
        self.m = Matcher(build(1).data["services"])

    def test_abbreviations_and_noise_codes(self):
        r = self.m.match("Svc Preop Ent Steril /NG-1234")
        self.assertEqual((r["service"], r["certainty"]), ("Preoperative Otolaryngologic Sterilisation Service", "exact"))

    def test_dropped_word_tie_is_ambiguous(self):
        r = self.m.match("Emer Ortho")
        self.assertEqual(r["certainty"], "ambiguous")
        self.assertEqual(set(r["candidates"]), {"Emergency Orthopaedic Consultation", "Emergency Orthopaedic Rehabilitation Programme"})

    def test_lookalike_not_in_contract(self):
        self.assertEqual(self.m.match("Amb Gastrointestinal Discharge Plng")["certainty"], "none")


class H1Regression(unittest.TestCase):
    """Development-set guard: the engine must keep reproducing the H1 labels."""

    def test_flags_and_totals(self):
        rules = json.loads((ROOT / "rules" / "hospital_1.json").read_text())
        report = compare(HospitalAudit(1, rules, load(1)).run(), verbose=False)
        self.assertEqual((report["invoice_flag"]["fp"], report["invoice_flag"]["fn"]), (0, 0))
        self.assertEqual(report["expected_total_exact"]["clean"], "855/855")
        self.assertEqual(report["expected_total_exact"]["erroneous"], "54/58")  # 4 daily-cap label cases


class SubmissionFormat(unittest.TestCase):
    def test_template_columns_integers_and_confidence(self):
        path = ROOT / "submission.csv"
        if not path.exists():
            self.skipTest("run `python -m audit` first")
        template = (ROOT / "submission_template.csv").read_text().strip().split(",")
        with open(path) as f:
            reader = csv.DictReader(f)
            self.assertEqual(reader.fieldnames, template)
            rows = list(reader)
        self.assertEqual(len({r["invoice_id"] for r in rows}), len(rows))
        for r in rows:
            self.assertTrue(r["expected_total_cents"].isdigit() and r["billed_total_cents"].isdigit())
            self.assertIn(r["flagged"], ("0", "1"))
            self.assertTrue(0 <= float(r["confidence"]) <= 1)
            self.assertEqual(r["flagged"] == "1", bool(r["error_category"]))
            self.assertTrue(r["invoice_id"].split("-")[1] in ("H2", "H3", "H4", "H5"))


if __name__ == "__main__":
    unittest.main()
