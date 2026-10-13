import datetime as dt
import json
import math
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_site import build, read_csv  # noqa: E402
from calculate_index import BASE_DATE, calculate  # noqa: E402
from update_prices import fetch_sample  # noqa: E402


class IndexTests(unittest.TestCase):
    def test_attachment_recomputes_exactly(self):
        members = json.loads((ROOT / "data/constituents.json").read_text(encoding="utf-8"))
        ids = [member[0] for member in members]
        prices = read_csv(ROOT / "data/daily_prices.csv")
        expected = read_csv(ROOT / "data/attachment_index_values.csv")
        actual = calculate(prices[: len(expected)], ids)
        self.assertEqual(len(actual), 365)
        self.assertEqual(actual[-1]["date"], BASE_DATE)
        self.assertEqual(actual[-1]["LZ_Alt30_live"], 1000)
        for row, original in zip(actual, expected):
            self.assertEqual(row["date"], original["date"])
            for key in ("LZ_Alt30_live", "Alt30_current_basket_reference", "BTC_reference", "ETH_reference"):
                if row[key] is None:
                    self.assertEqual(original[key], "")
                else:
                    self.assertTrue(math.isclose(row[key], float(original[key]), rel_tol=1e-12, abs_tol=1e-9))

    def test_generated_public_data_keeps_reference_separate(self):
        result = build()
        self.assertEqual(len(result["official"]), len(read_csv(ROOT / "data/daily_prices.csv")) - 364)
        self.assertEqual(len(result["reference"]), 365)
        self.assertEqual(result["reference"][-1]["date"], BASE_DATE)
        self.assertEqual(result["official"][0]["value"], 1000)
        self.assertEqual(len(result["constituents"]), 30)
        self.assertAlmostEqual(sum(item["current_weight_pct"] for item in result["constituents"]), 100, places=3)
        next_rebalance = dt.date.fromisoformat(result["meta"]["next_rebalance_date"])
        latest = dt.date.fromisoformat(result["meta"]["latest_date"])
        self.assertGreater(next_rebalance, latest)
        self.assertEqual(next_rebalance.day, 1)
        self.assertIn(next_rebalance.month, (1, 4, 7, 10))

    def test_calculator_rejects_missing_or_nonpositive_price(self):
        members = json.loads((ROOT / "data/constituents.json").read_text(encoding="utf-8"))
        ids = [member[0] for member in members]
        last = read_csv(ROOT / "data/daily_prices.csv")[-1].copy()
        last["ethereum"] = "0"
        with self.assertRaises(ValueError):
            calculate([last], ids)

    def test_fetch_rejects_stale_quote(self):
        date = dt.date(2026, 10, 14)
        timestamp = int(dt.datetime.combine(date, dt.time.min, dt.timezone.utc).timestamp())
        payload = {"coins": {"coingecko:ethereum": {"price": 100.0, "timestamp": timestamp - 901}}}

        class Response:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, *args): return json.dumps(payload).encode()

        with patch("update_prices.urlopen", return_value=Response()):
            with self.assertRaisesRegex(ValueError, "Stale quote"):
                fetch_sample(date, ["ethereum"])


if __name__ == "__main__":
    unittest.main()
