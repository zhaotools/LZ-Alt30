"""LZ-Alt30 index with dated, value-neutral constituent changes."""
import argparse
import csv
import datetime as dt
import json
import math
from pathlib import Path

BASE_DATE = "2026-10-13"
BASE_VALUE = 1000.0


def validate_changes(initial_ids, changes):
    active = list(initial_ids)
    previous = BASE_DATE
    for change in changes:
        date = change["effective_date"]
        dt.date.fromisoformat(date)
        removed, added = change["removed_id"], change["added"][0]
        if date <= previous or removed not in active or added in active or len(change["added"]) != 8:
            raise ValueError("Invalid constituent substitution")
        active[active.index(removed)] = added
        previous = date


def active_ids(initial_ids, changes, date):
    ids = list(initial_ids)
    for change in changes:
        if change["effective_date"] > date:
            break
        ids[ids.index(change["removed_id"])] = change["added"][0]
    return ids


def required_ids(initial_ids, changes, date):
    ids = active_ids(initial_ids, changes, date)
    ids.extend(change["removed_id"] for change in changes if change["effective_date"] == date)
    return list(dict.fromkeys(ids + ["bitcoin"]))


def calculate_with_state(rows, initial_ids, changes=(), skipped_dates=(), base_date=BASE_DATE):
    if not rows:
        raise ValueError("No price rows")
    if len(initial_ids) != 30 or len(set(initial_ids)) != 30:
        raise ValueError("Expected 30 distinct initial constituents")
    validate_changes(initial_ids, changes)
    dates = [row["date"] for row in rows]
    if dates != sorted(set(dates)):
        raise ValueError("Dates must be unique and increasing")
    skipped = set(skipped_dates)
    if skipped.intersection(dates):
        raise ValueError("Skipped date has a price row")
    for before, after in zip(dates, dates[1:]):
        missing = {(dt.date.fromisoformat(before) + dt.timedelta(days=offset)).isoformat()
                   for offset in range(1, (dt.date.fromisoformat(after) - dt.date.fromisoformat(before)).days)}
        if not missing.issubset(skipped):
            raise ValueError("Missing daily sampling date")
    if base_date not in dates:
        raise ValueError("Missing base date " + base_date)
    for row in rows:
        dt.date.fromisoformat(row["date"])
        needed = initial_ids + ["bitcoin"] if row["date"] <= base_date else required_ids(initial_ids, changes, row["date"])
        for cid in needed:
            try:
                price = float(row[cid])
            except (KeyError, TypeError, ValueError):
                raise ValueError("Missing or invalid price: " + row["date"] + " " + cid) from None
            if not math.isfinite(price) or price <= 0:
                raise ValueError("Missing or invalid price: " + row["date"] + " " + cid)

    reference_q = None
    live_q = None
    output = []
    first = rows[0]
    for row in rows:
        date = row["date"]
        day = dt.date.fromisoformat(date)
        if reference_q is None:
            reference_q = {cid: BASE_VALUE / 30 / float(row[cid]) for cid in initial_ids}
        reference = sum(reference_q[cid] * float(row[cid]) for cid in initial_ids) if date <= base_date else None
        if date <= base_date and day.day == 1 and day.month in (1, 4, 7, 10):
            reference_q = {cid: reference / 30 / float(row[cid]) for cid in initial_ids}
        live = None
        if date == base_date:
            live_q = {cid: BASE_VALUE / 30 / float(row[cid]) for cid in initial_ids}
            live = BASE_VALUE
        elif date > base_date:
            if live_q is None:
                raise ValueError("Missing live index initialization")
            live = sum(quantity * float(row[cid]) for cid, quantity in live_q.items())
            if any(change["effective_date"] == date for change in changes) or (day.day == 1 and day.month in (1, 4, 7, 10)):
                ids = active_ids(initial_ids, changes, date)
                live_q = {cid: live / 30 / float(row[cid]) for cid in ids}
        output.append({
            "date": date,
            "LZ_Alt30_live": live,
            "Alt30_current_basket_reference": reference,
            "BTC_reference": BASE_VALUE * float(row["bitcoin"]) / float(first["bitcoin"]),
            "ETH_reference": BASE_VALUE * float(row["ethereum"]) / float(first["ethereum"]),
        })
    return output, live_q


def calculate(rows, ids, base_date=BASE_DATE, changes=(), skipped_dates=()):
    return calculate_with_state(rows, ids, changes, skipped_dates, base_date)[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prices", default="daily_prices.csv")
    parser.add_argument("--output", default="index_values.csv")
    args = parser.parse_args()
    data = Path(__file__).resolve().parents[1] / "data"
    members = json.loads((data / "constituents.json").read_text(encoding="utf-8"))
    changes = json.loads((data / "constituent_changes.json").read_text(encoding="utf-8"))
    skipped = json.loads((data / "skipped_dates.json").read_text(encoding="utf-8"))
    with open(args.prices, encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if Path(args.prices).resolve() == (data / "daily_prices.csv").resolve():
        with (data / "daily_prices_additions.csv").open(encoding="utf-8-sig", newline="") as stream:
            rows.extend(csv.DictReader(stream))
    output = calculate(rows, [member[0] for member in members], changes=changes, skipped_dates=[item["date"] for item in skipped])
    with open(args.output, "w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(output[0]))
        writer.writeheader()
        writer.writerows(output)
    print(json.dumps({"rows": len(output), "base_date": BASE_DATE, "latest": output[-1]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
