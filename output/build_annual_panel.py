"""Build the annual panel for Model 2 from the monthly file.

Each row is one country-year, keyed by `iso` and `year`. Monthly series are
averaged inside the year; the outcome is the mean of the twelve monthly
three-month rolling standard deviations, exactly parallel to how the quarterly
file averages three of them.

Lags are applied on this script's output, not here: the regression shifts the
regressors by one year. WGI is stored as the calendar-year value (unshifted),
because it is constant within the year in the source panel.

Writes cleaned/replication_cleaned/country_year.csv.
"""

from __future__ import annotations

import csv
import os
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MONTHLY = os.path.join(ROOT, "cleaned", "replication_cleaned", "country_month.csv")
ANNUAL = os.path.join(ROOT, "cleaned", "replication_cleaned", "country_year.csv")

GROUP = "Emerging"
YEAR_MIN, YEAR_MAX = 2000, 2023

AVERAGED = [
    "capital_flow_volatility",
    "portfolio_inflow",
    "gpr_z",
    "vix",
    "wgi_va",
    "wgi_pv",
    "wgi_ge",
    "wgi_rq",
    "wgi_rl",
    "wgi_cc",
    "d_policy_rate",
    "d_inflation",
    "d_log_oil",
    "d_log_gepu",
    "d_financial_development",
    "d_public_debt_gdp",
]


def num(text):
    text = (text or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def main():
    buckets = defaultdict(lambda: defaultdict(list))
    meta = {}

    with open(MONTHLY, encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if (row.get("group") or "").strip() != GROUP:
                continue
            date = (row.get("date") or "").strip()
            if len(date) < 4:
                continue
            year = int(date[:4])
            if not (YEAR_MIN <= year <= YEAR_MAX):
                continue
            iso = (row.get("iso") or "").strip()
            meta[iso] = (row.get("country") or "").strip()
            for column in AVERAGED:
                value = num(row.get(column))
                if value is not None:
                    buckets[iso][year].append((column, value))

    fields = ["iso", "country", "year", "months"] + AVERAGED + ["wgi_years"]
    rows = []
    for iso, years in buckets.items():
        for year in sorted(years):
            cells = years[year]
            record = {"iso": iso, "country": meta[iso], "year": year}
            # Number of months with a usable outcome, which is what governs the sample.
            record["months"] = sum(
                1 for column, _ in cells if column == "capital_flow_volatility"
            )
            for column in AVERAGED:
                values = [v for c, v in cells if c == column]
                record[column] = sum(values) / len(values) if values else None
            rows.append(record)

    with open(ANNUAL, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in rows:
            writer.writerow(
                {
                    k: ("" if v is None else f"{v:.6f}" if isinstance(v, float) else v)
                    for k, v in record.items()
                }
            )

    print(f"Wrote {ANNUAL}")
    print(f"  {len(rows)} country-years, {len(buckets)} countries")
    full = sum(1 for r in rows if r["months"] == 12)
    print(f"  {full} country-years carry all twelve months of the outcome")


if __name__ == "__main__":
    main()
