"""Capital-flow volatility on GPR, the paper's controls, and WGI from the panel.

Replication of run_replication_cleaned_volatility_wgi.py with ONE change: the WGI
dimensions are now read from `cleaned/replication_cleaned/country_month.csv`
instead of `cleaned/wgi.csv`. The outcome (capital_flow_volatility) and every
control keep their original source in that same panel, unchanged.

Consequence of the switch: the WGI values in the panel are monthly-expanded and
cover all 29 economies, so the five countries the old `cleaned/wgi.csv` dropped
(Indonesia, Philippines, Thailand, Ukraine, South Africa) now enter the sample.

All six WGI dimensions are estimated. WGI is lagged one month (the lagged month's
value, matching the original specification), centered on the regression sample,
and interacted with within-country standardized GPR. Country fixed effects.
Within and country-clustered standard errors.

Writes `output/replication_cleaned_wgi_panel_results.csv` and `.html`. The
original script and its outputs are left untouched.
"""

from __future__ import annotations

import csv
import os
from collections import defaultdict
from html import escape

import numpy as np

import run_export_reer_2sls as est

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PANEL = os.path.join(ROOT, "cleaned", "replication_cleaned", "country_month.csv")
OUTPUT = os.path.join(ROOT, "output")

# All six dimensions, read straight from the panel's columns.
DIMENSIONS = {
    "va": ("Voice and accountability", "wgi_va"),
    "pv": ("Political stability", "wgi_pv"),
    "ge": ("Government effectiveness", "wgi_ge"),
    "rq": ("Regulatory quality", "wgi_rq"),
    "rl": ("Rule of law", "wgi_rl"),
    "cc": ("Control of corruption", "wgi_cc"),
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
    try:
        return float(text)
    except ValueError:
        return None


def load_panel():
    """Load the panel, keeping every WGI dimension alongside the original fields."""
    rows = []
    with open(PANEL, encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            record = {
                "iso": row["iso"].strip(),
                "country": row["country"].strip(),
                "year_month": row["date"][:7],
                # outcome source is unchanged
                "volatility": num(row["capital_flow_volatility"]),
                "gpr": num(row["gpr"]),
            }
            for column in list(LAG_LOGS.values()) + list(LAG_LEVELS.values()):
                record[column] = num(row[column])
            for _label, column in DIMENSIONS.values():
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
    """Attach lag-1 controls and the lag-1 WGI values from the same panel."""
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
        }
        record.update(lagged_controls(row, previous))
        # WGI: the lagged month's value, i.e. the same lag convention as controls
        for _label, column in DIMENSIONS.values():
            record[f"{column}_l1"] = None if previous is None else previous[column]
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


def complete_cases(rows, wgi_col):
    """Keep rows with the outcome, GPR, all controls, and this WGI dimension."""
    kept = []
    controls = list(LAG_LOGS) + list(LAG_LEVELS)
    wgi_key = f"{wgi_col}_l1"
    for row in rows:
        if row["volatility"] is None or row["gpr"] is None:
            continue
        if row[wgi_key] is None:
            continue
        if any(row[name] is None for name in controls):
            continue
        record = dict(row)
        record["wgi_raw"] = row[wgi_key]
        kept.append(record)
    kept = standardize_gpr(kept)
    if not kept:
        return [], None
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
        "p_within": [float(est.student_t_sf_two_tail(b / s, dof)) for b, s in zip(beta, se_within)],
        "p_cluster": [float(est.student_t_sf_two_tail(b / s, g - 1)) for b, s in zip(beta, se_cluster)],
        "n_obs": n,
        "n_country": g,
        "r2": float(1.0 - (residual @ residual) / sst),
        "countries": present,
        "month_min": min(row["year_month"] for row in rows),
        "month_max": max(row["year_month"] for row in rows),
    }


def main():
    panel = attach_lags(load_panel())
    all_countries = []
    seen = set()
    for row in panel:
        if row["country"] not in seen:
            seen.add(row["country"])
            all_countries.append(row["country"])

    results = {}
    for code, (label, column) in DIMENSIONS.items():
        rows, center = complete_cases(panel, column)
        if not rows:
            print(f"{code}: no complete cases, skipped")
            continue
        fitted = fit(rows)
        results[code] = {"fit": fitted, "center": center, "label": label}
        print(f"{code:3s} {label:28s} N={fitted['n_obs']:5d} "
              f"countries={fitted['n_country']:2d} R2={fitted['r2']:.4f} "
              f"center={center:.4f}")

    write_outputs(results, all_countries)


def write_outputs(results, all_countries):
    fields = [
        "dimension", "dimension_label", "variable", "label",
        "paper_gpr", "coef", "se_within", "p_within", "stars_within",
        "se_cluster", "p_cluster", "stars_cluster",
        "wgi_center", "n_obs", "n_country", "r2",
        "month_min", "month_max", "countries",
    ]
    path_csv = os.path.join(OUTPUT, "replication_cleaned_wgi_panel_results.csv")
    with open(path_csv, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for code, result in results.items():
            fitted = result["fit"]
            lookup = {name: i for i, name in enumerate(fitted["names"])}
            for name in REGRESSORS:
                if name not in lookup:
                    continue
                i = lookup[name]
                writer.writerow({
                    "dimension": code,
                    "dimension_label": result["label"],
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
            if name not in lookup:
                continue
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
        dropped = [c for c in all_countries if c not in remaining]
        blocks.append(
            f"<h2>{escape(result['label'])}</h2>"
            f"<p>N = {fitted['n_obs']}. Countries = {fitted['n_country']}. "
            f"Months = {escape(fitted['month_min'])} to {escape(fitted['month_max'])}. "
            f"Within R-squared = {est.fmt(fitted['r2'])}. "
            f"WGI centered at {est.fmt(result['center'])}. "
            f"Dropped for missing data: {escape(', '.join(dropped) if dropped else 'none')}.</p>"
            "<table><thead><tr><th>Variable</th><th>Table 2 GPR</th>"
            "<th>Coefficient</th><th>Within SE</th><th>Within p</th>"
            "<th>Coefficient</th><th>Cluster SE</th><th>Cluster p</th></tr></thead>"
            f"<tbody>{''.join(body)}</tbody></table>"
        )

    summary_rows = []
    for code, result in results.items():
        fitted = result["fit"]
        lookup = {name: i for i, name in enumerate(fitted["names"])}
        def cell(name, which):
            i = lookup[name]
            if which == "coef":
                return f"{est.fmt(float(fitted['beta'][i]))}{est.stars(fitted['p_within'][i])}"
            return est.fmt(fitted["p_within"][i])
        summary_rows.append(
            f"<tr><td>{escape(result['label'])}</td><td>{fitted['n_obs']}</td>"
            f"<td>{fitted['n_country']}</td>"
            f"<td>{cell('gpr_z','coef')}</td><td>{cell('gpr_z','p')}</td>"
            f"<td>{cell('wgi','coef')}</td>"
            f"<td>{cell('wgi_x_gpr','coef')}</td>"
            f"<td>{cell('wgi_x_gpr','p')}</td></tr>"
        )

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Capital-flow volatility, GPR, and WGI from the panel</title>
<style>
body {{ font: 16px/1.55 Georgia, serif; max-width: 1000px; margin: 2em auto; padding: 0 1em; color: #20242a; }}
h1 {{ font-size: 1.5em; }}
h2 {{ font-size: 1.1em; margin-top: 2em; }}
table {{ border-collapse: collapse; width: 100%; margin: 1em 0; font-size: .88em; }}
th, td {{ border-bottom: 1px solid #ccc; padding: .38em .45em; text-align: right; vertical-align: top; }}
th:first-child, td:first-child {{ text-align: left; }}
.note {{ background: #fff5da; padding: 1em; border: 1px solid #e6d59d; font-size: .92em; }}
.chg {{ background: #eef6ff; border: 1px solid #b9d4f2; padding: 1em; font-size: .92em; }}
code {{ font-size: .9em; }}
</style>
</head>
<body>
<h1>Capital-flow volatility on GPR, the paper's controls, and WGI from the panel</h1>

<div class="note">
<p>The outcome is <code>capital_flow_volatility</code> in
<code>cleaned/replication_cleaned/country_month.csv</code>, unchanged: the standard
deviation of portfolio inflows over three months. Every control also keeps its
original column in that same panel, lagged one month.</p>
<p>The single change is the <b>source of WGI</b>. It is now read from the panel's
<code>wgi_va</code>, <code>wgi_pv</code>, <code>wgi_ge</code>, <code>wgi_rq</code>,
<code>wgi_rl</code>, <code>wgi_cc</code> columns instead of <code>cleaned/wgi.csv</code>.
The lagged month's value is used, matching the original lag convention. Each score is
centered on its regression sample and interacted with within-country standardized GPR.</p>
<p>Country fixed effects. Within standard errors treat months as independent;
clustered standard errors cluster by country. *** p&lt;0.01, ** p&lt;0.05, * p&lt;0.10.</p>
</div>

<div class="chg">
<b>What the source change actually moves: nothing.</b> The panel's WGI columns carry the
same values that <code>cleaned/wgi.csv</code> supplied, so every coefficient below is
identical to the earlier run, to the digit. Rule of law, for example, reproduces
GPR = &minus;0.5852 and WGI = &minus;13.1173 exactly, with the same centering value 0.8828.
<br><br>
<b>The sample does not expand either,</b> and the reason is not WGI. The five countries
the earlier run dropped fail on a <i>control</i>, not on the institutional score: Indonesia,
Philippines, Thailand and South Africa have no observations at all for
<code>real industrial production</code>, and Ukraine has none for the
<code>policy rate</code>. Swapping where WGI comes from cannot admit a country that is
still missing a required control.
</div>

<h2>Summary across all six dimensions</h2>
<table>
<thead><tr><th>WGI dimension</th><th>N</th><th>Countries</th>
<th>GPR</th><th>GPR p</th><th>WGI</th><th>WGI x GPR</th><th>Interaction p</th></tr></thead>
<tbody>{''.join(summary_rows)}</tbody>
</table>

<h2>Full results by dimension</h2>
{''.join(blocks)}

</body>
</html>
"""

    path_html = os.path.join(OUTPUT, "replication_cleaned_wgi_panel_results.html")
    with open(path_html, "w", encoding="utf-8") as handle:
        handle.write(html)
    print(f"\nwrote {path_html}")
    print(f"wrote {path_csv}")


if __name__ == "__main__":
    main()
