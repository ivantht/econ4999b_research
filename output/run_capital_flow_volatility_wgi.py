"""Monthly portfolio-inflow volatility on country GPR and one WGI dimension.

The outcome is cf_vol in the literature-review panel: the standard deviation of
portfolio inflows over three months. GPR is that panel's within-country z-score.
WGI comes from cleaned/wgi.csv, lagged to the previous month and centered.
Industrial production is omitted. Country fixed effects, clustered standard errors.
"""

import csv
import os
from html import escape

import numpy as np

import run_export_reer_2sls as est


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUTPUT = os.path.join(ROOT, "output")
PANEL = os.path.join(
    ROOT, "econ4999b_literature_review", "replication", "output", "panel.csv"
)

ISO = {
    "MX": "Mexico",
    "CL": "Chile",
    "HU": "Hungary",
    "UA": "Ukraine",
    "TR": "Turkey",
    "ZA": "South Africa",
    "IN": "India",
    "ID": "Indonesia",
    "PH": "Philippines",
    "TH": "Thailand",
    "KR": "South Korea",
}

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
    "central_bank_independence_l1",
    "debt_gdp_l1",
]

PANEL_CONTROLS = {
    "policy_rate_l1": "rate_l1",
    "inflation_l1": "infl_l1",
    "log_oil_l1": "ln_oil_l1",
    "log_vix_l1": "ln_vix_l1",
    "log_gepu_l1": "ln_gepu_l1",
    "financial_development_l1": "fd_l1",
    "central_bank_independence_l1": "cbi_l1",
    "debt_gdp_l1": "debt_l1",
}

CONTROL_LABELS = {
    "policy_rate_l1": "Policy rate",
    "inflation_l1": "Inflation",
    "log_oil_l1": "Oil price",
    "log_vix_l1": "VIX",
    "log_gepu_l1": "Global EPU",
    "financial_development_l1": "Financial development",
    "central_bank_independence_l1": "Central bank independence",
    "debt_gdp_l1": "Debt/GDP",
}

INTEREST = ["gpr", "wgi", "wgi_x_gpr"]


def num(text):
    text = (text or "").strip()
    if not text:
        return None
    return float(text)


def load_panel():
    rows = []
    with open(PANEL, encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            country = ISO.get(row["iso"].strip())
            month = row["date"][:7]
            if country is None or not ("2000-01" <= month <= "2023-12"):
                continue
            record = {
                "country": country,
                "year_month": month,
                "volatility": num(row["cf_vol"]),
                "gpr": num(row["gpr_z"]),
                "lag_year": int(est.add_months(month, -1)[:4]),
            }
            for name, source in PANEL_CONTROLS.items():
                record[name] = num(row[source])
            rows.append(record)
    return rows


def build_rows(panel_rows, wgi):
    rows = []
    for row in panel_rows:
        record = dict(row)
        record["wgi_raw"] = wgi.get(row["country"], {}).get(row["lag_year"])
        needed = ["volatility", "gpr", "wgi_raw", *CONTROLS]
        if any(record[name] is None for name in needed):
            continue
        rows.append(record)
    if not rows:
        raise RuntimeError("No complete cases.")
    center = float(np.mean([row["wgi_raw"] for row in rows]))
    for row in rows:
        row["wgi"] = row["wgi_raw"] - center
        row["wgi_x_gpr"] = row["wgi"] * row["gpr"]
    return rows, center


def fit(rows, country_order):
    present = [country for country in country_order if any(row["country"] == country for row in rows)]
    y = np.array([row["volatility"] for row in rows], dtype=float)
    x_matrix, names, base = est.design_matrix(rows, INTEREST + CONTROLS, present)
    n, k = x_matrix.shape
    beta = np.linalg.lstsq(x_matrix, y, rcond=None)[0]
    residual = y - x_matrix @ beta
    grouped = est.cluster_indices(rows)
    variance, _ = est.cluster_variance(x_matrix, residual, grouped, n, k)
    stats = est.inference(names, beta, variance, len(grouped))
    sst = float(np.sum((y - np.mean(y)) ** 2))
    return {
        "countries": present,
        "base_country": base,
        "n_obs": n,
        "n_country": len(grouped),
        "month_min": min(row["year_month"] for row in rows),
        "month_max": max(row["year_month"] for row in rows),
        "r2": float(1.0 - np.sum(residual**2) / sst),
        "stats": stats,
    }


def write_outputs(path_csv, path_html, results):
    labels = {"gpr": "GPR", "wgi": "WGI", "wgi_x_gpr": "WGI x GPR", **CONTROL_LABELS}
    fields = [
        "dimension", "dimension_label", "variable", "label",
        "coef", "se", "p", "stars", "wgi_center",
        "n_obs", "n_country", "r2", "month_min", "month_max", "countries",
    ]
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
                    "month_min": fitted["month_min"],
                    "month_max": fitted["month_max"],
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
            f"Months = {escape(fitted['month_min'])} to {escape(fitted['month_max'])}. "
            f"R-squared = {est.fmt(fitted['r2'])}. "
            f"WGI is centered at {est.fmt(result['center'])}.</p>"
            "<table><thead><tr><th>Variable</th><th>Coefficient</th><th>SE</th><th>p-value</th></tr></thead>"
            f"<tbody>{''.join(body)}</tbody></table>"
        )
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Capital-flow volatility, GPR, and WGI</title>
<style>
body {{ font: 16px/1.5 Georgia, serif; max-width: 900px; margin: 2em auto; padding: 0 1em; color: #20242a; }}
table {{ border-collapse: collapse; width: 100%; margin: 1em 0; font-size: .92em; }}
th, td {{ border-bottom: 1px solid #ccc; padding: .45em; text-align: right; }}
th:first-child, td:first-child {{ text-align: left; }}
.note {{ background: #fff5da; padding: 1em; border: 1px solid #e6d59d; }}
</style>
</head>
<body>
<h1>Capital-flow volatility on GPR and WGI</h1>
<div class="note">
<p>The outcome is the standard deviation of portfolio inflows over three months, the author's volatility measure. It is not the quarterly dollar flow.</p>
<p>GPR is the country index standardized within each country, in the same month. Each regression uses one WGI dimension from <code>cleaned/wgi.csv</code>, taken from the year of the previous month and centered on this sample. The GPR coefficient is the effect at that average. The interaction is the extra GPR effect when WGI is one point higher.</p>
<p>Real industrial production is omitted. The other controls are lagged one month and include central bank independence. Standard errors are clustered by country. *** p&lt;0.01, ** p&lt;0.05, * p&lt;0.10.</p>
</div>
{''.join(blocks)}
</body>
</html>
"""
    with open(path_html, "w", encoding="utf-8") as handle:
        handle.write(html)


def main():
    panel_rows = load_panel()
    country_order = [country for country in est.read_country_order() if country in set(ISO.values())]
    results = {}
    for code in DIMENSIONS:
        rows, center = build_rows(panel_rows, est.read_wgi(code))
        fitted = fit(rows, country_order)
        results[code] = {"fit": fitted, "center": center}
        print(
            code, "N", fitted["n_obs"], "countries", fitted["n_country"],
            "R2", fitted["r2"], "center", center,
        )
        print(",".join(fitted["countries"]))
        for name in INTEREST:
            stat = fitted["stats"][name]
            print(" ", name, stat["coef"], stat["se"], stat["p"], est.stars(stat["p"]))
    write_outputs(
        os.path.join(OUTPUT, "capital_flow_volatility_wgi_results.csv"),
        os.path.join(OUTPUT, "capital_flow_volatility_wgi_results.html"),
        results,
    )


if __name__ == "__main__":
    main()
