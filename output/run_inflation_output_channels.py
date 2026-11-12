"""Mechanism regressions for inflation and real industrial production.

GPR, lagged WGI, and their interaction are the terms of interest. WGI is
centered on the estimation sample before the interaction is formed. Controls
are lagged. The output equation is annual. These regressions do not replace
the export trend in the exchange-rate 2SLS.
"""

import csv
import math
import os
from html import escape

import numpy as np

import run_export_reer_2sls as est


OUTPUT = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")), "output")

DIMENSIONS = [
    ("rq", "Regulatory quality"),
    ("ge", "Government effectiveness"),
    ("rl", "Rule of law"),
]

INTEREST = ["gpr", "wgi_l1", "wgi_x_gpr"]
INFLATION_CONTROLS = [
    "inflation_l1",
    "policy_rate_l1",
    "log_oil_l1",
    "log_industrial_production_l1",
]
OUTPUT_CONTROLS = [
    "export_change_l1",
    "policy_rate_l1",
    "log_oil_l1",
    "inflation_l1",
]

LABELS = {
    "gpr": "GPR",
    "wgi_l1": "WGI, centered and lagged",
    "wgi_x_gpr": "WGI × GPR",
    "inflation_l1": "Inflation, lagged",
    "policy_rate_l1": "Policy rate, lagged",
    "log_oil_l1": "Log oil price, lagged",
    "log_industrial_production_l1": "Log industrial production, lagged",
    "export_change_l1": "Real export trend change, lagged",
}


def values_in_year(series, year):
    prefix = f"{int(year):04d}-"
    return [series[key] for key in series if str(key).startswith(prefix)]


def mean_in_year(series, year):
    values = values_in_year(series, year)
    if not values:
        return None
    return float(sum(values) / len(values))


def mean_log_in_year(series, year):
    values = [math.log(value) for value in values_in_year(series, year) if value is not None and value > 0]
    if not values:
        return None
    return float(sum(values) / len(values))


def center_wgi(rows):
    center = float(sum(row["wgi_raw"] for row in rows) / len(rows))
    for row in rows:
        row["wgi_l1"] = row["wgi_raw"] - center
        row["wgi_x_gpr"] = row["wgi_l1"] * row["gpr"]
    return center


def build_inflation_rows(sources):
    rows = []
    for country in sources["countries"]:
        for month in sorted(sources["inflation"].get(country, {})):
            lag = est.add_months(month, -1)
            lag_year = int(lag[:4])
            ip = sources["ip"].get(country, {}).get(lag_year)
            record = {
                "country": country,
                "period": month,
                "outcome": sources["inflation"][country][month],
                "gpr": sources["gpr"].get(month),
                "wgi_raw": sources["wgi"].get(country, {}).get(lag_year),
                "inflation_l1": sources["inflation"].get(country, {}).get(lag),
                "policy_rate_l1": sources["policy"].get(country, {}).get(lag),
                "log_oil_l1": est.positive_log(sources["oil"].get(lag)),
                "log_industrial_production_l1": est.positive_log(ip),
            }
            needed = ["outcome", "gpr", "wgi_raw", *INFLATION_CONTROLS]
            if any(record[name] is None for name in needed):
                continue
            rows.append(record)
    return rows


def build_output_rows(sources):
    rows = []
    for country in sources["countries"]:
        for month in sorted(sources["export_change"].get(country, {})):
            lag = est.add_months(month, -1)
            lag_year = int(lag[:4])
            record = {
                "country": country,
                "period": month,
                "outcome": sources["export_change"][country][month],
                "gpr": sources["gpr"].get(month),
                "wgi_raw": sources["wgi"].get(country, {}).get(lag_year),
                "export_change_l1": sources["export_change"].get(country, {}).get(lag),
                "policy_rate_l1": sources["policy"].get(country, {}).get(lag),
                "log_oil_l1": est.positive_log(sources["oil"].get(lag)),
                "inflation_l1": sources["inflation"].get(country, {}).get(lag),
            }
            needed = ["outcome", "gpr", "wgi_raw", *OUTPUT_CONTROLS]
            if any(record[name] is None for name in needed):
                continue
            rows.append(record)
    return rows


def fit_equation(rows, controls):
    countries = sorted({row["country"] for row in rows})
    if len(countries) < 2:
        raise RuntimeError("Need at least two countries for country fixed effects.")
    y = np.array([row["outcome"] for row in rows], dtype=float)
    x_matrix, names, base = est.design_matrix(rows, [*INTEREST, *controls], countries)
    n, k = x_matrix.shape
    if n <= k:
        raise RuntimeError(f"Insufficient observations (N={n}) for {k} parameters.")
    beta = np.linalg.lstsq(x_matrix, y, rcond=None)[0]
    residual = y - x_matrix @ beta
    grouped = est.cluster_indices(rows)
    variance, _ = est.cluster_variance(x_matrix, residual, grouped, n, k)
    stats = est.inference(names, beta, variance, len(grouped))
    sst = float(np.sum((y - np.mean(y)) ** 2))
    r2 = float(1.0 - np.sum(residual**2) / sst) if sst > 0 else float("nan")
    return {
        "countries": countries,
        "base_country": base,
        "n_obs": n,
        "n_country": len(grouped),
        "df": len(grouped) - 1,
        "period_min": min(row["period"] for row in rows),
        "period_max": max(row["period"] for row in rows),
        "r2": r2,
        "stats": stats,
    }


def load_sources():
    return {
        "countries": est.read_country_order(),
        "inflation": est.read_monthly_country("inflation.csv", "value"),
        "policy": est.read_monthly_country("policy_rate.csv", "value"),
        "oil": est.read_monthly_global("oil_price.csv", "wti_spot"),
        "gpr": est.read_monthly_global("gpr_index.csv", "value", series="GPR"),
        "ip": est.read_annual("industrial_production.csv", "year", "index"),
        "export_change": est.read_monthly_country("real_export_hp_trend_change.csv", "log_change"),
    }


def stat_fields(stat):
    return {key: f"{stat[key]:.10g}" for key in ("coef", "se", "t", "p", "ci_lo", "ci_hi")}


def write_csv(path, results):
    fields = [
        "equation", "dimension", "dimension_label", "variable", "label",
        "coef", "se", "t", "p", "ci_lo", "ci_hi",
        "n_obs", "n_country", "df", "r2", "wgi_center",
        "period_min", "period_max", "countries",
    ]
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for equation, code, label, fit, controls in results:
            shared = {
                "equation": equation,
                "dimension": code,
                "dimension_label": label,
                "n_obs": fit["n_obs"],
                "n_country": fit["n_country"],
                "df": fit["df"],
                "r2": f"{fit['r2']:.10g}",
                "wgi_center": f"{fit['wgi_center']:.10g}",
                "period_min": fit["period_min"],
                "period_max": fit["period_max"],
                "countries": "; ".join(fit["countries"]),
            }
            for variable in [*INTEREST, *controls]:
                writer.writerow({
                    **shared,
                    "variable": variable,
                    "label": LABELS[variable],
                    **stat_fields(fit["stats"][variable]),
                })


def cell(stat):
    return (
        f"{est.fmt(stat['coef'])}{est.stars(stat['p'])}<br>"
        f"({est.fmt(stat['se'])})"
    )


def equation_table(title, note, rows_for_equation, controls):
    header = "".join(f"<th>{escape(label)}</th>" for _, _, label, _, _ in rows_for_equation)
    body = []
    for variable in [*INTEREST, *controls]:
        cells = "".join(f"<td>{cell(fit['stats'][variable])}</td>" for _, _, _, fit, _ in rows_for_equation)
        body.append(f"<tr><td>{escape(LABELS[variable])}</td>{cells}</tr>")
    sample = "".join(
        f"<td>{fit['n_obs']}<br>{fit['n_country']} countries<br>"
        f"{escape(fit['period_min'])} to {escape(fit['period_max'])}<br>"
        f"R² {est.fmt(fit['r2'])}</td>"
        for _, _, _, fit, _ in rows_for_equation
    )
    countries = "".join(
        f"<li>{escape(label)}: {escape(', '.join(fit['countries']))}. "
        f"WGI is centered at {est.fmt(fit['wgi_center'])}.</li>"
        for _, _, label, fit, _ in rows_for_equation
    )
    return f"""
<h2>{escape(title)}</h2>
<p>{note}</p>
<table>
<thead><tr><th>Variable</th>{header}</tr></thead>
<tbody>
{''.join(body)}
<tr><td>Sample</td>{sample}</tr>
</tbody>
</table>
<ul>{countries}</ul>
"""


def write_html(path, results):
    inflation = [row for row in results if row[0] == "inflation"]
    output = [row for row in results if row[0] == "output"]
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Inflation and output channels</title>
<style>
body {{ font: 16px/1.5 Georgia, serif; max-width: 1100px; margin: 2em auto; padding: 0 1em; color: #20242a; }}
table {{ border-collapse: collapse; width: 100%; margin: 1em 0; font-size: .92em; }}
th, td {{ border-bottom: 1px solid #ccc; padding: .45em; text-align: right; vertical-align: top; }}
th:first-child, td:first-child {{ text-align: left; }}
.note {{ background: #fff5da; padding: 1em; border: 1px solid #e6d59d; }}
</style>
</head>
<body>
<h1>Inflation and output as the export channels</h1>
<div class="note">
<p>Each equation includes GPR, lagged WGI, and their interaction, plus country fixed effects. WGI is centered on that equation's sample, so the GPR coefficient is the effect at the average institution and the interaction is the cushion around that average.</p>
<p>A negative inflation interaction means a higher WGI reduces the inflation response to GPR. For the export-trend change, the interaction is how much a higher WGI changes the response of that growth rate to GPR. Standard errors in parentheses are clustered by country.</p>
<p>Import/GDP is not available. The log oil price is the imported-cost control. The second equation uses the year-over-year log change of the real-export Hodrick-Prescott trend. That series is already a log change.</p>
</div>
{equation_table(
    "Inflation, monthly",
    "Controls are lagged one month. Industrial production uses the year of that lagged month.",
    inflation,
    INFLATION_CONTROLS,
)}
{equation_table(
    "Real export trend change, monthly",
    "The outcome is the year-over-year log change of the real-export Hodrick-Prescott trend. GPR is contemporaneous. WGI and the controls are lagged one month.",
    output,
    OUTPUT_CONTROLS,
)}
<p><em>Significance:</em> *** p&lt;0.01, ** p&lt;0.05, * p&lt;0.10.</p>
</body>
</html>
"""
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(html)


def main():
    if abs(est.student_t_ppf(0.975, 12) - 2.1788128296666256) > 1e-6:
        raise RuntimeError("The t critical value does not match the reference.")
    common = load_sources()
    results = []
    for code, label in DIMENSIONS:
        sources = dict(common)
        sources["wgi"] = est.read_wgi(code)
        inflation_rows = build_inflation_rows(sources)
        inflation_center = center_wgi(inflation_rows)
        inflation_fit = fit_equation(inflation_rows, INFLATION_CONTROLS)
        inflation_fit["wgi_center"] = inflation_center
        output_rows = build_output_rows(sources)
        output_center = center_wgi(output_rows)
        output_fit = fit_equation(output_rows, OUTPUT_CONTROLS)
        output_fit["wgi_center"] = output_center
        results.append(("inflation", code, label, inflation_fit, INFLATION_CONTROLS))
        results.append(("output", code, label, output_fit, OUTPUT_CONTROLS))
        for equation, fit in (("inflation", inflation_fit), ("output", output_fit)):
            interaction = fit["stats"]["wgi_x_gpr"]
            print(
                equation,
                label,
                "N", fit["n_obs"],
                "countries", fit["n_country"],
                "gpr", fit["stats"]["gpr"]["coef"],
                "wgi", fit["stats"]["wgi_l1"]["coef"],
                "interaction", interaction["coef"],
                "p", interaction["p"],
            )
    write_csv(os.path.join(OUTPUT, "inflation_output_channels_results.csv"), results)
    write_html(os.path.join(OUTPUT, "inflation_output_channels_results.html"), results)


if __name__ == "__main__":
    main()
