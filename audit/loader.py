"""Step 1: load invoices from JSONL (keeps invoices that reuse an ID apart; the CSVs merge their lines)."""

import datetime
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def parse_date(text):
    if not isinstance(text, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return None
    try:
        return datetime.date.fromisoformat(text)
    except ValueError:
        return None


def load(hospital: int):
    invoices = []
    path = ROOT / "invoices" / f"hospital_{hospital}_invoices.jsonl"
    for position, line in enumerate(path.read_text().splitlines()):
        inv = json.loads(line)
        inv["position"] = position
        inv["invoice_date_parsed"] = parse_date(inv["invoice_date"])
        inv["admission_date_parsed"] = parse_date(inv["admission_date"])
        inv["discharge_date_parsed"] = parse_date(inv["discharge_date"])
        for li in inv["line_items"]:
            li["service_date_parsed"] = parse_date(li["service_date"])
        invoices.append(inv)
    return invoices
