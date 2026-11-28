"""Emerging economies only: correlation of gpr_z (x) with capital_flow_volatility (y).

Reads cleaned/replication_cleaned/country_month.csv, keeps group == "Emerging",
and computes a per-country Pearson correlation on monthly data, 2000-2023.

Output: output/correlation_gpr_z_cfv_emerging.html (+ .svg)
"""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PANEL = ROOT / "cleaned" / "replication_cleaned" / "country_month.csv"
OUT_HTML = ROOT / "output" / "correlation_gpr_z_cfv_emerging.html"
OUT_SVG = ROOT / "output" / "correlation_gpr_z_cfv_emerging.svg"

Y0, Y1 = 2000, 2023

# China and Hungary are excluded: they carry the two largest country correlations
# in the 15-country sample and, between them, account for the whole pooled
# positive association. Dropping them is a fragility check, not a preferred
# specification.
DROP_COUNTRIES = {"China", "Hungary"}


def to_float(x):
    if x is None:
        return None
    x = str(x).strip()
    if not x:
        return None
    try:
        return float(x)
    except ValueError:
        return None


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def pear(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    sxx = sum((a - mx) ** 2 for a in xs)
    syy = sum((b - my) ** 2 for b in ys)
    if sxx <= 0 or syy <= 0:
        return None
    return sxy / math.sqrt(sxx * syy)


def load():
    by = defaultdict(lambda: {"z": [], "v": [], "mon": [], "country": None, "group": None})
    kept_rows = 0
    with PANEL.open(encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            if r["group"].strip() != "Emerging":
                continue
            if r["country"].strip() in DROP_COUNTRIES:
                continue
            date = r["date"].strip()
            yr = to_float(date[:4])
            if yr is None or not (Y0 <= yr <= Y1):
                continue
            z = to_float(r["gpr_z"])
            v = to_float(r["capital_flow_volatility"])
            if z is None or v is None:
                continue
            d = by[r["iso"].strip()]
            d["country"] = r["country"].strip()
            d["group"] = r["group"].strip()
            d["z"].append(z)
            d["v"].append(v)
            d["mon"].append(date[:7])
            kept_rows += 1
    return by, kept_rows


by_iso, n_rows = load()

records = []
for iso, d in by_iso.items():
    n = len(d["z"])
    rr = pear(d["z"], d["v"])
    if rr is None:
        continue
    t = abs(rr) * math.sqrt(max(n - 2, 1) / max(1 - rr * rr, 1e-12))
    records.append({
        "iso": iso,
        "country": d["country"],
        "n": n,
        "r": rr,
        "t": t,
        "sig": t > 1.96,
        "first": min(d["mon"]),
        "last": max(d["mon"]),
    })

records.sort(key=lambda x: -x["r"])
n_ctry = len(records)
n_pos = sum(1 for x in records if x["r"] > 0)
n_sig = sum(1 for x in records if x["sig"])

# pooled, for the note
all_z, all_v = [], []
for d in by_iso.values():
    all_z.extend(d["z"])
    all_v.extend(d["v"])
r_pool = pear(all_z, all_v)

# country-demeaned pooled (equals the fixed-effects identifying variation)
dz, dv = [], []
for d in by_iso.values():
    mz = sum(d["z"]) / len(d["z"])
    mv = sum(d["v"]) / len(d["v"])
    dz.extend(a - mz for a in d["z"])
    dv.extend(b - mv for b in d["v"])
r_within = pear(dz, dv)

mean_r = sum(x["r"] for x in records) / n_ctry
median_r = sorted(x["r"] for x in records)[n_ctry // 2]

# ------------------------------------------------------------------ chart
W, H = 880, 520
PL, PR, PT, PB = 140, 86, 64, 82
PW = W - PL - PR
PH = H - PT - PB
r_lo, r_hi = -0.45, 0.45


def sx(v):
    return PL + (v - r_lo) / (r_hi - r_lo) * PW


rows_sorted = sorted(records, key=lambda x: -x["r"])
bh = PH / len(rows_sorted)
bar_h = min(bh * 0.64, 17)
VAL_X = PL + PW + 12

parts = []
# gridlines
for tick in [-0.4, -0.2, 0.0, 0.2, 0.4]:
    x = sx(tick)
    dash = "" if tick == 0 else ' stroke-dasharray="2 3"'
    parts.append(f'<line x1="{x:.1f}" y1="{PT}" x2="{x:.1f}" y2="{PT + PH}" '
                 f'stroke="#dfe3e8" stroke-width="1"{dash}/>')
    lab = "0.0" if abs(tick) < 1e-9 else (f"{tick:+.1f}")
    parts.append(f'<text x="{x:.1f}" y="{PT + PH + 17}" font-size="10.5" fill="#6b7280" '
                 f'text-anchor="middle">{lab}</text>')

for i, rec in enumerate(rows_sorted):
    yc = PT + bh * (i + 0.5)
    x0 = sx(0)
    x1 = sx(rec["r"])
    col = "#2f6fb5" if rec["r"] >= 0 else "#c2410c"
    op = "0.92" if rec["sig"] else "0.5"
    parts.append(f'<rect x="{min(x0, x1):.1f}" y="{yc - bar_h / 2:.1f}" '
                 f'width="{max(abs(x1 - x0), 1.2):.1f}" height="{bar_h:.1f}" fill="{col}" '
                 f'fill-opacity="{op}" rx="1.5"/>')
    parts.append(f'<text x="{PL - 10}" y="{yc + 4:.1f}" font-size="11" fill="#16181d" '
                 f'text-anchor="end">{esc(rec["country"])}</text>')
    star = "*" if rec["sig"] else ""
    weight = ' font-weight="600"' if rec["sig"] else ""
    parts.append(f'<text x="{VAL_X:.1f}" y="{yc + 3.5:.1f}" font-size="10" fill="#374151" '
                 f'text-anchor="start"{weight}>{rec["r"]:+.3f}{star}</text>')

parts.append(f'<line x1="{sx(0):.1f}" y1="{PT}" x2="{sx(0):.1f}" y2="{PT + PH}" '
             f'stroke="#9aa3ad" stroke-width="1.2"/>')
parts.append(f'<text x="{PL + PW / 2:.1f}" y="{PT + PH + 44}" font-size="11" fill="#6b7280" '
             f'text-anchor="middle">Pearson r  (gpr_z , capital_flow_volatility), monthly 2000&#8211;2023</text>')
parts.append(f'<text x="{VAL_X:.1f}" y="{PT + PH + 17}" font-size="10.5" fill="#9aa3ad" '
             f'text-anchor="start">r</text>')

# title block
parts.append(f'<text x="{PL - 100}" y="26" font-size="13.5" font-weight="600" fill="#16181d">'
             f'GPR and capital-flow volatility: emerging economies</text>')
parts.append(f'<text x="{PL - 100}" y="43" font-size="10.5" fill="#6b7280">'
             f'{n_ctry} countries, {n_rows:,} country-months, excluding China and Hungary. '
             f'Solid bars are significant at 5% (|t| &gt; 1.96).</text>')

# legend
ly = PT + PH + 68
parts.append(f'<rect x="{PL}" y="{ly - 5}" width="9" height="9" fill="#2f6fb5" rx="1.5"/>')
parts.append(f'<text x="{PL + 14}" y="{ly + 3}" font-size="10" fill="#6b7280">positive</text>')
parts.append(f'<rect x="{PL + 78}" y="{ly - 5}" width="9" height="9" fill="#c2410c" rx="1.5"/>')
parts.append(f'<text x="{PL + 92}" y="{ly + 3}" font-size="10" fill="#6b7280">negative</text>')
parts.append(f'<rect x="{PL + 156}" y="{ly - 5}" width="9" height="9" fill="#8b8f96" rx="1.5" fill-opacity="0.5"/>')
parts.append(f'<text x="{PL + 170}" y="{ly + 3}" font-size="10" fill="#6b7280">faded = not significant</text>')

svg_body = "\n".join(parts)
svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
       f'viewBox="0 0 {W} {H}" font-family="Segoe UI, Helvetica, Arial, sans-serif">\n'
       f'<rect width="{W}" height="{H}" fill="#ffffff"/>\n{svg_body}\n</svg>')

OUT_SVG.write_text(svg, encoding="utf-8")

# ------------------------------------------------------------------ table
def rows_html():
    out = []
    for rec in records:
        sig = ' <span class="sig">*</span>' if rec["sig"] else ""
        out.append(
            f'<tr><td>{esc(rec["country"])}</td>'
            f'<td class="num">{rec["n"]}</td>'
            f'<td class="num strong">{rec["r"]:+.3f}{sig}</td></tr>'
        )
    return "\n".join(out)


markdown = "\n".join(
    f'{r["country"]:<17}{r["n"]:>5}   {r["r"]:+.3f}{"  *" if r["sig"] else ""}'
    for r in records
)

page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>GPR z-score and capital-flow volatility: emerging economies</title>
<style>
  :root {{ --ink:#16181d; --muted:#6b7280; --line:#e3e6ea; --pos:#2f6fb5; --neg:#c2410c; }}
  body {{ font-family:"Segoe UI",-apple-system,BlinkMacSystemFont,sans-serif;
          margin:38px auto 70px; max-width:900px; padding:0 26px;
          color:var(--ink); background:#fff; line-height:1.58; }}
  h1 {{ font-size:21px; font-weight:650; margin:0 0 5px; letter-spacing:-.01em; }}
  h2 {{ font-size:15px; font-weight:650; margin:32px 0 6px; }}
  .sub {{ color:var(--muted); font-size:13px; margin:0 0 16px; }}
  p {{ margin:0 0 11px; font-size:14px; max-width:820px; }}
  .note {{ background:#fbfcfd; border-left:3px solid #94a3b8; padding:12px 15px;
           font-size:13px; color:#374151; margin:18px 0; max-width:820px; }}
  .note b {{ color:var(--ink); }}
  .warn {{ background:#fffbf3; border-left:3px solid #b45309; padding:12px 15px;
           font-size:13px; color:#4a3a1e; margin:18px 0; max-width:820px; }}
  .warn b {{ color:var(--ink); }}
  .wrap {{ border:1px solid var(--line); border-radius:6px; background:#fff;
           max-width:900px; overflow-x:auto; }}
  .wrap svg {{ display:block; }}
  table {{ width:100%; border-collapse:collapse; margin:10px 0 6px; font-size:13px; max-width:560px; }}
  thead th {{ text-align:left; font-weight:640; font-size:11px; letter-spacing:.04em;
              text-transform:uppercase; color:var(--muted);
              border-bottom:1.5px solid var(--ink); padding:7px 9px; }}
  tbody td {{ padding:5px 9px; border-bottom:1px solid var(--line); }}
  tbody tr:hover {{ background:#fbfcfd; }}
  .num {{ text-align:right; font-variant-numeric:tabular-nums; }}
  .strong {{ font-weight:620; }}
  .sig {{ color:var(--neg); }}
  .kpi {{ display:flex; gap:30px; margin:18px 0 4px; flex-wrap:wrap; }}
  .kpi div span {{ display:block; font-size:11px; color:var(--muted);
                   text-transform:uppercase; letter-spacing:.05em; }}
  .big {{ font-size:26px; font-weight:620; letter-spacing:-.02em; }}
  footer {{ margin-top:34px; padding-top:14px; border-top:1px solid var(--line);
            font-size:12px; color:var(--muted); max-width:820px; }}
  code {{ font-size:12px; background:#f3f4f6; padding:1px 5px; border-radius:3px; }}
  pre {{ background:#f8f9fb; border:1px solid var(--line); border-radius:5px;
         padding:12px 14px; font-size:12px; overflow-x:auto; max-width:560px; }}
</style>
</head>
<body>

<h1>GPR and capital-flow volatility: emerging economies</h1>
<p class="sub">Pearson correlation per country &middot; monthly &middot; January 2000 &ndash; December 2023
&middot; 13 emerging markets, excluding China and Hungary</p>

<div class="note">
<b>x is <code>gpr_z</code>, y is <code>capital_flow_volatility</code>, both current month.</b>
Because <code>gpr_z</code> is built as (gpr &minus; country mean) / country standard deviation,
it is a strictly increasing linear transform of <code>gpr</code> <i>within</i> each country.
Pearson correlation is invariant to such transforms, so every number below is numerically
identical to the one obtained from raw <code>gpr</code>. The standardization only changes how
values are interpreted, not the correlation.
</div>

<div class="warn">
<b>China and Hungary are excluded, and that single change flips the headline result.</b>
In the 15-country sample those two countries carry the largest correlations (+0.410 and +0.342)
and together account for the entire pooled positive association. Removing them takes the pooled
r from +0.135 to {r_pool:+.3f} and the country-mean r from +0.026 to {mean_r:+.3f}. The
15-country table was therefore not robust: two observations out of fifteen were driving it.
</div>

<div class="kpi">
  <div><span>Countries</span><div class="big">{n_ctry}</div></div>
  <div><span>Observations</span><div class="big">{n_rows:,}</div></div>
  <div><span>Mean r</span><div class="big">{mean_r:+.3f}</div></div>
  <div><span>Median r</span><div class="big">{median_r:+.3f}</div></div>
  <div><span>Significant (5%)</span><div class="big">{n_sig}/{n_ctry}</div></div>
</div>

<div class="wrap">
{svg}
</div>

<h2>Correlation table</h2>
<p>Each row uses only the months in which both series are observed for that country, so the sample
size varies. <span class="sig">*</span> marks |t| &gt; 1.96 using the standard
t = r&radic;(n&minus;2)/(1&minus;r&sup2;) approximation.</p>
<table>
  <thead><tr><th>Country</th><th class="num">Months</th><th class="num">r</th></tr></thead>
  <tbody>
{rows_html()}
  </tbody>
</table>

<h2>What the pattern says</h2>
<p>{n_pos} of {n_ctry} countries have a positive correlation, but the spread runs from
{max(x["r"] for x in records):+.3f} to {min(x["r"] for x in records):+.3f}. The country-level
average is {mean_r:+.3f} and the median {median_r:+.3f}: with the two high-correlation economies
gone, the centre of the distribution is essentially zero and very slightly negative.</p>
<p>Only <b>Brazil</b> (+0.130), <b>Thailand</b> (&minus;0.143) and <b>Ukraine</b> (&minus;0.271)
clear the conventional threshold, and Brazil and Thailand only just, at |t| slightly above 2. The
three largest remaining coefficients disagree in sign, so there is no emerging-market pattern to
read off this table.</p>
<p>Read together with the pooled figures &mdash; {r_pool:+.3f} on the raw pool and
{r_within:+.4f} after removing country means &mdash; the per-country scatter is consistent with
there being <i>no</i> stable within-country link between geopolitical risk and capital-flow
volatility once China and Hungary are set aside.</p>

<h2>Ready-to-paste block</h2>
<pre>Country            Months       r
{markdown}</pre>

<h2>Method</h2>
<p>Data: <code>cleaned/replication_cleaned/country_month.csv</code>, rows with
<code>group == "Emerging"</code> and country not in {{China, Hungary}}. Months outside 2000-01 to
2023-12 are excluded, as are rows where either series is missing. Volatility values at or below
zero cannot be logged but are kept here because this table uses Pearson on levels, not on logs.
No controls, no lags, no detrending: these are raw contemporaneous associations.</p>
<p>The exclusion is a fragility check, not a preferred specification. China and Hungary were not
selected on any institutional criterion; they were removed because they are the two outliers that
generate the result.</p>

<footer>
Chart is hand-built SVG. Correlation is Pearson. Within-country figure is computed on
country-demeaned values of both series. Significance uses the t approximation and is indicative
only, since monthly volatility is serially correlated, which makes the effective sample smaller
than the month count.
</footer>

</body>
</html>
"""

OUT_HTML.write_text(page, encoding="utf-8")

print(f"wrote {OUT_HTML}")
print(f"wrote {OUT_SVG}")
print(f"countries={n_ctry} rows={n_rows:,} mean_r={mean_r:+.3f} "
      f"median_r={median_r:+.3f} positive={n_pos}/{n_ctry} significant={n_sig}")
print(f"pooled r={r_pool:+.4f}  within r={r_within:+.4f}")
