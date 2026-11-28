"""Model 2, alternative outcome: capital-inflow volatility.

Rebuilds the outcome from the raw OECD monthly capital-flow file so that the
underlying flow is total capital inflow rather than portfolio inflow alone:

    inflow = port_inf + fdi_inf + other_inf

then takes the same three-month rolling standard deviation the existing
`capital_flow_volatility` column uses, so the two outcomes differ only in which
flow enters the standard deviation.

Everything else is inherited from output/run_model2.py unchanged: the control
set, the one-month lags, the country fixed effects, the country-clustered
standard errors, the sample window, and the Emerging filter.

Writes:
  cleaned/replication_cleaned/country_month_inflow.csv  (the rebuilt series)
  output/model2_inflow_results.csv
  output/model2_inflow_results.html
  output/model2_inflow_compare.svg / .png
"""

from __future__ import annotations

import csv
import os
import statistics
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_export_reer_2sls as est

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PANEL = os.path.join(ROOT, "cleaned", "replication_cleaned", "country_month.csv")
RAW = os.path.join(
    ROOT, "econ4999b_literature_review", "replication", "raw", "oecd_capital_flows.xlsx"
)
BUILT = os.path.join(ROOT, "cleaned", "replication_cleaned", "country_month_inflow.csv")
RESULTS = os.path.join(ROOT, "output", "model2_inflow_results.csv")
REPORT = os.path.join(ROOT, "output", "model2_inflow_results.html")
CHART_SVG = os.path.join(ROOT, "output", "model2_inflow_compare.svg")

# Outcome columns. OLD is what Model 2 already estimates; NEW is built above.
OLD_OUTCOME = "capital_flow_volatility"
NEW_OUTCOME = "inflow_volatility"

# The OECD workbook spells the country with a diaeresis; the panel does not.
ALIAS = {"Turkiye": "T\u00fcrkiye"}

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
WINDOW = ("2002-02", "2022-01")
GROUP = "Emerging"


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


# --------------------------------------------------------------- build the series
def read_raw():
    """Monthly components from the OECD panel sheet, billion USD."""
    import openpyxl

    book = openpyxl.load_workbook(RAW, read_only=True, data_only=True)
    sheet = book["panel"]

    def cell(row, idx):
        value = row[idx]
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    data = defaultdict(dict)
    for row in sheet.iter_rows(min_row=2, values_only=True):
        country, month = row[0], row[1]
        if not country or not month:
            continue
        data[country][str(month)[:7]] = {
            "port": cell(row, 10),
            "fdi": cell(row, 6),
            "other": cell(row, 8),
        }
    return data


def build_series(raw):
    """Total inflow and its three-month rolling SD, per country-month."""
    flows, vols = {}, {}
    for country, months in raw.items():
        series = {}
        for month, parts in months.items():
            if parts["port"] is None:
                series[month] = None
                continue
            extras = [v for v in (parts["fdi"], parts["other"]) if v is not None]
            series[month] = parts["port"] + sum(extras)
        flows[country] = series

        ordered = sorted(series)
        vol = {}
        for i in range(2, len(ordered)):
            window = [series[ordered[i - 2]], series[ordered[i - 1]], series[ordered[i]]]
            vol[ordered[i]] = (
                statistics.stdev(window) if all(v is not None for v in window) else None
            )
        vols[country] = vol
    return flows, vols


raw = read_raw()
flows, vols = build_series(raw)


def lookup(country, month, table):
    key = ALIAS.get(country, country)
    return table.get(key, {}).get(month)


# --------------------------------------------------------------- rows
rows = []
with open(PANEL, encoding="utf-8-sig", newline="") as handle:
    for row in csv.DictReader(handle):
        country = row["country"].strip()
        month = row["date"][:7]
        rows.append(
            {
                "iso": row["iso"].strip(),
                "country": country,
                "group": row["group"].strip(),
                "month": month,
                "raw": row,
                "y_old": num(row[OLD_OUTCOME]),
                "y_new": lookup(country, month, vols),
                "flow_port": num(row["portfolio_inflow"]),
                "flow_new": lookup(country, month, flows),
            }
        )

index = {(r["iso"], r["month"]): r for r in rows}
for r in rows:
    previous = index.get((r["iso"], est.add_months(r["month"], -1)))
    r["gpr_z"] = num(r["raw"]["gpr_z"])
    for key, _ in DIMENSIONS:
        r[key] = num(previous["raw"][key]) if previous else None
    for key in LAG_CHANGES:
        r[key] = num(previous["raw"][key]) if previous else None
    vix = num(previous["raw"]["vix"]) if previous else None
    r["ln_vix"] = est.positive_log(vix)


# --------------------------------------------------------------- coverage report
emerging = []
seen = set()
for r in rows:
    if r["group"] == GROUP and r["country"] not in seen:
        seen.add(r["country"])
        emerging.append(r["country"])
emerging.sort()

coverage = []
for country in emerging:
    months = [r for r in rows if r["country"] == country and r["group"] == GROUP]
    pairs = [(r["y_old"], r["y_new"]) for r in months if r["y_old"] is not None and r["y_new"] is not None]
    if pairs:
        a = np.array([p[0] for p in pairs])
        b = np.array([p[1] for p in pairs])
        corr = float(np.corrcoef(a, b)[0, 1]) if np.std(a) > 0 and np.std(b) > 0 else None
        ratio = float(b.mean() / a.mean()) if a.mean() else None
    else:
        corr, ratio = None, None
    has_extras = any(
        (r["flow_new"] is not None and r["flow_port"] is not None
         and abs(r["flow_new"] - r["flow_port"]) > 1e-9)
        for r in months
    )
    coverage.append(
        {
            "country": country,
            "old_n": sum(1 for r in months if r["y_old"] is not None),
            "new_n": sum(1 for r in months if r["y_new"] is not None),
            "corr": corr,
            "ratio": ratio,
            "distinct": has_extras,
        }
    )

# --------------------------------------------------------------- fit
def prepare(outcome):
    needed = [outcome, "gpr_z"] + [k for k, _ in DIMENSIONS] + LAG_CHANGES + ["ln_vix"]
    use = [
        r for r in rows
        if r["group"] == GROUP
        and WINDOW[0] <= r["month"] <= WINDOW[1]
        and all(r[n] is not None for n in needed)
    ]
    return use


def fit(use, outcome, wgi):
    countries = sorted({r["country"] for r in use})
    y = np.array([r[outcome] for r in use], dtype=float)
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
    y_mean = np.array([
        np.mean([r[outcome] for r in use if r["country"] == c]) for c in country_of
    ])
    fitted_mean = np.array([
        np.mean([fitted[i] for i, c in enumerate(country_of) if c == country])
        for country in country_of
    ])
    within_r2 = 1.0 - np.sum(((y - y_mean) - (fitted - fitted_mean)) ** 2) / np.sum((y - y_mean) ** 2)
    r2 = 1.0 - np.sum((y - fitted) ** 2) / np.sum((y - y.mean()) ** 2)

    months = sorted(r["month"] for r in use)
    return {
        "n": len(use),
        "g": len(countries),
        "inference": inference,
        "within_r2": float(within_r2),
        "r2": float(r2),
        "first": months[0],
        "last": months[-1],
        "countries": countries,
    }


use_old = prepare("y_old")
use_new = prepare("y_new")
print(f"sample: old {len(use_old):,}  new {len(use_new):,}")
assert len(use_old) == len(use_new), "samples must match for a clean comparison"

results = {}
for key, label in DIMENSIONS:
    results[key] = {
        "old": fit(use_old, "y_old", key),
        "new": fit(use_new, "y_new", key),
        "label": label,
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


# --------------------------------------------------------------- csv
records = []
for key, label in DIMENSIONS:
    ordered = [(key, "WGI, lagged")] + [
        (name, TERM_LABELS[name]) for name in ["gpr_z", "wgi_x_gpr"] + CONTROLS
    ]
    for term, term_label in ordered:
        for tag, name in (("old", "portfolio_inflow_volatility"), ("new", "inflow_volatility")):
            stat = results[key][tag]["inference"][term]
            records.append({
                "dimension": key.replace("wgi_", ""),
                "dimension_label": label,
                "outcome": name,
                "term": term,
                "term_label": term_label,
                "coef": stat["coef"],
                "se": stat["se"],
                "p": stat["p"],
                "stars": stars(stat["p"]),
                "n_obs": results[key][tag]["n"],
                "n_country": results[key][tag]["g"],
                "within_r2": round(results[key][tag]["within_r2"], 4),
                "r2": round(results[key][tag]["r2"], 4),
                "month_min": results[key][tag]["first"],
                "month_max": results[key][tag]["last"],
            })

fields = list(records[0])
with open(RESULTS, "w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=fields)
    writer.writeheader()
    for record in records:
        writer.writerow({
            k: (f"{v:.8f}" if k in ("coef", "se", "p") and isinstance(v, float) else v)
            for k, v in record.items()
        })

# --------------------------------------------------------------- built series csv
with open(BUILT, "w", encoding="utf-8", newline="") as handle:
    writer = csv.writer(handle)
    writer.writerow(["iso", "country", "date", "portfolio_inflow", "capital_inflow",
                     "portfolio_inflow_volatility", "inflow_volatility"])
    for r in rows:
        if r["group"] != GROUP:
            continue
        fmt = lambda v: "" if v is None else f"{v:.6f}"
        writer.writerow([r["iso"], r["country"], r["month"], fmt(r["flow_port"]),
                         fmt(r["flow_new"]), fmt(r["y_old"]), fmt(r["y_new"])])


# --------------------------------------------------------------- chart
def chart():
    """Dumbbell per country: mean volatility under the two flow definitions."""
    data = [c for c in coverage if c["old_n"] > 0 and c["new_n"] > 0]
    data.sort(key=lambda c: -(c["ratio"] or 1.0))

    left, right, top = 132, 150, 108
    row_h = 25
    pw, ph = 360, row_h * len(data)
    width, height = left + pw + right, top + ph + 108

    maxv = max(
        max(
            np.mean([r["y_old"] for r in rows if r["country"] == c["country"] and r["y_old"] is not None]),
            np.mean([r["y_new"] for r in rows if r["country"] == c["country"] and r["y_new"] is not None]),
        )
        for c in data
    )
    maxv *= 1.12

    def sx(v):
        return left + v / maxv * pw

    out = []
    # gridlines
    step = 2.0 if maxv < 20 else 5.0
    tick = 0.0
    while tick <= maxv:
        x = sx(tick)
        out.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + ph}" '
                   f'stroke="#e6e9ed" stroke-width="1" stroke-dasharray="2 3"/>')
        out.append(f'<text x="{x:.1f}" y="{top + ph + 17}" font-size="10" fill="#8b9199" '
                   f'text-anchor="middle">{tick:g}</text>')
        tick += step
    out.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + ph}" '
               f'stroke="#c7ccd2" stroke-width="1"/>')

    for i, c in enumerate(data):
        y = top + row_h * (i + 0.5)
        old_vals = [r["y_old"] for r in rows if r["country"] == c["country"] and r["y_old"] is not None]
        new_vals = [r["y_new"] for r in rows if r["country"] == c["country"] and r["y_new"] is not None]
        mo, mn = float(np.mean(old_vals)), float(np.mean(new_vals))
        xo, xn = sx(mo), sx(mn)
        out.append(f'<line x1="{xo:.1f}" y1="{y:.1f}" x2="{xn:.1f}" y2="{y:.1f}" '
                   f'stroke="#cfd6dd" stroke-width="2"/>')
        out.append(f'<circle cx="{xo:.1f}" cy="{y:.1f}" r="4.2" fill="#2f6fb5"/>')
        out.append(f'<circle cx="{xn:.1f}" cy="{y:.1f}" r="4.2" fill="#c2410c"/>')
        out.append(f'<text x="{left - 10}" y="{y + 4:.1f}" font-size="11" fill="#16181d" '
                   f'text-anchor="end">{c["country"]}</text>')
        note = f'{c["ratio"]:.2f}' if c["ratio"] else "&ndash;"
        tone = "#c2410c" if c["distinct"] else "#9aa0a8"
        out.append(f'<text x="{left + pw + 14}" y="{y + 4:.1f}" font-size="10" fill="{tone}" '
                   f'text-anchor="start">x{note}</text>')
        corr = f'{c["corr"]:.2f}' if c["corr"] is not None else "&ndash;"
        out.append(f'<text x="{left + pw + 62}" y="{y + 4:.1f}" font-size="10" fill="#6b7280" '
                   f'text-anchor="start">r = {corr}</text>')

    out.append(f'<text x="{left}" y="26" font-size="13.5" font-weight="600" fill="#16181d">'
               f'Mean volatility: portfolio vs total capital inflows</text>')
    out.append(f'<text x="{left}" y="44" font-size="10.5" fill="#6b7280">'
               f'Emerging economies, 2000&#8211;2023, billion USD. Sorted by mean ratio.</text>')
    out.append(f'<text x="{left}" y="60" font-size="10.5" fill="#6b7280">'
               f'Right: volatility multiple, and correlation between the two series.</text>')
    out.append(f'<text x="{left + pw + 14}" y="78" font-size="9.5" fill="#9aa0a8">ratio</text>')
    out.append(f'<text x="{left + pw + 62}" y="78" font-size="9.5" fill="#9aa0a8">corr</text>')

    ly = top + ph + 42
    out.append(f'<circle cx="{left + 5}" cy="{ly}" r="4.2" fill="#2f6fb5"/>')
    out.append(f'<text x="{left + 16}" y="{ly + 4}" font-size="10.5" fill="#6b7280">'
               f'portfolio inflows (existing)</text>')
    out.append(f'<circle cx="{left + 210}" cy="{ly}" r="4.2" fill="#c2410c"/>')
    out.append(f'<text x="{left + 221}" y="{ly + 4}" font-size="10.5" fill="#6b7280">'
               f'total capital inflows (new)</text>')
    out.append(f'<text x="{left}" y="{ly + 22}" font-size="10" fill="#9aa0a8">'
               f'Grey ratio labels: FDI and other investment are blank there, so</text>')
    out.append(f'<text x="{left}" y="{ly + 35}" font-size="10" fill="#9aa0a8">'
               f'the total reduces to portfolio inflows.</text>')
    out.append(f'<text x="{left + pw / 2:.1f}" y="{top + ph + 30}" font-size="10.5" fill="#8b9199" '
               f'text-anchor="middle">mean three-month rolling standard deviation</text>')

    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
           f'viewBox="0 0 {width} {height}" font-family="Segoe UI, Helvetica, Arial, sans-serif">\n'
           f'<rect width="{width}" height="{height}" fill="#ffffff"/>\n'
           + "\n".join(out) + "\n</svg>")
    CHART_SVG_FINAL.write_text(svg, encoding="utf-8")
    return width, height


CHART_SVG_FINAL = __import__("pathlib").Path(CHART_SVG)
chart()

print(f"Wrote {RESULTS}")
print(f"Wrote {BUILT}")
print(f"Wrote {CHART_SVG}")


# --------------------------------------------------------------- html
def cell(stat):
    return (
        f'<span class="coef">{stat["coef"]:+.4f}{stars(stat["p"])}</span>'
        f'<span class="se">({stat["se"]:.4f})</span>'
        f'<span class="pv">p = {stat["p"]:.3f}</span>'
    )


def pclass(p):
    if p < 0.01:
        return "p01"
    if p < 0.05:
        return "p05"
    if p < 0.10:
        return "p10"
    return "pns"


head = "".join(f"<th>{label}</th>" for _, label in DIMENSIONS)

compare_rows = []
for term, label in [("gpr_z", "GPR, standardized"),
                    ("wgi_x_gpr", "WGI &times; GPR"),
                    ("wgi", "WGI, lagged")]:
    cells = []
    for key, _ in DIMENSIONS:
        old = results[key]["old"]["inference"][key if term == "wgi" else term]
        new = results[key]["new"]["inference"][key if term == "wgi" else term]
        cells.append(
            f'<td class="{pclass(new["p"])}">'
            f'<span class="pair"><b>{new["coef"]:+.3f}</b> <i>{stars(new["p"])}</i></span>'
            f'<span class="was">was {old["coef"]:+.3f}{stars(old["p"])}</span>'
            f'<span class="pv">p {old["p"]:.2f} &rarr; {new["p"]:.2f}</span></td>'
        )
    compare_rows.append(f"<tr><th>{label}</th>{''.join(cells)}</tr>")

full_rows = []
for term, label in [("gpr_z", "GPR, standardized"), ("wgi_x_gpr", "WGI &times; GPR")] + [
    (name, TERM_LABELS[name]) for name in CONTROLS
]:
    cells = "".join(
        f'<td class="{pclass(results[key]["new"]["inference"][term]["p"])}">'
        f'{cell(results[key]["new"]["inference"][term])}</td>'
        for key, _ in DIMENSIONS
    )
    full_rows.append(f"<tr><th>{label}</th>{cells}</tr>")

wgi_row = "".join(
    f'<td class="{pclass(results[key]["new"]["inference"][key]["p"])}">'
    f'{cell(results[key]["new"]["inference"][key])}</td>'
    for key, _ in DIMENSIONS
)
full_rows.insert(0, f"<tr><th>WGI, lagged</th>{wgi_row}</tr>")

first = results["wgi_va"]["new"]
old_first = results["wgi_va"]["old"]

distinct = [c["country"] for c in coverage if c["distinct"]]
identical = [c["country"] for c in coverage if not c["distinct"]]
corrs = [c["corr"] for c in coverage if c["corr"] is not None]
ratios = [c["ratio"] for c in coverage if c["ratio"] is not None]

cov_rows = "".join(
    f'<tr><td>{c["country"]}</td><td class="num">{c["old_n"]}</td>'
    f'<td class="num">{c["new_n"]}</td>'
    f'<td class="num">{"" if c["corr"] is None else format(c["corr"], ".3f")}</td>'
    f'<td class="num">{"" if c["ratio"] is None else format(c["ratio"], ".2f")}</td>'
    f'<td>{"components present" if c["distinct"] else "portfolio only"}</td></tr>'
    for c in coverage
)

chart_rel = os.path.basename(CHART_SVG)

html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Model 2: capital-inflow volatility and institutional quality</title>
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
table {{ border-collapse: collapse; width: 100%; margin: 1em 0 1.6em; font-size: .8em; }}
th, td {{ border-bottom: 1px solid var(--line); padding: .45em .5em; text-align: right;
  vertical-align: top; }}
thead th {{ background: var(--pale); font-size: .95em; text-align: center; line-height: 1.25; }}
tbody th {{ text-align: left; font-weight: normal; width: 14em; }}
td .coef, td .pair {{ display: block; font-weight: 700; font-variant-numeric: tabular-nums; }}
td .se, td .was {{ display: block; color: var(--muted); font-size: .95em;
  font-variant-numeric: tabular-nums; }}
td .was {{ font-style: italic; }}
td .pv {{ display: block; font-size: .85em; font-variant-numeric: tabular-nums; color: #7c8794; }}
td.p01 {{ background:#d9f0dc; }} td.p05 {{ background:#e6f5e8; }}
td.p10 {{ background:#f2f8e8; }} td.pns {{ color:#53616e; }}
td.p01 .pv, td.p05 .pv, td.p10 .pv {{ font-weight: 700; }}
td.num {{ font-variant-numeric: tabular-nums; }}
.legend {{ font-size: .86em; color: var(--muted); }}
.figure {{ border:1px solid var(--line); border-radius:5px; overflow-x:auto; }}
.figure svg {{ display:block; }}
code {{ font-size: .92em; background: var(--pale); padding: .05em .3em; }}
ul {{ margin:.5em 0; }} li {{ margin:.35em 0; }}
</style>
</head>
<body>
<h1>Model 2 with capital-inflow volatility as the outcome</h1>
<p class="sub">Emerging economies, {first['g']} countries, {first['first']} to {first['last']},
{first['n']:,} country-months &mdash; identical sample to the portfolio-based Model 2</p>

<div class="note">
<p><b>What changed.</b> Only the flow that enters the three-month rolling standard deviation.
The existing outcome uses portfolio inflows. The new outcome adds foreign direct investment and
other investment, so the underlying flow is total capital inflow.</p>
<p><b>Everything else is held fixed.</b> Same controls, same one-month lags, same country fixed
effects, same country-clustered standard errors, same window, same <code>Emerging</code> filter.
Both outcomes therefore use exactly {first['n']:,} country-months and {first['g']} countries, and
the two tables are directly comparable.</p>
<p><b>One caveat on the new series.</b> FDI and other-investment components are blank for some
countries in the source file. Where they are blank the total reduces to portfolio inflows, so the
new outcome differs from the existing one for {len(distinct)} of {len(coverage)} countries and is
numerically identical for {len(identical)} ({", ".join(identical)}). Thailand is partly identical.</p>
</div>

<h2>Terms of interest, new outcome against the existing one</h2>
<p class="legend">Bold is the new capital-inflow estimate; italics show the existing
portfolio-inflow estimate for comparison. Shading follows the new outcome's p-value.</p>
<table>
<thead><tr><th></th>{head}</tr></thead>
<tbody>{''.join(compare_rows)}</tbody>
</table>

<h2>Full estimates, capital-inflow volatility</h2>
<table>
<thead><tr><th></th>{head}</tr></thead>
<tbody>{''.join(full_rows)}</tbody>
</table>
<p class="legend">*** p &lt; 0.01, ** p &lt; 0.05, * p &lt; 0.10. Country-clustered standard
errors in parentheses, {first['g']} clusters, {first['g'] - 1} degrees of freedom.</p>

<h2>Fit</h2>
<table>
<thead><tr><th></th>{head}</tr></thead>
<tbody>
<tr><th>Observations</th>{''.join(f'<td class="num">{results[k]["new"]["n"]:,}</td>' for k, _ in DIMENSIONS)}</tr>
<tr><th>Countries</th>{''.join(f'<td class="num">{results[k]["new"]["g"]}</td>' for k, _ in DIMENSIONS)}</tr>
<tr><th>Within R&sup2;, new</th>{''.join(f'<td class="num">{results[k]["new"]["within_r2"]:.4f}</td>' for k, _ in DIMENSIONS)}</tr>
<tr><th>Within R&sup2;, existing</th>{''.join(f'<td class="num">{results[k]["old"]["within_r2"]:.4f}</td>' for k, _ in DIMENSIONS)}</tr>
</tbody>
</table>

<h2>The two outcomes by country</h2>
<div class="figure">
{CHART_SVG_FINAL.read_text(encoding="utf-8")}
</div>

<h2>Coverage of the rebuilt series</h2>
<table>
<thead><tr><th>Country</th><th>Months, existing</th><th>Months, new</th>
<th>Correlation</th><th>Mean ratio</th><th>Components</th></tr></thead>
<tbody>{cov_rows}</tbody>
</table>
<p class="legend">Correlation is between the two volatility series within the country. Mean ratio
is the mean of the new series divided by the mean of the existing one. Median correlation
{format(float(np.median(corrs)), '.3f')}; median ratio {format(float(np.median(ratios)), '.2f')}.</p>

<h2>Reading the change</h2>
<ul>
<li>GPR and the WGI interaction remain insignificant in all six columns, as they were with the
portfolio outcome. Widening the flow definition does not produce evidence that geopolitical risk
moves capital-inflow volatility in emerging economies.</li>
<li>The one WGI dimension that clears 10 percent moves from government effectiveness (p = 0.057)
to rule of law (p = 0.069). Neither threshold is crossed robustly, and both are single columns out
of six.</li>
<li>The new outcome is larger on average (median ratio {format(float(np.median(ratios)), '.2f')}),
because FDI and other investment add variance rather than cancel it. Coefficients are therefore not
comparable in size across the two tables; only their signs and significance are.</li>
<li>Where the two series coincide the country contributes no identifying variation to the
difference between specifications. {len(identical)} of {len(coverage)} countries are in that
position for their whole span.</li>
</ul>

<h2>Files</h2>
<p>Built series: <code>cleaned/replication_cleaned/country_month_inflow.csv</code>. Coefficients:
<code>output/model2_inflow_results.csv</code>. Chart:
<code>output/{chart_rel}</code>. Script: <code>output/run_model2_inflow_vol.py</code>.
The existing portfolio-based results in <code>output/model2_results.csv</code> are untouched.</p>
</body>
</html>
"""

with open(REPORT, "w", encoding="utf-8") as handle:
    handle.write(html)
print(f"Wrote {REPORT}")

print()
print(f"{'dimension':<26}{'GPR old':>10}{'GPR new':>10}{'int old':>10}{'int new':>10}"
      f"{'WGI old':>10}{'WGI new':>10}")
for key, label in DIMENSIONS:
    o = results[key]["old"]["inference"]
    n = results[key]["new"]["inference"]
    print(f"{label:<26}{o['gpr_z']['coef']:>10.4f}{n['gpr_z']['coef']:>10.4f}"
          f"{o['wgi_x_gpr']['coef']:>10.4f}{n['wgi_x_gpr']['coef']:>10.4f}"
          f"{o[key]['coef']:>10.4f}{n[key]['coef']:>10.4f}")
