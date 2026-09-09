"""M0 smoke harness: no registered executors, no live calls."""

import argparse
import json

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--smoke", action="store_true", required=True)
parser.parse_args()
print(json.dumps({"milestone": "M0", "executed_cases": 0, "live_calls": 0}))
