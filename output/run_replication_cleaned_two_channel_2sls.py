"""2SLS of log REER on fitted real exports and fitted inflation.

Two first stages. Real exports keep inflation as a regressor. The inflation
equation drops it. GPR, one WGI dimension, and their interaction are excluded
from the second stage. Country fixed effects are in every stage. Standard
errors are clustered by country and use the structural residual.
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

PANEL_NAME = {"Turkiye": "Turkey", "Korea": "South Korea"}

DIMENSIONS = [
    ("rl", "Rule of law"),
    ("ge", "Government effectiveness"),
    ("rq", "Regulatory quality"),
]

EXCLUDED = ["gpr", "wgi_l1", "wgi_x_gpr"]

INCLUDED = [
    "policy_rate_l1",
    "log_industrial_production_l1",
    "log_oil_l1",
    "log_vix_l1",
    "log_gepu_l1",
    "financial_development_l1",
    "central_bank_independence_l1",
    "debt_gdp_l1",
]

EXPORT_COLUMNS = [*EXCLUDED, "inflation_l1", *INCLUDED]
INFLATION_COLUMNS = [*EXCLUDED, *INCLUDED]
SECOND_COLUMNS = ["log_export_hat", "inflation_hat", *INCLUDED]

LAG_LOGS = {
    "log_industrial_production_l1": "industrial_production",
    "log_oil_l1": "oil_price",
    "log_vix_l1": "vix",
    "log_gepu_l1": "gepu",
}
LAG_LEVELS = {
    "policy_rate_l1": "policy_rate",
    "financial_development_l1": "financial_development",
    "central_bank_independence_l1": "central_bank_independence",
    "debt_gdp_l1": "public_debt_gdp",
}

LABELS = {
    "log_export_hat": "Fitted log real exports",
    "inflation_hat": "Fitted inflation",
    "gpr": "GPR, contemporaneous",
    "wgi_l1": "WGI, lagged",
    "wgi_x_gpr": "WGI × GPR",
    "inflation_l1": "Inflation, lagged",
    "policy_rate_l1": "Policy rate, lagged",
    "log_industrial_production_l1": "Log industrial production, lagged",
    "log_oil_l1": "Log oil price, lagged",
    "log_vix_l1": "Log VIX, lagged",
    "log_gepu_l1": "Log global EPU, lagged",
    "financial_development_l1": "Financial development, lagged",
    "central_bank_independence_l1": "Central bank independence, lagged",
    "debt_gdp_l1": "Debt/GDP, lagged",
}


def num(text):
    text = (text or "").strip()
    if not text:
        return None
    return float(text)


def load_country_month(path, value_name):
    out = defaultdict(dict)
    with open(path, encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            value = num(row[value_name])
            if value is not None:
                out[row["country"].strip()][row["year_month"].strip()] = value
    return out


def load_replication():
    index = {}
    countries = set()
    with open(PANEL, encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            country = PANEL_NAME.get(row["country"].strip(), row["country"].strip())
            index[(country, row["date"][:7])] = row
            countries.add(country)
    return index, countries


def control_values(source):
    names = list(LAG_LOGS) + list(LAG_LEVELS)
    if source is None:
        return {name: None for name in names}
    out = {}
    for name, column in LAG_LOGS.items():
        out[name] = est.positive_log(num(source[column]))
    for name, column in LAG_LEVELS.items():
        out[name] = num(source[column])
    return out


def build_panel(replication, panel_countries, exports, inflation, wgi):
    rows = []
    dropped = []
    candidates = sorted(set(exports) & set(inflation) & panel_countries)
    for country in candidates:
        has_ip = any(
            (source.get("industrial_production") or "").strip()
            for (name, _month), source in replication.items()
            if name == country
        )
        if not has_ip:
            dropped.append((country, "no industrial production in the replication file"))
            continue
        country_rows = []
        for month, source in replication.items():
            if month[0] != country or num(source.get("reer")) is None:
                continue
            year_month = month[1]
            lag = est.add_months(year_month, -1)
            current = replication.get((country, year_month))
            record = {
                "country": country,
                "year_month": year_month,
                "log_reer": est.positive_log(num(source.get("reer"))),
                "log_export_l1": est.positive_log(exports[country].get(lag)),
                "inflation_l1": inflation[country].get(lag),
                "wgi_raw": wgi.get(country, {}).get(int(lag[:4])),
                "gpr_raw": num(current["gpr"]) if current is not None else None,
            }
            record.update(control_values(replication.get((country, lag))))
            needed = [
                "log_reer", "log_export_l1", "inflation_l1", "wgi_raw", "gpr_raw",
                *LAG_LOGS, *LAG_LEVELS,
            ]
            if any(record[name] is None for name in needed):
                continue
            country_rows.append(record)
        if country_rows:
            rows.extend(country_rows)
        else:
            dropped.append((country, "no month with exports, inflation, the exchange rate, WGI, GPR, and every control"))
    outside = sorted((set(exports) & set(inflation)) - panel_countries)
    for country in outside:
        dropped.append((country, "not in the replication file"))
    return shape_instruments(rows), dropped


def shape_instruments(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["country"]].append(row["gpr_raw"])
    moments = {}
    for country, values in grouped.items():
        array = np.array(values, dtype=float)
        sd = float(array.std(ddof=1)) if len(array) > 1 else float("nan")
        moments[country] = (float(array.mean()), sd)
    kept = []
    for row in rows:
        mean, sd = moments[row["country"]]
        if not np.isfinite(sd) or sd == 0:
            continue
        row["gpr"] = (row["gpr_raw"] - mean) / sd
        kept.append(row)
    if not kept:
        raise RuntimeError("No complete cases after standardizing GPR.")
    center = float(np.mean([row["wgi_raw"] for row in kept]))
    for row in kept:
        row["wgi_l1"] = row["wgi_raw"] - center
        row["wgi_x_gpr"] = row["wgi_l1"] * row["gpr"]
    return kept


def partial_f(beta, variance, names, df2):
    indexes = [names.index(name) for name in EXCLUDED]
    restriction = beta[indexes]
    cov = variance[np.ix_(indexes, indexes)]
    wald = float(restriction.T @ np.linalg.inv(cov) @ restriction)
    q = len(indexes)
    f_stat = wald / q
    return f_stat, float(est.f_sf(f_stat, q, df2))


def first_stage(z_matrix, z_names, outcome, grouped, g):
    n, k = z_matrix.shape
    beta = np.linalg.lstsq(z_matrix, outcome, rcond=None)[0]
    residual = outcome - z_matrix @ beta
    variance, _ = est.cluster_variance(z_matrix, residual, grouped, n, k)
    stats = est.inference(z_names, beta, variance, g)
    f_stat, f_p = partial_f(beta, variance, z_names, g - 1)
    return {
        "fitted": z_matrix @ beta,
        "stats": stats,
        "partial_f": f_stat,
        "partial_f_p": f_p,
        "partial_f_df1": len(EXCLUDED),
        "partial_f_df2": g - 1,
    }


def fit_2sls(rows):
    countries = sorted({row["country"] for row in rows})
    if len(countries) < 2:
        raise RuntimeError("Need at least two countries for country fixed effects.")
    y = np.array([row["log_reer"] for row in rows], dtype=float)
    export = np.array([row["log_export_l1"] for row in rows], dtype=float)
    inflation = np.array([row["inflation_l1"] for row in rows], dtype=float)
    z_export, export_names, base = est.design_matrix(rows, EXPORT_COLUMNS, countries)
    z_inflation, inflation_names, _ = est.design_matrix(rows, INFLATION_COLUMNS, countries)
    n = len(rows)
    grouped = est.cluster_indices(rows)
    g = len(grouped)
    export_stage = first_stage(z_export, export_names, export, grouped, g)
    inflation_stage = first_stage(z_inflation, inflation_names, inflation, grouped, g)

    included_and_fe = z_inflation[:, 1 + len(EXCLUDED):]
    included_names = inflation_names[1 + len(EXCLUDED):]
    x_struct = np.column_stack([np.ones(n), export, inflation, included_and_fe])
    xhat = np.column_stack([
        np.ones(n), export_stage["fitted"], inflation_stage["fitted"], included_and_fe,
    ])
    x_names = ["const", "log_export_hat", "inflation_hat", *included_names]
    k_x = xhat.shape[1]
    if n <= k_x:
        raise RuntimeError(f"Insufficient observations (N={n}) for the parameter count.")
    beta = np.linalg.lstsq(xhat, y, rcond=None)[0]
    structural = y - x_struct @ beta
    variance, _ = est.cluster_variance(xhat, structural, grouped, n, k_x)
    return {
        "countries": countries,
        "base_country": base,
        "n_obs": n,
        "n_country": g,
        "month_min": min(row["year_month"] for row in rows),
        "month_max": max(row["year_month"] for row in rows),
        "export": export_stage,
        "inflation": inflation_stage,
        "second": est.inference(x_names, beta, variance, g),
    }


def stat_fields(stat):
    return {key: f"{stat[key]:.10g}" for key in ("coef", "se", "t", "p", "ci_lo", "ci_hi")}


def write_csv(path, results):
    fields = [
        "dimension", "dimension_label", "stage", "variable", "label",
        "coef", "se", "t", "p", "ci_lo", "ci_hi",
        "n_obs", "n_country",
        "export_partial_f", "export_partial_f_p",
        "inflation_partial_f", "inflation_partial_f_p",
        "partial_f_df1", "partial_f_df2",
        "month_min", "month_max", "countries", "dropped",
    ]
    stages = [
        ("second", SECOND_COLUMNS, "second"),
        ("export", EXPORT_COLUMNS, "export"),
        ("inflation", INFLATION_COLUMNS, "inflation"),
    ]
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for code, label, fit, dropped in results:
            shared = {
                "dimension": code,
                "dimension_label": label,
                "n_obs": fit["n_obs"],
                "n_country": fit["n_country"],
                "export_partial_f": f"{fit['export']['partial_f']:.10g}",
                "export_partial_f_p": f"{fit['export']['partial_f_p']:.10g}",
                "inflation_partial_f": f"{fit['inflation']['partial_f']:.10g}",
                "inflation_partial_f_p": f"{fit['inflation']['partial_f_p']:.10g}",
                "partial_f_df1": fit["export"]["partial_f_df1"],
                "partial_f_df2": fit["export"]["partial_f_df2"],
                "month_min": fit["month_min"],
                "month_max": fit["month_max"],
                "countries": "; ".join(fit["countries"]),
                "dropped": "; ".join(f"{country}: {reason}" for country, reason in dropped),
            }
            for stage_name, columns, stats_key in stages:
                stats = fit[stats_key] if stage_name == "second" else fit[stage_name]["stats"]
                for variable in columns:
                    if variable.startswith("fe_"):
                        continue
                    writer.writerow({
                        **shared,
                        "stage": stage_name,
                        "variable": variable,
                        "label": LABELS[variable],
                        **stat_fields(stats[variable]),
                    })


def cell(stat):
    return (
        f"{est.fmt(stat['coef'])}{est.stars(stat['p'])}<br>"
        f"({est.fmt(stat['se'])})<br>"
        f"[{est.fmt(stat['ci_lo'])}, {est.fmt(stat['ci_hi'])}]"
    )


def write_html(path, results):
    header = "".join(f"<th>{escape(label)}</th>" for _, label, _, _ in results)

    def row(stats_of, variable, label):
        cells = []
        for _, _, fit, _ in results:
            stats = fit["second"] if stats_of == "second" else fit[stats_of]["stats"]
            cells.append(f"<td>{cell(stats[variable])}</td>")
        return f"<tr><td>{escape(label)}</td>{''.join(cells)}</tr>"

    sample = "".join(
        f"<td>{fit['n_obs']}<br>{fit['n_country']} countries<br>"
        f"{escape(fit['month_min'])} to {escape(fit['month_max'])}</td>"
        for _, _, fit, _ in results
    )
    export_f = "".join(
        f"<td>{est.fmt(fit['export']['partial_f'], 2)}<br>p={est.fmt(fit['export']['partial_f_p'])}<br>"
        f"F({fit['export']['partial_f_df1']}, {fit['export']['partial_f_df2']})</td>"
        for _, _, fit, _ in results
    )
    inflation_f = "".join(
        f"<td>{est.fmt(fit['inflation']['partial_f'], 2)}<br>p={est.fmt(fit['inflation']['partial_f_p'])}<br>"
        f"F({fit['inflation']['partial_f_df1']}, {fit['inflation']['partial_f_df2']})</td>"
        for _, _, fit, _ in results
    )
    kept = "".join(
        f"<li>{escape(label)}: {escape(', '.join(fit['countries']))}</li>"
        for _, label, fit, _ in results
    )
    dropped = "".join(
        f"<li>{escape(country)}: {escape(reason)}</li>" for country, reason in results[0][3]
    )
    second_rows = "".join(row("second", name, LABELS[name]) for name in SECOND_COLUMNS)
    export_rows = "".join(row("export", name, LABELS[name]) for name in EXPORT_COLUMNS)
    inflation_rows = "".join(row("inflation", name, LABELS[name]) for name in INFLATION_COLUMNS)
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Exports, inflation, and the exchange rate</title>
<style>
body {{ font: 16px/1.5 Georgia, serif; max-width: 1100px; margin: 2em auto; padding: 0 1em; color: #20242a; }}
table {{ border-collapse: collapse; width: 100%; margin: 1em 0; font-size: .92em; }}
th, td {{ border-bottom: 1px solid #ccc; padding: .45em; text-align: right; vertical-align: top; }}
th:first-child, td:first-child {{ text-align: left; }}
.note {{ background: #fff5da; padding: 1em; border: 1px solid #e6d59d; }}
</style>
</head>
<body>
<h1>Real exports, inflation, and the exchange rate</h1>
<div class="note">
<p>Second stage: log real effective exchange rate on the fitted log real exports, the fitted inflation rate, and the paper's lagged controls except inflation and GPR. The exchange rate is <code>reer</code> in <code>cleaned/replication_cleaned</code>.</p>
<p>Export first stage: log real exports, lagged one month, on GPR, one WGI dimension, their interaction, lagged inflation, and the other lagged controls. Inflation first stage: lagged inflation, not logged, on the same regressors with inflation removed. GPR, WGI, and the interaction are the excluded instruments. GPR is standardized within country. WGI is centered before the interaction.</p>
<p>Each cell shows the coefficient, the country-clustered standard error in parentheses, and the 95% confidence interval. The second-stage standard errors use the structural residual. *** p&lt;0.01, ** p&lt;0.05, * p&lt;0.10.</p>
</div>
<h2>Second stage</h2>
<table>
<thead><tr><th>Variable</th>{header}</tr></thead>
<tbody>
{second_rows}
<tr><td>Observations</td>{sample}</tr>
<tr><td>Export-equation partial F on GPR, WGI, and WGI × GPR</td>{export_f}</tr>
<tr><td>Inflation-equation partial F on GPR, WGI, and WGI × GPR</td>{inflation_f}</tr>
</tbody>
</table>
<h2>First stage: real exports</h2>
<table>
<thead><tr><th>Variable</th>{header}</tr></thead>
<tbody>
{export_rows}
</tbody>
</table>
<h2>First stage: inflation</h2>
<table>
<thead><tr><th>Variable</th>{header}</tr></thead>
<tbody>
{inflation_rows}
</tbody>
</table>
<h2>Countries that remain</h2>
<ul>
{kept}
</ul>
<h2>Countries that drop</h2>
<ul>
{dropped}
</ul>
</body>
</html>
"""
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(html)


def main():
    replication, panel_countries = load_replication()
    exports = load_country_month(os.path.join(CLEANED, "real_export.csv"), "real_export")
    inflation = load_country_month(os.path.join(CLEANED, "inflation.csv"), "value")
    results = []
    for code, label in DIMENSIONS:
        rows, dropped = build_panel(
            replication, panel_countries, exports, inflation, est.read_wgi(code),
        )
        fit = fit_2sls(rows)
        results.append((code, label, fit, dropped))
        export_coef = fit["second"]["log_export_hat"]
        inflation_coef = fit["second"]["inflation_hat"]
        print(
            label,
            "N", fit["n_obs"],
            "countries", fit["n_country"],
            fit["month_min"], fit["month_max"],
            "export", round(export_coef["coef"], 4),
            "p", round(export_coef["p"], 4),
            "inflation", round(inflation_coef["coef"], 4),
            "inflation_p", round(inflation_coef["p"], 4),
            "F_export", round(fit["export"]["partial_f"], 2),
            "F_inflation", round(fit["inflation"]["partial_f"], 2),
        )
        print(" ", ", ".join(fit["countries"]))
        print("  dropped", "; ".join(f"{country}: {reason}" for country, reason in dropped))
    write_csv(os.path.join(OUTPUT, "replication_cleaned_two_channel_2sls_results.csv"), results)
    write_html(os.path.join(OUTPUT, "replication_cleaned_two_channel_2sls_results.html"), results)


if __name__ == "__main__":
    main()
