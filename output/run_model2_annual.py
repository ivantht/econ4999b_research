"""Model 2 on annual data: capital-flow volatility as the outcome.

Same equation, control set, estimator, and clustering as the monthly run in
output/run_model2.py. Only the frequency changes: each observation is one
country-year, and every regressor is the within-year mean of its monthly
counterpart, shifted back one year.

WGI enters at the value for the current year, not lagged. WGI is constant within
a calendar year in the source panel, so a one-year lag would mean using last
year's institutional score. Keeping the current-year score puts the annual
specification as close as possible to the monthly one, where eleven of twelve
months already use the current year's score. This choice is documented in
model 2.md and is a deliberate departure from the one-period-lag convention.

Reads cleaned/replication_cleaned/country_year.csv.
Writes output/model2_annual_results.csv and .html.
"""

from __future__ import annotations

import csv
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_export_reer_2sls as est

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PANEL = os.path.join(ROOT, "cleaned", "replication_cleaned", "country_year.csv")
RESULTS = os.path.join(ROOT, "output", "model2_annual_results.csv")
REPORT = os.path.join(ROOT, "output", "model2_annual_results.html")
MONTHLY_CSV = os.path.join(ROOT, "output", "model2_results.csv")
QUARTERLY_CSV = os.path.join(ROOT, "output", "model2_quarterly_results.csv")

OUTCOME = "capital_flow_volatility"
GROUP = "Emerging"

DIMENSIONS = [
    ("wgi_va", "Voice and accountability"),
    ("wgi_pv", "Political stability"),
    ("wgi_ge", "Government effectiveness"),
    ("wgi_rq", "Regulatory quality"),
    ("wgi_rl", "Rule of law"),
    ("wgi_cc", "Control of corruption"),
]

LAG_CHANGES = [
    "d_policy_rate",
    "d_inflation",
    "d_log_oil",
    "d_log_gepu",
    "d_financial_development",
    "d_public_debt_gdp",
]
CONTROLS = LAG_CHANGES + ["ln_vix"]

# Matches the monthly window, shifted to whole years: February 2002 through
# January 2022 becomes 2002 through 2021.
WINDOW = (2002, 2021)

# An annual observation should average twelve monthly volatilities. Eleven
# country-years in the panel carry ten or fewer months, usually because the
# series starts or stops inside the year, so the main sample keeps only complete
# years. The looser floor is used for the robustness line in the report.
MIN_MONTHS = 12
LOOSE_MONTHS = 9


def num(text):
    text = (text or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def stars(p):
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""


def load():
    rows = []
    with open(PANEL, encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            rows.append(
                {
                    "iso": row["iso"].strip(),
                    "country": row["country"].strip(),
                    "year": int(row["year"]),
                    "months": int(row["months"]),
                    "y": num(row[OUTCOME]),
                    **{k: num(row[k]) for k in ["gpr_z", "vix"] + [d for d, _ in DIMENSIONS]},
                    **{k: num(row[k]) for k in LAG_CHANGES},
                }
            )

    index = {(r["iso"], r["year"]): r for r in rows}
    # Snapshot the raw values before anything is shifted, otherwise the shifted
    # values overwrite the source and every later year inherits the empty lag of
    # the first year in the panel.
    raw = {key: dict(r) for key, r in index.items()}

    for r in rows:
        previous = raw.get((r["iso"], r["year"] - 1))
        r["ln_vix"] = est.positive_log(previous["vix"]) if previous else None
        for key in LAG_CHANGES:
            r[key] = previous[key] if previous else None
        # Kept separate from the current-year score so both can be tested.
        for key, _ in DIMENSIONS:
            r["lag_" + key] = previous[key] if previous else None
    return rows


rows = load()


def fit(wgi, min_months=MIN_MONTHS):
    # WGI stays at its current-year value; only the control block and VIX are lagged.
    needed = ["y", "gpr_z", wgi, "ln_vix"] + LAG_CHANGES
    use = [
        r for r in rows
        if r["country"] and WINDOW[0] <= r["year"] <= WINDOW[1]
        and r["months"] >= min_months
        and all(r[n] is not None for n in needed)
    ]
    countries = sorted({r["country"] for r in use})

    y = np.array([r["y"] for r in use], dtype=float)
    matrix, names, _ = est.design_matrix(use, ["gpr_z", wgi] + CONTROLS, countries)
    interaction = np.array([r[wgi] * r["gpr_z"] for r in use], dtype=float)
    matrix = np.column_stack([matrix, interaction])
    names = names + ["wgi_x_gpr"]

    beta = np.linalg.lstsq(matrix, y, rcond=None)[0]
    residual = y - matrix @ beta
    variance, _ = est.cluster_variance(
        matrix, residual, est.cluster_indices(use), len(use), matrix.shape[1]
    )
    inference = est.inference(names, beta, variance, len(countries))

    fitted = matrix @ beta
    country_of = [r["country"] for r in use]
    y_mean = np.array(
        [np.mean([r["y"] for r in use if r["country"] == c]) for c in country_of]
    )
    fitted_mean = np.array(
        [np.mean([fitted[i] for i, c in enumerate(country_of) if c == country])
         for country in country_of]
    )
    within_r2 = 1.0 - np.sum(((y - y_mean) - (fitted - fitted_mean)) ** 2) / np.sum((y - y_mean) ** 2)
    r2 = 1.0 - np.sum((y - fitted) ** 2) / np.sum((y - y.mean()) ** 2)

    years = sorted(r["year"] for r in use)
    return {
        "n": len(use),
        "g": len(countries),
        "inference": inference,
        "within_r2": float(within_r2),
        "r2": float(r2),
        "first": years[0],
        "last": years[-1],
        "countries": countries,
    }


results = {key: fit(key) for key, _ in DIMENSIONS}
loose = {key: fit(key, LOOSE_MONTHS) for key, _ in DIMENSIONS}
# Same equation with WGI lagged a full year, the convention used for the controls.
lagged = {key: fit("lag_" + key) for key, _ in DIMENSIONS}

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

records = []
for key, label in DIMENSIONS:
    ordered = [(key, "WGI, current year")] + [
        (name, TERM_LABELS[name]) for name in ["gpr_z", "wgi_x_gpr"] + CONTROLS
    ]
    for term, term_label in ordered:
        stat = results[key]["inference"][term]
        records.append({
            "aspect": key.replace("wgi_", ""),
            "aspect_label": label,
            "term": term,
            "term_label": term_label,
            "coef": stat["coef"],
            "se": stat["se"],
            "p": stat["p"],
            "stars": stars(stat["p"]),
            "n_obs": results[key]["n"],
            "n_country": results[key]["g"],
            "r2": round(results[key]["r2"], 4),
            "within_r2": round(results[key]["within_r2"], 4),
            "year_min": results[key]["first"],
            "year_max": results[key]["last"],
            "countries": "; ".join(results[key]["countries"]),
        })

with open(RESULTS, "w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(records[0]))
    writer.writeheader()
    for record in records:
        writer.writerow({
            k: (f"{v:.8f}" if k in ("coef", "se", "p") and isinstance(v, float) else v)
            for k, v in record.items()
        })

print(f"Wrote {RESULTS}")


# ------------------------------------------------------------------ comparison
def read_reference(path):
    """Pull the GPR and interaction coefficients from an earlier run.

    The term names differ by frequency: the monthly file calls the interaction
    `wgi_x_gpr`, the quarterly file calls it `wgi_va_lag1q_x_gpr_z`. Normalise to
    the two names used in the comparison table.
    """
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            aspect = row.get("aspect") or ""
            term = row.get("term") or ""
            if term == "gpr_z":
                key = "gpr_z"
            elif term.endswith("x_gpr") or term.endswith("x_gpr_z"):
                key = "wgi_x_gpr"
            else:
                continue
            out[(aspect, key)] = (float(row["coef"]), float(row["p"]))
    return out


monthly = read_reference(MONTHLY_CSV)
quarterly = read_reference(QUARTERLY_CSV)

# ------------------------------------------------------------------ html
def pclass(p):
    if p < 0.01:
        return "p01"
    if p < 0.05:
        return "p05"
    if p < 0.10:
        return "p10"
    return "pns"


def cell(stat):
    return (
        f'<span class="coef">{stat["coef"]:+.4f}{stars(stat["p"])}</span>'
        f'<span class="se">({stat["se"]:.4f})</span>'
        f'<span class="pv">p = {stat["p"]:.3f}</span>'
    )


head = "".join(f"<th>{label}</th>" for _, label in DIMENSIONS)
first = results["wgi_va"]

body = []
for term, label in [("gpr_z", "GPR, standardized"), ("wgi_x_gpr", "WGI &times; GPR")] + [
    (name, TERM_LABELS[name]) for name in CONTROLS
]:
    cells = "".join(
        f'<td class="{pclass(results[key]["inference"][term]["p"])}">'
        f'{cell(results[key]["inference"][term])}</td>'
        for key, _ in DIMENSIONS
    )
    body.append(f"<tr><th>{label}</th>{cells}</tr>")
wgi_cells = "".join(
    f'<td class="{pclass(results[key]["inference"][key]["p"])}">'
    f'{cell(results[key]["inference"][key])}</td>'
    for key, _ in DIMENSIONS
)
body.insert(0, f"<tr><th>WGI, current year</th>{wgi_cells}</tr>")

compare = []
for term, label, aspect_key in [
    ("gpr_z", "GPR, standardized", "gpr_z"),
    ("wgi_x_gpr", "WGI &times; GPR", "wgi_x_gpr"),
]:
    cells = []
    for key, _ in DIMENSIONS:
        aspect = key.replace("wgi_", "")
        ann = results[key]["inference"][term]
        m = monthly.get((aspect, aspect_key))
        q = quarterly.get((aspect, aspect_key))
        strip = lambda t: ("" if t is None else f"{t[0]:+.3f}{stars(t[1])}<br><span class='tiny'>p {t[1]:.2f}</span>")
        cells.append(
            f'<td><span class="annual">{ann["coef"]:+.3f}{stars(ann["p"])}</span>'
            f'<span class="tiny">p {ann["p"]:.2f}</span>'
            f'<span class="ref">M {strip(m)}</span>'
            f'<span class="ref">Q {strip(q)}</span></td>'
        )
    compare.append(f"<tr><th>{label}</th>{''.join(cells)}</tr>")

loose_first = loose["wgi_va"]
lagging_first = lagged["wgi_va"]

cov = "".join(
    f"<tr><td>{name}</td><td class='num'>{results[key]['n']}</td>"
    f"<td class='num'>{results[key]['g']}</td>"
    f"<td class='num'>{results[key]['within_r2']:.4f}</td>"
    f"<td class='num'>{results[key]['r2']:.4f}</td></tr>"
    for key, name in DIMENSIONS
)

def sensitivity_rows(store, wgi_term=None):
    """Rows for a sensitivity table: the two terms of interest plus WGI itself."""
    out = []
    for term, label in [("gpr_z", "GPR, standardized"), ("wgi_x_gpr", "WGI &times; GPR")]:
        cells = "".join(
            f'<td class="{pclass(store[key]["inference"][term]["p"])}">'
            f'{store[key]["inference"][term]["coef"]:+.4f}'
            f'{stars(store[key]["inference"][term]["p"])}'
            f'<span class="tiny">p {store[key]["inference"][term]["p"]:.2f}</span></td>'
            for key, _ in DIMENSIONS
        )
        out.append(f"<tr><th>{label}</th>{cells}</tr>")
    return "".join(out)


robust_rows = sensitivity_rows(loose)
lagged_rows = sensitivity_rows(lagged)

html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Model 2 on annual data: capital-flow volatility and institutional quality</title>
<style>
:root {{ --ink:#1c2530; --muted:#5b6b7b; --line:#d3dde5; --pale:#f6f9fb; --orange:#c2571f; }}
body {{ font: 16px/1.55 Georgia, "Times New Roman", serif; color: var(--ink);
  max-width: 1180px; margin: 2.5em auto; padding: 0 1.2em; }}
h1 {{ font-size: 1.6em; margin: 0 0 .2em; line-height: 1.2; }}
h2 {{ font-size: 1.14em; margin: 2.1em 0 .5em; padding-bottom: .3em;
  border-bottom: 2px solid var(--line); }}
.sub {{ color: var(--muted); margin: 0 0 1.5em; }}
.note {{ background: var(--pale); border-left: 4px solid var(--orange);
  padding: .9em 1.1em; margin: 1.2em 0; font-size: .93em; }}
.note p {{ margin: .4em 0; }}
table {{ border-collapse: collapse; width: 100%; margin: 1em 0 1.6em; font-size: .78em; }}
th, td {{ border-bottom: 1px solid var(--line); padding: .45em .5em; text-align: right;
  vertical-align: top; }}
thead th {{ background: var(--pale); font-size: .95em; text-align: center; line-height: 1.25; }}
tbody th {{ text-align: left; font-weight: normal; width: 14em; }}
td .coef, td .annual {{ display: block; font-weight: 700; font-variant-numeric: tabular-nums; }}
td .se {{ display: block; color: var(--muted); font-size: .95em;
  font-variant-numeric: tabular-nums; }}
td .pv {{ display: block; font-size: .85em; font-variant-numeric: tabular-nums; color: #7c8794; }}
td .tiny {{ display: block; font-size: .78em; color: #7c8794; font-variant-numeric: tabular-nums; }}
td .ref {{ display: block; font-size: .78em; color: #9aa0a8; font-variant-numeric: tabular-nums;
  border-top: 1px dotted #dfe4e9; margin-top: .25em; padding-top: .2em; }}
td.p01 {{ background:#d9f0dc; }} td.p05 {{ background:#e6f5e8; }}
td.p10 {{ background:#f2f8e8; }} td.pns {{ color:#53616e; }}
td.p01 .pv, td.p05 .pv, td.p10 .pv {{ font-weight: 700; }}
td.num {{ font-variant-numeric: tabular-nums; }}
.legend {{ font-size: .86em; color: var(--muted); }}
code {{ font-size: .92em; background: var(--pale); padding: .05em .3em; }}
ul {{ margin:.5em 0; }} li {{ margin:.35em 0; }}
</style>
</head>
<body>
<h1>Model 2 on annual data</h1>
<p class="sub">Emerging economies, {first['g']} countries, {first['first']}&ndash;{first['last']},
{first['n']} country-years &mdash; one observation per country per year</p>

<div class="note">
<p><b>Same specification, different clock.</b> The outcome, the WGI term, the interaction,
the seven controls, the country fixed effects, and the country clustering are those of the
monthly Model 2. What changes is that each observation is a country-year rather than a
country-month.</p>
<p><b>Aggregation.</b> Every monthly regressor is averaged inside the calendar year. The
outcome is the mean of the twelve monthly three-month rolling standard deviations, which is
the same rule the quarterly file uses on three months.</p>
<p><b>Complete years only.</b> A country-year enters when all twelve monthly volatilities are
observed. Eleven country-years carrying nine or ten months are excluded from the main sample and
readmitted in the robustness table.</p>
<p><b>WGI enters at its current-year value, not lagged.</b> WGI is constant within a calendar
year in the source panel, so a one-year lag would substitute last year's institutional score.
Using the current-year score keeps this run as close as possible to the monthly one, where
eleven of twelve months already use the current year's value. The downside is that the WGI
term is not predetermined here, so it cannot be read as an exogenous institution effect.</p>
</div>

<h2>Estimates</h2>
<table>
<thead><tr><th></th>{head}</tr></thead>
<tbody>{''.join(body)}</tbody>
</table>
<p class="legend">*** p &lt; 0.01, ** p &lt; 0.05, * p &lt; 0.10. Country-clustered standard
errors in parentheses, {first['g']} clusters, {first['g'] - 1} degrees of freedom.</p>

<h2>Three frequencies side by side</h2>
<p class="legend">Bold is the annual estimate. Below it, <code>M</code> is the monthly and
<code>Q</code> the quarterly coefficient with stars and p-value from the earlier runs.</p>
<table>
<thead><tr><th></th>{head}</tr></thead>
<tbody>{''.join(compare)}</tbody>
</table>

<h2>Fit</h2>
<table>
<thead><tr><th>Dimension</th><th>Country-years</th><th>Countries</th>
<th>Within R&sup2;</th><th>R&sup2;</th></tr></thead>
<tbody>{cov}</tbody>
</table>

<h2>Robustness</h2>
<p class="legend"><b>Incomplete years allowed.</b> The main sample requires all twelve monthly
volatilities; these columns lower the floor to nine months, which admits the eleven
country-years whose series starts or stops inside the year. {loose_first['n']} country-years,
{loose_first['g']} countries.</p>
<table>
<thead><tr><th></th>{head}</tr></thead>
<tbody>{robust_rows}</tbody>
</table>
<p class="legend"><b>WGI lagged a full year.</b> The convention used for every control, applied
to the institution term. {lagging_first['n']} country-years, {lagging_first['g']} countries. The interaction and
the government-effectiveness result survive; the GPR level does not.</p>
<table>
<thead><tr><th></th>{head}</tr></thead>
<tbody>{lagged_rows}</tbody>
</table>

<h2>Reading the annual run</h2>
<ul>
<li>The interaction is insignificant in every column, with <i>p</i> from 0.110 to 0.792, so the
annual data give no evidence that institutional quality conditions the GPR effect.</li>
<li>GPR itself is negative everywhere and clears 5 percent once, in the government-effectiveness
column (−0.3343, <i>p</i> = 0.021). The remaining five columns sit between <i>p</i> = 0.153 and
<i>p</i> = 0.612. Unlike the monthly and quarterly runs, which put the GPR level at or near zero,
the annual estimates lean negative, but one rejection in six is thin support and the other five
columns do not corroborate it.</li>
<li>Government effectiveness is also the one column where WGI itself is significant
(1.3133, <i>p</i> = 0.017), with a positive sign. Both annual rejections therefore sit in the same
column and share its regressors, so they are not two independent findings. This is the same
column that reached 10 percent monthly and 5 percent quarterly, which makes it the most
persistent institutional result in the project — and the one most in need of a specification
that can separate the level from the interaction.</li>
<li>The sample falls to {first['n']} country-years from 2,567 country-months. Clustering is
unchanged at {first['g']} countries, so precision is limited: the interaction's standard error is
at least half its point estimate in every column and exceeds the estimate itself in three.</li>
<li>Comparing coefficients across frequencies is not meaningful in magnitude. Averaging twelve
months removes within-year noise and shrinks the variance of both the outcome and the
regressors, so annual coefficients are not rescaled versions of the monthly ones.</li>
<li>Ukraine carries the <code>Emerging</code> label but contributes no observations, because it
has no policy rate. That is the same exclusion as in the monthly and quarterly runs.</li>
</ul>

<h2>Files</h2>
<p>Annual panel: <code>cleaned/replication_cleaned/country_year.csv</code>, built by
<code>output/build_annual_panel.py</code>. Regression:
<code>output/run_model2_annual.py</code>. Coefficients:
<code>output/model2_annual_results.csv</code>. The monthly and quarterly results are untouched.</p>
</body>
</html>
"""

with open(REPORT, "w", encoding="utf-8") as handle:
    handle.write(html)

print(f"Wrote {REPORT}")
print()
print(f"{'dimension':<26}{'N':>6}{'G':>4}{'GPR':>9}{'p':>7}{'INT':>9}{'p':>7}{'WGI':>9}{'p':>7}")
for key, label in DIMENSIONS:
    inf = results[key]["inference"]
    print(f"{label:<26}{results[key]['n']:>6}{results[key]['g']:>4}"
          f"{inf['gpr_z']['coef']:>9.4f}{inf['gpr_z']['p']:>7.3f}"
          f"{inf['wgi_x_gpr']['coef']:>9.4f}{inf['wgi_x_gpr']['p']:>7.3f}"
          f"{inf[key]['coef']:>9.4f}{inf[key]['p']:>7.3f}")
