"""Published public model selector contract, independent of provider identifiers."""

import json
from pathlib import Path


def load_profiles() -> tuple[str, ...]:
    contract = Path(__file__).resolve().parents[1] / "contracts/m21-profiles.json"
    models = json.loads(contract.read_text())["models"]
    if (
        not isinstance(models, list)
        or not models
        or any(not isinstance(name, str) or not name for name in models)
        or len(set(models)) != len(models)
    ):
        raise ValueError("invalid_public_profiles")
    return tuple(models)


PROFILES = load_profiles()
