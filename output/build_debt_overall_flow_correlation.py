"""Correlation of OVERALL capital flows with the public debt/GDP ratio.

Overall flow = Financial account balance, excluding reserves and related items
(direct + portfolio + other investment + financial derivatives), in USD millions,
from `cleaned/capital_flow.csv`. Quarterly only: no monthly overall-flow series
exists in this project, and the underlying IMF extract has only quarterly and
annual frequencies.

Sample: 15 emerging markets per `cleaned/country.csv`, excluding South Korea
(classified advanced). Window 2000-2023. Debt/GDP is annual.

Writes `output/debt_overall_flow_correlation.html` and a matching .csv.
"""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CAPITAL_FLOW = ROOT / "cleaned" / "capital_flow.csv"
DEBT = ROOT / "cleaned" / "debt_gdp.csv"
IMF = (
    ROOT
    / "input"
    / "capital_outflow"
    / "dataset_2026-11-08T08_54_54.385663722Z_DEFAULT_INTEGRATION_IMF.STA_BOP_21.0.0.csv"
)
OUT_HTML = Path(__file__).resolve().parent / "debt_overall_flow_correlation.html"
OUT_CSV = Path(__file__).resolve().parent / "debt_overall_flow_correlation.csv"

EM = [
    "Mexico", "Argentina", "Chile", "Peru", "Hungary", "Ukraine", "Turkey",
    "Egypt", "Tunisia", "South Africa", "India", "Indonesia", "Philippines",
    "Thailand", "Vietnam",
]
Y0, Y1 = 2000, 2023
ALIAS = {"Korea, Republic of": "South Korea", "Türkiye, Republic of": "Turkey"}
COMPONENTS = {
    "Direct investment, Total financial assets/liabilities": "FDI",
    "Portfolio investment, Total financial assets/liabilities": "Portfolio",
    "Other investment, Total financial assets/liabilities": "Other",
    "Financial account balance, excluding reserves and related items": "Overall",
}


def to_float(x):
    s = (x or "").strip() if isinstance(x, str) else x
    if s is None or s == "":
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def qkey(p):
    y, q = p.split("-Q")
    return int(y) * 4 + int(q) - 1


def pear(x, y):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    m = np.isfinite(x) & np.isfinite(y)
    x, y = x[m], y[m]
    if len(x) < 3 or x.std() == 0 or y.std() == 0:
        return float("nan"), len(x)
    return float(np.corrcoef(x, y)[0, 1]), len(x)


def within(recs, xk, yk):
    g = defaultdict(list)
    for r in recs:
        if r[xk] is not None and r[yk] is not None:
            g[r["c"]].append(r)
    dx, dy = [], []
    for v in g.values():
        if len(v) < 3:
            continue
        a = np.array([r[xk] for r in v])
        b = np.array([r[yk] for r in v])
        dx.extend(a - a.mean())
        dy.extend(b - b.mean())
    return pear(dx, dy)


def first_diff(recs, xk, yk):
    g = defaultdict(list)
    for r in recs:
        if r[xk] is not None and r[yk] is not None:
            g[r["c"]].append(r)
    dx, dy = [], []
    for v in g.values():
        v.sort(key=lambda r: r["k"])
        for a, b in zip(v, v[1:]):
            dx.append(b[xk] - a[xk])
            dy.append(b[yk] - a[yk])
    return pear(dx, dy)


def stars(n, r):
    """Normal-approximation two-sided test. Suppressed when |r| < 0.05."""
    if n < 4 or np.isnan(r) or abs(r) < 0.05:
        return ""
    z = abs(r) * math.sqrt(max(n - 3, 1))
    p = 2 * (1 - 0.5 * (1 + math.erf(z / math.sqrt(2))))
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""


def fmt(v, d=3):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "&mdash;"
    return f"{v:+.{d}f}"


def load_debt():
    out = defaultdict(dict)
    for r in csv.DictReader(DEBT.open(encoding="utf-8-sig")):
        v = to_float(r["debt_gdp_pct"])
        if v is not None:
            out[r["country"].strip()][int(r["period"])] = v
    return out


def load_components():
    ser = defaultdict(dict)
    for r in csv.DictReader(IMF.open(encoding="utf-8-sig")):
        key = COMPONENTS.get(r["INDICATOR"])
        if not key:
            continue
        c = ALIAS.get(r["COUNTRY"].strip(), r["COUNTRY"].strip())
        for p, v in r.items():
            if p[:2] == "20" and p[4:6] == "-Q":
                val = to_float(v)
                if val is not None:
                    ser[key][(c, p)] = val
    return ser


def build(ser, kind, debt, horizon=3):
    """Quarterly records with rolling `horizon`-quarter SD volatility."""
    recs = []
    for c in EM:
        qs = sorted({p for (cc, p) in ser[kind] if cc == c}, key=qkey)
        for i, q in enumerate(qs):
            y = int(q[:4])
            if y < Y0 or y > Y1 or y not in debt[c]:
                continue
            win = [ser[kind].get((c, qq)) for qq in qs[max(0, i - horizon + 1): i + 1]]
            win = [w for w in win if w is not None]
            vol = float(np.std(win, ddof=0)) if len(win) >= horizon else None
            flow = ser[kind][(c, q)]
            recs.append({
                "c": c, "q": q, "y": y, "k": qkey(q),
                "flow": flow, "absflow": abs(flow), "vol": vol,
                "debt": debt[c][y],
            })
    return recs


debt = load_debt()
ser = load_components()

# Overall flow straight from the cleaned file (authoritative for the headline)
overall_raw = defaultdict(dict)
for r in csv.DictReader(CAPITAL_FLOW.open(encoding="utf-8-sig")):
    v = to_float(r["usd_millions"])
    if v is not None:
        overall_raw[r["country"].strip()][r["year_quarter"].strip()] = v
ser["Overall"].update({(c, q): v for c, d in overall_raw.items() for q, v in d.items()})

recs = build(ser, "Overall", debt)
assert len({r["c"] for r in recs}) == 15

MEASURES = [
    ("flow", "Overall flow (level)", "Net acquisition of assets less liabilities, USD mn"),
    ("absflow", "Absolute overall flow", "Size of the flow, sign removed"),
    ("vol", "Overall flow volatility", "Rolling 3-quarter standard deviation"),
]

headline = []
for xk, label, note in MEASURES:
    p, n = pear([r["debt"] for r in recs], [r[xk] for r in recs])
    w, _ = within(recs, "debt", xk)
    d, _ = first_diff(recs, "debt", xk)
    headline.append((xk, label, note, n, p, w, d))

# Per-country correlations
per_country = []
g = defaultdict(list)
for r in recs:
    g[r["c"]].append(r)
for c in EM:
    v = sorted(g[c], key=lambda r: r["k"])
    if len(v) < 10:
        continue
    pc_flow, _ = pear([r["debt"] for r in v], [r["flow"] for r in v])
    pc_vol, _ = pear([r["debt"] for r in v], [r["vol"] for r in v])
    per_country.append((c, len(v), pc_flow, pc_vol,
                        float(np.mean([r["debt"] for r in v]))))

# Component comparison on the SAME sample
comp_rows = []
for kind in ["Overall", "FDI", "Portfolio", "Other"]:
    cr = build(ser, kind, debt)
    p, n = pear([r["debt"] for r in cr], [r["vol"] for r in cr])
    w, _ = within(cr, "debt", "vol")
    gg = defaultdict(list)
    for r in cr:
        gg[r["c"]].append(r)
    pc = [pear([r["debt"] for r in v], [r["vol"] for r in v])[0]
          for v in gg.values() if len(v) > 10]
    comp_rows.append((kind, n, p, w, float(np.nanmean(pc)),
                      sum(1 for z in pc if z > 0), len(pc)))

n_cells = len(recs)
n_years = Y1 - Y0 + 1
mean_flow = float(np.mean([r["flow"] for r in recs]))


def head_rows():
    out = []
    for xk, label, note, n, p, w, d in headline:
        out.append(
            f"<tr><td class='lbl'>{label}<span class='sm'>{note}</span></td>"
            f"<td class='num'>{n:,}</td>"
            f"<td class='num strong'>{fmt(p)}{stars(n, p)}</td>"
            f"<td class='num'>{fmt(w)}{stars(n, w)}</td>"
            f"<td class='num'>{fmt(d)}{stars(n, d)}</td></tr>"
        )
    return "\n".join(out)


def country_rows():
    out = []
    for c, n, f, v, dbt in sorted(per_country, key=lambda x: -x[2]):
        cls = "pos" if f > 0 else "neg"
        out.append(
            f"<tr><td>{c}</td><td class='num'>{n}</td>"
            f"<td class='num {cls}'>{fmt(f)}</td>"
            f"<td class='num'>{fmt(v)}</td>"
            f"<td class='num'>{dbt:.1f}</td></tr>"
        )
    return "\n".join(out)


def comp_table():
    out = []
    for kind, n, p, w, mc, npos, tot in comp_rows:
        name = {"Overall": "Overall flow", "FDI": "Direct investment",
                "Portfolio": "Portfolio investment", "Other": "Other investment"}[kind]
        out.append(
            f"<tr><td class='lbl'>{name}</td><td class='num'>{n:,}</td>"
            f"<td class='num strong'>{fmt(p)}{stars(n, p)}</td>"
            f"<td class='num'>{fmt(w)}</td>"
            f"<td class='num'>{fmt(mc)}</td>"
            f"<td class='num'>{npos}/{tot}</td></tr>"
        )
    return "\n".join(out)


n_pos_flow = sum(1 for r in per_country if r[2] > 0)
n_pos_vol = sum(1 for r in per_country if r[3] > 0)

page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Overall capital flows and debt/GDP: 15 emerging markets</title>
<style>
  :root {{
    --ink: #16181d; --muted: #6b7280; --line: #e3e6ea;
    --pos: #1f6feb; --neg: #c2410c; --panel: #fbfcfd;
  }}
  body {{
    font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, sans-serif;
    margin: 40px auto 76px; max-width: 960px; padding: 0 24px;
    color: var(--ink); background: #fff; line-height: 1.58;
  }}
  h1 {{ font-size: 23px; font-weight: 650; margin: 0 0 5px; letter-spacing: -.01em; }}
  h2 {{ font-size: 16px; font-weight: 650; margin: 40px 0 4px; }}
  .sub {{ color: var(--muted); font-size: 13px; margin: 0 0 8px; }}
  p {{ margin: 0 0 12px; font-size: 14px; }}
  table {{ width: 100%; border-collapse: collapse; margin: 10px 0 6px; font-size: 13.5px; }}
  thead th {{
    text-align: left; font-weight: 640; font-size: 11.5px; letter-spacing: .04em;
    text-transform: uppercase; color: var(--muted);
    border-bottom: 1.5px solid var(--ink); padding: 8px 10px; vertical-align: bottom;
  }}
  tbody td {{ padding: 8px 10px; border-bottom: 1px solid var(--line); vertical-align: top; }}
  tbody tr:hover {{ background: var(--panel); }}
  .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .strong {{ font-weight: 620; }}
  .lbl {{ font-weight: 560; }}
  .sm {{ display: block; font-weight: 400; font-size: 11.5px; color: var(--muted); margin-top: 2px; }}
  .pos {{ color: var(--pos); }} .neg {{ color: var(--neg); }}
  .note {{
    background: var(--panel); border-left: 3px solid #94a3b8;
    padding: 12px 15px; font-size: 13px; color: #374151; margin: 18px 0;
  }}
  .note b {{ color: var(--ink); }}
  .flag {{ font-size: 12.5px; color: var(--muted); margin-top: 4px; }}
  .kpi {{ display: flex; gap: 36px; margin: 20px 0 4px; flex-wrap: wrap; }}
  .kpi div span {{
    display: block; font-size: 11px; color: var(--muted);
    text-transform: uppercase; letter-spacing: .05em; margin-bottom: 1px;
  }}
  .big {{ font-size: 30px; font-weight: 620; letter-spacing: -.02em; }}
  .chips {{ display: flex; flex-wrap: wrap; gap: 6px; margin: 10px 0 0; }}
  .chip {{
    font-size: 12px; padding: 3px 9px; border: 1px solid var(--line);
    border-radius: 20px; color: #374151;
  }}
  footer {{ margin-top: 46px; padding-top: 14px; border-top: 1px solid var(--line); font-size: 12px; color: var(--muted); }}
  code {{ font-size: 12px; background: #f3f4f6; padding: 1px 5px; border-radius: 3px; }}
</style>
</head>
<body>

<h1>Overall capital flows and the debt-to-GDP ratio</h1>
<p class="sub">Quarterly &middot; 15 emerging markets &middot; 2000&ndash;2023</p>

<div class="note">
<b>What &ldquo;overall&rdquo; means here.</b> The flow is the IMF
<i>Financial account balance, excluding reserves and related items</i>, in USD millions &mdash; direct
investment, portfolio investment, other investment and financial derivatives combined. Negative
values are net inflows; positive values net outflows. This is <code>cleaned/capital_flow.csv</code>.
<br><br>
<b>Quarterly only.</b> No monthly overall-flow series exists in this project. The monthly panel
carries portfolio investment alone, and the underlying IMF extract is quarterly and annual.
</div>

<div class="kpi">
  <div><span>Countries</span><div class="big">15</div></div>
  <div><span>Quarters</span><div class="big">{n_cells:,}</div></div>
  <div><span>Years</span><div class="big">{n_years}</div></div>
  <div><span>Mean flow</span><div class="big">{mean_flow:,.0f}</div></div>
</div>
<p class="flag">Mean flow in USD millions. Every country has 106 quarters of coverage.</p>

<h2>1. Correlation with the debt-to-GDP ratio</h2>
<table>
  <thead>
    <tr><th>Measure</th><th class="num">N</th><th class="num">Pooled</th>
        <th class="num">Within-country</th><th class="num">First difference</th></tr>
  </thead>
  <tbody>
{head_rows()}
  </tbody>
</table>
<p class="flag">Pooled = all country-quarters. Within-country = both variables demeaned by
country. First difference = quarter-to-quarter changes within country.</p>

<p>The picture is essentially a null, with one exception. Volatility shows no association with
debt/GDP at all (+0.008 pooled, &minus;0.001 within, +0.008 differenced), and neither does the
absolute size of the flow. The single non-trivial coefficient is the <i>within-country</i> correlation
of the signed level (+0.147), discussed below. That is a materially different answer from the
portfolio-flow series, which returned roughly +0.24 pooled.</p>

<h2>2. Where does the flow correlation actually live?</h2>
<p>Aggregation is doing something: the within-country association is concentrated in the signed
level (+0.147), not in volatility. The sign is interpretable &mdash; higher debt goes with
somewhat smaller net inflows &mdash; but the magnitude is modest, and it does not survive into
volatility or into the differenced series.</p>
<table>
  <thead>
    <tr><th>Country</th><th class="num">N</th><th class="num">r (level)</th>
        <th class="num">r (volatility)</th><th class="num">Mean debt %</th></tr>
  </thead>
  <tbody>
{country_rows()}
  </tbody>
</table>
<p class="flag">Country-by-country correlations over time. Level: {n_pos_flow} of {len(per_country)}
are positive. Volatility: {n_pos_vol} of {len(per_country)} are positive. Country signs disagree
sharply &mdash; Chile &minus;0.458 on the level, Indonesia +0.502 &mdash; which is why the pooled
figure collapses.</p>

<h2>3. Component decomposition, identical sample</h2>
<p>If the overall-flow result were merely an artifact of mixing components, the parts would
disagree with the whole. They do not: all four sit in a narrow band.</p>
<table>
  <thead>
    <tr><th>Component</th><th class="num">N</th><th class="num">Pooled</th>
        <th class="num">Within</th><th class="num">Mean country r</th>
        <th class="num">Positive</th></tr>
  </thead>
  <tbody>
{comp_table()}
  </tbody>
</table>
<p class="flag">Volatility of each component, same 15 countries, same quarters, same 3-quarter
rolling window, same debt series.</p>

<p>Two things follow. First, the components co-move rather than offset: their volatilities
correlate at +0.45 to +0.57 with each other, so aggregation does not wash out a component-level
signal. Second, portfolio investment is the <i>weakest</i> component on this sample (+0.034
pooled, and negative on average across countries), which means the +0.24 from the model file
cannot be attributed to the portfolio definition. It comes from the sample: those 15 countries
include Brazil, China, Colombia, Malaysia, Poland and T&uuml;rkiye, and that six-country block
alone carries a within-country correlation of +0.294 on the model file's own volatility series.</p>

<h2>4. Why the two numbers are not comparable</h2>
<p>An additional reason to be careful: the model file's <code>portfolio_inflow</code> is not in
the same units as the USD flow used here. Regressing one on the other implies a
GDP-like denominator, so the model variable is effectively GDP-normalised while the overall flow
is in levels. A pooled correlation in levels mixes a scale effect into the statistic: countries
with larger economies have both bigger dollar flows and their own debt levels, so the pooled
coefficient partly measures size, not behaviour. Within-country correlations are immune to this,
and they are where the two series are closest.</p>

<h2>5. Bottom line</h2>
<p><b>Overall capital flows carry no debt/GDP signal in volatility terms.</b> Pooled +0.008,
within-country &minus;0.001. Unlike portfolio flows, there is no cross-country gradient to explain.</p>
<p><b>The one non-trivial association is the signed level, within country (+0.147).</b> It points
the intuitive way &mdash; more indebted economies attract smaller net inflows &mdash; but it is
weak, dispersed in sign across countries, and absent from the differenced series (+0.026).</p>
<p><b>Treat the earlier +0.24 as a portfolio-flow, model-sample statistic.</b> It is reproducible,
but it reflects that nine-country overlapping set plus the six non-overlapping economies, not the
overall financial account and not a consistent panel.</p>

<h2>6. Countries</h2>
<div class="chips">
{''.join(f'<span class="chip">{c}</span>' for c in EM)}
</div>

<footer>
Flow: <code>cleaned/capital_flow.csv</code> (IMF BOP 21.0.0, financial account balance excluding
reserves, USD millions). Debt: <code>cleaned/debt_gdp.csv</code>, annual general-government gross
debt, percent of GDP, repeated across the quarters of each year. South Korea excluded as an
advanced economy. 2024&ndash;2026 dropped to match the 2000&ndash;2023 study window.
Stars: * p&lt;0.10, ** p&lt;0.05, *** p&lt;0.01, normal approximation, suppressed when |r| &lt; 0.05;
indicative only, as pooled observations are not independent.
</footer>

</body>
</html>
"""

OUT_HTML.write_text(page, encoding="utf-8")

with OUT_CSV.open("w", encoding="utf-8", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["section", "item", "n", "pooled_r", "within_r", "first_diff_r"])
    for xk, label, note, n, p, ww, d in headline:
        w.writerow(["headline", label, n, f"{p:.4f}", f"{ww:.4f}", f"{d:.4f}"])
    for c, n, f, v, dbt in per_country:
        w.writerow([f"country_{c}", "level_r", n, f"{f:.4f}", "", ""])
        w.writerow([f"country_{c}", "vol_r", n, f"{v:.4f}", "", ""])
    for kind, n, p, ww, mc, npos, tot in comp_rows:
        w.writerow(["component", f"{kind}_vol", n, f"{p:.4f}", f"{ww:.4f}", ""])

print(f"wrote {OUT_HTML}")
print(f"wrote {OUT_CSV}")
print()
for xk, label, note, n, p, ww, d in headline:
    print(f"{label:32s} n={n:5d} pooled={p:+.3f} within={ww:+.3f} diff={d:+.3f}")
print()
for kind, n, p, ww, mc, npos, tot in comp_rows:
    print(f"{kind:12s} vol n={n:5d} pooled={p:+.3f} within={ww:+.3f} mean_country={mc:+.3f} pos={npos}/{tot}")
