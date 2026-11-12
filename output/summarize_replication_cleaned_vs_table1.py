"""Summary statistics of replication_cleaned beside the paper's Table 1.

Moments use every non-missing country-month. Oil, VIX, and global EPU are
repeated once per country, which is how a panel summary counts them. The
minimum and maximum name the country and month. A second table gives each
country's count, span, and moments for every series that varies by country.
"""

import csv
import math
import os
from html import escape

import numpy as np


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PANEL = os.path.join(ROOT, "cleaned", "replication_cleaned", "country_month.csv")
OUTPUT = os.path.join(ROOT, "output")

# label, kind, paper (mean, sd, min, max) or None, note
# kind "level" reads the column. kind "log" takes the log of a positive column.
# kind "real_stock" is log(share_price / cpi). Global series are not in the
# country table.
SPECS = [
    ("Capital flow volatility (SD)", "level", "capital_flow_volatility", False,
     (7.22, 19.62, 0.0, 528.40),
     "Three-month standard deviation of portfolio inflows, billion dollars."),
    ("Real stock prices (log)", "log", "share_price", False,
     (4.32, 0.47, 2.37, 5.46),
     "Log of the nominal share-price index, 2015=100. This is the scale of Table 1."),
    ("Real stock prices, CPI-deflated (log)", "real_stock", None, False,
     None,
     "Log of the share-price index divided by the CPI. Table 1 does not print this series."),
    ("Long-term bond yield (%)", "level", "bond_yield", False,
     (4.74, 3.63, -0.65, 42.18),
     "Long-term government bond yield."),
    ("Real effective exchange rate (log)", "log", "reer", False,
     (4.64, 0.18, 3.61, 5.23),
     "Log of the broad real effective exchange rate."),
    ("Geopolitical risk (index)", "level", "gpr", False,
     (0.22, 0.52, 0.0, 13.23),
     "Raw country article share. The regression standardizes this within each country."),
    ("Policy rate (%)", "level", "policy_rate", False,
     (4.37, 4.87, -0.75, 57.0),
     "Central-bank policy rate. Euro-area members use the euro-area rate."),
    ("Real industrial production (log)", "log", "industrial_production", False,
     (4.58, 0.31, 2.29, 5.81),
     "Log of the industrial-production index, 2015=100."),
    ("Inflation (%)", "level", "inflation", False,
     (4.06, 6.18, -4.43, 85.51),
     "Year-on-year CPI inflation."),
    ("Oil price (log)", "log", "oil_price", True,
     (3.73, 0.63, 2.42, 4.90),
     "Log of the WTI spot price, repeated for every country in a month."),
    ("VIX, level", "level", "vix", True,
     (19.59, 7.54, 10.13, 62.67),
     "Table 1 is labeled log, but the printed numbers are the VIX level. Repeated for every country."),
    ("VIX, log", "log", "vix", True,
     None,
     "Natural log of the VIX. Table 1 does not print these moments."),
    ("Global economic policy uncertainty (index)", "level", "gepu", True,
     (140.26, 74.91, 49.23, 431.73),
     "GEPU current index, the level, repeated for every country in a month."),
    ("Financial development (index)", "level", "financial_development", False,
     (0.60, 0.19, 0.11, 0.93),
     "IMF financial-development index, 0 to 1. Annual, repeated within the year."),
    ("Central bank independence (index)", "level", "central_bank_independence", False,
     (0.66, 0.19, 0.14, 0.93),
     "Romelli central-bank independence index. Annual, repeated within the year."),
    ("Public debt to GDP (%)", "level", "public_debt_gdp", False,
     (68.77, 36.40, 11.82, 216.33),
     "General-government gross debt as a percent of GDP. Annual, repeated within the year."),
]


def number(text):
    text = (text or "").strip()
    if not text:
        return None
    value = float(text)
    if not math.isfinite(value):
        return None
    return value


def month_label(date):
    return date[:7]


def load_rows():
    with open(PANEL, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def countries_in_order(rows):
    seen = []
    known = set()
    for row in rows:
        iso = row["iso"]
        if iso not in known:
            known.add(iso)
            seen.append((iso, row["country"], row["group"]))
    return seen


def series_points(rows, kind, column):
    points = []
    for row in rows:
        if kind == "real_stock":
            share = number(row["share_price"])
            cpi = number(row["cpi"])
            if share is None or cpi is None or share <= 0 or cpi <= 0:
                continue
            value = math.log(share / cpi)
        else:
            raw = number(row[column])
            if raw is None:
                continue
            if kind == "log":
                if raw <= 0:
                    continue
                value = math.log(raw)
            else:
                value = raw
        points.append((row["iso"], row["country"], month_label(row["date"]), value))
    return points


def summarize(points, global_series):
    values = np.array([point[3] for point in points], dtype=float)
    order = sorted(range(len(points)), key=lambda i: (points[i][2], points[i][1]))
    ordered_values = values[order]
    imin = order[int(np.argmin(ordered_values))]
    imax = order[int(np.argmax(ordered_values))]
    months = [point[2] for point in points]
    isos = {point[0] for point in points}
    minimum = points[imin]
    maximum = points[imax]
    if global_series:
        min_where = minimum[2]
        max_where = maximum[2]
    else:
        min_where = f"{minimum[1]} {minimum[2]}"
        max_where = f"{maximum[1]} {maximum[2]}"
    return {
        "n": int(len(points)),
        "n_countries": len(isos),
        "isos": isos,
        "first": min(months),
        "last": max(months),
        "mean": float(values.mean()),
        "sd": float(values.std(ddof=1)) if len(values) > 1 else float("nan"),
        "min": float(minimum[3]),
        "max": float(maximum[3]),
        "min_where": min_where,
        "max_where": max_where,
    }


def judgment(paper, stats):
    if paper is None:
        return "not printed in Table 1"
    mean_gap = abs(stats["mean"] - paper[0]) / abs(paper[0])
    sd_gap = abs(stats["sd"] - paper[1]) / abs(paper[1])
    if mean_gap <= 0.15 and sd_gap <= 0.25:
        return "close to Table 1"
    return "same concept, moments differ"


def fmt(value, digits=2):
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return ""
    return f"{value:.{digits}f}"


def country_rows(points, countries, label):
    by_iso = {}
    for iso, _country, month, value in points:
        by_iso.setdefault(iso, []).append((month, value))
    records = []
    for iso, country, group in countries:
        observed = by_iso.get(iso, [])
        if not observed:
            records.append({
                "country": country,
                "group": group,
                "variable": label,
                "n": 0,
                "first": "",
                "last": "",
                "mean": "",
                "minimum": "",
                "maximum": "",
            })
            continue
        values = np.array([item[1] for item in observed], dtype=float)
        months = [item[0] for item in observed]
        records.append({
            "country": country,
            "group": group,
            "variable": label,
            "n": len(observed),
            "first": min(months),
            "last": max(months),
            "mean": f"{float(values.mean()):.10g}",
            "minimum": f"{float(values.min()):.10g}",
            "maximum": f"{float(values.max()):.10g}",
        })
    return records


def write_csv(path, records, fields):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)


def html_page(pooled, country):
    pooled_body = []
    for record in pooled:
        pooled_body.append(
            "<tr>"
            f"<td>{escape(record['variable'])}</td>"
            f"<td>{escape(record['judgment'])}</td>"
            f"<td>{escape(record['paper_mean'])}</td><td>{escape(record['paper_sd'])}</td>"
            f"<td>{escape(record['paper_min'])}</td><td>{escape(record['paper_max'])}</td>"
            f"<td>{record['n']}</td><td>{record['n_countries']}</td>"
            f"<td>{escape(record['first'])}</td><td>{escape(record['last'])}</td>"
            f"<td>{escape(fmt(float(record['mean'])) if record['mean'] else '')}</td>"
            f"<td>{escape(fmt(float(record['sd'])) if record['sd'] else '')}</td>"
            f"<td>{escape(fmt(float(record['minimum'])) if record['minimum'] else '')}</td>"
            f"<td>{escape(fmt(float(record['maximum'])) if record['maximum'] else '')}</td>"
            f"<td>{escape(record['min_where'])}</td>"
            f"<td>{escape(record['max_where'])}</td>"
            f"<td>{escape(record['missing_countries'])}</td>"
            "</tr>"
        )
    country_body = []
    for record in country:
        country_body.append(
            "<tr>"
            f"<td>{escape(record['country'])}</td>"
            f"<td>{escape(record['group'])}</td>"
            f"<td>{escape(record['variable'])}</td>"
            f"<td>{record['n']}</td>"
            f"<td>{escape(record['first'])}</td><td>{escape(record['last'])}</td>"
            f"<td>{escape(fmt(float(record['mean'])) if record['mean'] else '')}</td>"
            f"<td>{escape(fmt(float(record['minimum'])) if record['minimum'] else '')}</td>"
            f"<td>{escape(fmt(float(record['maximum'])) if record['maximum'] else '')}</td>"
            "</tr>"
        )
    notes = "".join(
        f"<li><strong>{escape(record['variable'])}.</strong> {escape(record['note'])}</li>"
        for record in pooled
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>replication_cleaned and Table 1</title>
<style>
body {{ font: 16px/1.5 Georgia, serif; max-width: 1280px; margin: 2em auto; padding: 0 1em; color: #20242a; }}
table {{ border-collapse: collapse; width: 100%; margin: 1em 0 2em; font-size: .82em; }}
th, td {{ border-bottom: 1px solid #ccc; padding: .35em .4em; text-align: right; vertical-align: top; }}
.pooled th:nth-child(-n+2), .pooled td:nth-child(-n+2),
.pooled th:nth-last-child(-n+3), .pooled td:nth-last-child(-n+3),
.country th:nth-child(-n+3), .country td:nth-child(-n+3) {{ text-align: left; }}
.note {{ background: #fff5da; padding: 1em; border: 1px solid #e6d59d; }}
</style>
</head>
<body>
<h1>replication_cleaned beside Table 1</h1>
<div class="note">
<p>Moments use every non-missing row in <code>cleaned/replication_cleaned/country_month.csv</code>. The file is the paper's 29 economies, January 2000 through December 2023. Oil, VIX, and global EPU are repeated once for each country in a month. The minimum and maximum name the country and the month. A blank country on a global series means the extreme is a month, not a country.</p>
<p>"Close to Table 1" means the mean is within 15 percent and the standard deviation within 25 percent of the published moment. "Not printed in Table 1" is a transform this file can compute that the published table does not show.</p>
</div>
<h2>Pooled comparison</h2>
<table class="pooled">
<thead>
<tr>
<th>Variable</th><th>Judgment</th>
<th>Paper mean</th><th>Paper SD</th><th>Paper min</th><th>Paper max</th>
<th>N</th><th>Countries</th><th>First</th><th>Last</th>
<th>Mean</th><th>SD</th><th>Min</th><th>Max</th>
<th>Minimum at</th><th>Maximum at</th><th>Countries with no observations</th>
</tr>
</thead>
<tbody>
{''.join(pooled_body)}
</tbody>
</table>
<h2>What each row is</h2>
<ul>
{notes}
</ul>
<h2>Country and timeframe</h2>
<p>Each row is one country and one series that varies across countries. N is the number of months with a value. The first and last months are the span of those months, not a claim that every month in between is filled.</p>
<table class="country">
<thead>
<tr><th>Country</th><th>Group</th><th>Variable</th><th>N</th><th>First</th><th>Last</th><th>Mean</th><th>Min</th><th>Max</th></tr>
</thead>
<tbody>
{''.join(country_body)}
</tbody>
</table>
</body>
</html>
"""


def main():
    rows = load_rows()
    countries = countries_in_order(rows)
    all_names = [country for _iso, country, _group in countries]

    pooled = []
    by_country = []
    for label, kind, column, global_series, paper, note in SPECS:
        points = series_points(rows, kind, column)
        stats = summarize(points, global_series)
        missing = [name for iso, name, _group in countries if iso not in stats["isos"]]
        pooled.append({
            "variable": label,
            "judgment": judgment(paper, stats),
            "paper_mean": "" if paper is None else f"{paper[0]:.2f}",
            "paper_sd": "" if paper is None else f"{paper[1]:.2f}",
            "paper_min": "" if paper is None else f"{paper[2]:.2f}",
            "paper_max": "" if paper is None else f"{paper[3]:.2f}",
            "n": stats["n"],
            "n_countries": stats["n_countries"],
            "first": stats["first"],
            "last": stats["last"],
            "mean": f"{stats['mean']:.10g}",
            "sd": f"{stats['sd']:.10g}",
            "minimum": f"{stats['min']:.10g}",
            "maximum": f"{stats['max']:.10g}",
            "min_where": stats["min_where"],
            "max_where": stats["max_where"],
            "missing_countries": ", ".join(missing),
            "note": note,
        })
        if not global_series:
            by_country.extend(country_rows(points, countries, label))
        print(
            judgment(paper, stats), "|", label,
            "| n", stats["n"], "countries", f"{stats['n_countries']}/{len(all_names)}",
            "|", stats["first"], stats["last"],
            "| mean", fmt(stats["mean"]), "sd", fmt(stats["sd"]),
            "| min", fmt(stats["min"]), "at", stats["min_where"],
            "| max", fmt(stats["max"]), "at", stats["max_where"],
            "| missing", ", ".join(missing) or "none",
        )

    pooled_fields = [
        "variable", "judgment", "paper_mean", "paper_sd", "paper_min", "paper_max",
        "n", "n_countries", "first", "last", "mean", "sd", "minimum", "maximum",
        "min_where", "max_where", "missing_countries", "note",
    ]
    country_fields = [
        "country", "group", "variable", "n", "first", "last", "mean", "minimum", "maximum",
    ]
    write_csv(os.path.join(OUTPUT, "replication_cleaned_vs_table1.csv"), pooled, pooled_fields)
    write_csv(os.path.join(OUTPUT, "replication_cleaned_by_country.csv"), by_country, country_fields)
    html_path = os.path.join(OUTPUT, "replication_cleaned_vs_table1.html")
    with open(html_path, "w", encoding="utf-8") as handle:
        handle.write(html_page(pooled, by_country))
    print("wrote", html_path)


if __name__ == "__main__":
    main()
