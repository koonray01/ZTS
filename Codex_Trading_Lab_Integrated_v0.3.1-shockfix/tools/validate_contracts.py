from __future__ import annotations

import json
import sys
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError, ValidationError

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas"
VALID_DIR = ROOT / "examples" / "valid"
INVALID_DIR = ROOT / "examples" / "invalid"

MAPPING = {
    "snapshot": "snapshot.schema.json",
    "sensor_output": "sensor_output.schema.json",
    "market_packet": "market_packet.schema.json",
    "scenario": "scenario.schema.json",
    "entry_candidate": "entry_candidate.schema.json",
}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def schema_for_example(path: Path) -> Path:
    name = path.name
    for key, schema_name in MAPPING.items():
        if name.startswith(key):
            return SCHEMA_DIR / schema_name
    if name.startswith("snapshot_"):
        return SCHEMA_DIR / MAPPING["snapshot"]
    if name.startswith("sensor_"):
        return SCHEMA_DIR / MAPPING["sensor_output"]
    if name.startswith("market_"):
        return SCHEMA_DIR / MAPPING["market_packet"]
    if name.startswith("scenario_"):
        return SCHEMA_DIR / MAPPING["scenario"]
    if name.startswith("entry_"):
        return SCHEMA_DIR / MAPPING["entry_candidate"]
    raise KeyError(f"No schema mapping for {path.name}")


def validate_all() -> int:
    failures = []
    schemas = {}
    for schema_path in sorted(SCHEMA_DIR.glob("*.schema.json")):
        schema = load(schema_path)
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as exc:
            failures.append(f"SCHEMA INVALID {schema_path.name}: {exc.message}")
        schemas[schema_path.name] = schema

    for path in sorted(VALID_DIR.glob("*.json")):
        schema_path = schema_for_example(path)
        validator = Draft202012Validator(schemas[schema_path.name], format_checker=FormatChecker())
        errors = sorted(validator.iter_errors(load(path)), key=lambda e: list(e.path))
        if errors:
            failures.append(f"VALID EXAMPLE FAILED {path.name}: {errors[0].message}")

    for path in sorted(INVALID_DIR.glob("*.json")):
        schema_path = schema_for_example(path)
        validator = Draft202012Validator(schemas[schema_path.name], format_checker=FormatChecker())
        errors = list(validator.iter_errors(load(path)))
        if not errors:
            failures.append(f"INVALID EXAMPLE PASSED {path.name}")

    if failures:
        print("CONTRACT VALIDATION: FAIL")
        for f in failures:
            print("-", f)
        return 1
    print("CONTRACT VALIDATION: PASS")
    print(f"Schemas: {len(schemas)}")
    print(f"Valid examples: {len(list(VALID_DIR.glob('*.json')))}")
    print(f"Invalid examples: {len(list(INVALID_DIR.glob('*.json')))}")
    return 0


if __name__ == "__main__":
    sys.exit(validate_all())
