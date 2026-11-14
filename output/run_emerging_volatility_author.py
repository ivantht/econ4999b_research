"""Emerging-market capital-flow volatility on the paper's controls plus WGI.

The outcome is the three-month standard deviation of portfolio inflows, in
billion US dollars. The controls are the paper's lagged controls, including
log industrial production and central-bank independence, plus one centered WGI
score and its interaction with GPR. Advanced economies are left out.
"""

import csv
import os
from collections import defaultdict
from html import escape

import numpy as np

import run_export_reer_2sls as est


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUTPUT = os.path.join(ROOT, "output")
PANEL = os.path.join(ROOT, "cleaned", "replication_cleaned", "country_month.csv")

PANEL_NAME = {"Turkiye": "Turkey", "Korea": "South Korea"}
DIMENSIONS = [
    ("rl", "Rule of law"),
    ("ge", "Government effectiveness"),
    ("rq", "Regulatory quality"),
]
COLUMNS = [
    "gpr", "wgi_l1", "wgi_x_gpr",
    "policy_rate_l1", "log_ip_l1", "inflation_l1", "log_oil_l1", "log_vix_l1",
    "log_gepu_l1", "financial_development_l1", "cbi_l1", "debt_gdp_l1",
]
LABELS = {
    "gpr": "GPR",
    "wgi_l1": "WGI",
    "wgi_x_gpr": "WGI x GPR",
    "policy_rate_l1": "Policy rate",
    "log_ip_l1": "Real industrial production",
    "inflation_l1": "Inflation",
    "log_oil_l1": "Oil price",
    "log_vix_l1": "VIX",
    "log_gepu_l1": "Global EPU",
    "financial_development_l1": "Financial development",
    "cbi_l1": "Central bank independence",
    "debt_gdp_l1": "Debt/GDP",
}
NEEDED = [
    "outcome", "gpr_raw", "wgi_raw",
    "policy_rate_l1", "log_ip_l1", "inflation_l1", "log_oil_l1", "log_vix_l1",
    "log_gepu_l1", "financial_development_l1", "cbi_l1", "debt_gdp_l1",
]
EQUATION = (
    "Capital-flow volatility = GPR + lagged policy rate + lagged log industrial production "
    "+ lagged inflation + lagged log oil + lagged log VIX + lagged log global EPU "
    "+ lagged financial development + lagged central-bank independence + lagged debt/GDP "
    "+ lagged WGI + lagged WGI x GPR + country effects"
)
PAPER_GPR = 0.867
OUTCOME = "Capital-flow volatility, billion US dollars"


def num(text):
    if text is None:
        return None
    text = str(text).strip()
    if not text:
        return None
    return float(text)


def load_panel():
    index = {}
    countries = []
    seen = set()
    with open(PANEL, encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["group"].strip() != "Emerging":
                continue
            country = PANEL_NAME.get(row["country"].strip(), row["country"].strip())
            index[(country, row["date"][:7])] = row
            if country not in seen:
                seen.add(country)
                countries.append(country)
    return index, countries


def lagged_controls(source):
    if source is None:
        return {name: None for name in (
            "policy_rate_l1", "log_ip_l1", "inflation_l1", "log_oil_l1", "log_vix_l1",
            "log_gepu_l1", "financial_development_l1", "cbi_l1", "debt_gdp_l1",
        )}
    return {
        "policy_rate_l1": num(source.get("policy_rate")),
        "log_ip_l1": est.positive_log(num(source.get("industrial_production"))),
        "inflation_l1": num(source.get("inflation")),
        "log_oil_l1": est.positive_log(num(source.get("oil_price"))),
        "log_vix_l1": est.positive_log(num(source.get("vix"))),
        "log_gepu_l1": est.positive_log(num(source.get("gepu"))),
        "financial_development_l1": num(source.get("financial_development")),
        "cbi_l1": num(source.get("central_bank_independence")),
        "debt_gdp_l1": num(source.get("public_debt_gdp")),
    }


def any_filled(index, country, column):
    return any(
        (source.get(column) or "").strip()
        for (name, _month), source in index.items()
        if name == country
    )


def shape_instruments(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["country"]].append(row["gpr_raw"])
    moments = {}
    for country, values in grouped.items():
        array = np.array(values, dtype=float)
        deviation = float(array.std(ddof=1)) if len(array) > 1 else float("nan")
        moments[country] = (float(array.mean()), deviation)
    kept = []
    for row in rows:
        mean, deviation = moments[row["country"]]
        if not np.isfinite(deviation) or deviation == 0:
            continue
        row["gpr"] = (row["gpr_raw"] - mean) / deviation
        kept.append(row)
    if not kept:
        raise RuntimeError("No complete cases after standardizing GPR.")
    center = float(np.mean([row["wgi_raw"] for row in kept]))
    for row in kept:
        row["wgi_l1"] = row["wgi_raw"] - center
        row["wgi_x_gpr"] = row["wgi_l1"] * row["gpr"]
    return kept, center


def collect(index, countries, wgi):
    rows = []
    present = []
    for country in countries:
        country_rows = []
        for (name, month), source in index.items():
            if name != country:
                continue
            lag = est.add_months(month, -1)
            record = {
                "country": country,
                "year_month": month,
                "outcome": num(source.get("capital_flow_volatility")),
                "gpr_raw": num(source.get("gpr")),
                "wgi_raw": wgi.get(country, {}).get(int(lag[:4])),
            }
            record.update(lagged_controls(index.get((country, lag))))
            if any(record.get(name) is None for name in NEEDED):
                continue
            country_rows.append(record)
        if country_rows:
            rows.extend(country_rows)
            present.append(country)
    shaped, center = shape_instruments(rows)
    return shaped, present, center


def drop_reason(index, country):
    if not any_filled(index, country, "industrial_production"):
        return "no industrial production in the replication file"
    if not any_filled(index, country, "policy_rate"):
        return "no policy rate in the replication file"
    return "no month with every required series"


def sample_info(rows):
    countries = []
    seen = set()
    for row in rows:
        if row["country"] not in seen:
            seen.add(row["country"])
            countries.append(row["country"])
    return {
        "countries": countries,
        "n_obs": len(rows),
        "n_country": len(countries),
        "month_min": min(row["year_month"] for row in rows),
        "month_max": max(row["year_month"] for row in rows),
    }


def fit_ols(rows):
    countries = sorted({row["country"] for row in rows})
    outcome = np.array([row["outcome"] for row in rows], dtype=float)
    matrix, names, _base = est.design_matrix(rows, COLUMNS, countries)
    count, width = matrix.shape
    grouped = est.cluster_indices(rows)
    coefficient = np.linalg.lstsq(matrix, outcome, rcond=None)[0]
    residual = outcome - matrix @ coefficient
    variance, _ = est.cluster_variance(matrix, residual, grouped, count, width)
    return {
        "stats": est.inference(names, coefficient, variance, len(grouped)),
        "sample": sample_info(rows),
        "center": float(np.mean([row["wgi_raw"] for row in rows])),
    }


def stat_fields(stat):
    return {key: f"{stat[key]:.10g}" for key in ("coef", "se", "t", "p", "ci_lo", "ci_hi")}


def write_csv(path, results, dropped):
    fields = [
        "dimension", "dimension_label", "variable", "label", "paper_gpr",
        "coef", "se", "t", "p", "ci_lo", "ci_hi",
        "n_obs", "n_country", "month_min", "month_max", "countries", "dropped",
        "wgi_center",
    ]
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for code, label, fitted in results:
            shared = {
                "dimension": code,
                "dimension_label": label,
                "n_obs": fitted["sample"]["n_obs"],
                "n_country": fitted["sample"]["n_country"],
                "month_min": fitted["sample"]["month_min"],
                "month_max": fitted["sample"]["month_max"],
                "countries": "; ".join(fitted["sample"]["countries"]),
                "dropped": "; ".join(f"{country}: {reason}" for country, reason in dropped),
                "wgi_center": f"{fitted['center']:.10g}",
            }
            for variable in COLUMNS:
                writer.writerow({
                    **shared,
                    "variable": variable,
                    "label": LABELS[variable],
                    "paper_gpr": f"{PAPER_GPR:.3f}" if variable == "gpr" else "",
                    **stat_fields(fitted["stats"][variable]),
                })


def cell(stat):
    return (
        f"{est.fmt(stat['coef'])}{est.stars(stat['p'])}<br>"
        f"({est.fmt(stat['se'])})<br>"
        f"[{est.fmt(stat['ci_lo'])}, {est.fmt(stat['ci_hi'])}]"
    )


def write_html(path, results, dropped):
    header = "".join(f"<th>{escape(label)}</th>" for _, label, _ in results)
    body = []
    for variable in COLUMNS:
        cells = "".join(f"<td>{cell(fitted['stats'][variable])}</td>" for _, _, fitted in results)
        reference = ""
        if variable == "gpr":
            reference = "<br>Paper Table 2: 0.867**"
        body.append(f"<tr><td>{escape(LABELS[variable])}{reference}</td>{cells}</tr>")
    sample = "".join(
        "<td>{n}<br>{g} countries<br>{start} to {end}<br>WGI center {center}</td>".format(
            n=fitted["sample"]["n_obs"],
            g=fitted["sample"]["n_country"],
            start=escape(fitted["sample"]["month_min"]),
            end=escape(fitted["sample"]["month_max"]),
            center=est.fmt(fitted["center"]),
        )
        for _, _, fitted in results
    )
    kept = "".join(
        f"<li>{escape(label)}: {escape(', '.join(fitted['sample']['countries']))}</li>"
        for _, label, fitted in results
    )
    dropped_items = "".join(
        f"<li>{escape(country)}: {escape(reason)}</li>" for country, reason in dropped
    )
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Emerging-market capital-flow volatility</title>
<style>
body {{ font: 16px/1.5 Georgia, serif; max-width: 1100px; margin: 2em auto; padding: 0 1em; color: #20242a; }}
table {{ border-collapse: collapse; width: 100%; margin: 1em 0; font-size: .92em; }}
th, td {{ border-bottom: 1px solid #ccc; padding: .45em; text-align: right; vertical-align: top; }}
th:first-child, td:first-child {{ text-align: left; }}
.equation {{ background: #f4f6f8; padding: .8em 1em; }}
.note {{ background: #fff5da; padding: 1em; border: 1px solid #e6d59d; }}
</style>
</head>
<body>
<h1>Emerging-market capital-flow volatility</h1>
<div class="note">
<p>The sample is the emerging economies in the replication file. Advanced economies are out. GPR is contemporaneous and standardized within country. The other controls, including WGI, use the previous month. WGI is the calendar year of that month, and a year missing from the file stays blank. WGI is centered before it is multiplied by GPR. Oil, VIX, global EPU, and industrial production are logged. Each cell shows the coefficient, the country-clustered standard error in parentheses, and the 95% confidence interval. *** p&lt;0.01, ** p&lt;0.05, * p&lt;0.10.</p>
<p>The outcome is the paper's capital-flow volatility: the three-month standard deviation of portfolio inflows, in billion US dollars. It is not divided by the size of the flow. The controls are the paper's lagged controls, including industrial production and central-bank independence, plus one WGI score and its interaction with GPR. Table 2's full-sample GPR coefficient is 0.867 and is shown as a reference. That column has no WGI term and is not limited to emerging markets.</p>
</div>
<h2>Capital-flow volatility</h2>
<p><strong>Outcome:</strong> {escape(OUTCOME)}</p>
<p class="equation">{escape(EQUATION)}</p>
<table><thead><tr><th>Variable</th>{header}</tr></thead>
<tbody>{''.join(body)}<tr><td>Observations</td>{sample}</tr></tbody></table>
<h3>Emerging countries that remain</h3>
<ul>{kept}</ul>
<h3>Emerging countries that drop</h3>
<ul>{dropped_items}</ul>
</body>
</html>
"""
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(html)


def main():
    index, countries = load_panel()
    results = []
    present = None
    for code, label in DIMENSIONS:
        rows, kept, _center = collect(index, countries, est.read_wgi(code))
        fitted = fit_ols(rows)
        results.append((code, label, fitted))
        if present is None:
            present = kept
        print(
            label, "N", fitted["sample"]["n_obs"], fitted["sample"]["n_country"],
            fitted["sample"]["month_min"], fitted["sample"]["month_max"],
        )
        for variable in ("gpr", "wgi_l1", "wgi_x_gpr"):
            stat = fitted["stats"][variable]
            print(
                " ", variable, round(stat["coef"], 4),
                "p", round(stat["p"], 4), est.stars(stat["p"]),
            )
    dropped = [
        (country, drop_reason(index, country))
        for country in countries
        if country not in present
    ]
    write_csv(os.path.join(OUTPUT, "emerging_volatility_author_results.csv"), results, dropped)
    write_html(os.path.join(OUTPUT, "emerging_volatility_author_results.html"), results, dropped)
    for country, reason in dropped:
        print("drop", country, reason)


if __name__ == "__main__":
    main()
