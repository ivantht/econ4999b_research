"""2SLS of log REER on the lagged nominal-export trend.

GPR and the paper's controls enter both stages. One WGI dimension and its
interaction with GPR are the excluded instruments. Country fixed effects are
in both stages. Standard errors are clustered by country and use the
structural residual.
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

EXCLUDED = ["wgi_l1", "wgi_x_gpr"]

CONTROLS = [
    "gpr",
    "policy_rate_l1",
    "log_industrial_production_l1",
    "inflation_l1",
    "log_oil_l1",
    "log_vix_l1",
    "log_gepu_l1",
    "financial_development_l1",
    "central_bank_independence_l1",
    "debt_gdp_l1",
]

LABELS = {
    "ytrend_hat": "Fitted export trend",
    "wgi_l1": "WGI, lagged",
    "wgi_x_gpr": "WGI × GPR",
    "gpr": "GPR, contemporaneous",
    "policy_rate_l1": "Policy rate, lagged",
    "log_industrial_production_l1": "Log industrial production, lagged",
    "inflation_l1": "Inflation, lagged",
    "log_oil_l1": "Log oil price, lagged",
    "log_vix_l1": "Log VIX, lagged",
    "log_gepu_l1": "Log global EPU, lagged",
    "financial_development_l1": "Financial development, lagged",
    "central_bank_independence_l1": "Central bank independence, lagged",
    "debt_gdp_l1": "Debt/GDP, lagged",
}

LAG_LOGS = {
    "log_industrial_production_l1": "industrial_production",
    "log_oil_l1": "oil_price",
    "log_vix_l1": "vix",
    "log_gepu_l1": "gepu",
}
LAG_LEVELS = {
    "policy_rate_l1": "policy_rate",
    "inflation_l1": "inflation",
    "financial_development_l1": "financial_development",
    "central_bank_independence_l1": "central_bank_independence",
    "debt_gdp_l1": "public_debt_gdp",
}


def num(text):
    text = (text or "").strip()
    if not text:
        return None
    return float(text)


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


def build_panel(replication, panel_countries, reer, trend, wgi):
    rows = []
    dropped = []
    candidates = sorted(set(reer) & set(trend))
    for country in candidates:
        if country not in panel_countries:
            dropped.append((country, "not in the replication file"))
            continue
        has_ip = any(
            (source.get("industrial_production") or "").strip()
            for (name, _month), source in replication.items()
            if name == country
        )
        if not has_ip:
            dropped.append((country, "no industrial production in the replication file"))
            continue
        country_rows = []
        for month in sorted(reer[country]):
            lag = est.add_months(month, -1)
            current = replication.get((country, month))
            record = {
                "country": country,
                "year_month": month,
                "log_reer": est.positive_log(reer[country][month]),
                "ytrend_l1": trend[country].get(lag),
                "wgi_raw": wgi.get(country, {}).get(int(lag[:4])),
                "gpr_raw": num(current["gpr"]) if current is not None else None,
            }
            record.update(control_values(replication.get((country, lag))))
            needed = ["log_reer", "ytrend_l1", "wgi_raw", "gpr_raw", *LAG_LOGS, *LAG_LEVELS]
            if any(record[name] is None for name in needed):
                continue
            country_rows.append(record)
        if country_rows:
            rows.extend(country_rows)
        else:
            dropped.append((country, "no month with the export trend, the exchange rate, WGI, GPR, and every control"))
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
        row["wgi_center"] = center
    return kept


def partial_f_excluded(beta, variance, names, df2):
    indexes = [names.index(name) for name in EXCLUDED]
    restriction = beta[indexes]
    cov = variance[np.ix_(indexes, indexes)]
    wald = float(restriction.T @ np.linalg.inv(cov) @ restriction)
    q = len(indexes)
    f_stat = wald / q
    return f_stat, float(est.f_sf(f_stat, q, df2))


def fit_2sls(rows):
    countries = sorted({row["country"] for row in rows})
    if len(countries) < 2:
        raise RuntimeError("Need at least two countries for country fixed effects.")
    y = np.array([row["log_reer"] for row in rows], dtype=float)
    endog = np.array([row["ytrend_l1"] for row in rows], dtype=float)
    z_matrix, z_names, base = est.design_matrix(rows, [*EXCLUDED, *CONTROLS], countries)
    control_start = 1 + len(EXCLUDED)
    x_matrix = np.column_stack([np.ones(len(rows)), endog, z_matrix[:, control_start:]])
    x_names = ["const", "ytrend_hat", *z_names[control_start:]]
    n, k_z = z_matrix.shape
    k_x = x_matrix.shape[1]
    if n <= max(k_z, k_x):
        raise RuntimeError(f"Insufficient observations (N={n}) for the parameter count.")
    grouped = est.cluster_indices(rows)
    g = len(grouped)

    first_beta = np.linalg.lstsq(z_matrix, endog, rcond=None)[0]
    first_resid = endog - z_matrix @ first_beta
    first_var, _ = est.cluster_variance(z_matrix, first_resid, grouped, n, k_z)
    first_stats = est.inference(z_names, first_beta, first_var, g)
    f_stat, f_p = partial_f_excluded(first_beta, first_var, z_names, g - 1)

    xhat = z_matrix @ np.linalg.lstsq(z_matrix, x_matrix, rcond=None)[0]
    beta = np.linalg.lstsq(xhat, y, rcond=None)[0]
    structural = y - x_matrix @ beta
    second_var, _ = est.cluster_variance(xhat, structural, grouped, n, k_x)
    second_stats = est.inference(x_names, beta, second_var, g)
    return {
        "countries": countries,
        "base_country": base,
        "n_obs": n,
        "n_country": g,
        "month_min": min(row["year_month"] for row in rows),
        "month_max": max(row["year_month"] for row in rows),
        "partial_f": f_stat,
        "partial_f_p": f_p,
        "partial_f_df1": len(EXCLUDED),
        "partial_f_df2": g - 1,
        "first": first_stats,
        "second": second_stats,
    }


def stat_fields(stat):
    return {key: f"{stat[key]:.10g}" for key in ("coef", "se", "t", "p", "ci_lo", "ci_hi")}


def write_csv(path, results):
    fields = [
        "dimension", "dimension_label", "stage", "variable", "label",
        "coef", "se", "t", "p", "ci_lo", "ci_hi",
        "n_obs", "n_country", "partial_f", "partial_f_p", "partial_f_df1", "partial_f_df2",
        "month_min", "month_max", "countries", "dropped",
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
                "partial_f": f"{fit['partial_f']:.10g}",
                "partial_f_p": f"{fit['partial_f_p']:.10g}",
                "partial_f_df1": fit["partial_f_df1"],
                "partial_f_df2": fit["partial_f_df2"],
                "month_min": fit["month_min"],
                "month_max": fit["month_max"],
                "countries": "; ".join(fit["countries"]),
                "dropped": "; ".join(f"{country}: {reason}" for country, reason in dropped),
            }
            for variable in ["ytrend_hat", *CONTROLS]:
                writer.writerow({
                    **shared,
                    "stage": "second",
                    "variable": variable,
                    "label": LABELS[variable],
                    **stat_fields(fit["second"][variable]),
                })
            for variable in [*EXCLUDED, *CONTROLS]:
                writer.writerow({
                    **shared,
                    "stage": "first",
                    "variable": variable,
                    "label": LABELS[variable],
                    **stat_fields(fit["first"][variable]),
                })


def cell(stat):
    return (
        f"{est.fmt(stat['coef'])}{est.stars(stat['p'])}<br>"
        f"({est.fmt(stat['se'])})<br>"
        f"[{est.fmt(stat['ci_lo'])}, {est.fmt(stat['ci_hi'])}]"
    )


def write_html(path, results):
    header = "".join(f"<th>{escape(label)}</th>" for _, label, _, _ in results)
    def row(stage, variable, label):
        cells = "".join(f"<td>{cell(fit[stage][variable])}</td>" for _, _, fit, _ in results)
        return f"<tr><td>{escape(label)}</td>{cells}</tr>"

    sample = "".join(
        f"<td>{fit['n_obs']}<br>{fit['n_country']} countries<br>"
        f"{escape(fit['month_min'])} to {escape(fit['month_max'])}</td>"
        for _, _, fit, _ in results
    )
    partial = "".join(
        f"<td>{est.fmt(fit['partial_f'], 2)}<br>p={est.fmt(fit['partial_f_p'])}<br>"
        f"F({fit['partial_f_df1']}, {fit['partial_f_df2']})</td>"
        for _, _, fit, _ in results
    )
    kept = "".join(
        f"<li>{escape(label)}: {escape(', '.join(fit['countries']))}</li>"
        for _, label, fit, _ in results
    )
    dropped_items = results[0][3]
    dropped = "".join(
        f"<li>{escape(country)}: {escape(reason)}</li>" for country, reason in dropped_items
    )
    second_rows = "".join(row("second", name, LABELS[name]) for name in ["ytrend_hat", *CONTROLS])
    first_rows = "".join(row("first", name, LABELS[name]) for name in [*EXCLUDED, *CONTROLS])
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Export trend and the exchange rate, two stages</title>
<style>
body {{ font: 16px/1.5 Georgia, serif; max-width: 1100px; margin: 2em auto; padding: 0 1em; color: #20242a; }}
table {{ border-collapse: collapse; width: 100%; margin: 1em 0; font-size: .92em; }}
th, td {{ border-bottom: 1px solid #ccc; padding: .45em; text-align: right; vertical-align: top; }}
th:first-child, td:first-child {{ text-align: left; }}
.note {{ background: #fff5da; padding: 1em; border: 1px solid #e6d59d; }}
</style>
</head>
<body>
<h1>Export trend and the real effective exchange rate</h1>
<div class="note">
<p>Second stage: log real effective exchange rate on the fitted lagged export trend, contemporaneous GPR, the paper's controls, and country fixed effects. GPR is included here because the paper treats it as a direct exchange-rate shock. Leaving it out of this stage would force that shock to operate only through exports. The exchange rate is <code>cleaned/real effective exchange rate.xlsx</code>.</p>
<p>First stage: the lagged Hodrick-Prescott trend of nominal exports on one lagged WGI dimension, that dimension times GPR, the same GPR term, the same controls, and country fixed effects. The trend is the <code>ytrend</code> sheet and is not logged again. WGI and WGI × GPR are the excluded instruments. GPR is the country article share, standardized within each country on the months in the regression. WGI is centered on this sample before the interaction, so the first-stage GPR coefficient is the export response at the average WGI score. The other controls come from <code>cleaned/replication_cleaned</code> and are lagged one month.</p>
<p>Each cell shows the coefficient, the country-clustered standard error in parentheses, and the 95% confidence interval. The standard errors use the 2SLS structural residual. *** p&lt;0.01, ** p&lt;0.05, * p&lt;0.10.</p>
</div>
<h2>Second stage</h2>
<table>
<thead><tr><th>Variable</th>{header}</tr></thead>
<tbody>
{second_rows}
<tr><td>Observations</td>{sample}</tr>
<tr><td>First-stage partial F on WGI and WGI × GPR</td>{partial}</tr>
</tbody>
</table>
<h2>First stage</h2>
<table>
<thead><tr><th>Variable</th>{header}</tr></thead>
<tbody>
{first_rows}
</tbody>
</table>
<h2>Countries that remain</h2>
<ul>
{kept}
</ul>
<h2>Countries in the exchange-rate and export files that drop</h2>
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
    reer = est.read_reer()
    trend = est.read_export_trend()
    results = []
    for code, label in DIMENSIONS:
        rows, dropped = build_panel(replication, panel_countries, reer, trend, est.read_wgi(code))
        fit = fit_2sls(rows)
        results.append((code, label, fit, dropped))
        export_coef = fit["second"]["ytrend_hat"]
        gpr_coef = fit["second"]["gpr"]
        wgi_coef = fit["first"]["wgi_l1"]
        interaction = fit["first"]["wgi_x_gpr"]
        print(
            label,
            "N", fit["n_obs"],
            "countries", fit["n_country"],
            fit["month_min"], fit["month_max"],
            "export", round(export_coef["coef"], 4),
            "p", round(export_coef["p"], 4),
            "gpr", round(gpr_coef["coef"], 4),
            "gpr_p", round(gpr_coef["p"], 4),
            "wgi", round(wgi_coef["coef"], 4),
            "wgi_p", round(wgi_coef["p"], 4),
            "interaction", round(interaction["coef"], 4),
            "interaction_p", round(interaction["p"], 4),
            "F", round(fit["partial_f"], 2),
            "F_p", round(fit["partial_f_p"], 4),
        )
        print(" ", ", ".join(fit["countries"]))
        print("  dropped", "; ".join(f"{country}: {reason}" for country, reason in dropped))
    write_csv(os.path.join(OUTPUT, "replication_cleaned_export_reer_2sls_results.csv"), results)
    write_html(os.path.join(OUTPUT, "replication_cleaned_export_reer_2sls_results.html"), results)


if __name__ == "__main__":
    main()
