"""Exchange-rate equation using the country article-share GPR.

GPR is the raw value in cleaned/gpr_country.csv. On the estimation sample it
is standardized within each country. Country fixed effects and standard errors
clustered by country. Sample 2000-2023. Industrial production and central bank
independence are omitted.
"""

import csv
import os
from html import escape

import numpy as np

import run_export_reer_2sls as est


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUTPUT = os.path.join(ROOT, "output")
CLEANED = os.path.join(ROOT, "cleaned")

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

PAPER = {
    "emerging": {
        "table": "Table 3, column 4",
        "coef": -0.010,
        "stars": "***",
        "n_obs": 1970,
        "r2": 0.651,
    },
    "all": {
        "table": "Table 2, column 4",
        "coef": 0.001,
        "stars": "",
        "n_obs": 5671,
        "r2": 0.517,
    },
}


def in_window(month):
    return "2000-01" <= month <= "2023-12"


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


def build_rows(sources, emerging_only):
    rows = []
    for country in sources["countries"]:
        if emerging_only and country in ADVANCED:
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
                "gpr_z": sources["gpr"].get(country, {}).get(month),
                "policy_rate_l1": sources["policy"].get(country, {}).get(lag),
                "inflation_l1": sources["inflation"].get(country, {}).get(lag),
                "log_oil_l1": est.positive_log(sources["oil"].get(lag)),
                "log_vix_l1": est.positive_log(sources["vix"].get(lag)),
                "log_gepu_l1": est.positive_log(sources["gepu"].get(lag)),
                "financial_development_l1": sources["fd"].get(country, {}).get(lag_year),
                "debt_gdp_l1": sources["debt"].get(country, {}).get(lag_year),
            }
            if any(record[name] is None for name in ("log_reer", *REGRESSORS)):
                continue
            rows.append(record)
    standardize_within_country(rows, "gpr_z")
    return rows


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
    y = np.array([row["log_reer"] for row in rows], dtype=float)
    x_matrix, names, base = est.design_matrix(rows, REGRESSORS, present)
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


def same_sign(paper_coef, our_coef):
    if paper_coef == 0 or our_coef == 0:
        return "no"
    return "yes" if (paper_coef > 0) == (our_coef > 0) else "no"


def write_outputs(path_csv, path_html, results):
    fields = [
        "sample", "variable", "label", "paper_coef", "paper_stars",
        "our_coef", "our_se", "our_p", "our_stars",
        "same_sign", "same_significance",
        "n_obs", "n_country", "r2", "countries",
    ]
    with open(path_csv, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for sample, fitted in results.items():
            paper = PAPER[sample]
            for name in REGRESSORS:
                stat = fitted["stats"][name]
                our_stars = est.stars(stat["p"])
                published = name == "gpr_z"
                writer.writerow({
                    "sample": sample,
                    "variable": name,
                    "label": LABELS[name],
                    "paper_coef": f"{paper['coef']:.3f}" if published else "",
                    "paper_stars": paper["stars"] if published else "",
                    "our_coef": f"{stat['coef']:.10g}",
                    "our_se": f"{stat['se']:.10g}",
                    "our_p": f"{stat['p']:.10g}",
                    "our_stars": our_stars,
                    "same_sign": same_sign(paper["coef"], stat["coef"]) if published else "",
                    "same_significance": (
                        "yes" if our_stars == paper["stars"] else "no"
                    ) if published else "",
                    "n_obs": fitted["n_obs"],
                    "n_country": fitted["n_country"],
                    "r2": f"{fitted['r2']:.10g}",
                    "countries": "; ".join(fitted["countries"]),
                })

    sections = []
    for sample, fitted in results.items():
        paper = PAPER[sample]
        body = []
        for name in REGRESSORS:
            stat = fitted["stats"][name]
            our_stars = est.stars(stat["p"])
            if name == "gpr_z":
                paper_cell = f"{paper['coef']:.3f}{paper['stars']}"
                sign_cell = same_sign(paper["coef"], stat["coef"])
                star_cell = "yes" if our_stars == paper["stars"] else "no"
            else:
                paper_cell = "not published for this column" if sample == "emerging" else "published only for the pooled sample"
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
        sections.append(
            f"<h2>{escape(paper['table'])}</h2>"
            f"<p>N = {fitted['n_obs']}. Countries = {fitted['n_country']}: "
            f"{escape(', '.join(fitted['countries']))}. "
            f"Months = {escape(fitted['month_min'])} to {escape(fitted['month_max'])}. "
            f"R-squared = {est.fmt(fitted['r2'])}. "
            f"The paper has {paper['n_obs']:,} observations and an R-squared of {paper['r2']:.3f}.</p>"
            "<table><thead><tr><th>Variable</th><th>Paper GPR</th><th>Ours</th>"
            "<th>Our SE</th><th>Our p-value</th><th>Same sign</th><th>Same stars</th></tr></thead>"
            f"<tbody>{''.join(body)}</tbody></table>"
        )
    emerging = results["emerging"]["stats"]["gpr_z"]
    emerging_stars = est.stars(emerging["p"])
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Exchange rate with country GPR</title>
<style>
body {{ font: 16px/1.5 Georgia, serif; max-width: 980px; margin: 2em auto; padding: 0 1em; color: #20242a; }}
table {{ border-collapse: collapse; width: 100%; margin: 1em 0; font-size: .92em; }}
th, td {{ border-bottom: 1px solid #ccc; padding: .45em; text-align: right; vertical-align: top; }}
th:first-child, td:first-child {{ text-align: left; }}
.note {{ background: #fff5da; padding: 1em; border: 1px solid #e6d59d; }}
</style>
</head>
<body>
<h1>Exchange rate with the country GPR</h1>
<div class="note">
<p>GPR starts as the raw country article share in <code>cleaned/gpr_country.csv</code>. On the months that enter the regression it is standardized within each country, which is the paper's regression step. A negative coefficient is a depreciation of the real effective exchange rate.</p>
<p>The emerging-economy GPR coefficient is {est.fmt(emerging['coef'])}{emerging_stars}. Table 3, column 4 is −0.010 and significant at 1 percent. The sign {"agrees" if emerging["coef"] < 0 else "does not agree"} and the significance star {"agrees" if emerging_stars == "***" else "does not agree"}.</p>
<p>Industrial production is omitted so that Argentina, Peru, South Africa, India, Indonesia, the Philippines, and Thailand remain. Central bank independence is not in <code>cleaned/</code>. Financial development is <code>fd_fdi_ovrl</code>. Controls are lagged one month. Standard errors are clustered by country. *** p&lt;0.01, ** p&lt;0.05, * p&lt;0.10.</p>
</div>
{''.join(sections)}
</body>
</html>
"""
    with open(path_html, "w", encoding="utf-8") as handle:
        handle.write(html)


def main():
    countries = est.read_country_order()
    sources = {
        "countries": countries,
        "reer": est.read_reer(),
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
    for sample, emerging_only in (("emerging", True), ("all", False)):
        rows = build_rows(sources, emerging_only)
        results[sample] = fit(rows, countries)
        fitted = results[sample]
        stat = fitted["stats"]["gpr_z"]
        print(
            sample, "N", fitted["n_obs"], "countries", fitted["n_country"],
            "R2", fitted["r2"],
            "GPR", stat["coef"], stat["se"], stat["p"], est.stars(stat["p"]),
        )
        print(",".join(fitted["countries"]))
    write_outputs(
        os.path.join(OUTPUT, "paper_fx_country_gpr_results.csv"),
        os.path.join(OUTPUT, "paper_fx_country_gpr_results.html"),
        results,
    )


if __name__ == "__main__":
    main()
