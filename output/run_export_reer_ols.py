"""OLS of log REER on the lagged HP export trend and the paper's significant controls.

Country fixed effects and standard errors clustered by country follow the
exchange-rate column of the source paper. A missing value drops that
country-month. Nothing is imputed.
"""

import csv
import math
import os
from collections import defaultdict
from html import escape

import numpy as np

import run_export_reer_2sls as est


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUTPUT = os.path.join(ROOT, "output")

REGRESSORS = [
    "ytrend_l1",
    "policy_rate_l1",
    "log_industrial_production_l1",
    "inflation_l1",
    "log_oil_l1",
    "log_vix_l1",
    "log_gepu_l1",
    "financial_development_l1",
    "debt_gdp_l1",
]

LABELS = {
    "log_reer": "Log real effective exchange rate",
    "ytrend_l1": "Export trend, lagged",
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
        months = sorted(sources["reer"].get(country, {}))
        for month in months:
            lag = est.add_months(month, -1)
            lag_year = int(lag[:4])
            ip = sources["ip"].get(country, {}).get(lag_year)
            record = {
                "country": country,
                "year_month": month,
                "log_reer": est.positive_log(sources["reer"][country][month]),
                "ytrend_l1": sources["trend"].get(country, {}).get(lag),
                "policy_rate_l1": sources["policy"].get(country, {}).get(lag),
                "log_industrial_production_l1": est.positive_log(ip),
                "inflation_l1": sources["inflation"].get(country, {}).get(lag),
                "log_oil_l1": est.positive_log(sources["oil"].get(lag)),
                "log_vix_l1": est.positive_log(sources["vix"].get(lag)),
                "log_gepu_l1": est.positive_log(sources["gepu"].get(lag)),
                "financial_development_l1": sources["fd"].get(country, {}).get(lag_year),
                "debt_gdp_l1": sources["debt"].get(country, {}).get(lag_year),
            }
            if any(record[name] is None for name in ["log_reer", *REGRESSORS]):
                continue
            rows.append(record)
    return rows


def fit_ols(rows):
    countries = sorted({row["country"] for row in rows})
    if len(countries) < 2:
        raise RuntimeError("Need at least two countries for country fixed effects.")
    y = np.array([row["log_reer"] for row in rows], dtype=float)
    x_matrix, names, base = est.design_matrix(rows, REGRESSORS, countries)
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
        "k_params": k,
        "df": len(grouped) - 1,
        "month_min": min(row["year_month"] for row in rows),
        "month_max": max(row["year_month"] for row in rows),
        "r2": r2,
        "stats": stats,
    }


def summary_rows(rows):
    out = []
    for name in ["log_reer", *REGRESSORS]:
        values = np.array([row[name] for row in rows], dtype=float)
        demeaned = []
        outcome = []
        for country in sorted({row["country"] for row in rows}):
            country_values = np.array([row[name] for row in rows if row["country"] == country], dtype=float)
            country_outcome = np.array([row["log_reer"] for row in rows if row["country"] == country], dtype=float)
            demeaned.append(country_values - country_values.mean())
            outcome.append(country_outcome - country_outcome.mean())
        within = np.concatenate(demeaned)
        outcome_within = np.concatenate(outcome)
        total_var = float(values.var(ddof=1))
        within_var = float(within.var(ddof=1))
        if name == "log_reer":
            correlation = 1.0
        elif float(within.std(ddof=1)) == 0.0 or float(outcome_within.std(ddof=1)) == 0.0:
            correlation = float("nan")
        else:
            correlation = float(np.corrcoef(within, outcome_within)[0, 1])
        out.append({
            "variable": name,
            "label": LABELS[name],
            "n": len(values),
            "mean": float(values.mean()),
            "sd": float(values.std(ddof=1)),
            "min": float(values.min()),
            "max": float(values.max()),
            "within_sd": float(within.std(ddof=1)),
            "between_share": 1.0 - within_var / total_var if total_var > 0 else float("nan"),
            "within_corr_log_reer": correlation,
        })
    return out


def write_results(path, fit):
    fields = [
        "variable", "label", "coef", "se", "t", "p", "ci_lo", "ci_hi",
        "n_obs", "n_country", "df", "r2", "month_min", "month_max", "countries",
    ]
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for name in REGRESSORS:
            stat = fit["stats"][name]
            writer.writerow({
                "variable": name,
                "label": LABELS[name],
                "coef": f"{stat['coef']:.10g}",
                "se": f"{stat['se']:.10g}",
                "t": f"{stat['t']:.10g}",
                "p": f"{stat['p']:.10g}",
                "ci_lo": f"{stat['ci_lo']:.10g}",
                "ci_hi": f"{stat['ci_hi']:.10g}",
                "n_obs": fit["n_obs"],
                "n_country": fit["n_country"],
                "df": fit["df"],
                "r2": f"{fit['r2']:.10g}",
                "month_min": fit["month_min"],
                "month_max": fit["month_max"],
                "countries": "; ".join(fit["countries"]),
            })


def write_summary(path, rows):
    fields = [
        "variable", "label", "n", "mean", "sd", "min", "max",
        "within_sd", "between_share", "within_corr_log_reer",
    ]
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({
                key: row[key] if key in ("variable", "label", "n") else f"{row[key]:.10g}"
                for key in fields
            })


def fmt(value, digits=4):
    if isinstance(value, float) and not math.isfinite(value):
        return ""
    return f"{value:.{digits}f}"


def write_html(path, fit, summary, reer_countries):
    result_rows = []
    for name in REGRESSORS:
        stat = fit["stats"][name]
        result_rows.append(
            "<tr>"
            f"<td>{escape(LABELS[name])}</td>"
            f"<td>{fmt(stat['coef'])}{est.stars(stat['p'])}</td>"
            f"<td>{fmt(stat['se'])}</td>"
            f"<td>{fmt(stat['p'])}</td>"
            f"<td>[{fmt(stat['ci_lo'])}, {fmt(stat['ci_hi'])}]</td>"
            "</tr>"
        )
    summary_rows_html = []
    for row in summary:
        summary_rows_html.append(
            "<tr>"
            f"<td>{escape(row['label'])}</td>"
            f"<td>{fmt(row['mean'])}</td>"
            f"<td>{fmt(row['sd'])}</td>"
            f"<td>{fmt(row['min'])}</td>"
            f"<td>{fmt(row['max'])}</td>"
            f"<td>{fmt(row['within_sd'])}</td>"
            f"<td>{fmt(row['between_share'])}</td>"
            f"<td>{fmt(row['within_corr_log_reer'])}</td>"
            "</tr>"
        )
    order = est.read_country_order()
    no_reer = [country for country in order if country not in reer_countries]
    no_ip = [country for country in sorted(reer_countries) if country not in fit["countries"]]
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Export trend and real effective exchange rate</title>
<style>
body {{ font: 16px/1.5 Georgia, serif; max-width: 1100px; margin: 2em auto; padding: 0 1em; color: #20242a; }}
table {{ border-collapse: collapse; width: 100%; margin: 1em 0; font-size: .92em; }}
th, td {{ border-bottom: 1px solid #ccc; padding: .45em; text-align: right; vertical-align: top; }}
th:first-child, td:first-child {{ text-align: left; }}
.note {{ background: #fff5da; padding: 1em; border: 1px solid #e6d59d; }}
code {{ font-size: .92em; }}
</style>
</head>
<body>
<h1>Export trend and the real effective exchange rate</h1>
<div class="note">
<p><code>log(REER)</code> on the lagged Hodrick-Prescott log trend of nominal exports, the controls that are significant in the paper's exchange-rate column, and country fixed effects.</p>
<p>Controls are lagged one month. Annual industrial production, financial development, and debt/GDP use the year of that lagged month, so January uses the previous year. GPR and WGI are omitted: GPR is not significant in that column, and the paper's central-bank-independence term is not significant either.</p>
<p>Standard errors are clustered by country. N = {fit['n_obs']}. Countries = {fit['n_country']}. Months = {escape(fit['month_min'])} to {escape(fit['month_max'])}. R-squared = {fmt(fit['r2'])}. The fixed-effect base country is {escape(fit['base_country'])}.</p>
<p>Countries in the regression: {escape(', '.join(fit['countries']))}.</p>
<p>No exchange-rate series: {escape(', '.join(no_reer))}. Exchange rate is present, but industrial production is not, so the country is out of this complete-case sample: {escape(', '.join(no_ip))}.</p>
</div>
<h2>Regression</h2>
<table>
<thead><tr><th>Variable</th><th>Coefficient</th><th>Std. error</th><th>p-value</th><th>95% CI</th></tr></thead>
<tbody>
{''.join(result_rows)}
</tbody>
</table>
<p><em>Significance:</em> *** p&lt;0.01, ** p&lt;0.05, * p&lt;0.10.</p>
<h2>Summary statistics on the estimation sample</h2>
<table>
<thead><tr><th>Series</th><th>Mean</th><th>SD</th><th>Min</th><th>Max</th><th>Within SD</th><th>Share across countries</th><th>Within correlation with log REER</th></tr></thead>
<tbody>
{''.join(summary_rows_html)}
</tbody>
</table>
<p>Within SD is the standard deviation after subtracting each country's own mean. The share across countries is the part of the variance removed by country fixed effects.</p>
</body>
</html>
"""
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(html)


def main():
    if abs(est.student_t_ppf(0.975, 12) - 2.1788128296666256) > 1e-6:
        raise RuntimeError("The t critical value does not match the reference.")
    reer = est.read_reer()
    rows = build_panel({
        "countries": est.read_country_order(),
        "reer": reer,
        "trend": est.read_export_trend(),
        "policy": est.read_monthly_country("policy_rate.csv", "value"),
        "ip": est.read_annual("industrial_production.csv", "year", "index"),
        "inflation": est.read_monthly_country("inflation.csv", "value"),
        "oil": est.read_monthly_global("oil_price.csv", "wti_spot"),
        "vix": est.read_monthly_global("vix.csv", "value"),
        "gepu": est.read_monthly_global("gepu_current.csv", "value"),
        "fd": est.read_annual("financial_development.csv", "year", "fd_fdi_ovrl"),
        "debt": est.read_annual("debt_gdp.csv", "period", "debt_gdp_pct", frequency="Annual"),
    })
    fit = fit_ols(rows)
    stats_rows = summary_rows(rows)
    write_results(os.path.join(OUTPUT, "export_reer_ols_results.csv"), fit)
    write_summary(os.path.join(OUTPUT, "export_reer_ols_summary.csv"), stats_rows)
    write_html(os.path.join(OUTPUT, "export_reer_ols_results.html"), fit, stats_rows, set(reer))
    export_stat = fit["stats"]["ytrend_l1"]
    print(
        "N", fit["n_obs"],
        "countries", fit["n_country"],
        ",".join(fit["countries"]),
        "months", fit["month_min"], fit["month_max"],
        "export", export_stat["coef"],
        "se", export_stat["se"],
        "p", export_stat["p"],
    )


if __name__ == "__main__":
    main()
