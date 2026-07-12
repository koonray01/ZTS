from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]


def load(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


class ContractTests(unittest.TestCase):
    def test_all_schemas_are_valid_draft_2020_12(self):
        for path in (ROOT / "schemas").glob("*.schema.json"):
            schema = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            Draft202012Validator.check_schema(schema)

    def test_valid_examples_pass(self):
        mapping = {
            "snapshot.example.json": "snapshot.schema.json",
            "sensor_output.example.json": "sensor_output.schema.json",
            "market_packet.example.json": "market_packet.schema.json",
            "scenario.example.json": "scenario.schema.json",
            "entry_candidate.example.json": "entry_candidate.schema.json",
        }
        for example_name, schema_name in mapping.items():
            schema = load(f"schemas/{schema_name}")
            data = load(f"examples/valid/{example_name}")
            errors = list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(data))
            self.assertEqual(errors, [], f"{example_name}: {[e.message for e in errors]}")

    def test_invalid_examples_fail(self):
        mapping = {
            "snapshot_open_bar.invalid.json": "snapshot.schema.json",
            "sensor_trade_signal.invalid.json": "sensor_output.schema.json",
            "market_packet_permission.invalid.json": "market_packet.schema.json",
            "scenario_probability.invalid.json": "scenario.schema.json",
            "entry_permission.invalid.json": "entry_candidate.schema.json",
        }
        for example_name, schema_name in mapping.items():
            schema = load(f"schemas/{schema_name}")
            data = load(f"examples/invalid/{example_name}")
            errors = list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(data))
            self.assertTrue(errors, f"Invalid example unexpectedly passed: {example_name}")

    def test_market_packet_cannot_grant_permission(self):
        schema = load("schemas/market_packet.schema.json")
        self.assertEqual(schema["properties"]["permission_state"]["const"], "NOT_EVALUATED")

    def test_entry_candidate_cannot_grant_permission(self):
        schema = load("schemas/entry_candidate.schema.json")
        self.assertEqual(schema["properties"]["permission_state"]["const"], "NOT_EVALUATED")
        item = schema["properties"]["candidates"]["items"]
        self.assertEqual(item["properties"]["permission_state"]["const"], "NOT_EVALUATED")

    def test_scenario_probability_is_not_allowed(self):
        schema = load("schemas/scenario.schema.json")
        item = schema["properties"]["scenarios"]["items"]
        self.assertFalse(item["additionalProperties"])
        self.assertNotIn("probability", item["properties"])
        self.assertEqual(schema["properties"]["probability_status"]["const"], "UNAVAILABLE_UNTIL_CALIBRATED")

    def test_snapshot_requires_closed_bars(self):
        schema = load("schemas/snapshot.schema.json")
        bar = schema["properties"]["timeframes"]["items"]["properties"]["bars"]["items"]
        self.assertIs(bar["properties"]["is_closed"]["const"], True)

    def test_manual_execution_is_locked(self):
        cfg = (ROOT / "config/project.yaml").read_text(encoding="utf-8")
        self.assertIn("execution_mode: manual", cfg)
        self.assertIn("production_order_api_enabled: false", cfg)

    def test_core_documents_have_metadata(self):
        for path in sorted((ROOT / "docs").glob("*.md")):
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---\n"), path.name)
            self.assertTrue(text.startswith("---\n"), path.name)
            for field in ["document_version:", "status:", "owner:", "last_updated:"]:
                self.assertIn(field, text, f"{path.name} missing {field}")

    def test_no_placeholder_schemas(self):
        for path in (ROOT / "schemas").glob("*.json"):
            self.assertNotIn("PLACEHOLDER", path.read_text(encoding="utf-8"))

    def test_no_forbidden_cross_system_paths_or_imports(self):
        forbidden_patterns = [
            r"import\s+tradingos",
            r"from\s+tradingos",
            r"ZTS_AHCL_v0\.1_P0",
            r"system_overview_current",
            r"TRADINGOS_CHAT_TRADING_ANALYSIS_WORKFLOW",
        ]
        scan_dirs = [ROOT / "src", ROOT / "config", ROOT / "tools"]
        for d in scan_dirs:
            for path in d.rglob("*"):
                if path.is_file() and path.suffix in {".py", ".yaml", ".yml", ".json", ".toml"}:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                    for pat in forbidden_patterns:
                        self.assertIsNone(re.search(pat, text, re.IGNORECASE), f"{path}: {pat}")

    def test_no_public_order_write_commands(self):
        contract = (ROOT / "docs/10_PUBLIC_TOOL_AND_CLI_CONTRACT.md").read_text(encoding="utf-8").lower()
        forbidden_commands = ["ctl place-order", "ctl order-send", "ctl modify-order", "ctl cancel-order", "ctl close-position"]
        for cmd in forbidden_commands:
            self.assertNotIn(cmd, contract)


if __name__ == "__main__":
    unittest.main()
