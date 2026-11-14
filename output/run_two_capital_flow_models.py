"""Two capital-flow regressions on the replication countries except Ukraine, Thailand, and China.

Model 1 is the paper's capital-flow-volatility equation plus one WGI dimension
and its interaction with GPR. The outcome is the three-month standard deviation
divided by that country's average absolute portfolio inflow. Industrial
production and central-bank independence are left out because they are not in
the requested regressor list.

Model 2 uses the same regressors. The outcome is the year-over-year percent
change of portfolio inflows. Portfolio inflows change sign, so the percent
change uses the midpoint of the absolute flows. The percent is not logged and
is not replaced by its straight-line trend.
"""

import csv
import os
from collections import defaultdict
from html import escape

import numpy as np

import run_export_reer_2sls as est


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUTPUT = os.path.join(ROOT, "output")
CLEANED = os.path.join(ROOT, "cleaned")
PANEL = os.path.join(CLEANED, "replication_cleaned", "country_month.csv")
PERCENT_PATH = os.path.join(CLEANED, "portfolio_inflow_yoy_percent.csv")

PANEL_NAME = {"Turkiye": "Turkey", "Korea": "South Korea"}
DROP = {"Ukraine", "Thailand", "China"}
DIMENSIONS = [
    ("rl", "Rule of law"),
    ("ge", "Government effectiveness"),
    ("rq", "Regulatory quality"),
]
COLUMNS = [
    "gpr", "wgi_l1", "wgi_x_gpr",
    "policy_rate_l1", "inflation_l1", "log_oil_l1", "log_vix_l1", "log_gepu_l1",
    "financial_development_l1", "debt_gdp_l1",
]
LABELS = {
    "gpr": "GPR",
    "wgi_l1": "WGI",
    "wgi_x_gpr": "WGI x GPR",
    "policy_rate_l1": "Policy rate",
    "inflation_l1": "Inflation",
    "log_oil_l1": "Oil price",
    "log_vix_l1": "VIX",
    "log_gepu_l1": "Global EPU",
    "financial_development_l1": "Financial development",
    "debt_gdp_l1": "Debt/GDP",
}
NEEDED = [
    "outcome", "gpr_raw", "wgi_raw",
    "policy_rate_l1", "inflation_l1", "log_oil_l1", "log_vix_l1", "log_gepu_l1",
    "financial_development_l1", "debt_gdp_l1",
]
EQUATION = (
    "Y = GPR + lagged policy rate + lagged inflation + lagged log oil "
    "+ lagged log VIX + lagged log global EPU + lagged financial development "
    "+ lagged debt/GDP + lagged WGI + lagged WGI x GPR + country effects"
)


def num(text):
    if text is None:
        return None
    text = str(text).strip()
    if not text:
        return None
    return float(text)


def contiguous_stretches(months):
    stretches = []
    current = []
    for month in months:
        if current and month != est.add_months(current[-1], 1):
            stretches.append(current)
            current = []
        current.append(month)
    if current:
        stretches.append(current)
    return stretches


def symmetric_percent(current, earlier):
    scale = (abs(current) + abs(earlier)) / 2.0
    if scale == 0:
        return None
    return 100.0 * (current - earlier) / scale


def load_panel():
    index = {}
    countries = []
    seen = set()
    with open(PANEL, encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            country = PANEL_NAME.get(row["country"].strip(), row["country"].strip())
            index[(country, row["date"][:7])] = row
            if country not in seen:
                seen.add(country)
                countries.append(country)
    return index, countries


def write_series(path, column, rows):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["country", "year_month", column])
        for country, month, value in rows:
            writer.writerow([country, month, f"{value:.16g}"])


def inflow_levels(index, country):
    levels = {}
    for (name, month), source in index.items():
        if name != country:
            continue
        value = num(source.get("portfolio_inflow"))
        if value is not None:
            levels[month] = value
    return levels


def average_absolute_inflow(index, countries):
    scales = {}
    for country in countries:
        levels = inflow_levels(index, country)
        if not levels:
            continue
        total = sum(abs(value) for value in levels.values())
        if total > 0:
            scales[country] = total / len(levels)
    return scales


def percent_changes(levels):
    growth = {}
    for month, value in levels.items():
        earlier = levels.get(est.add_months(month, -12))
        if earlier is None:
            continue
        change = symmetric_percent(value, earlier)
        if change is not None:
            growth[month] = change
    return growth


def write_percent_file(index, countries):
    rows = []
    notes = []
    for country in countries:
        growth = percent_changes(inflow_levels(index, country))
        for month in sorted(growth):
            rows.append((country, month, growth[month]))
        for stretch in contiguous_stretches(sorted(growth)):
            notes.append(f"{country} {stretch[0]} to {stretch[-1]}: {len(stretch)} months")
        if not growth:
            notes.append(f"{country}: no year-over-year percent change")
    write_series(PERCENT_PATH, "percent", rows)
    return notes


def load_percent():
    out = defaultdict(dict)
    with open(PERCENT_PATH, encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            out[row["country"].strip()][row["year_month"].strip()] = float(row["percent"])
    return out


def lagged_controls(source):
    if source is None:
        return {name: None for name in (
            "policy_rate_l1", "inflation_l1", "log_oil_l1", "log_vix_l1",
            "log_gepu_l1", "financial_development_l1", "debt_gdp_l1",
        )}
    return {
        "policy_rate_l1": num(source.get("policy_rate")),
        "inflation_l1": num(source.get("inflation")),
        "log_oil_l1": est.positive_log(num(source.get("oil_price"))),
        "log_vix_l1": est.positive_log(num(source.get("vix"))),
        "log_gepu_l1": est.positive_log(num(source.get("gepu"))),
        "financial_development_l1": num(source.get("financial_development")),
        "debt_gdp_l1": num(source.get("public_debt_gdp")),
    }


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


def collect(index, countries, wgi, outcome_for):
    rows = []
    present = []
    for country in countries:
        if country in DROP:
            continue
        country_rows = []
        for (name, month), source in index.items():
            if name != country:
                continue
            lag = est.add_months(month, -1)
            record = {
                "country": country,
                "year_month": month,
                "outcome": outcome_for(country, month, source),
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


def drop_list(countries, present):
    dropped = []
    for country in countries:
        if country in DROP:
            dropped.append((country, "dropped by request"))
        elif country not in present:
            dropped.append((country, "no month with every required series"))
    return dropped


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
    matrix, names, base = est.design_matrix(rows, COLUMNS, countries)
    count, width = matrix.shape
    grouped = est.cluster_indices(rows)
    coefficient = np.linalg.lstsq(matrix, outcome, rcond=None)[0]
    residual = outcome - matrix @ coefficient
    variance, _ = est.cluster_variance(matrix, residual, grouped, count, width)
    return {
        "stats": est.inference(names, coefficient, variance, len(grouped)),
        "base": base,
        "sample": sample_info(rows),
        "center": float(np.mean([row["wgi_raw"] for row in rows])),
    }


def stat_fields(stat):
    return {key: f"{stat[key]:.10g}" for key in ("coef", "se", "t", "p", "ci_lo", "ci_hi")}


def write_csv(path, blocks):
    fields = [
        "model", "outcome", "dimension", "dimension_label", "variable", "label",
        "coef", "se", "t", "p", "ci_lo", "ci_hi",
        "n_obs", "n_country", "month_min", "month_max", "countries", "dropped",
        "wgi_center",
    ]
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for block in blocks:
            for code, label, fitted in block["results"]:
                shared = {
                    "model": block["model"],
                    "outcome": block["outcome"],
                    "dimension": code,
                    "dimension_label": label,
                    "n_obs": fitted["sample"]["n_obs"],
                    "n_country": fitted["sample"]["n_country"],
                    "month_min": fitted["sample"]["month_min"],
                    "month_max": fitted["sample"]["month_max"],
                    "countries": "; ".join(fitted["sample"]["countries"]),
                    "dropped": "; ".join(
                        f"{country}: {reason}" for country, reason in block["dropped"]
                    ),
                    "wgi_center": f"{fitted['center']:.10g}",
                }
                for variable in COLUMNS:
                    writer.writerow({
                        **shared,
                        "variable": variable,
                        "label": LABELS[variable],
                        **stat_fields(fitted["stats"][variable]),
                    })


def cell(stat):
    return (
        f"{est.fmt(stat['coef'])}{est.stars(stat['p'])}<br>"
        f"({est.fmt(stat['se'])})<br>"
        f"[{est.fmt(stat['ci_lo'])}, {est.fmt(stat['ci_hi'])}]"
    )


def write_html(path, blocks, notes):
    parts = []
    for block in blocks:
        header = "".join(f"<th>{escape(label)}</th>" for _, label, _ in block["results"])
        body = []
        for variable in COLUMNS:
            cells = "".join(
                f"<td>{cell(fitted['stats'][variable])}</td>"
                for _, _, fitted in block["results"]
            )
            body.append(f"<tr><td>{escape(LABELS[variable])}</td>{cells}</tr>")
        sample = "".join(
            "<td>{n}<br>{g} countries<br>{start} to {end}<br>WGI center {center}</td>".format(
                n=fitted["sample"]["n_obs"],
                g=fitted["sample"]["n_country"],
                start=escape(fitted["sample"]["month_min"]),
                end=escape(fitted["sample"]["month_max"]),
                center=est.fmt(fitted["center"]),
            )
            for _, _, fitted in block["results"]
        )
        kept = "".join(
            f"<li>{escape(label)}: {escape(', '.join(fitted['sample']['countries']))}</li>"
            for _, label, fitted in block["results"]
        )
        dropped = "".join(
            f"<li>{escape(country)}: {escape(reason)}</li>"
            for country, reason in block["dropped"]
        )
        parts.append(
            f"<h2>{escape(block['title'])}</h2>"
            f"<p><strong>Outcome:</strong> {escape(block['outcome'])}</p>"
            f"<p class=\"equation\">{escape(block['equation'])}</p>"
            "<table><thead><tr><th>Variable</th>"
            f"{header}</tr></thead><tbody>{''.join(body)}"
            f"<tr><td>Observations</td>{sample}</tr></tbody></table>"
            "<h3>Countries that remain</h3><ul>"
            f"{kept}</ul><h3>Countries that drop</h3><ul>{dropped}</ul>"
        )
    stretches = "".join(f"<li>{escape(note)}</li>" for note in notes)
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Two capital-flow models</title>
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
<h1>Two capital-flow models</h1>
<div class="note">
<p>Ukraine, Thailand, and China are dropped. GPR is contemporaneous and standardized within country. The other controls, including WGI, use the previous month. WGI is the calendar year of that month, and a year missing from the file stays blank. WGI is centered before it is multiplied by GPR, so the GPR coefficient is the effect at average WGI. Oil, VIX, and global EPU are logged. Each cell shows the coefficient, the country-clustered standard error in parentheses, and the 95% confidence interval. *** p&lt;0.01, ** p&lt;0.05, * p&lt;0.10.</p>
<p>Model 1 copies the paper's capital-flow-volatility regression. The outcome is the three-month standard deviation of portfolio inflows divided by that country's average absolute portfolio inflow. The average uses every non-missing inflow, so it is a country constant, and a blank inflow stays out of the average. The unit is the country's typical monthly inflow. Industrial production and central-bank independence are in the paper's equation and are left out here because they are not in the requested regressor list.</p>
<p>Model 2 uses the year-over-year percent change of the same portfolio inflows, not the straight line fitted to that percent. Because a flow can change sign, the percent is 100 times the change divided by the average of the two absolute flows. A missing lag, or a zero denominator, stays blank. The percent is not logged. A positive coefficient means the flow moves toward a larger inflow. A positive WGI interaction means a higher score offsets the GPR effect.</p>
</div>
{''.join(parts)}
<h2>Prepared year-over-year percent changes</h2>
<ul>{stretches}</ul>
</body>
</html>
"""
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(html)


def run_model(title, model, outcome_name, index, countries, outcome_for):
    results = []
    present = None
    for code, label in DIMENSIONS:
        rows, kept, _center = collect(index, countries, est.read_wgi(code), outcome_for)
        fitted = fit_ols(rows)
        results.append((code, label, fitted))
        if present is None:
            present = kept
        print(
            title, label, "N", fitted["sample"]["n_obs"],
            fitted["sample"]["n_country"],
            fitted["sample"]["month_min"], fitted["sample"]["month_max"],
        )
        for variable in ("gpr", "wgi_l1", "wgi_x_gpr"):
            stat = fitted["stats"][variable]
            print(
                " ", variable, round(stat["coef"], 4),
                "p", round(stat["p"], 4), est.stars(stat["p"]),
            )
    return {
        "title": title,
        "model": model,
        "outcome": outcome_name,
        "equation": EQUATION,
        "results": results,
        "dropped": drop_list(countries, present),
    }


def main():
    index, countries = load_panel()
    scales = average_absolute_inflow(index, countries)
    notes = write_percent_file(index, countries)
    percent = load_percent()

    def scaled_volatility(country, _month, source):
        volatility = num(source.get("capital_flow_volatility"))
        scale = scales.get(country)
        if volatility is None or scale is None:
            return None
        return volatility / scale

    def percent_change(country, month, _source):
        return percent.get(country, {}).get(month)

    blocks = [
        run_model(
            "Model 1. Scaled capital-flow volatility",
            "1",
            "Capital-flow volatility divided by the country's average absolute portfolio inflow",
            index,
            countries,
            scaled_volatility,
        ),
        run_model(
            "Model 2. Capital-flow percent change",
            "2",
            "Year-over-year percent change of portfolio inflows",
            index,
            countries,
            percent_change,
        ),
    ]
    write_csv(os.path.join(OUTPUT, "two_capital_flow_models_results.csv"), blocks)
    write_html(os.path.join(OUTPUT, "two_capital_flow_models_results.html"), blocks, notes)
    for note in notes:
        print(note)


if __name__ == "__main__":
    main()
