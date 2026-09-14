"""Step 4 (LLM part): second opinion on descriptions the deterministic matcher was not fully sure about.

Usage: python -m audit.llm_map_descriptions [hospital numbers...] [--force]
Writes mappings/llm_hospital_N.json. The pipeline reads that file; it never calls the LLM itself.
"""

import json
import sys
from collections import Counter

from . import llm
from .contracts import ROOT
from .loader import load
from .mapping import Matcher

PROMPT = ROOT / "prompts" / "pipeline" / "description_mapping_v1.md"
OUT = ROOT / "mappings"

S = {"type": "string"}
SCHEMA = {
    "type": "object",
    "properties": {"results": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "description": S,
            "verdict": {"type": "string", "enum": ["match", "ambiguous", "none"]},
            "service": {"type": ["string", "null"]},
            "candidates": {"type": "array", "items": S},
            "reason": S,
        },
        "required": ["description", "verdict", "service", "candidates", "reason"],
        "additionalProperties": False,
    }}},
    "required": ["results"],
    "additionalProperties": False,
}


def uncertain_descriptions(hospital):
    rules = json.loads((ROOT / "rules" / f"hospital_{hospital}.json").read_text())
    matcher = Matcher(rules["services"])
    counts = Counter(li["description"] for inv in load(hospital) for li in inv["line_items"])
    picked = {d: matcher.match(d) for d in counts if matcher.match(d)["certainty"] != "exact"}
    return rules, dict(sorted(picked.items()))


def main(argv):
    force = "--force" in argv
    hospitals = [int(a) for a in argv if a.isdigit()] or [1, 2, 3, 4, 5]
    OUT.mkdir(exist_ok=True)
    for h in hospitals:
        target = OUT / f"llm_hospital_{h}.json"
        if target.exists() and not force:
            print(f"H{h}: already mapped, skipping")
            continue
        rules, picked = uncertain_descriptions(h)
        payload = {"services": sorted(rules["services"]), "descriptions": list(picked)}
        print(f"H{h}: asking about {len(picked)} descriptions...", flush=True)
        result = llm.run(PROMPT, "Map every description in the JSON on stdin.", json.dumps(payload, indent=1), SCHEMA)
        returned = {r["description"] for r in result["output"]["results"]}
        result["meta"]["missing_descriptions"] = sorted(set(picked) - returned)
        result["meta"]["matcher_view"] = picked
        target.write_text(json.dumps(result, indent=2) + "\n")
        print(f"H{h}: done, {len(returned)} answers, missing {len(result['meta']['missing_descriptions'])}, "
              f"est. ${result['meta']['estimated_cost_usd']}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
