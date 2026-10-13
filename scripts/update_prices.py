"""Append complete UTC-midnight price samples from DefiLlama, then rebuild the site."""

import argparse
import csv
import datetime as dt
import io
import json
import math
import os
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from build_site import DATA, ROOT, build, read_csv
from calculate_index import BASE_DATE, calculate


PRICE_FILE = DATA / "daily_prices.csv"
QUOTE_FILE = DATA / "quote_times.csv"
QUOTE_FIELDS = ["采样日期", "CoinGecko_ID", "实际报价UTC", "价格_USD", "实际报价与UTC零点差_秒"]
MAX_OFFSET_SECONDS = 900


def fetch_sample(date, ids):
    timestamp = int(dt.datetime.combine(date, dt.time.min, dt.timezone.utc).timestamp())
    coins = ",".join("coingecko:" + coin_id for coin_id in ids)
    url = f"https://coins.llama.fi/prices/historical/{timestamp}/{coins}"
    last_error = None
    for attempt in range(3):
        try:
            request = Request(url, headers={"User-Agent": "LZ-Alt30/1.0 (+https://github.com/zhaotools/LZ-Alt30)"})
            with urlopen(request, timeout=25) as response:
                if response.status != 200:
                    raise ValueError(f"HTTP {response.status}")
                payload = json.load(response)
            break
        except (HTTPError, URLError, TimeoutError, ValueError) as error:
            last_error = error
            if attempt == 2:
                raise RuntimeError(f"Price request failed for {date}: {error}") from error
            time.sleep(2 ** attempt)
    else:
        raise RuntimeError(f"Price request failed for {date}: {last_error}")

    response_coins = payload.get("coins")
    if not isinstance(response_coins, dict):
        raise ValueError(f"Malformed price response for {date}")
    prices = {"date": date.isoformat()}
    quotes = []
    for coin_id in ids:
        entry = response_coins.get("coingecko:" + coin_id)
        if not isinstance(entry, dict):
            raise ValueError(f"Missing price for {date}: {coin_id}")
        price = entry.get("price")
        quote_time = entry.get("timestamp")
        if isinstance(price, bool) or not isinstance(price, (int, float)) or not math.isfinite(price) or price <= 0:
            raise ValueError(f"Invalid price for {date}: {coin_id}")
        if isinstance(quote_time, bool) or not isinstance(quote_time, int):
            raise ValueError(f"Missing quote timestamp for {date}: {coin_id}")
        offset = quote_time - timestamp
        if abs(offset) > MAX_OFFSET_SECONDS:
            raise ValueError(f"Stale quote for {date}: {coin_id} offset {offset}s")
        prices[coin_id] = repr(price)
        quotes.append(
            {
                "采样日期": date.isoformat(),
                "CoinGecko_ID": coin_id,
                "实际报价UTC": dt.datetime.fromtimestamp(quote_time, dt.timezone.utc).isoformat(),
                "价格_USD": repr(price),
                "实际报价与UTC零点差_秒": str(offset),
            }
        )
    return prices, quotes


def write_csv_atomically(path, rows, fields):
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(buffer.getvalue(), encoding="utf-8-sig")
    os.replace(temporary, path)


def update(target_date):
    members = json.loads((DATA / "constituents.json").read_text(encoding="utf-8"))
    ids = [member[0] for member in members]
    all_ids = ids + ["bitcoin"]
    rows = read_csv(PRICE_FILE)
    quotes = read_csv(QUOTE_FILE)
    calculate(rows, ids)
    last = dt.date.fromisoformat(rows[-1]["date"])
    if last < dt.date.fromisoformat(BASE_DATE):
        raise ValueError("Price ledger does not contain the official base date")
    if target_date > dt.datetime.now(dt.timezone.utc).date():
        raise ValueError("Target date is in the future")
    if target_date <= last:
        print(f"Already current through {last}; no prices added")
        build()
        return 0

    new_rows = []
    new_quotes = []
    for offset in range(1, (target_date - last).days + 1):
        date = last + dt.timedelta(days=offset)
        price_row, quote_rows = fetch_sample(date, all_ids)
        new_rows.append(price_row)
        new_quotes.extend(quote_rows)
        print(f"Validated {date}: 31 prices, max offset {max(abs(int(r['实际报价与UTC零点差_秒'])) for r in quote_rows)}s")

    calculate(rows + new_rows, ids)
    write_csv_atomically(PRICE_FILE, rows + new_rows, ["date"] + all_ids)
    write_csv_atomically(QUOTE_FILE, quotes + new_quotes, QUOTE_FIELDS)
    build()
    return len(new_rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Last UTC sampling date to append (YYYY-MM-DD); defaults to today")
    args = parser.parse_args()
    target = dt.date.fromisoformat(args.date) if args.date else dt.datetime.now(dt.timezone.utc).date()
    update(target)
