"""Emerging-economy replication of the paper's exchange-rate column.

Table 3, column 4, not the pooled Table 2. South Korea and Taiwan are left out.
Industrial production is left out because the annual index is missing for most
emerging markets and would drop them. Country fixed effects and standard errors
clustered by country. GPR is the global index divided by its estimation-sample
standard deviation. The sample is 2000-2023.
"""

import os
from html import escape

import numpy as np

import run_export_reer_2sls as est


OUTPUT = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")), "output")

ADVANCED = {"South Korea", "Taiwan"}

REGRESSORS = [
    "gpr_z",
    "policy_rate_l1",
    "inflation_l1",
    "log_oil_l1",
    "log_vix_l1",
    "log_gepu_l1",
    "financial_development_l1",
    "debt_gdp_l1",
]

LABELS = {
    "gpr_z": "GPR",
    "policy_rate_l1": "Policy rate",
    "inflation_l1": "Inflation",
    "log_oil_l1": "Oil price",
    "log_vix_l1": "VIX",
    "log_gepu_l1": "Global EPU",
    "financial_development_l1": "Financial development",
    "debt_gdp_l1": "Debt/GDP",
}

# Table 3, emerging economies, exchange-rate column. Controls are included in
# that column but the paper does not print their coefficients.
PAPER_GPR = {"coef": -0.010, "stars": "***", "n_obs": 1970, "r2": 0.651}


def in_window(month):
    return "2000-01" <= month <= "2023-12"


def build_rows(sources):
    rows = []
    for country in sources["countries"]:
        if country in ADVANCED:
            continue
        for month in sorted(sources["reer"].get(country, {})):
            if not in_window(month):
                continue
            lag = est.add_months(month, -1)
            lag_year = int(lag[:4])
            record = {
                "country": country,
                "year_month": month,
                "log_reer": est.positive_log(sources["reer"][country][month]),
                "gpr": sources["gpr"].get(month),
                "policy_rate_l1": sources["policy"].get(country, {}).get(lag),
                "inflation_l1": sources["inflation"].get(country, {}).get(lag),
                "log_oil_l1": est.positive_log(sources["oil"].get(lag)),
                "log_vix_l1": est.positive_log(sources["vix"].get(lag)),
                "log_gepu_l1": est.positive_log(sources["gepu"].get(lag)),
                "financial_development_l1": sources["fd"].get(country, {}).get(lag_year),
                "debt_gdp_l1": sources["debt"].get(country, {}).get(lag_year),
            }
            needed = ["log_reer", "gpr", *REGRESSORS[1:]]
            if any(record[name] is None for name in needed):
                continue
            rows.append(record)
    gpr_values = np.array([row["gpr"] for row in rows], dtype=float)
    gpr_sd = float(gpr_values.std(ddof=1))
    gpr_mean = float(gpr_values.mean())
    for row in rows:
        row["gpr_z"] = (row["gpr"] - gpr_mean) / gpr_sd
    return rows, gpr_mean, gpr_sd


def fit(rows):
    countries = sorted({row["country"] for row in rows})
    y = np.array([row["log_reer"] for row in rows], dtype=float)
    x_matrix, names, base = est.design_matrix(rows, REGRESSORS, countries)
    n, k = x_matrix.shape
    beta = np.linalg.lstsq(x_matrix, y, rcond=None)[0]
    residual = y - x_matrix @ beta
    grouped = est.cluster_indices(rows)
    variance, _ = est.cluster_variance(x_matrix, residual, grouped, n, k)
    stats = est.inference(names, beta, variance, len(grouped))
    sst = float(np.sum((y - np.mean(y)) ** 2))
    return {
        "countries": countries,
        "base_country": base,
        "n_obs": n,
        "n_country": len(grouped),
        "df": len(grouped) - 1,
        "month_min": min(row["year_month"] for row in rows),
        "month_max": max(row["year_month"] for row in rows),
        "r2": float(1.0 - np.sum(residual**2) / sst),
        "stats": stats,
    }


def same_sign(paper_coef, our_coef):
    if paper_coef == 0 or our_coef == 0:
        return "no"
    return "yes" if (paper_coef > 0) == (our_coef > 0) else "no"


def write_outputs(path_csv, path_html, fit, gpr_mean, gpr_sd):
    import csv

    fields = [
        "variable", "label", "paper_coef", "paper_stars",
        "our_coef", "our_se", "our_p", "our_stars",
        "same_sign", "same_significance",
        "n_obs", "n_country", "r2", "countries",
    ]
    with open(path_csv, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for name in REGRESSORS:
            stat = fit["stats"][name]
            our_stars = est.stars(stat["p"])
            published = name == "gpr_z"
            writer.writerow({
                "variable": name,
                "label": LABELS[name],
                "paper_coef": f"{PAPER_GPR['coef']:.3f}" if published else "",
                "paper_stars": PAPER_GPR["stars"] if published else "",
                "our_coef": f"{stat['coef']:.10g}",
                "our_se": f"{stat['se']:.10g}",
                "our_p": f"{stat['p']:.10g}",
                "our_stars": our_stars,
                "same_sign": same_sign(PAPER_GPR["coef"], stat["coef"]) if published else "",
                "same_significance": (
                    "yes" if our_stars == PAPER_GPR["stars"] else "no"
                ) if published else "",
                "n_obs": fit["n_obs"],
                "n_country": fit["n_country"],
                "r2": f"{fit['r2']:.10g}",
                "countries": "; ".join(fit["countries"]),
            })

    body = []
    for name in REGRESSORS:
        stat = fit["stats"][name]
        our_stars = est.stars(stat["p"])
        if name == "gpr_z":
            paper_cell = f"{PAPER_GPR['coef']:.3f}{PAPER_GPR['stars']}"
            sign_cell = same_sign(PAPER_GPR["coef"], stat["coef"])
            star_cell = "yes" if our_stars == PAPER_GPR["stars"] else "no"
        else:
            paper_cell = "not published"
            sign_cell = ""
            star_cell = ""
        body.append(
            "<tr>"
            f"<td>{escape(LABELS[name])}</td>"
            f"<td>{paper_cell}</td>"
            f"<td>{est.fmt(stat['coef'])}{our_stars}</td>"
            f"<td>{est.fmt(stat['se'])}</td>"
            f"<td>{est.fmt(stat['p'])}</td>"
            f"<td>{sign_cell}</td>"
            f"<td>{star_cell}</td>"
            "</tr>"
        )
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Emerging-economy exchange-rate replication</title>
<style>
body {{ font: 16px/1.5 Georgia, serif; max-width: 980px; margin: 2em auto; padding: 0 1em; color: #20242a; }}
table {{ border-collapse: collapse; width: 100%; margin: 1em 0; font-size: .92em; }}
th, td {{ border-bottom: 1px solid #ccc; padding: .45em; text-align: right; vertical-align: top; }}
th:first-child, td:first-child {{ text-align: left; }}
.note {{ background: #fff5da; padding: 1em; border: 1px solid #e6d59d; }}
</style>
</head>
<body>
<h1>Emerging-economy exchange rate</h1>
<div class="note">
<p>The comparison is Table 3, column 4, the emerging-economy exchange rate. In that column GPR is −0.010 and significant at 1 percent. The pooled sample in Table 2 is not the benchmark: there GPR is 0.001 and not significant, because advanced economies dilute the depreciation.</p>
<p>N = {fit['n_obs']}. Emerging economies = {fit['n_country']}: {escape(', '.join(fit['countries']))}. Months = {escape(fit['month_min'])} to {escape(fit['month_max'])}. R-squared = {est.fmt(fit['r2'])}. The paper's emerging exchange-rate column has 1,970 observations and an R-squared of 0.651. South Korea and Taiwan are excluded.</p>
<p>GPR is the global index, centered and divided by its sample standard deviation ({est.fmt(gpr_sd, 2)}; mean {est.fmt(gpr_mean, 2)}). The paper uses a country GPR index standardized within each country, so the comparison is the sign and the significance star. A negative coefficient is a depreciation of the real effective exchange rate.</p>
<p>Industrial production is omitted. It is an annual index and is missing for Argentina, Peru, South Africa, India, Indonesia, the Philippines, and Thailand, so requiring it would leave only Chile, Hungary, Mexico, and Turkey. The paper includes industrial production, but Table 3 does not print that coefficient. Financial development is <code>fd_fdi_ovrl</code>, not the paper's 0-to-1 index. Central bank independence is not in <code>cleaned/</code>. Controls are lagged one month. Standard errors are clustered by country.</p>
</div>
<h2>Table 3, emerging economies, exchange rate</h2>
<table>
<thead><tr><th>Variable</th><th>Paper</th><th>Ours</th><th>Our SE</th><th>Our p-value</th><th>Same sign</th><th>Same stars</th></tr></thead>
<tbody>
{''.join(body)}
</tbody>
</table>
<p><em>Significance:</em> *** p&lt;0.01, ** p&lt;0.05, * p&lt;0.10. Table 3 includes the other controls and country fixed effects, and it does not print their coefficients.</p>
</body>
</html>
"""
    with open(path_html, "w", encoding="utf-8") as handle:
        handle.write(html)


def main():
    rows, gpr_mean, gpr_sd = build_rows({
        "countries": est.read_country_order(),
        "reer": est.read_reer(),
        "gpr": est.read_monthly_global("gpr_index.csv", "value", series="GPR"),
        "policy": est.read_monthly_country("policy_rate.csv", "value"),
        "inflation": est.read_monthly_country("inflation.csv", "value"),
        "oil": est.read_monthly_global("oil_price.csv", "wti_spot"),
        "vix": est.read_monthly_global("vix.csv", "value"),
        "gepu": est.read_monthly_global("gepu_current.csv", "value"),
        "fd": est.read_annual("financial_development.csv", "year", "fd_fdi_ovrl"),
        "debt": est.read_annual("debt_gdp.csv", "period", "debt_gdp_pct", frequency="Annual"),
    })
    fitted = fit(rows)
    write_outputs(
        os.path.join(OUTPUT, "paper_fx_replication_results.csv"),
        os.path.join(OUTPUT, "paper_fx_replication_results.html"),
        fitted,
        gpr_mean,
        gpr_sd,
    )
    print(
        "N", fitted["n_obs"],
        "countries", fitted["n_country"],
        ",".join(fitted["countries"]),
        "R2", fitted["r2"],
    )
    for name in REGRESSORS:
        stat = fitted["stats"][name]
        print(name, stat["coef"], stat["se"], stat["p"], est.stars(stat["p"]))


if __name__ == "__main__":
    main()
