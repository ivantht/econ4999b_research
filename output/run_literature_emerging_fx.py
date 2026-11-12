"""Emerging-economy exchange-rate equation on the literature-review panel.

Reads the saved panel. Does not download or rebuild it. Equation (2), Table 3,
emerging economies, exchange-rate column. Country fixed effects. Reports the
ordinary within standard error and the standard error clustered by country.
"""

import csv
import os
from html import escape

import numpy as np

import run_export_reer_2sls as est


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PANEL = os.path.join(
    ROOT, "econ4999b_literature_review", "replication", "output", "panel.csv"
)
OUTPUT = os.path.join(ROOT, "output")

NAMES = {
    "BR": "Brazil", "CL": "Chile", "CN": "China", "CO": "Colombia", "HU": "Hungary",
    "IN": "India", "ID": "Indonesia", "MY": "Malaysia", "MX": "Mexico",
    "PH": "Philippines", "PL": "Poland", "ZA": "South Africa", "TH": "Thailand",
    "TR": "Turkey", "UA": "Ukraine",
}

REGRESSORS = [
    "gpr_z",
    "rate_l1",
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
    "rate_l1": "Policy rate",
    "ln_ip_l1": "Real industrial production",
    "infl_l1": "Inflation",
    "ln_oil_l1": "Oil price",
    "ln_vix_l1": "VIX",
    "ln_gepu_l1": "Global EPU",
    "fd_l1": "Financial development",
    "cbi_l1": "Central bank independence",
    "debt_l1": "Debt/GDP",
}

PAPER_GPR = {"coef": -0.010, "se": 0.002, "stars": "***", "n_obs": 1970, "r2": 0.651}


def num(text):
    text = (text or "").strip()
    if not text:
        return None
    return float(text)


def load_rows():
    emerging = []
    kept = []
    with open(PANEL, encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["group"].strip() != "Emerging":
                continue
            record = {
                "iso": row["iso"].strip(),
                "year_month": row["date"][:7],
                "ln_reer": num(row["ln_reer"]),
            }
            for name in REGRESSORS:
                record[name] = num(row[name])
            emerging.append(record["iso"])
            if record["ln_reer"] is None or any(record[name] is None for name in REGRESSORS):
                continue
            kept.append(record)
    return kept, sorted(set(emerging))


def demean(values, countries):
    out = values.copy()
    for iso in set(countries):
        index = countries == iso
        out[index] -= out[index].mean(axis=0)
    return out


def fit(rows):
    countries = np.array([row["iso"] for row in rows])
    y = demean(np.array([row["ln_reer"] for row in rows], dtype=float), countries)
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
    present = sorted({NAMES.get(iso, iso) for iso in countries})
    available = sorted({NAMES.get(iso, iso) for iso in set(countries)})
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
        "dof_within": dof,
        "r2": float(1.0 - (residual @ residual) / sst),
        "countries": present,
        "month_min": min(row["year_month"] for row in rows),
        "month_max": max(row["year_month"] for row in rows),
        "available_names": available,
    }


def same_sign(paper_coef, our_coef):
    if paper_coef == 0 or our_coef == 0:
        return "no"
    return "yes" if (paper_coef > 0) == (our_coef > 0) else "no"


def write_outputs(path_csv, path_html, fitted, dropped):
    fields = [
        "variable", "label", "paper_coef", "paper_se", "paper_stars",
        "our_coef", "se_within", "p_within", "stars_within",
        "se_cluster", "p_cluster", "stars_cluster",
        "same_sign", "n_obs", "n_country", "r2", "countries",
    ]
    lookup = {name: i for i, name in enumerate(fitted["names"])}
    with open(path_csv, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for name in REGRESSORS:
            i = lookup[name]
            coef = float(fitted["beta"][i])
            published = name == "gpr_z"
            writer.writerow({
                "variable": name,
                "label": LABELS[name],
                "paper_coef": f"{PAPER_GPR['coef']:.3f}" if published else "",
                "paper_se": f"{PAPER_GPR['se']:.3f}" if published else "",
                "paper_stars": PAPER_GPR["stars"] if published else "",
                "our_coef": f"{coef:.10g}",
                "se_within": f"{float(fitted['se_within'][i]):.10g}",
                "p_within": f"{fitted['p_within'][i]:.10g}",
                "stars_within": est.stars(fitted["p_within"][i]),
                "se_cluster": f"{float(fitted['se_cluster'][i]):.10g}",
                "p_cluster": f"{fitted['p_cluster'][i]:.10g}",
                "stars_cluster": est.stars(fitted["p_cluster"][i]),
                "same_sign": same_sign(PAPER_GPR["coef"], coef) if published else "",
                "n_obs": fitted["n_obs"],
                "n_country": fitted["n_country"],
                "r2": f"{fitted['r2']:.10g}",
                "countries": "; ".join(fitted["countries"]),
            })

    body = []
    for name in REGRESSORS:
        i = lookup[name]
        coef = float(fitted["beta"][i])
        within_stars = est.stars(fitted["p_within"][i])
        cluster_stars = est.stars(fitted["p_cluster"][i])
        if name == "gpr_z":
            paper = f"{PAPER_GPR['coef']:.3f}{PAPER_GPR['stars']}"
            paper_se = f"{PAPER_GPR['se']:.3f}"
            sign = same_sign(PAPER_GPR["coef"], coef)
        else:
            paper = "not published"
            paper_se = ""
            sign = ""
        body.append(
            "<tr>"
            f"<td>{escape(LABELS[name])}</td>"
            f"<td>{paper}</td>"
            f"<td>{paper_se}</td>"
            f"<td>{est.fmt(coef)}{within_stars}</td>"
            f"<td>{est.fmt(float(fitted['se_within'][i]))}</td>"
            f"<td>{est.fmt(fitted['p_within'][i])}</td>"
            f"<td>{est.fmt(coef)}{cluster_stars}</td>"
            f"<td>{est.fmt(float(fitted['se_cluster'][i]))}</td>"
            f"<td>{est.fmt(fitted['p_cluster'][i])}</td>"
            f"<td>{sign}</td>"
            "</tr>"
        )
    dropped_text = ", ".join(dropped) if dropped else "none"
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Emerging-market exchange rate</title>
<style>
body {{ font: 16px/1.5 Georgia, serif; max-width: 1100px; margin: 2em auto; padding: 0 1em; color: #20242a; }}
table {{ border-collapse: collapse; width: 100%; margin: 1em 0; font-size: .88em; }}
th, td {{ border-bottom: 1px solid #ccc; padding: .4em; text-align: right; vertical-align: top; }}
th:first-child, td:first-child {{ text-align: left; }}
.note {{ background: #fff5da; padding: 1em; border: 1px solid #e6d59d; }}
</style>
</head>
<body>
<h1>Emerging-economy exchange rate</h1>
<div class="note">
<p>Equation (2) on the literature-review panel, emerging economies only. GPR is the country article-share index, standardized within each country. The other regressors are lagged one month. Country fixed effects. The within R-squared is the share of within-country variation explained.</p>
<p>N = {fitted['n_obs']}. Countries = {fitted['n_country']}: {escape(', '.join(fitted['countries']))}. Months = {escape(fitted['month_min'])} to {escape(fitted['month_max'])}. Within R-squared = {est.fmt(fitted['r2'])}. The paper's emerging exchange-rate column has GPR −0.010 (standard error 0.002), 1,970 observations, and an R-squared of 0.651.</p>
<p>Dropped for a missing regressor: {escape(dropped_text)}. Table 3 includes these controls and does not print their coefficients. Stars on our columns use the standard error in that column. *** p&lt;0.01, ** p&lt;0.05, * p&lt;0.10.</p>
</div>
<h2>Table 3, emerging economies, exchange rate</h2>
<table>
<thead><tr><th>Variable</th><th>Paper</th><th>Paper SE</th><th>Ours, within SE</th><th>Within SE</th><th>Within p</th><th>Ours, clustered SE</th><th>Clustered SE</th><th>Clustered p</th><th>Same sign</th></tr></thead>
<tbody>
{''.join(body)}
</tbody>
</table>
</body>
</html>
"""
    with open(path_html, "w", encoding="utf-8") as handle:
        handle.write(html)


def main():
    rows, emerging = load_rows()
    fitted = fit(rows)
    dropped = [name for name in (NAMES[iso] for iso in emerging if iso in NAMES) if name not in fitted["countries"]]
    # Keep countries that appear in the emerging panel but not in the name map.
    extra = [iso for iso in emerging if iso not in NAMES and NAMES.get(iso, iso) not in fitted["countries"]]
    dropped.extend(extra)
    write_outputs(
        os.path.join(OUTPUT, "literature_emerging_fx_results.csv"),
        os.path.join(OUTPUT, "literature_emerging_fx_results.html"),
        fitted,
        dropped,
    )
    print(
        "N", fitted["n_obs"],
        "countries", fitted["n_country"],
        ",".join(fitted["countries"]),
        "R2", fitted["r2"],
        "dropped", ",".join(dropped),
    )
    for name, coef, se_w, se_c, p_w, p_c in zip(
        fitted["names"], fitted["beta"], fitted["se_within"], fitted["se_cluster"],
        fitted["p_within"], fitted["p_cluster"],
    ):
        print(name, coef, "within", se_w, p_w, "cluster", se_c, p_c)


if __name__ == "__main__":
    main()
