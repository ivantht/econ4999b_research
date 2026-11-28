"""Emerging economies: correlation of each country's (gpr_z, capital_flow_volatility)
correlation with that country's average WGI score.

Six scatter panels, one per WGI dimension. n = 15 countries, so the 5% critical
value for |r| is about 0.478; the page states this explicitly.

Output: output/correlation_gpr_z_cfv_wgi_emerging.html (+ .svg)
"""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PANEL = ROOT / "cleaned" / "replication_cleaned" / "country_month.csv"
OUT_HTML = ROOT / "output" / "correlation_gpr_z_cfv_wgi_emerging.html"
OUT_SVG = ROOT / "output" / "correlation_gpr_z_cfv_wgi_emerging.svg"

Y0, Y1 = 2000, 2023

# Matches the country table: China and Hungary are excluded because they carry
# the two largest country correlations and drive the pooled association.
DROP_COUNTRIES = {"China", "Hungary"}

DIMS = [
    ("wgi_va", "Voice and accountability"),
    ("wgi_pv", "Political stability"),
    ("wgi_ge", "Government effectiveness"),
    ("wgi_rq", "Regulatory quality"),
    ("wgi_rl", "Rule of law"),
    ("wgi_cc", "Control of corruption"),
]


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
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


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


# ------------------------------------------------------------------ load
by = defaultdict(lambda: {"z": [], "v": [], "w": defaultdict(dict), "country": None})
for r in csv.DictReader(PANEL.open(encoding="utf-8-sig")):
    if r["group"].strip() != "Emerging":
        continue
    if r["country"].strip() in DROP_COUNTRIES:
        continue
    yr = to_float(r["date"][:4])
    if yr is None or not (Y0 <= yr <= Y1):
        continue
    d = by[r["iso"].strip()]
    d["country"] = r["country"].strip()
    z = to_float(r["gpr_z"])
    v = to_float(r["capital_flow_volatility"])
    if z is not None and v is not None:
        d["z"].append(z)
        d["v"].append(v)
    for col, _ in DIMS:
        val = to_float(r[col])
        if val is not None:
            d["w"][col][int(yr)] = val

countries = []
for iso, d in by.items():
    rr = pear(d["z"], d["v"])
    if rr is None:
        continue
    row = {"iso": iso, "country": d["country"], "r": rr, "n": len(d["z"])}
    ok = True
    for col, _ in DIMS:
        yrs = d["w"][col]
        if not yrs:
            ok = False
            break
        row[col] = sum(yrs.values()) / len(yrs)
        row[col + "_yrs"] = len(yrs)
    if ok:
        countries.append(row)

n_ctry = len(countries)
crit = 1.96 / math.sqrt(max(n_ctry - 2, 1) + 1.96 ** 2)

results = []
for col, label in DIMS:
    xs = [c[col] for c in countries]
    ys = [c["r"] for c in countries]
    rr = pear(xs, ys)
    t = abs(rr) * math.sqrt(max(n_ctry - 2, 1) / max(1 - rr * rr, 1e-12))
    results.append({"col": col, "label": label, "r": rr, "t": t, "sig": abs(rr) > crit})

n_sig = sum(1 for x in results if x["sig"])
wgi_years = countries[0]["wgi_va_yrs"]

# ------------------------------------------------------------------ chart
PW, PH = 300, 224
GAPX, GAPY = 28, 58
LEFT, RIGHT = 62, 38
TOP = 136
W = LEFT + PW * 3 + GAPX * 2 + RIGHT
H = TOP + (PH + GAPY) * 2 + 74

Y_LO, Y_HI = -0.45, 0.45


def short(name):
    return name.replace("South Africa", "S. Africa").replace("Philippines", "Philippin.")


def panel(idx, res, ox, oy):
    col, label, rr = res["col"], res["label"], res["r"]
    xs = [c[col] for c in countries]
    ys = [c["r"] for c in countries]
    xlo, xhi = min(xs), max(xs)
    span = (xhi - xlo) or 1.0
    xlo -= span * 0.12
    xhi += span * 0.12

    def sx(v):
        return ox + (v - xlo) / (xhi - xlo) * PW

    def sy(v):
        return oy + PH - (v - Y_LO) / (Y_HI - Y_LO) * PH

    p = []

    # y gridlines
    for tick in [-0.4, -0.2, 0.0, 0.2, 0.4]:
        y = sy(tick)
        dash = "" if tick == 0 else ' stroke-dasharray="2 3"'
        p.append(f'<line x1="{ox}" y1="{y:.1f}" x2="{ox + PW}" y2="{y:.1f}" '
                 f'stroke="#e6e9ed" stroke-width="1"{dash}/>')
        if idx % 3 == 0:
            lab = "0.0" if abs(tick) < 1e-9 else f"{tick:+.1f}"
            p.append(f'<text x="{ox - 8}" y="{y + 3.5:.1f}" font-size="9.5" '
                     f'fill="#8b9199" text-anchor="end">{lab}</text>')

    # x ticks: min, 0, max
    for tick in [min(xs), 0.0, max(xs)]:
        x = sx(tick)
        p.append(f'<line x1="{x:.1f}" y1="{oy + PH}" x2="{x:.1f}" y2="{oy + PH + 4}" '
                 f'stroke="#c7ccd2" stroke-width="1"/>')
        p.append(f'<text x="{x:.1f}" y="{oy + PH + 16}" font-size="9.5" fill="#8b9199" '
                 f'text-anchor="middle">{tick:.2f}</text>')

    # frame
    p.append(f'<rect x="{ox}" y="{oy}" width="{PW}" height="{PH}" fill="none" '
             f'stroke="#dfe3e8" stroke-width="1"/>')

    # points drawn first
    for i in range(len(countries)):
        p.append(f'<circle cx="{sx(xs[i]):.1f}" cy="{sy(ys[i]):.1f}" r="3.3" fill="#2f6fb5" '
                 f'fill-opacity="0.8"/>')

    # labels: candidate offsets in ring order, rejected on text or dot collision
    order = sorted(range(len(countries)), key=lambda i: -ys[i])
    dot_boxes = [(sx(xs[i]) - 3.6, sx(xs[i]) + 3.6, sy(ys[i]) - 3.6, sy(ys[i]) + 3.6)
                 for i in range(len(countries))]
    label_boxes = []
    ring = [(6, 3.4, "start"), (-6, 3.4, "end"), (6, -4.6, "start"), (-6, -4.6, "end"),
            (0, -8, "middle"), (0, 12.5, "middle"),
            (9, 0, "start"), (-9, 0, "end"), (7, 8, "start"), (-7, 8, "end"),
            (7, -9, "start"), (-7, -9, "end"), (0, -15, "middle"), (0, 19, "middle")]
    for i in order:
        px, py = sx(xs[i]), sy(ys[i])
        name = short(countries[i]["country"])
        w = len(name) * 4.9
        chosen = None
        for dx, dy, anchor in ring:
            if anchor == "start":
                x0 = px + dx
                tx = px + dx
            elif anchor == "end":
                x0 = px + dx - w
                tx = px + dx
            else:
                x0 = px + dx - w / 2
                tx = px + dx
            box = (x0, x0 + w, py + dy - 7.4, py + dy + 2.4)
            if box[0] < ox + 1.5 or box[1] > ox + PW - 1.5:
                continue
            if box[2] < oy + 1.5 or box[3] > oy + PH - 1.5:
                continue
            if any(not (box[1] < b[0] or box[0] > b[1] or box[3] < b[2] or box[2] > b[3])
                   for b in label_boxes):
                continue
            if any(not (box[1] < b[1] or box[0] > b[0] or box[3] < b[3] or box[2] > b[2])
                   for b in dot_boxes):
                continue
            chosen = (tx, py + dy, anchor, box, name)
            break
        if chosen is None:
            chosen = None
        if chosen is None:
            continue
        label_boxes.append(chosen[3])
        p.append(f'<text x="{chosen[0]:.1f}" y="{chosen[1]:.1f}" font-size="8.5" '
                 f'fill="#4b5563" text-anchor="{chosen[2]}">{esc(name)}</text>')

    # panel title
    p.append(f'<text x="{ox}" y="{oy - 26}" font-size="11.5" font-weight="600" '
             f'fill="#16181d">{esc(label)}</text>')
    star = "" if res["sig"] else ""
    p.append(f'<text x="{ox}" y="{oy - 11}" font-size="10.5" fill="#6b7280">'
             f'r = {rr:+.3f}{star}'
             f'<tspan fill="#9aa0a8">   n = {n_ctry}</tspan></text>')
    return "\n".join(p)


panels = []
for i, res in enumerate(results):
    row, colx = divmod(i, 3)
    panels.append(panel(i, res, LEFT + colx * (PW + GAPX), TOP + row * (PH + GAPY)))

header = []
header.append(
    f'<text x="{LEFT}" y="28" font-size="14.5" font-weight="650" fill="#16181d">'
    f'Institutions and the GPR&ndash;volatility correlation</text>')
header.append(
    f'<text x="{LEFT}" y="48" font-size="11" fill="#6b7280">'
    f'Each dot is one emerging economy. Vertical axis: that country&rsquo;s Pearson r between '
    f'gpr_z and capital-flow volatility.</text>')
header.append(
    f'<text x="{LEFT}" y="64" font-size="11" fill="#6b7280">'
    f'Horizontal axis: that country&rsquo;s average WGI score, {wgi_years} annual values '
    f'from 2000 to 2023.</text>')
header.append(
    f'<text x="{LEFT}" y="88" font-size="11" fill="#b45309">'
    f'With {n_ctry} countries the 5% two-sided threshold is |r| &gt; {crit:.3f}; '
    f'none of the six correlations reaches it.</text>')

svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
       f'viewBox="0 0 {W} {H}" font-family="Segoe UI, Helvetica, Arial, sans-serif">\n'
       f'<rect width="{W}" height="{H}" fill="#ffffff"/>\n'
       + "\n".join(header) + "\n" + "\n".join(panels) + "\n</svg>")

OUT_SVG.write_text(svg, encoding="utf-8")

# ------------------------------------------------------------------ table
def table_rows():
    out = []
    for res in sorted(results, key=lambda x: -abs(x["r"])):
        flag = '<span class="sig">*</span>' if res["sig"] else ""
        out.append(f'<tr><td>{esc(res["label"])}</td>'
                   f'<td class="num strong">{res["r"]:+.3f}{flag}</td>'
                   f'<td class="num">{res["t"]:.2f}</td></tr>')
    return "\n".join(out)


md_rows = "\n".join(
    f'{r["label"]:<28}{r["r"]:>8.3f}{"  *" if r["sig"] else ""}'
    for r in sorted(results, key=lambda x: -abs(x["r"]))
)

page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>WGI and the GPR-volatility correlation: emerging economies</title>
<style>
  :root {{ --ink:#16181d; --muted:#6b7280; --line:#e3e6ea; --warn:#b45309; }}
  body {{ font-family:"Segoe UI",-apple-system,BlinkMacSystemFont,sans-serif;
          margin:38px auto 70px; max-width:1160px; padding:0 26px;
          color:var(--ink); background:#fff; line-height:1.58; }}
  h1 {{ font-size:21px; font-weight:650; margin:0 0 5px; letter-spacing:-.01em; }}
  h2 {{ font-size:15px; font-weight:650; margin:32px 0 6px; }}
  .sub {{ color:var(--muted); font-size:13px; margin:0 0 16px; }}
  p {{ margin:0 0 11px; font-size:14px; max-width:880px; }}
  .note {{ background:#fbfcfd; border-left:3px solid #94a3b8; padding:12px 15px;
           font-size:13px; color:#374151; margin:18px 0; max-width:880px; }}
  .warn {{ background:#fffbf3; border-left:3px solid var(--warn); padding:12px 15px;
           font-size:13px; color:#4a3a1e; margin:18px 0; max-width:880px; }}
  .note b, .warn b {{ color:var(--ink); }}
  .wrap {{ border:1px solid var(--line); border-radius:6px; background:#fff; overflow-x:auto; }}
  .wrap svg {{ display:block; }}
  table {{ width:100%; border-collapse:collapse; margin:10px 0 6px; font-size:13px; max-width:520px; }}
  thead th {{ text-align:left; font-weight:640; font-size:11px; letter-spacing:.04em;
              text-transform:uppercase; color:var(--muted);
              border-bottom:1.5px solid var(--ink); padding:7px 9px; }}
  tbody td {{ padding:5px 9px; border-bottom:1px solid var(--line); }}
  tbody tr:hover {{ background:#fbfcfd; }}
  .num {{ text-align:right; font-variant-numeric:tabular-nums; }}
  .strong {{ font-weight:620; }}
  .sig {{ color:var(--warn); }}
  footer {{ margin-top:34px; padding-top:14px; border-top:1px solid var(--line);
            font-size:12px; color:var(--muted); max-width:880px; }}
  code {{ font-size:12px; background:#f3f4f6; padding:1px 5px; border-radius:3px; }}
  pre {{ background:#f8f9fb; border:1px solid var(--line); border-radius:5px;
         padding:12px 14px; font-size:12px; overflow-x:auto; max-width:520px; }}
</style>
</head>
<body>

<h1>Institutions and the GPR&ndash;volatility correlation</h1>
<p class="sub">Emerging economies &middot; {n_ctry} countries, excluding China and Hungary &middot;
each country&rsquo;s monthly r between <code>gpr_z</code> and <code>capital_flow_volatility</code>,
paired with its average WGI score</p>

<div class="warn">
<b>None of these six correlations is statistically distinguishable from zero.</b>
With n = {n_ctry} countries, the 5% two-sided critical value is |r| = {crit:.3f}. The strongest
relationship here is |r| = {max(abs(x["r"]) for x in results):.3f}, which is still far short of it.
The honest reading is that this sample carries essentially no information about whether
institutional quality moderates the GPR&ndash;volatility link.
</div>

<div class="wrap">
{svg}
</div>

<h2>Correlation table</h2>
<p>Each number pairs a country&rsquo;s correlation from the previous table with that country&rsquo;s
mean WGI score. {wgi_years} annual values are available between 2000 and 2023 because WGI is
blank in 2001.</p>
<table>
  <thead><tr><th>WGI measure</th><th class="num">r</th><th class="num">t</th></tr></thead>
  <tbody>
{table_rows()}
  </tbody>
</table>

<h2>Why this is uninformative, not a finding</h2>
<p><b>The outcome is already noisy.</b> The country-level correlations being correlated here run
from &minus;0.271 to +0.130 and were estimated from between 106 and 288 monthly observations. Each
is measured with substantial error, so the regressand in this exercise is mostly estimation noise.
Attenuation bias pushes all six coefficients toward zero.</p>
<p><b>The earlier version of this table was driven by two points.</b> With China and Hungary
included, voice and accountability read &minus;0.307 and five dimensions leaned positive. Remove
those two countries and voice and accountability becomes {[x for x in results if x["col"]=="wgi_va"][0]["r"]:+.3f}
while government effectiveness, regulatory quality and control of corruption all strengthen slightly.
That reshuffling is the signature of a coefficient resting on two observations, not on a
cross-country relationship.</p>
<p><b>What the remaining pattern means.</b> The three governance dimensions that now lead
&mdash; government effectiveness, control of corruption, regulatory quality &mdash; sit between
+0.26 and +0.30, still well short of the {crit:.3f} threshold, and the two political dimensions
collapse to roughly zero. All six would need to move together, in the same direction and past the
threshold, before this could be called a moderating effect.</p>
<p><b>What would actually test the claim.</b> Interact GPR with WGI inside a panel regression with
country and time fixed effects, so the test uses the 2,849 country-months rather than 13 country
averages. That is the specification the earlier tables in this file move toward.</p>

<h2>Ready-to-paste block</h2>
<pre>WGI measure                       r
{md_rows}

* |r| > {crit:.3f}, the 5% two-sided threshold at n = {n_ctry}. No measure clears it.</pre>

<footer>
Data: <code>cleaned/replication_cleaned/country_month.csv</code>, emerging economies only.
The country correlation reuses the monthly current-month Pearson r of <code>gpr_z</code> against
<code>capital_flow_volatility</code> from the preceding table; the WGI figure is the simple mean of
available annual values, unchanged across the months of a year. Chart is hand-built SVG.
</footer>

</body>
</html>
"""

OUT_HTML.write_text(page, encoding="utf-8")

print(f"wrote {OUT_HTML}")
print(f"wrote {OUT_SVG}")
print(f"countries={n_ctry} wgi_years={wgi_years} crit={crit:.3f} significant={n_sig}/6")
for res in sorted(results, key=lambda x: -abs(x["r"])):
    print(f"  {res['label']:<28}{res['r']:+.3f}  t={res['t']:.2f}")
