"""python -m audit [run|rules|verify|evaluate]  (default: run)"""

import sys

from . import contracts, pipeline, verify

COMMANDS = {
    "run": pipeline.main,  # rules -> engine -> confidence -> submission.csv + outputs/
    "rules": lambda: [print(f"H{h}: {len(r.data['services'])} services, "
                            f"{sum(c['ok'] for c in r.checks)}/{len(r.checks)} checks ok")
                      for h, r in contracts.write_all().items()],
    "verify": verify.main,  # verification/report.md (parser checks, LLM diff, data majority)
}

if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "run"
    if command not in COMMANDS:
        sys.exit(f"unknown command {command!r}; choose from {', '.join(COMMANDS)}")
    COMMANDS[command]()
