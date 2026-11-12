"""Quarterly capital flow on country GPR, one WGI dimension, and their interaction.

The outcome is usd_millions in cleaned/capital_flow.csv. Negative values stay
negative. GPR is the quarterly mean of the raw country article share, then
standardized within each country on the estimation sample. WGI is centered on
the estimation sample. Controls follow equation (2) and are lagged one quarter.
Country fixed effects, standard errors clustered by country.
"""

import csv
import os
from html import escape

import numpy as np

import run_export_reer_2sls as est


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUTPUT = os.path.join(ROOT, "output")
CLEANED = os.path.join(ROOT, "cleaned")

DIMENSIONS = {
    "rq": "Regulatory quality",
    "ge": "Government effectiveness",
    "rl": "Rule of law",
}

CONTROLS = [
    "policy_rate_l1",
    "inflation_l1",
    "log_oil_l1",
    "log_vix_l1",
    "log_gepu_l1",
    "financial_development_l1",
    "debt_gdp_l1",
]

CONTROL_LABELS = {
    "policy_rate_l1": "Policy rate",
    "inflation_l1": "Inflation",
    "log_oil_l1": "Oil price",
    "log_vix_l1": "VIX",
    "log_gepu_l1": "Global EPU",
    "financial_development_l1": "Financial development",
    "debt_gdp_l1": "Debt/GDP",
}

INTEREST = ["gpr", "wgi", "wgi_x_gpr"]


def previous_quarter(year, quarter):
    if quarter == 1:
        return year - 1, 4
    return year, quarter - 1


def quarter_months(year, quarter):
    start = (quarter - 1) * 3 + 1
    return [f"{year:04d}-{month:02d}" for month in range(start, start + 3)]


def parse_quarter(label):
    year, quarter = label.split("-Q")
    return int(year), int(quarter)


def in_window(label):
    return "2000-Q1" <= label <= "2023-Q4"


def read_flows():
    out = {}
    path = os.path.join(CLEANED, "capital_flow.csv")
    with open(path, encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            value = (row.get("usd_millions") or "").strip()
            if not value:
                continue
            out.setdefault(row["country"].strip(), {})[row["year_quarter"].strip()] = float(value)
    return out


def read_gpr_country():
    out = {}
    path = os.path.join(CLEANED, "gpr_country.csv")
    with open(path, encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            value = (row.get("value") or "").strip()
            if not value:
                continue
            out.setdefault(row["country"].strip(), {})[row["year_month"].strip()] = float(value)
    return out


def mean_months(series, months, transform=None):
    values = []
    for month in months:
        value = series.get(month) if isinstance(series, dict) else series.get(month)
        if value is None:
            return None
        if transform is not None:
            value = transform(value)
            if value is None:
                return None
        values.append(value)
    return float(np.mean(values))


def build_rows(dimension, sources):
    rows = []
    for country in sources["countries"]:
        for label, flow in sorted(sources["flows"].get(country, {}).items()):
            if not in_window(label):
                continue
            year, quarter = parse_quarter(label)
            lag_year, lag_quarter = previous_quarter(year, quarter)
            lag_months = quarter_months(lag_year, lag_quarter)
            record = {
                "country": country,
                "year_quarter": label,
                "flow": flow,
                "gpr": mean_months(sources["gpr"].get(country, {}), quarter_months(year, quarter)),
                "wgi_raw": sources["wgi"].get(country, {}).get(lag_year),
                "policy_rate_l1": mean_months(sources["policy"].get(country, {}), lag_months),
                "inflation_l1": mean_months(sources["inflation"].get(country, {}), lag_months),
                "log_oil_l1": mean_months(sources["oil"], lag_months, est.positive_log),
                "log_vix_l1": mean_months(sources["vix"], lag_months, est.positive_log),
                "log_gepu_l1": mean_months(sources["gepu"], lag_months, est.positive_log),
                "financial_development_l1": sources["fd"].get(country, {}).get(lag_year),
                "debt_gdp_l1": sources["debt"].get(country, {}).get(lag_year),
            }
            needed = ["flow", "gpr", "wgi_raw", *CONTROLS]
            if any(record[name] is None for name in needed):
                continue
            rows.append(record)
    if not rows:
        raise RuntimeError(f"No complete cases for {dimension}.")
    standardize_within_country(rows, "gpr")
    center = float(np.mean([row["wgi_raw"] for row in rows]))
    for row in rows:
        row["wgi"] = row["wgi_raw"] - center
        row["wgi_x_gpr"] = row["wgi"] * row["gpr"]
    return rows, center


def standardize_within_country(rows, key):
    grouped = {}
    for row in rows:
        grouped.setdefault(row["country"], []).append(row[key])
    moments = {}
    for country, values in grouped.items():
        array = np.asarray(values, dtype=float)
        sd = float(array.std(ddof=1)) if len(array) > 1 else 0.0
        moments[country] = (float(array.mean()), sd)
    for row in rows:
        mean, sd = moments[row["country"]]
        row[key] = 0.0 if sd == 0.0 else (row[key] - mean) / sd


def fit(rows, country_order):
    present = [country for country in country_order if any(row["country"] == country for row in rows)]
    y = np.array([row["flow"] for row in rows], dtype=float)
    columns = INTEREST + CONTROLS
    x_matrix, names, base = est.design_matrix(rows, columns, present)
    n, k = x_matrix.shape
    beta = np.linalg.lstsq(x_matrix, y, rcond=None)[0]
    residual = y - x_matrix @ beta
    grouped = est.cluster_indices(rows)
    variance, _ = est.cluster_variance(x_matrix, residual, grouped, n, k)
    stats = est.inference(names, beta, variance, len(grouped))
    sst = float(np.sum((y - np.mean(y)) ** 2))
    return {
        "countries": present,
        "n_obs": n,
        "n_country": len(grouped),
        "quarter_min": min(row["year_quarter"] for row in rows),
        "quarter_max": max(row["year_quarter"] for row in rows),
        "r2": float(1.0 - np.sum(residual**2) / sst),
        "stats": stats,
        "base_country": base,
    }


def write_outputs(path_csv, path_html, results):
    fields = [
        "dimension", "dimension_label", "variable", "label",
        "coef", "se", "p", "stars", "wgi_center",
        "n_obs", "n_country", "r2", "quarter_min", "quarter_max", "countries",
    ]
    labels = {
        "gpr": "GPR",
        "wgi": "WGI",
        "wgi_x_gpr": "WGI x GPR",
        **CONTROL_LABELS,
    }
    with open(path_csv, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for code, result in results.items():
            fitted = result["fit"]
            for name in INTEREST + CONTROLS:
                stat = fitted["stats"][name]
                writer.writerow({
                    "dimension": code,
                    "dimension_label": DIMENSIONS[code],
                    "variable": name,
                    "label": labels[name],
                    "coef": f"{stat['coef']:.10g}",
                    "se": f"{stat['se']:.10g}",
                    "p": f"{stat['p']:.10g}",
                    "stars": est.stars(stat["p"]),
                    "wgi_center": f"{result['center']:.10g}",
                    "n_obs": fitted["n_obs"],
                    "n_country": fitted["n_country"],
                    "r2": f"{fitted['r2']:.10g}",
                    "quarter_min": fitted["quarter_min"],
                    "quarter_max": fitted["quarter_max"],
                    "countries": "; ".join(fitted["countries"]),
                })

    blocks = []
    for code, result in results.items():
        fitted = result["fit"]
        body = []
        for name in INTEREST + CONTROLS:
            stat = fitted["stats"][name]
            body.append(
                "<tr>"
                f"<td>{escape(labels[name])}</td>"
                f"<td>{est.fmt(stat['coef'])}{est.stars(stat['p'])}</td>"
                f"<td>{est.fmt(stat['se'])}</td>"
                f"<td>{est.fmt(stat['p'])}</td>"
                "</tr>"
            )
        blocks.append(
            f"<h2>{escape(DIMENSIONS[code])}</h2>"
            f"<p>N = {fitted['n_obs']}. Countries = {fitted['n_country']}: "
            f"{escape(', '.join(fitted['countries']))}. "
            f"Quarters = {escape(fitted['quarter_min'])} to {escape(fitted['quarter_max'])}. "
            f"R-squared = {est.fmt(fitted['r2'])}. "
            f"WGI is centered at {est.fmt(result['center'])}.</p>"
            "<table><thead><tr><th>Variable</th><th>Coefficient</th><th>SE</th><th>p-value</th></tr></thead>"
            f"<tbody>{''.join(body)}</tbody></table>"
        )
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Capital flow, GPR, and WGI</title>
<style>
body {{ font: 16px/1.5 Georgia, serif; max-width: 900px; margin: 2em auto; padding: 0 1em; color: #20242a; }}
table {{ border-collapse: collapse; width: 100%; margin: 1em 0; font-size: .92em; }}
th, td {{ border-bottom: 1px solid #ccc; padding: .45em; text-align: right; }}
th:first-child, td:first-child {{ text-align: left; }}
.note {{ background: #fff5da; padding: 1em; border: 1px solid #e6d59d; }}
</style>
</head>
<body>
<h1>Capital flow on GPR and WGI</h1>
<div class="note">
<p>The outcome is the quarterly dollar flow in <code>cleaned/capital_flow.csv</code>. Negative values stay negative. This is not a volatility and it is not a log.</p>
<p>GPR is the average of the raw country article share over the same quarter, then standardized within each country on the quarters that enter the regression. Each regression uses one WGI dimension, lagged to the year of the previous quarter and centered on this sample. The GPR coefficient is the effect at that average. The interaction is the extra GPR effect when WGI is one point higher. Regulatory quality, government effectiveness, and rule of law are estimated separately.</p>
<p>The other controls are lagged one quarter. Real industrial production is omitted so that countries without the annual index remain in the sample. Central bank independence is not in <code>cleaned/</code>. Standard errors are clustered by country. *** p&lt;0.01, ** p&lt;0.05, * p&lt;0.10.</p>
</div>
{''.join(blocks)}
</body>
</html>
"""
    with open(path_html, "w", encoding="utf-8") as handle:
        handle.write(html)


def main():
    countries = est.read_country_order()
    shared = {
        "countries": countries,
        "flows": read_flows(),
        "gpr": read_gpr_country(),
        "policy": est.read_monthly_country("policy_rate.csv", "value"),
        "inflation": est.read_monthly_country("inflation.csv", "value"),
        "oil": est.read_monthly_global("oil_price.csv", "wti_spot"),
        "vix": est.read_monthly_global("vix.csv", "value"),
        "gepu": est.read_monthly_global("gepu_current.csv", "value"),
        "fd": est.read_annual("financial_development.csv", "year", "fd_fdi_ovrl"),
        "debt": est.read_annual("debt_gdp.csv", "period", "debt_gdp_pct", frequency="Annual"),
    }
    results = {}
    for code in DIMENSIONS:
        sources = {**shared, "wgi": est.read_wgi(code)}
        rows, center = build_rows(code, sources)
        fitted = fit(rows, countries)
        results[code] = {"fit": fitted, "center": center}
        stat = fitted["stats"]
        print(
            code, "N", fitted["n_obs"], "countries", fitted["n_country"],
            "R2", fitted["r2"], "center", center,
        )
        print(",".join(fitted["countries"]))
        for name in INTEREST:
            print(" ", name, stat[name]["coef"], stat[name]["se"], stat[name]["p"], est.stars(stat[name]["p"]))
    write_outputs(
        os.path.join(OUTPUT, "capital_flow_wgi_results.csv"),
        os.path.join(OUTPUT, "capital_flow_wgi_results.html"),
        results,
    )


if __name__ == "__main__":
    main()
