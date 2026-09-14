"""Step 3a: independent LLM reading of each contract (verification only).

Usage: python -m audit.llm_extract_contracts [hospital numbers...]
Writes verification/llm_extraction/hospital_N.json. Skips hospitals already extracted unless --force.
"""

import json
import sys

from . import llm
from .contracts import CONTRACTS, ROOT

PROMPT = ROOT / "prompts" / "pipeline" / "contract_extraction_v1.md"
OUT = ROOT / "verification" / "llm_extraction"

DOCUMENTS = {
    1: ["provider_services_agreement.md"],
    2: ["master_services_agreement.md"],
    3: ["base_agreement.md", "appendix_b_rate_schedule.md", "amendment_no_1.md"],
    4: ["conditional_reimbursement_agreement.md"],
    5: ["network_reimbursement_agreement.md"],
}

S = {"type": "string"}
I = {"type": "integer"}
NS = {"type": ["string", "null"]}
NI = {"type": ["integer", "null"]}


def obj(**props):
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


def arr(item):
    return {"type": "array", "items": item}


SCHEMA = obj(
    contract_number=S,
    services=arr(obj(name=S, unit_basis=S, rate_gbp=S, daily_cap=NI, billable_from=NS,
                     rate_changes=arr(obj(from_date=S, rate_gbp=S)))),
    threshold_premiums=arr(obj(service=S, threshold=I, uplift_percent=S)),
    non_business_day_uplifts=arr(obj(service=S, uplift_percent=S)),
    volume_discounts=arr(obj(service=S, threshold=I, discount_percent=S)),
    bundles=arr(obj(service_a=S, rate_a_gbp=S, service_b=S, rate_b_gbp=S)),
    exclusions=arr(obj(service=S, days=I, excluded_by=S)),
    facility_multipliers=arr(obj(service=S, facility=S, multiplier=S)),
    tier_multipliers=arr(obj(service=S, tier=S, multiplier=S)),
    submission_deadline_days=NI,
)


def main(argv):
    force = "--force" in argv
    hospitals = [int(a) for a in argv if a.isdigit()] or [1, 2, 3, 4, 5]
    OUT.mkdir(parents=True, exist_ok=True)
    for h in hospitals:
        target = OUT / f"hospital_{h}.json"
        if target.exists() and not force:
            print(f"H{h}: already extracted, skipping")
            continue
        text = "\n\n".join(f"===== DOCUMENT: {name} =====\n{(CONTRACTS / f'hospital_{h}' / name).read_text()}"
                           for name in DOCUMENTS[h])
        print(f"H{h}: extracting ({len(text):,} chars)...", flush=True)
        result = llm.run(PROMPT, "Extract all pricing rules from the contract documents provided on stdin.",
                         text, SCHEMA)
        target.write_text(json.dumps(result, indent=2) + "\n")
        print(f"H{h}: done, {len(result['output']['services'])} services, "
              f"est. ${result['meta']['estimated_cost_usd']}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
