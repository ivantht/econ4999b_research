"""2SLS of log REER on the lagged export trend, with controls in both stages.

Each WGI dimension and its interaction with contemporaneous GPR are the
excluded instruments. GPR and the paper's significant exchange-rate controls
enter both stages. Country fixed effects are in both stages. Standard errors
are clustered by country and use the structural residual.
"""

import csv
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

CONTROLS = [
    "gpr",
    "policy_rate_l1",
    "log_industrial_production_l1",
    "inflation_l1",
    "log_oil_l1",
    "log_vix_l1",
    "log_gepu_l1",
    "financial_development_l1",
    "debt_gdp_l1",
]

EXCLUDED = ["wgi_l1", "wgi_x_gpr"]

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
    "debt_gdp_l1": "Debt/GDP, lagged",
}


def build_panel(sources):
    rows = []
    for country in sources["countries"]:
        for month in sorted(sources["reer"].get(country, {})):
            lag = est.add_months(month, -1)
            lag_year = int(lag[:4])
            ip = sources["ip"].get(country, {}).get(lag_year)
            record = {
                "country": country,
                "year_month": month,
                "log_reer": est.positive_log(sources["reer"][country][month]),
                "ytrend_l1": sources["trend"].get(country, {}).get(lag),
                "wgi_l1": sources["wgi"].get(country, {}).get(lag_year),
                "gpr": sources["gpr"].get(month),
                "policy_rate_l1": sources["policy"].get(country, {}).get(lag),
                "log_industrial_production_l1": est.positive_log(ip),
                "inflation_l1": sources["inflation"].get(country, {}).get(lag),
                "log_oil_l1": est.positive_log(sources["oil"].get(lag)),
                "log_vix_l1": est.positive_log(sources["vix"].get(lag)),
                "log_gepu_l1": est.positive_log(sources["gepu"].get(lag)),
                "financial_development_l1": sources["fd"].get(country, {}).get(lag_year),
                "debt_gdp_l1": sources["debt"].get(country, {}).get(lag_year),
            }
            needed = ["log_reer", "ytrend_l1", "wgi_l1", *CONTROLS]
            if any(record[name] is None for name in needed):
                continue
            record["wgi_x_gpr"] = record["wgi_l1"] * record["gpr"]
            rows.append(record)
    return rows


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
        "month_min", "month_max", "countries",
    ]
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for code, label, fit in results:
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
    header = "".join(f"<th>{escape(label)}</th>" for _, label, _ in results)
    def row(stage, variable, label):
        cells = "".join(f"<td>{cell(fit[stage][variable])}</td>" for _, _, fit in results)
        return f"<tr><td>{escape(label)}</td>{cells}</tr>"

    sample = "".join(
        f"<td>{fit['n_obs']}<br>{fit['n_country']} countries<br>"
        f"{escape(fit['month_min'])} to {escape(fit['month_max'])}</td>"
        for _, _, fit in results
    )
    partial = "".join(
        f"<td>{est.fmt(fit['partial_f'], 2)}<br>p={est.fmt(fit['partial_f_p'])}<br>"
        f"F({fit['partial_f_df1']}, {fit['partial_f_df2']})</td>"
        for _, _, fit in results
    )
    countries = "".join(
        f"<li>{escape(label)}: {escape(', '.join(fit['countries']))}</li>"
        for _, label, fit in results
    )
    second_rows = "".join(row("second", name, LABELS[name]) for name in ["ytrend_hat", *CONTROLS])
    first_rows = "".join(row("first", name, LABELS[name]) for name in [*EXCLUDED, *CONTROLS])
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>2SLS with controls in both stages</title>
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
<p>Second stage: log real effective exchange rate on the fitted lagged export trend, the controls, and country fixed effects.</p>
<p>First stage: the lagged Hodrick-Prescott log export trend on one lagged WGI dimension, that dimension times contemporaneous GPR, the same controls, and country fixed effects. WGI and WGI × GPR are the excluded instruments. GPR is contemporaneous. Every other control is lagged one month.</p>
<p>Each cell shows the coefficient, the country-clustered standard error in parentheses, and the 95% confidence interval. The standard errors use the 2SLS structural residual.</p>
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
<p><em>Significance:</em> *** p&lt;0.01, ** p&lt;0.05, * p&lt;0.10.</p>
<h2>First stage</h2>
<table>
<thead><tr><th>Variable</th>{header}</tr></thead>
<tbody>
{first_rows}
</tbody>
</table>
<h2>Countries</h2>
<ul>
{countries}
</ul>
</body>
</html>
"""
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(html)


def load_sources():
    return {
        "countries": est.read_country_order(),
        "reer": est.read_reer(),
        "trend": est.read_export_trend(),
        "gpr": est.read_monthly_global("gpr_index.csv", "value", series="GPR"),
        "policy": est.read_monthly_country("policy_rate.csv", "value"),
        "ip": est.read_annual("industrial_production.csv", "year", "index"),
        "inflation": est.read_monthly_country("inflation.csv", "value"),
        "oil": est.read_monthly_global("oil_price.csv", "wti_spot"),
        "vix": est.read_monthly_global("vix.csv", "value"),
        "gepu": est.read_monthly_global("gepu_current.csv", "value"),
        "fd": est.read_annual("financial_development.csv", "year", "fd_fdi_ovrl"),
        "debt": est.read_annual("debt_gdp.csv", "period", "debt_gdp_pct", frequency="Annual"),
    }


def main():
    if abs(est.student_t_ppf(0.975, 12) - 2.1788128296666256) > 1e-6:
        raise RuntimeError("The t critical value does not match the reference.")
    common = load_sources()
    results = []
    for code, label in DIMENSIONS:
        sources = dict(common)
        sources["wgi"] = est.read_wgi(code)
        fit = fit_2sls(build_panel(sources))
        results.append((code, label, fit))
        export_coef = fit["second"]["ytrend_hat"]
        wgi_coef = fit["first"]["wgi_l1"]
        interaction = fit["first"]["wgi_x_gpr"]
        print(
            label,
            "N", fit["n_obs"],
            "countries", fit["n_country"],
            "export", export_coef["coef"],
            "p", export_coef["p"],
            "wgi", wgi_coef["coef"],
            "wgi_p", wgi_coef["p"],
            "interaction", interaction["coef"],
            "interaction_p", interaction["p"],
            "F", fit["partial_f"],
        )
    write_csv(os.path.join(OUTPUT, "export_reer_2sls_controls_results.csv"), results)
    write_html(os.path.join(OUTPUT, "export_reer_2sls_controls_results.html"), results)


if __name__ == "__main__":
    main()
