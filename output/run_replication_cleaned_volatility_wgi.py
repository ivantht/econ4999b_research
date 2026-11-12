"""Capital-flow volatility on GPR, the paper's controls, and one WGI dimension.

The outcome and controls are in cleaned/replication_cleaned/country_month.csv.
WGI is in cleaned/wgi.csv. Equation (2) and Table 2, column 1, plus a centered
WGI term and its interaction with GPR. Three regressions: rule of law,
government effectiveness, and regulatory quality. Country fixed effects.
Within and country-clustered standard errors.
"""

import csv
import os
from collections import defaultdict
from html import escape

import numpy as np

import run_export_reer_2sls as est


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PANEL = os.path.join(ROOT, "cleaned", "replication_cleaned", "country_month.csv")
OUTPUT = os.path.join(ROOT, "output")

WGI_NAME = {"Turkiye": "Turkey", "Korea": "South Korea"}

DIMENSIONS = {
    "rl": "Rule of law",
    "ge": "Government effectiveness",
    "rq": "Regulatory quality",
}

REGRESSORS = [
    "gpr_z",
    "wgi",
    "wgi_x_gpr",
    "policy_rate_l1",
    "ln_ip_l1",
    "infl_l1",
    "ln_oil_l1",
    "ln_vix_l1",
    "ln_gepu_l1",
    "fd_l1",
    "cbi_l1",
    "debt_l1",
]

LABELS = {
    "gpr_z": "GPR",
    "wgi": "WGI",
    "wgi_x_gpr": "WGI x GPR",
    "policy_rate_l1": "Policy rate",
    "ln_ip_l1": "Real industrial production",
    "infl_l1": "Inflation",
    "ln_oil_l1": "Oil price",
    "ln_vix_l1": "VIX",
    "ln_gepu_l1": "Global EPU",
    "fd_l1": "Financial development",
    "cbi_l1": "Central bank independence",
    "debt_l1": "Debt/GDP",
}

LAG_LOGS = {
    "ln_ip_l1": "industrial_production",
    "ln_oil_l1": "oil_price",
    "ln_vix_l1": "vix",
    "ln_gepu_l1": "gepu",
}
LAG_LEVELS = {
    "policy_rate_l1": "policy_rate",
    "infl_l1": "inflation",
    "fd_l1": "financial_development",
    "cbi_l1": "central_bank_independence",
    "debt_l1": "public_debt_gdp",
}

PAPER_GPR = 0.867


def num(text):
    text = (text or "").strip()
    if not text:
        return None
    return float(text)


def load_panel():
    rows = []
    with open(PANEL, encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            month = row["date"][:7]
            record = {
                "iso": row["iso"].strip(),
                "country": row["country"].strip(),
                "year_month": month,
                "volatility": num(row["capital_flow_volatility"]),
                "gpr": num(row["gpr"]),
            }
            for column in list(LAG_LOGS.values()) + list(LAG_LEVELS.values()):
                record[column] = num(row[column])
            rows.append(record)
    return rows


def lagged_controls(current, previous):
    if previous is None:
        return {name: None for name in list(LAG_LOGS) + list(LAG_LEVELS)}
    out = {}
    for name, column in LAG_LOGS.items():
        out[name] = est.positive_log(previous[column])
    for name, column in LAG_LEVELS.items():
        out[name] = previous[column]
    return out


def attach_lags(rows):
    index = {(row["iso"], row["year_month"]): row for row in rows}
    prepared = []
    for row in rows:
        previous = index.get((row["iso"], est.add_months(row["year_month"], -1)))
        record = {
            "iso": row["iso"],
            "country": row["country"],
            "year_month": row["year_month"],
            "volatility": row["volatility"],
            "gpr": row["gpr"],
            "lag_year": int(est.add_months(row["year_month"], -1)[:4]),
        }
        record.update(lagged_controls(row, previous))
        prepared.append(record)
    return prepared


def standardize_gpr(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["iso"]].append(row["gpr"])
    moments = {}
    for iso, values in grouped.items():
        array = np.array(values, dtype=float)
        sd = float(array.std(ddof=1)) if len(array) > 1 else float("nan")
        moments[iso] = (float(array.mean()), sd)
    kept = []
    for row in rows:
        mean, sd = moments[row["iso"]]
        if not np.isfinite(sd) or sd == 0:
            continue
        row["gpr_z"] = (row["gpr"] - mean) / sd
        kept.append(row)
    return kept


def complete_cases(rows, wgi):
    kept = []
    controls = list(LAG_LOGS) + list(LAG_LEVELS)
    for row in rows:
        wgi_name = WGI_NAME.get(row["country"], row["country"])
        raw = wgi.get(wgi_name, {}).get(row["lag_year"])
        if row["volatility"] is None or row["gpr"] is None or raw is None:
            continue
        if any(row[name] is None for name in controls):
            continue
        record = dict(row)
        record["wgi_raw"] = raw
        kept.append(record)
    kept = standardize_gpr(kept)
    if not kept:
        raise RuntimeError("No complete cases.")
    center = float(np.mean([row["wgi_raw"] for row in kept]))
    for row in kept:
        row["wgi"] = row["wgi_raw"] - center
        row["wgi_x_gpr"] = row["wgi"] * row["gpr_z"]
    return kept, center


def demean(values, countries):
    out = values.copy()
    for iso in set(countries):
        index = countries == iso
        out[index] -= out[index].mean(axis=0)
    return out


def fit(rows):
    countries = np.array([row["iso"] for row in rows])
    y = demean(np.array([row["volatility"] for row in rows], dtype=float), countries)
    raw_x = np.column_stack([
        np.array([row[name] for row in rows], dtype=float) for name in REGRESSORS
    ])
    x_matrix = demean(raw_x, countries)
    keep = [i for i in range(x_matrix.shape[1]) if float(x_matrix[:, i].std()) > 1e-8]
    names = [REGRESSORS[i] for i in keep]
    x_matrix = x_matrix[:, keep]
    n, k = x_matrix.shape
    g = len(set(countries))
    beta = np.linalg.lstsq(x_matrix, y, rcond=None)[0]
    residual = y - x_matrix @ beta
    dof = n - k - g
    if dof <= 0:
        dof = max(n - k, 1)
    sigma2 = float(residual @ residual) / dof
    xtx_inv = np.linalg.inv(x_matrix.T @ x_matrix)
    se_within = np.sqrt(np.diag(xtx_inv) * sigma2)
    scores = x_matrix * residual[:, None]
    meat = np.zeros((k, k))
    for iso in set(countries):
        total = scores[countries == iso].sum(axis=0)
        meat += np.outer(total, total)
    scale = (g / (g - 1.0)) * ((n - 1.0) / dof)
    se_cluster = np.sqrt(np.diag(scale * xtx_inv @ meat @ xtx_inv))
    sst = float(y @ y)
    present = []
    seen = set()
    for row in rows:
        if row["country"] not in seen:
            seen.add(row["country"])
            present.append(row["country"])
    return {
        "names": names,
        "beta": beta,
        "se_within": se_within,
        "se_cluster": se_cluster,
        "p_within": [
            float(est.student_t_sf_two_tail(b / s, dof))
            for b, s in zip(beta, se_within)
        ],
        "p_cluster": [
            float(est.student_t_sf_two_tail(b / s, g - 1))
            for b, s in zip(beta, se_cluster)
        ],
        "n_obs": n,
        "n_country": g,
        "r2": float(1.0 - (residual @ residual) / sst),
        "countries": present,
        "month_min": min(row["year_month"] for row in rows),
        "month_max": max(row["year_month"] for row in rows),
    }


def write_outputs(path_csv, path_html, results, all_countries):
    fields = [
        "dimension", "dimension_label", "variable", "label",
        "paper_gpr", "coef",
        "se_within", "p_within", "stars_within",
        "se_cluster", "p_cluster", "stars_cluster",
        "wgi_center", "n_obs", "n_country", "r2",
        "month_min", "month_max", "countries",
    ]
    with open(path_csv, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for code, result in results.items():
            fitted = result["fit"]
            lookup = {name: i for i, name in enumerate(fitted["names"])}
            for name in REGRESSORS:
                i = lookup[name]
                writer.writerow({
                    "dimension": code,
                    "dimension_label": DIMENSIONS[code],
                    "variable": name,
                    "label": LABELS[name],
                    "paper_gpr": f"{PAPER_GPR:.3f}" if name == "gpr_z" else "",
                    "coef": f"{float(fitted['beta'][i]):.10g}",
                    "se_within": f"{float(fitted['se_within'][i]):.10g}",
                    "p_within": f"{fitted['p_within'][i]:.10g}",
                    "stars_within": est.stars(fitted["p_within"][i]),
                    "se_cluster": f"{float(fitted['se_cluster'][i]):.10g}",
                    "p_cluster": f"{fitted['p_cluster'][i]:.10g}",
                    "stars_cluster": est.stars(fitted["p_cluster"][i]),
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
        lookup = {name: i for i, name in enumerate(fitted["names"])}
        body = []
        for name in REGRESSORS:
            i = lookup[name]
            coef = float(fitted["beta"][i])
            paper = f"{PAPER_GPR:.3f}**" if name == "gpr_z" else ""
            body.append(
                "<tr>"
                f"<td>{escape(LABELS[name])}</td>"
                f"<td>{paper}</td>"
                f"<td>{est.fmt(coef)}{est.stars(fitted['p_within'][i])}</td>"
                f"<td>{est.fmt(float(fitted['se_within'][i]))}</td>"
                f"<td>{est.fmt(fitted['p_within'][i])}</td>"
                f"<td>{est.fmt(coef)}{est.stars(fitted['p_cluster'][i])}</td>"
                f"<td>{est.fmt(float(fitted['se_cluster'][i]))}</td>"
                f"<td>{est.fmt(fitted['p_cluster'][i])}</td>"
                "</tr>"
            )
        remaining = set(fitted["countries"])
        dropped = [country for country in all_countries if country not in remaining]
        blocks.append(
            f"<h2>{escape(DIMENSIONS[code])}</h2>"
            f"<p>N = {fitted['n_obs']}. Countries = {fitted['n_country']}: "
            f"{escape(', '.join(fitted['countries']))}. "
            f"Months = {escape(fitted['month_min'])} to {escape(fitted['month_max'])}. "
            f"Within R-squared = {est.fmt(fitted['r2'])}. "
            f"WGI is centered at {est.fmt(result['center'])}. "
            f"Countries with no complete month: {escape(', '.join(dropped) if dropped else 'none')}.</p>"
            "<table><thead><tr><th>Variable</th><th>Table 2 GPR</th>"
            "<th>Coefficient</th><th>Within SE</th><th>Within p</th>"
            "<th>Coefficient</th><th>Cluster SE</th><th>Cluster p</th></tr></thead>"
            f"<tbody>{''.join(body)}</tbody></table>"
        )
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Capital-flow volatility, GPR, and WGI</title>
<style>
body {{ font: 16px/1.5 Georgia, serif; max-width: 980px; margin: 2em auto; padding: 0 1em; color: #20242a; }}
table {{ border-collapse: collapse; width: 100%; margin: 1em 0; font-size: .9em; }}
th, td {{ border-bottom: 1px solid #ccc; padding: .4em; text-align: right; vertical-align: top; }}
th:first-child, td:first-child {{ text-align: left; }}
.note {{ background: #fff5da; padding: 1em; border: 1px solid #e6d59d; }}
</style>
</head>
<body>
<h1>Capital-flow volatility on GPR, the paper's controls, and WGI</h1>
<div class="note">
<p>The outcome is capital-flow volatility in <code>cleaned/replication_cleaned</code>, the standard deviation of portfolio inflows over three months, in billion dollars. GPR is the country article share, standardized within each country on the months that enter the regression. The controls are lagged one month: log industrial production, inflation, the policy rate, log oil, log VIX, log global EPU, financial development, central-bank independence, and debt to GDP.</p>
<p>Each regression uses one dimension from <code>cleaned/wgi.csv</code>: rule of law, government effectiveness, or regulatory quality. The score is the calendar year of the lagged month. Years the file does not contain are left blank. WGI is centered on this regression, and the interaction is that centered score times standardized GPR. The GPR coefficient is the effect at the average score.</p>
<p>Country fixed effects. The within standard error treats months as independent. The clustered standard error clusters by country. Table 2's GPR coefficient of 0.867 is shown as a reference and has no WGI term. *** p&lt;0.01, ** p&lt;0.05, * p&lt;0.10.</p>
</div>
{''.join(blocks)}
</body>
</html>
"""
    with open(path_html, "w", encoding="utf-8") as handle:
        handle.write(html)


def main():
    panel = attach_lags(load_panel())
    all_countries = []
    seen = set()
    for row in panel:
        if row["country"] not in seen:
            seen.add(row["country"])
            all_countries.append(row["country"])
    results = {}
    for code in DIMENSIONS:
        rows, center = complete_cases(panel, est.read_wgi(code))
        fitted = fit(rows)
        results[code] = {"fit": fitted, "center": center}
        print(
            code, "N", fitted["n_obs"], "countries", fitted["n_country"],
            "R2", round(fitted["r2"], 4), "center", round(center, 4),
            fitted["month_min"], fitted["month_max"],
        )
        print(" ", ", ".join(fitted["countries"]))
        lookup = {name: i for i, name in enumerate(fitted["names"])}
        for name in ("gpr_z", "wgi", "wgi_x_gpr"):
            i = lookup[name]
            print(
                " ", name,
                round(float(fitted["beta"][i]), 4),
                "within", round(fitted["p_within"][i], 4), est.stars(fitted["p_within"][i]),
                "cluster", round(fitted["p_cluster"][i], 4), est.stars(fitted["p_cluster"][i]),
            )
    write_outputs(
        os.path.join(OUTPUT, "replication_cleaned_volatility_wgi_results.csv"),
        os.path.join(OUTPUT, "replication_cleaned_volatility_wgi_results.html"),
        results,
        all_countries,
    )


if __name__ == "__main__":
    main()
