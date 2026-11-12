"""Summary statistics of the literature-review panel beside the author's Table 1.

Each moment uses every non-missing value in the panel. Global series are
repeated once per country-month, as they are in a panel summary.
"""

import csv
import math
import os
from html import escape

import numpy as np


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PANEL = os.path.join(
    ROOT, "econ4999b_literature_review", "replication", "output", "panel.csv"
)
OUTPUT = os.path.join(ROOT, "output")

# label, panel column, paper mean, sd, min, max, note
ROWS = [
    ("Capital flow volatility (SD)", "cf_vol", 7.22, 19.62, 0.0, 528.40,
     "3-month standard deviation of portfolio inflows, in billion dollars. This is the volatility outcome."),
    ("Stock prices (log)", "nominal_stock", 4.32, 0.47, 2.37, 5.46,
     "Log of the nominal equity index. The CPI-deflated series used in a stock regression has mean about -0.25, so it is not the Table 1 row."),
    ("Long-term bond yield (%)", "bond", 4.74, 3.63, -0.65, 42.18,
     "Long-term government bond yield."),
    ("Real effective exchange rate (log)", "ln_reer", 4.64, 0.18, 3.61, 5.23,
     "Log of the BIS broad real effective exchange rate."),
    ("Geopolitical risk (index)", "gpr", 0.22, 0.52, 0.0, 13.23,
     "Raw country article share, the series printed in Table 1. The regression standardizes this within each country, which gives mean 0 and standard deviation 1."),
    ("Policy rate (%)", "rate", 4.37, 4.87, -0.75, 57.0,
     "BIS policy rate."),
    ("Real industrial production (log)", "ln_ip", 4.58, 0.31, 2.29, 5.81,
     "Log of the monthly industrial-production index."),
    ("Inflation (%)", "infl", 4.06, 6.18, -4.43, 85.51,
     "Year-on-year CPI inflation."),
    ("Oil price (log)", "real_oil", 3.73, 0.63, 2.42, 4.90,
     "Log of the oil price deflated by US CPI, with January 2000 as the base. The regression uses the nominal log, whose mean is about 4.05."),
    ("VIX, level", "vix", 19.59, 7.54, 10.13, 62.67,
     "Table 1 is labeled log, but the printed numbers are the VIX level."),
    ("Global economic policy uncertainty (index)", "gepu", 140.26, 74.91, 49.23, 431.73,
     "GEPU current index, the level, repeated for every country in a month."),
    ("Financial development (index)", "fd", 0.60, 0.19, 0.11, 0.93,
     "IMF financial-development index, 0 to 1."),
    ("Central bank independence (index)", "cbi", 0.66, 0.19, 0.14, 0.93,
     "Romelli central-bank independence index."),
    ("Public debt to GDP (%)", "debt", 68.77, 36.40, 11.82, 216.33,
     "General-government gross debt as a percent of GDP."),
]


def moments(values):
    array = np.asarray(values, dtype=float)
    return {
        "n": int(len(array)),
        "mean": float(array.mean()),
        "sd": float(array.std(ddof=1)),
        "min": float(array.min()),
        "max": float(array.max()),
    }


def judgment(ours, paper_mean, paper_sd):
    if paper_mean == 0 or paper_sd == 0:
        return "close to the author's series"
    mean_gap = abs(ours["mean"] - paper_mean) / abs(paper_mean)
    sd_gap = abs(ours["sd"] - paper_sd) / abs(paper_sd)
    if mean_gap <= 0.15 and sd_gap <= 0.25:
        return "close to the author's series"
    return "same concept, moments differ"


def fmt(value):
    if value is None or not math.isfinite(value):
        return ""
    return f"{value:.2f}"


def number(text):
    text = (text or "").strip()
    return float(text) if text else None


def main():
    rows = list(csv.DictReader(open(PANEL, encoding="utf-8", newline="")))
    us_cpi = {}
    for row in rows:
        if row["iso"] == "US":
            cpi = number(row["PCPI_IX"])
            if cpi is not None:
                us_cpi[row["date"]] = cpi
    cpi_base = us_cpi["2000-01-01"]

    columns = {spec[1]: [] for spec in ROWS}
    nominal_stock = []
    real_oil = []
    for row in rows:
        for column in columns:
            value = number(row.get(column))
            if value is not None:
                columns[column].append(value)
        share = number(row["share_oecd"])
        if share is None:
            share = number(row["FPE_IX"])
        if share is not None and share > 0:
            nominal_stock.append(math.log(share))
        oil = number(row["oil"])
        cpi = us_cpi.get(row["date"])
        if oil is not None and oil > 0 and cpi:
            real_oil.append(math.log(oil / (cpi / cpi_base)))
    columns["nominal_stock"] = nominal_stock
    columns["real_oil"] = real_oil

    records = []
    for label, column, paper_mean, paper_sd, paper_min, paper_max, note in ROWS:
        ours = moments(columns[column])
        records.append({
            "variable": label,
            "judgment": judgment(ours, paper_mean, paper_sd),
            "paper_mean": f"{paper_mean:.2f}",
            "paper_sd": f"{paper_sd:.2f}",
            "paper_min": f"{paper_min:.2f}",
            "paper_max": f"{paper_max:.2f}",
            "n": ours["n"],
            "our_mean": f"{ours['mean']:.10g}",
            "our_sd": f"{ours['sd']:.10g}",
            "our_min": f"{ours['min']:.10g}",
            "our_max": f"{ours['max']:.10g}",
            "note": note,
        })

    fields = [
        "variable", "judgment", "paper_mean", "paper_sd", "paper_min", "paper_max",
        "n", "our_mean", "our_sd", "our_min", "our_max", "note",
    ]
    csv_path = os.path.join(OUTPUT, "author_panel_vs_table1.csv")
    with open(csv_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)

    body = []
    for record in records:
        body.append(
            "<tr>"
            f"<td>{escape(record['variable'])}</td>"
            f"<td>{escape(record['judgment'])}</td>"
            f"<td>{record['paper_mean']}</td><td>{record['paper_sd']}</td>"
            f"<td>{record['paper_min']}</td><td>{record['paper_max']}</td>"
            f"<td>{record['n']}</td>"
            f"<td>{fmt(float(record['our_mean']))}</td>"
            f"<td>{fmt(float(record['our_sd']))}</td>"
            f"<td>{fmt(float(record['our_min']))}</td>"
            f"<td>{fmt(float(record['our_max']))}</td>"
            "</tr>"
        )
    notes = "".join(
        f"<li><strong>{escape(record['variable'])}.</strong> {escape(record['note'])}</li>"
        for record in records
    )
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Panel summary and Table 1</title>
<style>
body {{ font: 16px/1.5 Georgia, serif; max-width: 1100px; margin: 2em auto; padding: 0 1em; color: #20242a; }}
table {{ border-collapse: collapse; width: 100%; margin: 1em 0; font-size: .86em; }}
th, td {{ border-bottom: 1px solid #ccc; padding: .4em; text-align: right; vertical-align: top; }}
th:nth-child(-n+2), td:nth-child(-n+2) {{ text-align: left; }}
.note {{ background: #fff5da; padding: 1em; border: 1px solid #e6d59d; }}
</style>
</head>
<body>
<h1>Literature-review panel beside Table 1</h1>
<div class="note">
<p>These moments use every non-missing value in the literature-review panel, the dataset behind the exchange-rate and capital-flow-volatility regressions. VIX and global EPU are repeated once for each country in a month. Stock prices are the log of the nominal index, which is the scale of Table 1. Oil is deflated by the US consumer price index. The regression itself uses the raw geopolitical-risk share after standardizing it within each country, and it uses the nominal log oil price.</p>
</div>
<table>
<thead>
<tr><th>Variable</th><th>Judgment</th><th>Author mean</th><th>Author SD</th><th>Author min</th><th>Author max</th><th>N</th><th>Panel mean</th><th>Panel SD</th><th>Panel min</th><th>Panel max</th></tr>
</thead>
<tbody>
{''.join(body)}
</tbody>
</table>
<h2>What each row is</h2>
<ul>
{notes}
</ul>
</body>
</html>
"""
    html_path = os.path.join(OUTPUT, "author_panel_vs_table1.html")
    with open(html_path, "w", encoding="utf-8") as handle:
        handle.write(html)
    for record in records:
        print(
            record["judgment"], "|", record["variable"],
            "| author", record["paper_mean"], record["paper_sd"],
            "| panel", fmt(float(record["our_mean"])), fmt(float(record["our_sd"])),
            "| n", record["n"],
        )


if __name__ == "__main__":
    main()
