"""Correlation table for the monthly Model 2 estimation sample.

Loads the monthly panel, keeps the emerging-market rows with a complete set of
regressors, and computes the Pearson correlation matrix over the variables that
enter the regression: the outcome, standardized GPR, the six lagged WGI scores,
and the seven lagged controls.

Uses the same loaders and sample rule as output/run_model2.py, so the matrix is
computed on exactly the 2,567 country-months the regression uses.

Writes output/model2_correlations.csv and output/model2_correlation.html.
"""

import csv
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_model2 as m2

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MATRIX = os.path.join(ROOT, "output", "model2_correlations.csv")
REPORT = os.path.join(ROOT, "output", "model2_correlation.html")

# (key in the loaded row dict, short label, longer label for the table)
VARIABLES = [
    ("y", "CFV", "Capital-flow volatility", "Outcome, billions of USD"),
    ("gpr_z", "GPR-z", "GPR, standardized", "Country GPR, current month"),
    ("wgi_va", "VA", "Voice and accountability", "Lagged one month"),
    ("wgi_pv", "PV", "Political stability", "Lagged one month"),
    ("wgi_ge", "GE", "Government effectiveness", "Lagged one month"),
    ("wgi_rq", "RQ", "Regulatory quality", "Lagged one month"),
    ("wgi_rl", "RL", "Rule of law", "Lagged one month"),
    ("wgi_cc", "CC", "Control of corruption", "Lagged one month"),
    ("d_policy_rate", "dPR", "Policy rate, change", "Lagged one month"),
    ("d_inflation", "dINF", "Inflation, change", "Lagged one month"),
    ("d_log_oil", "dOIL", "Log oil price, change", "Lagged one month"),
    ("ln_vix", "VIX", "Log VIX", "Lagged one month"),
    ("d_log_gepu", "dEPU", "Log global EPU, change", "Lagged one month"),
    ("d_financial_development", "dFD", "Financial development, change", "Lagged one month"),
    ("d_public_debt_gdp", "dDEBT", "Debt/GDP, change", "Lagged one month"),
]


def build_sample():
    rows = m2.load_rows()
    needed = [key for key, _, _, _ in VARIABLES]
    use = [
        row
        for row in rows
        if row["group"] == m2.GROUP
        and m2.WINDOW[0] <= row["year_month"] <= m2.WINDOW[1]
        and all(row[name] is not None for name in needed)
    ]
    return use


def correlation(use):
    keys = [key for key, _, _, _ in VARIABLES]
    data = np.array([[row[key] for key in keys] for row in use], dtype=float)
    return np.corrcoef(data, rowvar=False)


def write_csv(matrix):
    keys = [key for key, _, _, _ in VARIABLES]
    with open(MATRIX, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["variable"] + keys)
        for key, row in zip(keys, matrix):
            writer.writerow([key] + [f"{value:.6f}" for value in row])


def colour(value):
    """Diverging blue-positive / orange-negative fill on a 0 to 0.6 scale."""
    if not np.isfinite(value):
        return "#ffffff", "#53616e"
    strength = min(abs(value) / 0.6, 1.0)
    if value >= 0:
        base = (31, 82, 138)
    else:
        base = (176, 74, 28)
    alpha = strength * 0.62
    red = round(255 + (base[0] - 255) * alpha)
    green = round(255 + (base[1] - 255) * alpha)
    blue = round(255 + (base[2] - 255) * alpha)
    text = "#ffffff" if strength > 0.72 else "#1c2530"
    return f"rgb({red},{green},{blue})", text


def write_html(matrix, use):
    from html import escape

    labels = [label for _, label, _, _ in VARIABLES]
    header = "".join(
        f'<th title="{escape(long)}">{escape(short)}</th>'
        for _, short, long, _ in VARIABLES
    )

    body = []
    for i, (_, short, long, note) in enumerate(VARIABLES):
        cells = []
        for j in range(len(VARIABLES)):
            if i == j:
                cells.append('<td class="diag">&mdash;</td>')
                continue
            value = float(matrix[i, j])
            background, text = colour(value)
            cells.append(
                f'<td style="background:{background};color:{text}">{value:+.2f}</td>'
            )
        body.append(
            f"<tr><th><span class=\"short\">{escape(short)}</span>"
            f"<span class=\"long\">{escape(long)}</span>"
            f"<span class=\"note\">{escape(note)}</span></th>{''.join(cells)}</tr>"
        )

    # Strongest associations with the outcome, and the strongest pairs overall.
    outcome_rank = sorted(
        (
            (float(matrix[0, j]), labels[j])
            for j in range(1, len(VARIABLES))
        ),
        key=lambda item: -abs(item[0]),
    )
    outcome_rows = "".join(
        f"<tr><th>{escape(name)}</th><td>{value:+.3f}</td></tr>"
        for value, name in outcome_rank
    )

    pairs = []
    for i in range(len(VARIABLES)):
        for j in range(i + 1, len(VARIABLES)):
            pairs.append((float(matrix[i, j]), labels[i], labels[j]))
    pairs.sort(key=lambda item: -abs(item[0]))
    pair_rows = "".join(
        f"<tr><th>{escape(a)} &times; {escape(b)}</th><td>{value:+.3f}</td></tr>"
        for value, a, b in pairs[:10]
    )

    months = sorted(row["year_month"] for row in use)
    countries = sorted({row["country"] for row in use})

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Model 2 monthly correlations</title>
<style>
:root {{ --ink:#1c2530; --muted:#5b6b7b; --line:#d3dde5; --pale:#f6f9fb; --orange:#c2571f; }}
body {{ font: 16px/1.55 Georgia, "Times New Roman", serif; color: var(--ink);
  max-width: 1180px; margin: 2.5em auto; padding: 0 1.2em; }}
h1 {{ font-size: 1.6em; margin: 0 0 .2em; line-height: 1.2; }}
h2 {{ font-size: 1.12em; margin: 2em 0 .5em; padding-bottom: .3em;
  border-bottom: 2px solid var(--line); }}
.sub {{ color: var(--muted); margin: 0 0 1.5em; }}
.note {{ background: var(--pale); border-left: 4px solid var(--orange);
  padding: .9em 1.1em; margin: 1.2em 0; font-size: .93em; }}
.note p {{ margin: .35em 0; }}
.wrap {{ overflow-x: auto; }}
table.matrix {{ border-collapse: collapse; font-size: .76em; margin: 1em 0; }}
table.matrix th, table.matrix td {{ border: 1px solid #e4eaf0; padding: .4em .35em;
  text-align: center; font-variant-numeric: tabular-nums; min-width: 3.1em; }}
table.matrix thead th {{ background: var(--pale); font-weight: 700; font-size: .95em;
  position: sticky; top: 0; }}
table.matrix tbody th {{ text-align: left; font-weight: normal; background: #fff;
  min-width: 15em; padding-right: .6em; }}
table.matrix tbody th .short {{ display: block; font-weight: 700; font-size: 1.05em; }}
table.matrix tbody th .long {{ display: block; font-size: .95em; }}
table.matrix tbody th .note {{ display: block; color: var(--muted); font-size: .82em;
  padding: 0; margin: 0; border: 0; background: none; }}
td.diag {{ background: #f2f5f8; color: #a9b6c2; }}
table.rank {{ border-collapse: collapse; width: 100%; margin: .6em 0 1.2em;
  font-size: .87em; max-width: 34em; }}
table.rank th, table.rank td {{ border-bottom: 1px solid var(--line); padding: .38em .5em; }}
table.rank th {{ text-align: left; font-weight: normal; }}
table.rank td {{ text-align: right; font-variant-numeric: tabular-nums; }}
.legend {{ font-size: .87em; color: var(--muted); margin: .4em 0 1em; }}
.legend .bar {{ display: block; height: 10px; width: 340px; border-radius: 2px;
  margin: .35em 0; background: linear-gradient(to right,
  rgb(176,74,28) 0%, #ffffff 50%, rgb(31,82,138) 100%); border: 1px solid var(--line); }}
.legend .ends {{ display: flex; width: 340px; justify-content: space-between; }}
code {{ font-size: .92em; background: var(--pale); padding: .05em .3em; }}
</style>
</head>
<body>
<h1>Model 2 monthly correlations</h1>
<p class="sub">Emerging economies, {len(countries)} countries, {months[0]} to {months[-1]},
{len(use):,} country-months &mdash; the exact estimation sample</p>

<div class="note">
<p>Pearson correlations among the variables that enter the monthly Model 2
regression. Computed on the {len(use):,} country-months that survive the complete-case
rule, so no cell is a different sample from another.</p>
<p>Cells are shaded by sign and magnitude: blue for positive, orange for negative,
deeper as the absolute value grows. The diagonal is suppressed.</p>
<p>Lag means the previous calendar month for the same country. GPR is standardized
within country; the WGI scores are in their original units, uncentered. These are
raw correlations, not partial effects, so a pair can be correlated here while its
coefficient in the regression is insignificant.</p>
</div>

<h2>Correlation matrix</h2>
<div class="wrap">
<table class="matrix">
<thead><tr><th></th>{header}</tr></thead>
<tbody>{''.join(body)}</tbody>
</table>
</div>
<p class="legend">Scale
  <span class="bar"></span>
  <span class="ends"><span>&minus;1.0</span><span>0</span><span>+1.0</span></span>
  Shading saturates at |r| = 0.6.
</p>

<h2>Strongest with the outcome</h2>
<table class="rank"><tbody>{outcome_rows}</tbody></table>

<h2>Strongest pairs overall</h2>
<table class="rank"><tbody>{pair_rows}</tbody></table>
</body>
</html>
"""
    with open(REPORT, "w", encoding="utf-8") as handle:
        handle.write(html)


def main():
    use = build_sample()
    matrix = correlation(use)
    write_csv(matrix)
    write_html(matrix, use)
    print(f"Wrote {MATRIX}")
    print(f"Wrote {REPORT}")
    labels = [short for _, short, _, _ in VARIABLES]
    print(f"  n = {len(use)} country-months, {len({row['country'] for row in use})} countries")
    print("  outcome correlations:")
    for j in range(1, len(VARIABLES)):
        print(f"    {labels[j]:8s} {matrix[0, j]:+.3f}")


if __name__ == "__main__":
    main()
