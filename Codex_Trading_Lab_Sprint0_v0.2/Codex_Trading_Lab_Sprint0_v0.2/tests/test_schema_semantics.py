from __future__ import annotations

import json
import unittest
from pathlib import Path
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def load(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


class SchemaSemanticTests(unittest.TestCase):
    def test_open_bar_is_rejected(self):
        schema = load("schemas/snapshot.schema.json")
        data = load("examples/invalid/snapshot_open_bar.invalid.json")
        self.assertTrue(list(Draft202012Validator(schema).iter_errors(data)))

    def test_sensor_buy_signal_is_rejected(self):
        schema = load("schemas/sensor_output.schema.json")
        data = load("examples/invalid/sensor_trade_signal.invalid.json")
        self.assertTrue(list(Draft202012Validator(schema).iter_errors(data)))

    def test_market_approved_permission_is_rejected(self):
        schema = load("schemas/market_packet.schema.json")
        data = load("examples/invalid/market_packet_permission.invalid.json")
        self.assertTrue(list(Draft202012Validator(schema).iter_errors(data)))

    def test_entry_approved_permission_is_rejected(self):
        schema = load("schemas/entry_candidate.schema.json")
        data = load("examples/invalid/entry_permission.invalid.json")
        self.assertTrue(list(Draft202012Validator(schema).iter_errors(data)))

    def test_scenario_probability_is_rejected(self):
        schema = load("schemas/scenario.schema.json")
        data = load("examples/invalid/scenario_probability.invalid.json")
        self.assertTrue(list(Draft202012Validator(schema).iter_errors(data)))


if __name__ == "__main__":
    unittest.main()
