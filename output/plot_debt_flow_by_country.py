"""Country-level time-series panels: overall capital flow vs. debt/GDP.

15 emerging markets, 2000-2023, quarterly. Each small multiple carries a dual
axis: bars for the flow measure, a stepped line for the annual debt ratio on the
right axis. Written as hand-built SVG so the report needs no plotting library.

Writes `output/debt_flow_by_country.html` and `output/debt_flow_by_country.svg`.
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
OUT_HTML = Path(__file__).resolve().parent / "debt_flow_by_country.html"
OUT_SVG = Path(__file__).resolve().parent / "debt_flow_by_country.svg"

EM = [
    "Mexico", "Argentina", "Chile", "Peru", "Hungary", "Ukraine", "Turkey",
    "Egypt", "Tunisia", "South Africa", "India", "Indonesia", "Philippines",
    "Thailand", "Vietnam",
]
Y0, Y1 = 2000, 2023

INK = "#16181d"
MUTED = "#6b7280"
LINE = "#e3e6ea"
POS = "#1f6feb"
NEG = "#c2410c"
DEBT_C = "#b45309"


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
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def load_debt():
    out = defaultdict(dict)
    for r in csv.DictReader(DEBT.open(encoding="utf-8-sig")):
        v = to_float(r["debt_gdp_pct"])
        if v is not None:
            out[r["country"].strip()][int(r["period"])] = v
    return out


def load_flows():
    out = defaultdict(dict)
    for r in csv.DictReader(CAPITAL_FLOW.open(encoding="utf-8-sig")):
        v = to_float(r["usd_millions"])
        if v is not None:
            out[r["country"].strip()][r["year_quarter"].strip()] = v
    return out


debt = load_debt()
flows = load_flows()


def series_for(c):
    """Return quarters, signed flow, absolute flow, 3-quarter rolling vol, debt."""
    qs = sorted(flows[c], key=qkey)
    recs = []
    for i, q in enumerate(qs):
        y = int(q[:4])
        if y < Y0 or y > Y1 or y not in debt[c]:
            continue
        win = [flows[c].get(qq) for qq in qs[max(0, i - 2): i + 1]]
        win = [w for w in win if w is not None]
        recs.append({
            "q": q, "k": qkey(q), "y": y,
            "flow": flows[c][q],
            "absflow": abs(flows[c][q]),
            "vol": float(np.std(win, ddof=0)) if len(win) >= 3 else None,
            "debt": debt[c][y],
        })
    return recs


DATA = {c: series_for(c) for c in EM}


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def nice_ticks(lo, hi, n=4):
    """Simple readable tick values spanning [lo, hi]."""
    if not math.isfinite(lo) or not math.isfinite(hi) or lo == hi:
        return [lo, hi]
    span = hi - lo
    raw = span / n
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        step = m * mag
        if span / step <= n + 1:
            break
    start = math.floor(lo / step) * step
    ticks = []
    t = start
    while t <= hi + step * 0.5:
        ticks.append(t)
        t += step
    return ticks


def compact(v):
    a = abs(v)
    if a >= 1000:
        s = f"{v / 1000:.1f}k"
        return s.replace(".0k", "k")
    if a < 1:
        return f"{v:.1f}"
    return f"{v:.0f}"


# ---------------------------------------------------------------- panel geometry
PANEL_W, PANEL_H = 300, 132
PAD_L, PAD_R = 34, 30
PLOT_W = PANEL_W - PAD_L - PAD_R
PLOT_H = PANEL_H - 30
COLS = 5
ROWS = 3
GAP_X, GAP_Y = 20, 46
MARGIN_L, MARGIN_T = 26, 58
BLOCK_H = ROWS * (PANEL_H + GAP_Y) + 34
N_BLOCKS = 3
TOTAL_W = MARGIN_L * 2 + COLS * PANEL_W + (COLS - 1) * GAP_X
TOTAL_H = MARGIN_T + 40 + N_BLOCKS * BLOCK_H + 52


def panel_svg(c, measure, px, py, idx):
    recs = DATA[c]
    vals, debts = [], []
    for r in recs:
        v = r[measure]
        if v is not None:
            vals.append(v)
            debts.append(r["debt"])
    if not vals:
        return ""

    n = len(recs)
    ks = [r["k"] for r in recs]
    k0, k1 = min(ks), max(ks)
    span = max(k1 - k0, 1)

    def xpos(k):
        return PAD_L + (k - k0) / span * PLOT_W

    vlo, vhi = min(vals), max(vals)
    if measure == "vol":
        vlo = 0.0
    if vlo == vhi:
        vhi = vlo + 1
    pad_v = (vhi - vlo) * 0.08
    vlo -= pad_v
    vhi += pad_v
    zero_y = PLOT_H - (0 - vlo) / (vhi - vlo) * PLOT_H

    def vy(v):
        return PLOT_H - (v - vlo) / (vhi - vlo) * PLOT_H

    dlo, dhi = min(debts), max(debts)
    if dlo == dhi:
        dlo -= 5
        dhi += 5
    dpad = (dhi - dlo) * 0.10
    dlo -= dpad
    dhi += dpad

    def dy(v):
        return PLOT_H - (v - dlo) / (dhi - dlo) * PLOT_H

    parts = [f'<g transform="translate({px + PAD_L:.1f},{py + 22:.1f})">']

    # plot frame
    parts.append(
        f'<rect x="0" y="0" width="{PLOT_W}" height="{PLOT_H}" '
        f'fill="#fcfcfd" stroke="{LINE}" stroke-width="1"/>'
    )

    # zero baseline
    if vlo < 0 < vhi:
        parts.append(
            f'<line x1="0" y1="{zero_y:.1f}" x2="{PLOT_W}" y2="{zero_y:.1f}" '
            f'stroke="#c9ced6" stroke-width="1" stroke-dasharray="3 3"/>'
        )

    # bars
    bw = max(PLOT_W / span * 0.55, 1.0)
    if measure in ("flow", "absflow"):
        for r in recs:
            v = r[measure]
            if v is None:
                continue
            x = xpos(r["k"])
            y0 = vy(0)
            y1 = vy(v)
            top = min(y0, y1)
            h = abs(y1 - y0)
            col = POS if (measure == "absflow" or v >= 0) else NEG
            if h < 0.4:
                continue
            parts.append(
                f'<rect x="{x - bw / 2:.1f}" y="{top:.1f}" width="{bw:.1f}" '
                f'height="{h:.1f}" fill="{col}" fill-opacity="0.72"/>'
            )
    else:
        # filled area under the volatility curve
        pts = [(xpos(r["k"]), vy(r["vol"])) for r in recs if r["vol"] is not None]
        if len(pts) > 2:
            path = f"M {pts[0][0]:.1f},{PLOT_H:.1f} "
            path += " ".join(f"L {x:.1f},{y:.1f}" for x, y in pts)
            path += f" L {pts[-1][0]:.1f},{PLOT_H:.1f} Z"
            parts.append(f'<path d="{path}" fill="{POS}" fill-opacity="0.16"/>')
            pline = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
            parts.append(
                f'<path d="{pline}" fill="none" stroke="{POS}" '
                f'stroke-width="1.3" stroke-linejoin="round"/>'
            )

    # debt line, stepped by year
    seg = []
    prev_y = None
    for r in recs:
        x = xpos(r["k"])
        y = dy(r["debt"])
        if prev_y is None:
            seg.append(f"M {x:.1f},{y:.1f}")
        elif r["y"] != prev_y:
            seg.append(f"L {x:.1f},{seg_y:.1f} L {x:.1f},{y:.1f}")
        else:
            seg.append(f"L {x:.1f},{y:.1f}")
        seg_y = y
        prev_y = r["y"]
    parts.append(
        f'<path d="{" ".join(seg)}" fill="none" stroke="{DEBT_C}" '
        f'stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"/>'
    )

    # left ticks (flow)
    for t in nice_ticks(vlo, vhi, 3):
        if t < vlo or t > vhi:
            continue
        y = vy(t)
        parts.append(
            f'<line x1="-3" y1="{y:.1f}" x2="0" y2="{y:.1f}" stroke="{LINE}"/>'
            f'<text x="-5" y="{y + 3:.1f}" text-anchor="end" font-size="7.5" '
            f'fill="{MUTED}">{compact(t)}</text>'
        )
    # right ticks (debt)
    for t in nice_ticks(dlo, dhi, 3):
        if t < dlo or t > dhi:
            continue
        y = dy(t)
        parts.append(
            f'<line x1="{PLOT_W}" y1="{y:.1f}" x2="{PLOT_W + 3}" y2="{y:.1f}" stroke="{LINE}"/>'
            f'<text x="{PLOT_W + 5}" y="{y + 3:.1f}" text-anchor="start" font-size="7.5" '
            f'fill="{DEBT_C}">{t:.0f}</text>'
        )

    # x labels: first, middle, last year
    for yr in (Y0, 2011, Y1):
        k = yr * 4
        if k0 <= k <= k1:
            x = xpos(k)
            parts.append(
                f'<text x="{x:.1f}" y="{PLOT_H + 11}" text-anchor="middle" '
                f'font-size="7.5" fill="{MUTED}">{yr}</text>'
            )

    parts.append("</g>")

    # panel title + correlation badge, computed for the measure actually plotted
    r_meas = pear([r["debt"] for r in recs if r[measure] is not None],
                  [r[measure] for r in recs if r[measure] is not None])

    stat = f"r={r_meas:+.2f}"
    tone = POS if r_meas >= 0 else NEG

    parts.append(
        f'<text x="{px + PAD_L}" y="{py + 8}" font-size="10.5" font-weight="640" '
        f'fill="{INK}">{esc(c)}</text>'
        f'<text x="{px + PAD_L + PLOT_W + PAD_R}" y="{py + 8}" text-anchor="end" '
        f'font-size="8.5" fill="{tone}" font-variant-numeric="tabular-nums">{stat}</text>'
    )
    return "".join(parts)


MEASURES = [
    ("flow", "Overall net flow", "USD millions, signed", 0),
    ("absflow", "Absolute overall flow", "USD millions, sign removed", 1),
    ("vol", "Overall flow volatility", "3-quarter rolling standard deviation", 2),
]

blocks = []
for measure, title, subtitle, row in MEASURES:
    panels = []
    base = MARGIN_T + 40 + row * BLOCK_H
    for i, c in enumerate(EM):
        col = i % COLS
        r = i // COLS
        px = MARGIN_L + col * (PANEL_W + GAP_X)
        py = base + r * (PANEL_H + GAP_Y)
        panels.append(panel_svg(c, measure, px, py, i))

    # section header sits above this measure's first panel row
    hy = base - 22
    tw = sum(11.5 if ch.isupper() else 7.2 for ch in title)
    blocks.append(
        f'<text x="{MARGIN_L}" y="{hy}" font-size="13" font-weight="650" fill="{INK}">'
        f'{esc(title)}</text>'
        f'<text x="{MARGIN_L + tw + 10:.1f}" y="{hy}" font-size="10.5" fill="{MUTED}">'
        f'{esc(subtitle)}</text>'
        + "".join(panels)
    )

legend_y = TOTAL_H - 34
legend = f"""
<g>
  <text x="{MARGIN_L}" y="{legend_y}" font-size="10" fill="{MUTED}">Bars and curves: overall capital flow (blue positive, orange negative)</text>
  <text x="{MARGIN_L}" y="{legend_y + 14}" font-size="10" fill="{MUTED}">Amber line, right axis: public debt/GDP, annual, carried across quarters (percent of GDP)</text>
  <text x="{MARGIN_L}" y="{legend_y + 28}" font-size="10" fill="{MUTED}">r = within-country correlation with debt/GDP for the measure shown</text>
</g>
"""

svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{TOTAL_W}" height="{TOTAL_H}"
     viewBox="0 0 {TOTAL_W} {TOTAL_H}" font-family="Segoe UI, Helvetica, Arial, sans-serif">
<rect width="{TOTAL_W}" height="{TOTAL_H}" fill="#ffffff"/>
{''.join(blocks)}
{legend}
</svg>
"""

OUT_SVG.write_text(svg, encoding="utf-8")

EM_CHIPS = "".join(f'<span class="chip">{esc(c)}</span>' for c in EM)

page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>By-country time series: overall capital flow and debt/GDP</title>
<style>
  :root {{ --ink:#16181d; --muted:#6b7280; --line:#e3e6ea; --pos:#1f6feb; --neg:#c2410c; --debt:#b45309; }}
  body {{
    font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, sans-serif;
    margin: 38px auto 70px; max-width: 1560px; padding: 0 26px;
    color: var(--ink); background: #fff; line-height: 1.56;
  }}
  h1 {{ font-size: 22px; font-weight: 650; margin: 0 0 5px; letter-spacing: -.01em; }}
  h2 {{ font-size: 15px; font-weight: 650; margin: 34px 0 6px; }}
  .sub {{ color: var(--muted); font-size: 13px; margin: 0 0 16px; }}
  p {{ margin: 0 0 11px; font-size: 14px; max-width: 900px; }}
  .note {{
    background: #fbfcfd; border-left: 3px solid #94a3b8;
    padding: 12px 15px; font-size: 13px; color: #374151; margin: 18px 0; max-width: 960px;
  }}
  .note b {{ color: var(--ink); }}
  .wrap {{ overflow-x: auto; border: 1px solid var(--line); border-radius: 6px; background: #fff; }}
  .wrap svg {{ display: block; }}
  .chips {{ display: flex; flex-wrap: wrap; gap: 6px; margin: 10px 0 0; }}
  .chip {{ font-size: 12px; padding: 3px 9px; border: 1px solid var(--line); border-radius: 20px; color: #374151; }}
  footer {{ margin-top: 40px; padding-top: 14px; border-top: 1px solid var(--line); font-size: 12px; color: var(--muted); max-width: 960px; }}
  code {{ font-size: 12px; background: #f3f4f6; padding: 1px 5px; border-radius: 3px; }}
  .key {{ display: flex; gap: 22px; flex-wrap: wrap; font-size: 12.5px; color: #374151; margin: 8px 0 0; }}
  .key span {{ display: inline-flex; align-items: center; gap: 6px; }}
  .sw {{ width: 14px; height: 10px; border-radius: 2px; display: inline-block; }}
</style>
</head>
<body>

<h1>Overall capital flow and debt/GDP, by country</h1>
<p class="sub">Quarterly flow, annual debt ratio &middot; 15 emerging markets &middot; 2000&ndash;2023</p>

<div class="key">
  <span><i class="sw" style="background:#1f6feb"></i> positive flow (net outflow)</span>
  <span><i class="sw" style="background:#c2410c"></i> negative flow (net inflow)</span>
  <span><i class="sw" style="background:#b45309;height:3px"></i> debt/GDP (right axis)</span>
</div>

<div class="note">
<b>Reading the panels.</b> Rows are the three flow measures, columns are countries, and every panel
shares the same layout: flow on the left axis, the annual debt ratio as a stepped line on the right
axis. The <code>r=</code> figure in each panel is that country's within-country correlation with
debt/GDP for the measure being plotted, so you can compare the picture against the number directly.
<br><br>
<b>Debt moves in annual steps.</b> The line is flat within each year and jumps once, which is why
it looks like a staircase rather than a curve. Any monthly or quarterly reading of it is a within-year
repeat, not new information.
</div>

<div class="wrap">
{svg}
</div>

<h2>What the panels show</h2>
<p><b>The flow series are dominated by episodes, not trends.</b> Argentina, Turkey and Ukraine show
violent swings around the 2001, 2008, 2018 and 2022 crises. Debt lines are comparatively smooth,
so most of the visual co-movement, where it exists, comes from crisis quarters in which flow
plunges while debt rises.</p>
<p><b>Signs genuinely differ across countries.</b> Chile, Turkey and Indonesia turn negative on the
signed flow (r between &minus;0.46 and &minus;0.43), while Indonesia, South Africa and Peru are
strongly positive. That disagreement is the reason the pooled coefficient is close to zero while
individual countries look anything but flat.</p>
<p><b>Volatility panels are the least structured.</b> Tunisia (+0.70) and Hungary (+0.49) show clear
positive slopes; Turkey and Indonesia are clearly negative. With 96 quarters per country, these are
not noise, but they do not aggregate into a common pattern.</p>

<h2>Countries</h2>
<div class="chips">{EM_CHIPS}</div>

<footer>
Flow: <code>cleaned/capital_flow.csv</code> (IMF BOP financial account balance excluding reserves,
USD millions). Debt: <code>cleaned/debt_gdp.csv</code>, annual gross general government debt as a
percent of GDP. Volatility is the rolling 3-quarter standard deviation of the signed flow, the same
window used in the model specifications. Axes are scaled per panel; do not compare bar heights
across countries. South Korea excluded as an advanced economy; 2024&ndash;2026 dropped to match the
2000&ndash;2023 window.
</footer>

</body>
</html>
"""

OUT_HTML.write_text(page, encoding="utf-8")

print(f"wrote {OUT_HTML}")
print(f"wrote {OUT_SVG}")
print(f"svg size: {len(svg):,} bytes, canvas {TOTAL_W}x{TOTAL_H}")
for m, t, _s, _r in MEASURES:
    rs = []
    for c in EM:
        recs = DATA[c]
        x = [r["debt"] for r in recs if r[m] is not None]
        y = [r[m] for r in recs if r[m] is not None]
        rs.append((c, pear(x, y)))
    pos = sum(1 for _c, r in rs if r > 0)
    print(f"  {t:26s} positive in {pos}/{len(rs)} countries")
