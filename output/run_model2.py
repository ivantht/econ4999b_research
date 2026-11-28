"""Model 2: capital-flow volatility as the outcome.

Same estimator and control set as Model 1 (see model1.md), with the outcome
switched from the monthly log-REER change to the level of capital-flow
volatility. One regression per WGI dimension. Country fixed effects.
Standard errors clustered by country.

Reads cleaned/replication_cleaned/country_month.csv.
Writes output/model2_results.csv.
"""

import csv
import os
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_export_reer_2sls as est

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PANEL = os.path.join(ROOT, "cleaned", "replication_cleaned", "country_month.csv")
RESULTS = os.path.join(ROOT, "output", "model2_results.csv")
REPORT = os.path.join(ROOT, "output", "model2_results.html")

OUTCOME = "capital_flow_volatility"

DIMENSIONS = [
    ("wgi_va", "Voice and accountability"),
    ("wgi_pv", "Political stability"),
    ("wgi_ge", "Government effectiveness"),
    ("wgi_rq", "Regulatory quality"),
    ("wgi_rl", "Rule of law"),
    ("wgi_cc", "Control of corruption"),
]

# Lagged control changes, one month back.
LAG_CHANGES = {
    "d_policy_rate": "d_policy_rate",
    "d_inflation": "d_inflation",
    "d_log_oil": "d_log_oil",
    "d_log_gepu": "d_log_gepu",
    "d_financial_development": "d_financial_development",
    "d_public_debt_gdp": "d_public_debt_gdp",
}

CONTROLS = list(LAG_CHANGES) + ["ln_vix"]

WINDOW = ("2002-02", "2022-01")

# Restrict to the emerging-market subsample. The `group` column in the panel
# holds either "Emerging" or "Advanced".
GROUP = "Emerging"


def num(text):
    text = (text or "").strip()
    return None if not text else float(text)


def stars(p):
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""


def load_rows():
    rows = []
    with open(PANEL, encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            rows.append(
                {
                    "iso": row["iso"].strip(),
                    "country": row["country"].strip(),
                    "group": row["group"].strip(),
                    "year_month": row["date"][:7],
                    "raw": row,
                }
            )

    index = {(row["iso"], row["year_month"]): row for row in rows}
    for row in rows:
        previous = index.get(
            (row["iso"], est.add_months(row["year_month"], -1))
        )
        raw = row["raw"]
        row["y"] = num(raw[OUTCOME])
        row["gpr_z"] = num(raw["gpr_z"])
        for key, _ in DIMENSIONS:
            row[key] = num(previous["raw"][key]) if previous else None
        for key in LAG_CHANGES:
            row[key] = num(previous["raw"][key]) if previous else None
        vix = num(previous["raw"]["vix"]) if previous else None
        row["ln_vix"] = est.positive_log(vix)
    return rows


def fit(rows, wgi):
    needed = ["y", "gpr_z", wgi] + CONTROLS
    use = [
        row
        for row in rows
        if row["group"] == GROUP
        and WINDOW[0] <= row["year_month"] <= WINDOW[1]
        and all(row[name] is not None for name in needed)
    ]
    countries = sorted({row["country"] for row in use})

    y = np.array([row["y"] for row in use], dtype=float)
    columns = ["gpr_z", wgi] + CONTROLS

    matrix, names, _ = est.design_matrix(use, columns, countries)
    interaction = np.array(
        [row[wgi] * row["gpr_z"] for row in use], dtype=float
    )
    matrix = np.column_stack([matrix, interaction])
    names = names + ["wgi_x_gpr"]

    beta = np.linalg.lstsq(matrix, y, rcond=None)[0]
    residual = y - matrix @ beta

    grouped = est.cluster_indices(use)
    variance, _ = est.cluster_variance(
        matrix, residual, grouped, len(use), matrix.shape[1]
    )
    inference = est.inference(names, beta, variance, len(grouped))

    fitted = matrix @ beta
    country_of = [row["country"] for row in use]
    y_mean = np.array(
        [np.mean([row["y"] for row in use if row["country"] == c]) for c in country_of]
    )
    fitted_mean = np.array(
        [np.mean([fitted[i] for i, c in enumerate(country_of) if c == country]) for country in country_of]
    )
    within_r2 = 1.0 - np.sum(((y - y_mean) - (fitted - fitted_mean)) ** 2) / np.sum(
        (y - y_mean) ** 2
    )
    r2 = 1.0 - np.sum((y - fitted) ** 2) / np.sum((y - y.mean()) ** 2)

    months = sorted(row["year_month"] for row in use)
    return {
        "n": len(use),
        "g": len(countries),
        "inference": inference,
        "within_r2": float(within_r2),
        "r2": float(r2),
        "first": months[0],
        "last": months[-1],
        "countries": countries,
        "use": use,
    }


TERM_LABELS = {
    "gpr_z": "GPR, standardized",
    "wgi_x_gpr": "WGI x GPR",
    "d_policy_rate": "Policy rate, lagged change",
    "d_inflation": "Inflation, lagged change",
    "d_log_oil": "Log oil price, lagged change",
    "ln_vix": "Log VIX, lagged",
    "d_log_gepu": "Log global EPU, lagged change",
    "d_financial_development": "Financial development, lagged change",
    "d_public_debt_gdp": "Debt/GDP, lagged change",
}


def main():
    rows = load_rows()
    results = {}
    for key, label in DIMENSIONS:
        results[key] = fit(rows, key)
        results[key]["label"] = label

    records = []
    for key, label in DIMENSIONS:
        result = results[key]
        ordered = [(key, "WGI, lagged")] + [
            (name, TERM_LABELS[name])
            for name in ["gpr_z", "wgi_x_gpr"] + CONTROLS
        ]
        for term, term_label in ordered:
            stat = result["inference"][term]
            records.append(
                {
                    "aspect": key.replace("wgi_", ""),
                    "aspect_label": label,
                    "term": term,
                    "term_label": term_label,
                    "coef": stat["coef"],
                    "se": stat["se"],
                    "p": stat["p"],
                    "stars": stars(stat["p"]),
                    "n_obs": result["n"],
                    "n_country": result["g"],
                    "r2": round(result["r2"], 4),
                    "within_r2": round(result["within_r2"], 4),
                    "month_min": result["first"],
                    "month_max": result["last"],
                    "countries": "; ".join(result["countries"]),
                }
            )

    fields = [
        "aspect",
        "aspect_label",
        "term",
        "term_label",
        "coef",
        "se",
        "p",
        "stars",
        "n_obs",
        "n_country",
        "r2",
        "within_r2",
        "month_min",
        "month_max",
        "countries",
    ]
    with open(RESULTS, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    key: (
                        f"{value:.8f}"
                        if key in ("coef", "se", "p") and isinstance(value, float)
                        else value
                    )
                    for key, value in record.items()
                }
            )

    print(f"Wrote {RESULTS}")
    write_html(records, results)
    print(f"Wrote {REPORT}")
    for key, label in DIMENSIONS:
        result = results[key]
        print(
            f"  {label:24s} N={result['n']} G={result['g']} "
            f"GPR={result['inference']['gpr_z']['coef']:+.4f} "
            f"withinR2={result['within_r2']:.4f}"
        )


def write_html(records, results):
    """Readable report: coefficients, p-values, and a significance summary."""
    from html import escape

    dims = [(key.replace("wgi_", ""), label) for key, label in DIMENSIONS]

    def lookup(aspect, term):
        for record in records:
            if record["aspect"] == aspect and record["term"] == term:
                return record
        return None

    def wgi_key(aspect):
        return f"wgi_{aspect}"

    def pclass(p):
        if p < 0.01:
            return "p01"
        if p < 0.05:
            return "p05"
        if p < 0.10:
            return "p10"
        return "pns"

    rows = [
        ("WGI, lagged", wgi_key),
        ("GPR, standardized", lambda a: "gpr_z"),
        ("WGI x GPR", lambda a: "wgi_x_gpr"),
    ] + [
        (TERM_LABELS[name], lambda a, n=name: n) for name in CONTROLS
    ]

    body = []
    for label, keyfn in rows:
        cells = []
        for aspect, _ in dims:
            record = lookup(aspect, keyfn(aspect))
            if record is None:
                cells.append('<td class="na">&mdash;</td>')
                continue
            cells.append(
                '<td class="{}"><span class="coef">{:.4f}{}</span>'
                '<span class="se">({:.4f})</span>'
                '<span class="pv">p = {:.3f}</span></td>'.format(
                    pclass(record["p"]),
                    record["coef"],
                    record["stars"],
                    record["se"],
                    record["p"],
                )
            )
        body.append(f"<tr><th>{escape(label)}</th>{''.join(cells)}</tr>")

    first = records[0]
    fit_rows = [
        ("Observations", "{:,}".format(first["n_obs"])),
        ("Countries", str(first["n_country"])),
        ("Window", f"{escape(first['month_min'])} to {escape(first['month_max'])}"),
    ]
    footer = "".join(
        f"<tr><th>{name}</th>" + "".join(
            f'<td class="fit">{escape(value)}</td>' for _ in dims
        ) + "</tr>"
        for name, value in fit_rows
    ) + "".join(
        "<tr><th>{} </th>{}</tr>".format(
            escape(name),
            "".join(
                f'<td class="fit">{results[key][field]:.4f}</td>' for key, _ in DIMENSIONS
            ),
        )
        for name, field in [("Within R&sup2;", "within_r2"), ("R&sup2;", "r2")]
    )

    # Significance summary: the point of the report.
    summary = []
    for label, keyfn in [
        ("GPR, standardized", lambda a: "gpr_z"),
        ("WGI x GPR", lambda a: "wgi_x_gpr"),
        ("WGI, lagged", wgi_key),
    ]:
        ps = [lookup(a, keyfn(a))["p"] for a, _ in dims]
        sig = [d for (d, _), p in zip(dims, ps) if p < 0.10]
        summary.append(
            "<tr><th>{}</th><td>{}</td><td>{:.3f}&ndash;{:.3f}</td></tr>".format(
                escape(label),
                ", ".join(escape(results[f"wgi_{d}"]["label"]) for d in sig) or "none",
                min(ps),
                max(ps),
            )
        )

    countries = first["countries"].replace("; ", ", ")

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Model 2: capital-flow volatility and institutional quality</title>
<style>
:root {{ --ink:#1c2530; --muted:#5b6b7b; --line:#d3dde5; --pale:#f6f9fb; --orange:#c2571f; }}
body {{ font: 16px/1.55 Georgia, "Times New Roman", serif; color: var(--ink);
  max-width: 1180px; margin: 2.5em auto; padding: 0 1.2em; }}
h1 {{ font-size: 1.65em; margin: 0 0 .2em; line-height: 1.2; }}
h2 {{ font-size: 1.15em; margin: 2em 0 .5em; padding-bottom: .3em;
  border-bottom: 2px solid var(--line); }}
.sub {{ color: var(--muted); margin: 0 0 1.6em; }}
.note {{ background: var(--pale); border-left: 4px solid var(--orange);
  padding: .9em 1.1em; margin: 1.2em 0; font-size: .93em; }}
.note p {{ margin: .35em 0; }}
table {{ border-collapse: collapse; width: 100%; margin: 1em 0 1.6em; font-size: .82em; }}
th, td {{ border-bottom: 1px solid var(--line); padding: .45em .5em; text-align: right;
  vertical-align: top; }}
thead th {{ background: var(--pale); font-size: .95em; text-align: center; line-height: 1.25; }}
tbody th {{ text-align: left; font-weight: normal; width: 15em; }}
td .coef {{ display: block; font-weight: 700; font-variant-numeric: tabular-nums; }}
td .se {{ display: block; color: var(--muted); font-size: .95em;
  font-variant-numeric: tabular-nums; }}
td .pv {{ display: block; font-size: .88em; font-variant-numeric: tabular-nums; }}
td.p01 {{ background: #d9f0dc; }}
td.p05 {{ background: #e6f5e8; }}
td.p10 {{ background: #f2f8e8; }}
td.pns {{ color: #53616e; }}
td.p01 .pv, td.p05 .pv, td.p10 .pv {{ font-weight: 700; }}
td.na, td.fit {{ color: var(--muted); }}
caption {{ caption-side: bottom; text-align: left; color: var(--muted);
  font-size: .88em; padding-top: .6em; }}
.legend {{ font-size: .88em; color: var(--muted); }}
.legend span {{ display: inline-block; padding: .12em .55em; margin-right: .4em;
  border: 1px solid var(--line); }}
.legend .p01 {{ background: #d9f0dc; }} .legend .p05 {{ background: #e6f5e8; }}
.legend .p10 {{ background: #f2f8e8; }}
code {{ font-size: .92em; background: var(--pale); padding: .05em .3em; }}
ul {{ margin: .5em 0; }} li {{ margin: .35em 0; }}
</style>
</head>
<body>
<h1>Model 2: capital-flow volatility and institutional quality</h1>
<p class="sub">Emerging economies, {first['n_country']} countries,
{first['month_min']} to {first['month_max']}, {first['n_obs']:,} country-months</p>

<div class="note">
<p>Outcome: <code>capital_flow_volatility</code> from
<code>cleaned/replication_cleaned/country_month.csv</code> &mdash; the three-month
rolling standard deviation of monthly portfolio inflows, in billions of US dollars,
entering in levels.</p>
<p>Sample: rows where <code>group</code> is <code>Emerging</code>. One regression per
WGI dimension. Country fixed effects. Standard errors clustered by country.</p>
<p>Cells show the coefficient and stars, the clustered standard error in parentheses,
and the exact p-value. Shaded cells are significant at the level shown in the legend
below. Six WGI dimensions give six independent regressions, so a coefficient can be
positive in one column and negative in another without contradiction.</p>
</div>

<h2>Where the effects are significant</h2>
<table>
<thead><tr><th>Term</th><th>Columns with p &lt; 0.10</th><th>p-value range</th></tr></thead>
<tbody>{''.join(summary)}</tbody>
</table>
<p class="legend">
<span class="p01">p &lt; 0.01</span><span class="p05">p &lt; 0.05</span>
<span class="p10">p &lt; 0.10</span><span>not significant</span>
</p>

<h2>Full estimates</h2>
<table>
<thead><tr><th></th>{''.join(f'<th>{escape(label)}</th>' for _, label in dims)}</tr></thead>
<tbody>{''.join(body)}{footer}</tbody>
</table>
<p class="legend">*** p &lt; 0.01, ** p &lt; 0.05, * p &lt; 0.10. Country-clustered
standard errors in parentheses. p-values use a two-sided t distribution with
{first['n_country'] - 1} degrees of freedom.</p>

<h2>Reading the table</h2>
<ul>
<li>The outcome is in billions of dollars, so a coefficient is a change in that unit.</li>
<li>GPR is standardized within country, so its coefficient is the effect of a
one-standard-deviation rise in geopolitical risk.</li>
<li>The interaction is the change in that GPR slope per one point of the lagged WGI
score. Its coefficient is small relative to the spread of the WGI scores in most
columns.</li>
<li>Only the lagged log oil-price change is significant at 10 percent in all six
columns. GPR and the interaction are significant in none, and the lagged WGI score
in one (government effectiveness, p = 0.057).</li>
</ul>

<h2>Countries in this regression</h2>
<p>{escape(countries)}</p>
<p class="legend">Ukraine carries the <code>Emerging</code> label in the panel but
contributes no observations: it has no policy rate, so the lagged policy-rate change
is always blank.</p>
</body>
</html>
"""
    with open(REPORT, "w", encoding="utf-8") as handle:
        handle.write(html)


if __name__ == "__main__":
    main()
