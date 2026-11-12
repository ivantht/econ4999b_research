"""Summary statistics of cleaned series beside the paper's Table 1.

Every non-missing observation from 2000 through 2023. Global series are one
observation per month. This is not the regression complete case.
"""

import csv
import math
import os
from html import escape

import numpy as np

import run_export_reer_2sls as est


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUTPUT = os.path.join(ROOT, "output")
CLEANED = os.path.join(ROOT, "cleaned")


def in_month(month):
    return "2000-01" <= month <= "2023-12"


def in_year(year):
    return 2000 <= year <= 2023


def moments(values):
    array = np.asarray(list(values), dtype=float)
    array = array[np.isfinite(array)]
    if len(array) == 0:
        return None
    return {
        "n": int(len(array)),
        "mean": float(array.mean()),
        "sd": float(array.std(ddof=1)) if len(array) > 1 else float("nan"),
        "min": float(array.min()),
        "max": float(array.max()),
    }


def flatten_country_month(series, transform=None):
    values = []
    for country_months in series.values():
        for month, value in country_months.items():
            if not in_month(month):
                continue
            if transform is not None:
                value = transform(value)
            if value is not None:
                values.append(value)
    return values


def flatten_country_year(series, transform=None):
    values = []
    for country_years in series.values():
        for year, value in country_years.items():
            if not in_year(year):
                continue
            if transform is not None:
                value = transform(value)
            if value is not None:
                values.append(value)
    return values


def global_months(series, transform=None):
    values = []
    for month, value in series.items():
        if not in_month(month):
            continue
        if transform is not None:
            value = transform(value)
        if value is not None:
            values.append(value)
    return values


def read_flows():
    values = []
    path = os.path.join(CLEANED, "capital_flow.csv")
    with open(path, encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if not ("2000-Q1" <= row["year_quarter"] <= "2023-Q4"):
                continue
            text = (row.get("usd_millions") or "").strip()
            if text:
                values.append(float(text))
    return values


def read_gpr_country():
    values = []
    path = os.path.join(CLEANED, "gpr_country.csv")
    with open(path, encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if not in_month(row["year_month"]):
                continue
            text = (row.get("value") or "").strip()
            if text:
                values.append(float(text))
    return values


def collect():
    reer = flatten_country_month(est.read_reer(), est.positive_log)
    policy = flatten_country_month(est.read_monthly_country("policy_rate.csv", "value"))
    ip = flatten_country_year(
        est.read_annual("industrial_production.csv", "year", "index"),
        est.positive_log,
    )
    inflation = flatten_country_month(est.read_monthly_country("inflation.csv", "value"))
    oil = global_months(est.read_monthly_global("oil_price.csv", "wti_spot"), est.positive_log)
    vix = global_months(est.read_monthly_global("vix.csv", "value"))
    vix_log = global_months(est.read_monthly_global("vix.csv", "value"), est.positive_log)
    gepu = global_months(est.read_monthly_global("gepu_current.csv", "value"))
    fd = flatten_country_year(est.read_annual("financial_development.csv", "year", "fd_fdi_ovrl"))
    debt = flatten_country_year(est.read_annual("debt_gdp.csv", "period", "debt_gdp_pct", frequency="Annual"))
    gpr_global = global_months(est.read_monthly_global("gpr_index.csv", "value", series="GPR"))
    return {
        "capital_flow": moments(read_flows()),
        "reer": moments(reer),
        "gpr_country": moments(read_gpr_country()),
        "gpr_global": moments(gpr_global),
        "policy": moments(policy),
        "ip": moments(ip),
        "inflation": moments(inflation),
        "oil": moments(oil),
        "vix": moments(vix),
        "vix_log": moments(vix_log),
        "gepu": moments(gepu),
        "fd": moments(fd),
        "debt": moments(debt),
    }


PAPER = {
    "capital_flow": (7.22, 19.62, 0.0, 528.40),
    "stocks": (4.32, 0.47, 2.37, 5.46),
    "bonds": (4.74, 3.63, -0.65, 42.18),
    "reer": (4.64, 0.18, 3.61, 5.23),
    "gpr": (0.22, 0.52, 0.0, 13.23),
    "policy": (4.37, 4.87, -0.75, 57.0),
    "ip": (4.58, 0.31, 2.29, 5.81),
    "inflation": (4.06, 6.18, -4.43, 85.51),
    "oil": (3.73, 0.63, 2.42, 4.90),
    "vix": (19.59, 7.54, 10.13, 62.67),
    "gepu": (140.26, 74.91, 49.23, 431.73),
    "fd": (0.60, 0.19, 0.11, 0.93),
    "cbi": (0.66, 0.19, 0.14, 0.93),
    "debt": (68.77, 36.40, 11.82, 216.33),
}


def rows_for(stats):
    """Each item is paper label, paper key or None, our stats or None, judgment, note."""
    return [
        ("Capital flow volatility (SD)", "capital_flow", stats["capital_flow"], "a different variable",
         "Cleaned file is the quarterly dollar flow, not a 3-month standard deviation of portfolio inflows."),
        ("Real stock prices (log)", "stocks", None, "not in cleaned",
         "No stock-price series in cleaned."),
        ("Long-term bond yield (%)", "bonds", None, "not in cleaned",
         "No bond-yield series in cleaned."),
        ("Real effective exchange rate (log)", "reer", stats["reer"], None,
         "Log of the cleaned real effective exchange rate."),
        ("Geopolitical risk (index)", "gpr", stats["gpr_country"], None,
         "Raw country article share in gpr_country.csv, restricted here to 2000-2023. The author's regression then standardizes this within each country."),
        ("Geopolitical risk, global index", None, stats["gpr_global"], "a different variable",
         "Series GPR in gpr_index.csv. One global series scaled near 100, not the country article share."),
        ("Policy rate (%)", "policy", stats["policy"], None,
         "Monthly policy rate."),
        ("Real industrial production (log)", "ip", stats["ip"], "a different variable",
         "Cleaned index is annual. The paper's row is the log of a monthly index."),
        ("Inflation (%)", "inflation", stats["inflation"], None,
         "Monthly year-on-year inflation."),
        ("Oil price (log)", "oil", stats["oil"], None,
         "Log of the monthly WTI spot price. One observation per month."),
        ("VIX, level", "vix", stats["vix"], None,
         "Table 1 is labeled log, but its mean of 19.59 and maximum of 62.67 are the level. One observation per month."),
        ("VIX, log", "vix", stats["vix_log"], "a different variable",
         "Natural log of the cleaned VIX. These moments are not the numbers printed in Table 1."),
        ("Global economic policy uncertainty (index)", "gepu", stats["gepu"], None,
         "GEPU current index, the level. One observation per month."),
        ("Financial development (index)", "fd", stats["fd"], "a different variable",
         "Column fd_fdi_ovrl. The paper uses the IMF index on a 0-to-1 scale."),
        ("Central bank independence (index)", "cbi", None, "not in cleaned",
         "Romelli's index is not in cleaned."),
        ("Public debt to GDP (%)", "debt", stats["debt"], None,
         "Annual general-government gross debt as a percent of GDP."),
    ]


def judgment(preset, paper_key, ours):
    if preset:
        return preset
    if ours is None or paper_key is None:
        return "not in cleaned"
    paper_mean, paper_sd, _, _ = PAPER[paper_key]
    if paper_mean == 0 or paper_sd == 0:
        return "close to the same series"
    mean_gap = abs(ours["mean"] - paper_mean) / abs(paper_mean)
    sd_gap = abs(ours["sd"] - paper_sd) / abs(paper_sd)
    if mean_gap <= 0.25 and sd_gap <= 0.35:
        return "close to the same series"
    return "same concept, moments differ"


def fmt(value):
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return ""
    return f"{value:.2f}"


def write_outputs(path_csv, path_html, stats):
    fields = [
        "variable", "judgment",
        "paper_mean", "paper_sd", "paper_min", "paper_max",
        "n", "our_mean", "our_sd", "our_min", "our_max", "note",
    ]
    records = []
    for label, paper_key, ours, preset, note in rows_for(stats):
        paper = PAPER[paper_key] if paper_key else None
        records.append({
            "variable": label,
            "judgment": judgment(preset, paper_key, ours),
            "paper_mean": "" if paper is None else f"{paper[0]:.2f}",
            "paper_sd": "" if paper is None else f"{paper[1]:.2f}",
            "paper_min": "" if paper is None else f"{paper[2]:.2f}",
            "paper_max": "" if paper is None else f"{paper[3]:.2f}",
            "n": "" if ours is None else ours["n"],
            "our_mean": "" if ours is None else f"{ours['mean']:.10g}",
            "our_sd": "" if ours is None else f"{ours['sd']:.10g}",
            "our_min": "" if ours is None else f"{ours['min']:.10g}",
            "our_max": "" if ours is None else f"{ours['max']:.10g}",
            "note": note,
        })
    with open(path_csv, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)

    body = []
    for record in records:
        body.append(
            "<tr>"
            f"<td>{escape(record['variable'])}</td>"
            f"<td>{escape(record['judgment'])}</td>"
            f"<td>{escape(record['paper_mean'])}</td><td>{escape(record['paper_sd'])}</td>"
            f"<td>{escape(record['paper_min'])}</td><td>{escape(record['paper_max'])}</td>"
            f"<td>{escape(str(record['n']))}</td>"
            f"<td>{escape(fmt(float(record['our_mean'])) if record['our_mean'] else '')}</td>"
            f"<td>{escape(fmt(float(record['our_sd'])) if record['our_sd'] else '')}</td>"
            f"<td>{escape(fmt(float(record['our_min'])) if record['our_min'] else '')}</td>"
            f"<td>{escape(fmt(float(record['our_max'])) if record['our_max'] else '')}</td>"
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
<title>Cleaned series and Table 1</title>
<style>
body {{ font: 16px/1.5 Georgia, serif; max-width: 1100px; margin: 2em auto; padding: 0 1em; color: #20242a; }}
table {{ border-collapse: collapse; width: 100%; margin: 1em 0; font-size: .86em; }}
th, td {{ border-bottom: 1px solid #ccc; padding: .4em; text-align: right; vertical-align: top; }}
th:nth-child(-n+2), td:nth-child(-n+2) {{ text-align: left; }}
.note {{ background: #fff5da; padding: 1em; border: 1px solid #e6d59d; }}
</style>
</head>
<body>
<h1>Cleaned series beside Table 1</h1>
<div class="note">
<p>Cleaned moments use every non-missing observation from 2000 through 2023. The paper's moments are for 29 countries. Global series are one observation per month, so their means are not weighted by the number of countries.</p>
<p>A row marked "a different variable" cannot be the source of a coefficient gap inside the same regression, because it is not the series the paper used. A row marked "close to the same series" can. "Same concept, moments differ" means the definition matches and the 17-country window does not reproduce the published moments.</p>
</div>
<table>
<thead>
<tr><th>Variable</th><th>Judgment</th><th>Paper mean</th><th>Paper SD</th><th>Paper min</th><th>Paper max</th><th>N</th><th>Our mean</th><th>Our SD</th><th>Our min</th><th>Our max</th></tr>
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
    with open(path_html, "w", encoding="utf-8") as handle:
        handle.write(html)
    for record in records:
        print(
            record["judgment"], "|", record["variable"],
            "| paper", record["paper_mean"],
            "| ours", record["our_mean"], record["our_sd"],
            "| n", record["n"],
        )


def main():
    write_outputs(
        os.path.join(OUTPUT, "cleaned_vs_paper_summary.csv"),
        os.path.join(OUTPUT, "cleaned_vs_paper_summary.html"),
        collect(),
    )


if __name__ == "__main__":
    main()
