"""Model 2 on quarterly data: capital-flow volatility as the outcome.

Same specification and estimator as output/run_model2.py, but the panel is the
quarterly file cleaned/data_for_quarter_model.csv instead of the monthly
country_month.csv. The outcome is capital_flow_volatility, which in this file is
the mean of the three monthly three-month rolling standard deviations inside the
quarter, in billions of US dollars.

The quarterly file already stores the lagged regressors and the interaction, so
this script reads them rather than rebuilding lags:

    wgi_{d}_lag1q                  lagged WGI score, original units
    wgi_{d}_lag1q_x_gpr_z          lagged WGI times gpr_z
    d_policy_rate_lag1q            lagged quarterly change in the policy rate
    d_inflation_lag1q              lagged change in inflation
    d_log_oil_lag1q                lagged change in log WTI
    d_log_gepu_lag1q               lagged change in log global EPU
    d_financial_development_lag1q  lagged change in financial development
    d_public_debt_gdp_lag1q        lagged change in debt/GDP
    ln_vix_lag1q                   lagged log VIX

One regression per WGI dimension. Country fixed effects. Standard errors
clustered by country. Emerging economies only.

Writes output/model2_quarterly_results.csv and .html.
"""

import csv
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_export_reer_2sls as est

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PANEL = os.path.join(ROOT, "cleaned", "data_for_quarter_model.csv")
RESULTS = os.path.join(ROOT, "output", "model2_quarterly_results.csv")
REPORT = os.path.join(ROOT, "output", "model2_quarterly_results.html")

OUTCOME = "capital_flow_volatility"

DIMENSIONS = [
    ("va", "Voice and accountability"),
    ("pv", "Political stability"),
    ("ge", "Government effectiveness"),
    ("rq", "Regulatory quality"),
    ("rl", "Rule of law"),
    ("cc", "Control of corruption"),
]

CONTROLS = [
    "d_policy_rate_lag1q",
    "d_inflation_lag1q",
    "d_log_oil_lag1q",
    "d_log_gepu_lag1q",
    "d_financial_development_lag1q",
    "d_public_debt_gdp_lag1q",
    "ln_vix_lag1q",
]

# Whole quarterly file. Unlike the monthly model, this window runs to the end of
# the stored quarters rather than stopping at January 2022.
WINDOW = ("2000-Q1", "2023-Q4")

GROUP = "Emerging"


def num(text):
    text = (text or "").strip()
    return None if not text else float(text)


def stars(p):
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""


def wgi_col(aspect):
    return f"wgi_{aspect}_lag1q"


def interaction_col(aspect):
    return f"wgi_{aspect}_lag1q_x_gpr_z"


def load_rows():
    rows = []
    with open(PANEL, encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            rows.append(
                {
                    "country": (row.get("country") or "").strip(),
                    "group": (row.get("group") or "").strip(),
                    "quarter": (row.get("year_quarter") or "").strip(),
                    "raw": row,
                }
            )
    return rows


def select(rows, aspect):
    """Rows in the window, in the emerging group, complete on every regressor."""
    wgi = wgi_col(aspect)
    interaction = interaction_col(aspect)
    needed = [OUTCOME, "gpr_z", wgi, interaction, *CONTROLS]
    use = []
    for row in rows:
        if row["group"] != GROUP:
            continue
        if not (WINDOW[0] <= row["quarter"] <= WINDOW[1]):
            continue
        values = {name: num(row["raw"].get(name)) for name in needed}
        if any(value is None for value in values.values()):
            continue
        use.append({"country": row["country"], "quarter": row["quarter"], **values})
    return use


def fit(rows, aspect):
    wgi = wgi_col(aspect)
    interaction = interaction_col(aspect)
    countries = sorted({row["country"] for row in rows})

    y = np.array([row[OUTCOME] for row in rows], dtype=float)
    columns = [wgi, "gpr_z", interaction, *CONTROLS]
    matrix, names, _ = est.design_matrix(rows, columns, countries)

    beta = np.linalg.lstsq(matrix, y, rcond=None)[0]
    residual = y - matrix @ beta

    grouped = est.cluster_indices(rows)
    variance, _ = est.cluster_variance(
        matrix, residual, grouped, len(rows), matrix.shape[1]
    )
    inference = est.inference(names, beta, variance, len(grouped))

    fitted = matrix @ beta
    country_of = [row["country"] for row in rows]
    y_mean = np.array(
        [np.mean([row[OUTCOME] for row in rows if row["country"] == c]) for c in country_of]
    )
    fitted_mean = np.array(
        [
            np.mean([fitted[i] for i, c in enumerate(country_of) if c == country])
            for country in country_of
        ]
    )
    within_r2 = 1.0 - np.sum(((y - y_mean) - (fitted - fitted_mean)) ** 2) / np.sum(
        (y - y_mean) ** 2
    )
    r2 = 1.0 - np.sum((y - fitted) ** 2) / np.sum((y - y.mean()) ** 2)

    quarters = sorted(row["quarter"] for row in rows)
    return {
        "n": len(rows),
        "g": len(countries),
        "inference": inference,
        "within_r2": float(within_r2),
        "r2": float(r2),
        "first": quarters[0],
        "last": quarters[-1],
        "countries": countries,
    }


TERM_LABELS = {
    "gpr_z": "GPR, standardized",
    "d_policy_rate_lag1q": "Policy rate, lagged change",
    "d_inflation_lag1q": "Inflation, lagged change",
    "d_log_oil_lag1q": "Log oil price, lagged change",
    "ln_vix_lag1q": "Log VIX, lagged",
    "d_log_gepu_lag1q": "Log global EPU, lagged change",
    "d_financial_development_lag1q": "Financial development, lagged change",
    "d_public_debt_gdp_lag1q": "Debt/GDP, lagged change",
}

INTEREST_LABELS = {
    "gpr_z": "GPR, standardized",
    "interaction": "WGI x GPR",
    "wgi": "WGI, lagged",
}


def main():
    raw = load_rows()

    results = {}
    for aspect, label in DIMENSIONS:
        rows = select(raw, aspect)
        fitted = fit(rows, aspect)
        fitted["label"] = label
        results[aspect] = fitted

    records = []
    for aspect, label in DIMENSIONS:
        result = results[aspect]
        ordered = [(wgi_col(aspect), "WGI, lagged"), ("gpr_z", "GPR, standardized")]
        ordered.append((interaction_col(aspect), "WGI x GPR"))
        ordered += [(name, TERM_LABELS[name]) for name in CONTROLS]
        for term, term_label in ordered:
            stat = result["inference"][term]
            records.append(
                {
                    "aspect": aspect,
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
                    "quarter_min": result["first"],
                    "quarter_max": result["last"],
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
        "quarter_min",
        "quarter_max",
        "countries",
    ]
    with open(RESULTS, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
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
    for aspect, label in DIMENSIONS:
        result = results[aspect]
        print(
            f"  {label:24s} N={result['n']} G={result['g']} "
            f"GPR={result['inference']['gpr_z']['coef']:+.4f} "
            f"withinR2={result['within_r2']:.4f}"
        )


def write_html(records, results):
    """Readable report: coefficients, exact p-values, significance shading."""
    from html import escape

    def lookup(aspect, term):
        for record in records:
            if record["aspect"] == aspect and record["term"] == term:
                return record
        return None

    def pclass(p):
        if p < 0.01:
            return "p01"
        if p < 0.05:
            return "p05"
        if p < 0.10:
            return "p10"
        return "pns"

    table_rows = [
        ("WGI, lagged", lambda a: wgi_col(a)),
        ("GPR, standardized", lambda a: "gpr_z"),
        ("WGI x GPR", lambda a: interaction_col(a)),
    ] + [(TERM_LABELS[name], lambda a, n=name: n) for name in CONTROLS]

    body = []
    for label, keyfn in table_rows:
        cells = []
        for aspect, _ in DIMENSIONS:
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
        ("Quarters", "{:,}".format(first["n_obs"])),
        ("Countries", str(first["n_country"])),
        ("Window", f"{escape(first['quarter_min'])} to {escape(first['quarter_max'])}"),
    ]
    footer = "".join(
        f"<tr><th>{name}</th>"
        + "".join(f'<td class="fit">{escape(value)}</td>' for _ in DIMENSIONS)
        + "</tr>"
        for name, value in fit_rows
    ) + "".join(
        "<tr><th>{}</th>{}</tr>".format(
            escape(name),
            "".join(
                f'<td class="fit">{results[aspect][field]:.4f}</td>'
                for aspect, _ in DIMENSIONS
            ),
        )
        for name, field in [("Within R&sup2;", "within_r2"), ("R&sup2;", "r2")]
    )

    summary = []
    for label, keyfn in [
        ("GPR, standardized", lambda a: "gpr_z"),
        ("WGI x GPR", lambda a: interaction_col(a)),
        ("WGI, lagged", lambda a: wgi_col(a)),
    ]:
        stats = [lookup(a, keyfn(a)) for a, _ in DIMENSIONS]
        ps = [stat["p"] for stat in stats]
        sig = [
            label_
            for (aspect, label_), stat in zip(DIMENSIONS, stats)
            if stat["p"] < 0.10
        ]
        summary.append(
            "<tr><th>{}</th><td>{}</td><td>{:.3f}&ndash;{:.3f}</td></tr>".format(
                escape(label),
                ", ".join(escape(name) for name in sig) or "none",
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
<title>Model 2 on quarterly data: capital-flow volatility and institutional quality</title>
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
<h1>Model 2 on quarterly data: capital-flow volatility and institutional quality</h1>
<p class="sub">Emerging economies, {first['n_country']} countries,
{first['quarter_min']} to {first['quarter_max']}, {first['n_obs']:,} country-quarters</p>

<div class="note">
<p>Outcome: <code>capital_flow_volatility</code> from
<code>cleaned/data_for_quarter_model.csv</code> &mdash; the mean of the three
monthly three-month rolling standard deviations inside the quarter, in billions of
US dollars, entering in levels.</p>
<p>Sample: rows where <code>group</code> is <code>Emerging</code>. One regression per
WGI dimension. Country fixed effects. Standard errors clustered by country.</p>
<p>Cells show the coefficient and stars, the clustered standard error in parentheses,
and the exact p-value, shaded by significance level. Six WGI dimensions are six
independent regressions.</p>
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
<thead><tr><th></th>{''.join(f'<th>{escape(label)}</th>' for _, label in DIMENSIONS)}</tr></thead>
<tbody>{''.join(body)}{footer}</tbody>
</table>
<p class="legend">*** p &lt; 0.01, ** p &lt; 0.05, * p &lt; 0.10. Country-clustered
standard errors in parentheses. p-values use a two-sided t distribution with
{first['n_country'] - 1} degrees of freedom.</p>

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
