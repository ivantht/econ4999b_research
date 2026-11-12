"""Author's GPR coefficient on the exchange rate and capital-flow volatility.

Equation (2) on the literature-review panel. No WGI. Country fixed effects.
Reports the ordinary within standard error and the clustered standard error.
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
    "BE": "Belgium", "BR": "Brazil", "CA": "Canada", "CL": "Chile", "CN": "China",
    "CO": "Colombia", "DE": "Germany", "DK": "Denmark", "ES": "Spain", "FI": "Finland",
    "FR": "France", "HU": "Hungary", "ID": "Indonesia", "IN": "India", "IT": "Italy",
    "JP": "Japan", "KR": "South Korea", "MX": "Mexico", "MY": "Malaysia", "NL": "Netherlands",
    "PH": "Philippines", "PL": "Poland", "PT": "Portugal", "SE": "Sweden", "TH": "Thailand",
    "TR": "Turkey", "UA": "Ukraine", "US": "United States", "ZA": "South Africa",
}

REGRESSORS = [
    "gpr_z", "rate_l1", "ln_ip_l1", "infl_l1", "ln_oil_l1", "ln_vix_l1",
    "ln_gepu_l1", "fd_l1", "cbi_l1", "debt_l1",
]

OUTCOMES = {
    "ln_reer": "Exchange rate",
    "cf_vol": "Capital-flow volatility",
}

PAPER = {
    ("all", "ln_reer"): {"coef": 0.001, "stars": "", "n_obs": 5671, "r2": 0.517},
    ("all", "cf_vol"): {"coef": 0.867, "stars": "**", "n_obs": 4779, "r2": 0.058},
    ("emerging", "ln_reer"): {"coef": -0.010, "stars": "***", "n_obs": 1970, "r2": 0.651},
    ("emerging", "cf_vol"): {"coef": 3.144, "stars": "*", "n_obs": 1569, "r2": 0.011},
}


def num(text):
    text = (text or "").strip()
    if not text:
        return None
    return float(text)


def load_rows():
    rows = []
    with open(PANEL, encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            record = {
                "iso": row["iso"].strip(),
                "country": NAMES.get(row["iso"].strip(), row["iso"].strip()),
                "year_month": row["date"][:7],
                "group": row["group"].strip(),
                "ln_reer": num(row["ln_reer"]),
                "cf_vol": num(row["cf_vol"]),
            }
            for name in REGRESSORS:
                record[name] = num(row[name])
            rows.append(record)
    return rows


def complete(rows, outcome):
    kept = []
    for row in rows:
        if row[outcome] is None or any(row[name] is None for name in REGRESSORS):
            continue
        kept.append(row)
    return kept


def demean(values, countries):
    out = values.copy()
    for iso in set(countries):
        index = countries == iso
        out[index] -= out[index].mean(axis=0)
    return out


def fit(rows, outcome):
    countries = np.array([row["iso"] for row in rows])
    y = demean(np.array([row[outcome] for row in rows], dtype=float), countries)
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
    present = []
    for country in NAMES.values():
        if any(row["country"] == country for row in rows) and country not in present:
            present.append(country)
    for row in rows:
        if row["country"] not in present:
            present.append(row["country"])
    gpr_index = names.index("gpr_z")
    return {
        "coef": float(beta[gpr_index]),
        "se_within": float(se_within[gpr_index]),
        "p_within": float(est.student_t_sf_two_tail(
            beta[gpr_index] / se_within[gpr_index], dof
        )),
        "se_cluster": float(se_cluster[gpr_index]),
        "p_cluster": float(est.student_t_sf_two_tail(
            beta[gpr_index] / se_cluster[gpr_index], g - 1
        )),
        "n_obs": n,
        "n_country": g,
        "r2": float(1.0 - (residual @ residual) / float(y @ y)),
        "month_min": min(row["year_month"] for row in rows),
        "month_max": max(row["year_month"] for row in rows),
        "countries": present,
    }


def same_sign(paper_coef, our_coef):
    if paper_coef == 0 or our_coef == 0:
        return "no"
    return "yes" if (paper_coef > 0) == (our_coef > 0) else "no"


def reaches(our_stars, paper_stars):
    rank = {"": 0, "*": 1, "**": 2, "***": 3}
    return "yes" if rank[our_stars] >= rank[paper_stars] and paper_stars != "" else (
        "yes" if our_stars == paper_stars else "no"
    )


def write_outputs(path_csv, path_html, results):
    fields = [
        "sample", "outcome", "paper_coef", "paper_stars",
        "our_coef", "se_within", "p_within", "stars_within",
        "se_cluster", "p_cluster", "stars_cluster",
        "same_sign", "within_reaches_paper_star", "cluster_reaches_paper_star",
        "n_obs", "n_country", "r2", "countries",
    ]
    with open(path_csv, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for key, fitted in results.items():
            sample, outcome = key
            paper = PAPER[key]
            within_stars = est.stars(fitted["p_within"])
            cluster_stars = est.stars(fitted["p_cluster"])
            writer.writerow({
                "sample": sample,
                "outcome": OUTCOMES[outcome],
                "paper_coef": f"{paper['coef']:.3f}",
                "paper_stars": paper["stars"],
                "our_coef": f"{fitted['coef']:.10g}",
                "se_within": f"{fitted['se_within']:.10g}",
                "p_within": f"{fitted['p_within']:.10g}",
                "stars_within": within_stars,
                "se_cluster": f"{fitted['se_cluster']:.10g}",
                "p_cluster": f"{fitted['p_cluster']:.10g}",
                "stars_cluster": cluster_stars,
                "same_sign": same_sign(paper["coef"], fitted["coef"]),
                "within_reaches_paper_star": reaches(within_stars, paper["stars"]),
                "cluster_reaches_paper_star": reaches(cluster_stars, paper["stars"]),
                "n_obs": fitted["n_obs"],
                "n_country": fitted["n_country"],
                "r2": f"{fitted['r2']:.10g}",
                "countries": "; ".join(fitted["countries"]),
            })

    body = []
    for key, fitted in results.items():
        sample, outcome = key
        paper = PAPER[key]
        within_stars = est.stars(fitted["p_within"])
        cluster_stars = est.stars(fitted["p_cluster"])
        paper_cell = f"{paper['coef']:.3f}{paper['stars']}" if paper["stars"] or paper["coef"] else f"{paper['coef']:.3f}"
        if paper["stars"] == "" :
            paper_cell = f"{paper['coef']:.3f}"
        else:
            paper_cell = f"{paper['coef']:.3f}{paper['stars']}"
        body.append(
            "<tr>"
            f"<td>{escape(sample)}</td>"
            f"<td>{escape(OUTCOMES[outcome])}</td>"
            f"<td>{paper_cell}</td>"
            f"<td>{est.fmt(fitted['coef'])}{within_stars}</td>"
            f"<td>{est.fmt(fitted['se_within'])}</td>"
            f"<td>{est.fmt(fitted['p_within'])}</td>"
            f"<td>{est.fmt(fitted['coef'])}{cluster_stars}</td>"
            f"<td>{est.fmt(fitted['se_cluster'])}</td>"
            f"<td>{est.fmt(fitted['p_cluster'])}</td>"
            f"<td>{same_sign(paper['coef'], fitted['coef'])}</td>"
            f"<td>{reaches(within_stars, paper['stars'])}</td>"
            f"<td>{reaches(cluster_stars, paper['stars'])}</td>"
            f"<td>{fitted['n_obs']}</td>"
            f"<td>{escape(', '.join(fitted['countries']))}</td>"
            "</tr>"
        )
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Author GPR significance</title>
<style>
body {{ font: 16px/1.5 Georgia, serif; max-width: 1200px; margin: 2em auto; padding: 0 1em; color: #20242a; }}
table {{ border-collapse: collapse; width: 100%; margin: 1em 0; font-size: .82em; }}
th, td {{ border-bottom: 1px solid #ccc; padding: .4em; text-align: right; vertical-align: top; }}
th:nth-child(-n+2), td:nth-child(-n+2), td:last-child {{ text-align: left; }}
.note {{ background: #fff5da; padding: 1em; border: 1px solid #e6d59d; }}
</style>
</head>
<body>
<h1>Author's GPR on the exchange rate and capital-flow volatility</h1>
<div class="note">
<p>Equation (2) on the literature-review panel. GPR is the country index standardized within each country. Controls are lagged one month and include industrial production, financial development, central bank independence, and debt. No WGI term. Country fixed effects.</p>
<p>"Reaches the paper's star" is yes when our p-value is at least as strong as the star the paper prints. The full-sample exchange rate has no star in the paper, so that cell is yes only when our coefficient is also insignificant. *** p&lt;0.01, ** p&lt;0.05, * p&lt;0.10.</p>
</div>
<table>
<thead>
<tr>
<th>Sample</th><th>Outcome</th><th>Paper GPR</th>
<th>Ours, within</th><th>Within SE</th><th>Within p</th>
<th>Ours, clustered</th><th>Clustered SE</th><th>Clustered p</th>
<th>Same sign</th><th>Within reaches star</th><th>Cluster reaches star</th>
<th>N</th><th>Countries</th>
</tr>
</thead>
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
    loaded = load_rows()
    results = {}
    for sample, emerging in (("all", False), ("emerging", True)):
        pool = [row for row in loaded if (not emerging or row["group"] == "Emerging")]
        for outcome in OUTCOMES:
            rows = complete(pool, outcome)
            fitted = fit(rows, outcome)
            results[(sample, outcome)] = fitted
            print(
                sample, outcome,
                "N", fitted["n_obs"],
                "GPR", fitted["coef"],
                "within", fitted["p_within"], est.stars(fitted["p_within"]),
                "cluster", fitted["p_cluster"], est.stars(fitted["p_cluster"]),
            )
    write_outputs(
        os.path.join(OUTPUT, "author_gpr_significance.csv"),
        os.path.join(OUTPUT, "author_gpr_significance.html"),
        results,
    )


if __name__ == "__main__":
    main()
