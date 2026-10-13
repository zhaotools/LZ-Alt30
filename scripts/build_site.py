"""Build the public, static LZ-Alt30 data file from the preserved price ledger."""

import csv
import datetime as dt
import json
import math
from pathlib import Path

from calculate_index import BASE_DATE, BASE_VALUE, calculate


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUTPUT = ROOT / "site" / "data" / "index.json"


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def build():
    members = json.loads((DATA / "constituents.json").read_text(encoding="utf-8"))
    ids = [item[0] for item in members]
    if len(ids) != 30 or len(set(ids)) != 30:
        raise ValueError("Expected 30 unique constituents")

    prices = read_csv(DATA / "daily_prices.csv")
    values = calculate(prices, ids)
    by_date = {row["date"]: row for row in prices}
    base = by_date[BASE_DATE]
    latest = prices[-1]
    prior = prices[-2] if len(prices) > 1 else None
    latest_date = latest["date"]

    quote_rows = read_csv(DATA / "quote_times.csv")
    latest_quotes = [row for row in quote_rows if row["采样日期"] == latest_date]
    if len(latest_quotes) != 31 or {row["CoinGecko_ID"] for row in latest_quotes} != set(ids + ["bitcoin"]):
        raise ValueError("Latest quote provenance does not cover all 31 assets")
    max_quote_offset = max(abs(int(row["实际报价与UTC零点差_秒"])) for row in latest_quotes)
    if max_quote_offset > 900:
        raise ValueError("Latest quote exceeds the 15 minute sampling tolerance")

    official = []
    for row in values:
        if row["date"] < BASE_DATE:
            continue
        daily = by_date[row["date"]]
        official.append(
            {
                "date": row["date"],
                "value": round(row["LZ_Alt30_live"], 6),
                "btc": round(BASE_VALUE * float(daily["bitcoin"]) / float(base["bitcoin"]), 6),
                "eth": round(BASE_VALUE * float(daily["ethereum"]) / float(base["ethereum"]), 6),
            }
        )

    # The retrospective exercise ends on the official base date. The attachment's
    # calculator may continue that series, but the public site never extends it.
    reference = [
        {
            "date": row["date"],
            "alt30": round(row["Alt30_current_basket_reference"], 6),
            "btc": round(row["BTC_reference"], 6),
            "eth": round(row["ETH_reference"], 6),
        }
        for row in values
        if row["date"] <= BASE_DATE
    ]

    quantities = {coin_id: BASE_VALUE / len(ids) / float(base[coin_id]) for coin_id in ids}
    for row in prices:
        if row["date"] <= BASE_DATE:
            continue
        day = dt.date.fromisoformat(row["date"])
        point = sum(quantities[coin_id] * float(row[coin_id]) for coin_id in ids)
        if day.day == 1 and day.month in (1, 4, 7, 10):
            quantities = {coin_id: point / len(ids) / float(row[coin_id]) for coin_id in ids}
    last_value = official[-1]["value"]
    exact_value = sum(quantities[coin_id] * float(latest[coin_id]) for coin_id in ids)
    if not math.isclose(last_value, exact_value, rel_tol=0, abs_tol=0.000001):
        raise ValueError("Displayed official value differs from current holdings")

    sectors = {}
    constituents = []
    for coin_id, symbol, sector, priority, business, mechanism, risk, source in members:
        price = float(latest[coin_id])
        weight = quantities[coin_id] * price / exact_value
        previous_price = float(prior[coin_id]) if prior else None
        change = (price / previous_price - 1) * 100 if previous_price else None
        constituents.append(
            {
                "id": coin_id,
                "symbol": symbol,
                "sector": sector,
                "priority": priority,
                "business": business,
                "mechanism": mechanism,
                "risk": risk,
                "source": source,
                "price": price,
                "previous_sample_change_pct": round(change, 4) if change is not None else None,
                "target_weight_pct": 100 / len(ids),
                "current_weight_pct": round(weight * 100, 6),
            }
        )
        record = sectors.setdefault(sector, {"name": sector, "count": 0, "weight_pct": 0})
        record["count"] += 1
        record["weight_pct"] += weight * 100

    for record in sectors.values():
        record["weight_pct"] = round(record["weight_pct"], 4)

    result = {
        "meta": {
            "name": "LZ-Alt30",
            "full_name": "老赵基本面山寨指数",
            "version": "v0.2 · INJ版",
            "base_date": BASE_DATE,
            "base_value": BASE_VALUE,
            "latest_date": latest_date,
            "sampling_time": "00:00 UTC / 08:00 北京时间附近",
            "latest_quote_max_offset_seconds": max_quote_offset,
            "next_rebalance_date": next_rebalance_date(latest_date),
            "reference_start": reference[0]["date"],
            "reference_end": BASE_DATE,
        },
        "official": official,
        "reference": reference,
        "sectors": list(sectors.values()),
        "constituents": constituents,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Built {OUTPUT}: {len(official)} official, {len(reference)} reference dates; latest {last_value:.2f}")
    return result


def next_rebalance_date(date_string):
    date = dt.date.fromisoformat(date_string)
    for year in (date.year, date.year + 1):
        for month in (1, 4, 7, 10):
            candidate = dt.date(year, month, 1)
            if candidate > date:
                return candidate.isoformat()
    raise AssertionError("No future quarterly rebalance date")


if __name__ == "__main__":
    build()
