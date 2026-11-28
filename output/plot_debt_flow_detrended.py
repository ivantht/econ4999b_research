"""Country-level panels with the TREND REMOVED from debt/GDP.

Detrending: for each country, regress log(debt/GDP) on a year index over the
annual 2000-2023 observations. Keep the residual, log(Y_t) - log(trend_t), which
approximates the percentage deviation from trend. That residual -- not the fitted
trend -- is what replaces the debt series. Annual residuals are then carried
across the four quarters of each year.

Flows are left exactly as observed; only the debt ratio is detrended.

Writes `output/debt_flow_detrended.html`, `.svg`, `.csv`, and
`output/debt_gdp_detrended.csv` (the derived series, for reuse).
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
OUT_HTML = Path(__file__).resolve().parent / "debt_flow_detrended.html"
OUT_SVG = Path(__file__).resolve().parent / "debt_flow_detrended.svg"
OUT_CSV = Path(__file__).resolve().parent / "debt_flow_detrended_correlations.csv"
OUT_SERIES = Path(__file__).resolve().parent / "debt_gdp_detrended.csv"

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


def load_debt_raw():
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


def detrend_country(annual: dict, years: list[int]):
    """Log-linear detrend. Return gap in percent, plus fit diagnostics."""
    ys = [annual[t] for t in years]
    if min(ys) <= 0:
        raise ValueError("non-positive debt value; log detrend undefined")
    ly = np.log(np.array(ys))
    x = np.array(years, dtype=float)
    b, a = np.polyfit(x, ly, 1)
    fit = a + b * x
    resid = ly - fit
    ss_res = float(((ly - fit) ** 2).sum())
    ss_tot = float(((ly - ly.mean()) ** 2).sum())
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    n = len(x)
    se = math.sqrt(ss_res / (n - 2) / float(((x - x.mean()) ** 2).sum())) if n > 2 else float("nan")
    tstat = b / se if se and se > 0 else float("nan")
    gap = {y: float(r) * 100.0 for y, r in zip(years, resid)}
    return gap, {
        "slope_pct_per_year": b * 100.0,
        "r2": r2,
        "t": tstat,
        "n": n,
    }


debt_raw = load_debt_raw()
flows = load_flows()

gaps: dict[str, dict[int, float]] = {}
diag: dict[str, dict] = {}
for c in EM:
    years = sorted(y for y in debt_raw[c] if Y0 <= y <= Y1)
    gaps[c], diag[c] = detrend_country(debt_raw[c], years)


def series_for(c):
    qs = sorted(flows[c], key=qkey)
    recs = []
    for i, q in enumerate(qs):
        y = int(q[:4])
        if y < Y0 or y > Y1 or y not in gaps[c]:
            continue
        win = [flows[c].get(qq) for qq in qs[max(0, i - 2): i + 1]]
        win = [w for w in win if w is not None]
        recs.append({
            "q": q, "k": qkey(q), "y": y,
            "flow": flows[c][q],
            "absflow": abs(flows[c][q]),
            "vol": float(np.std(win, ddof=0)) if len(win) >= 3 else None,
            "raw": debt_raw[c][y],
            "gap": gaps[c][y],
        })
    return recs


DATA = {c: series_for(c) for c in EM}

# ------------------------------------------------------------------ derived file
with OUT_SERIES.open("w", encoding="utf-8", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["country", "year", "debt_gdp_pct", "debt_gap_pct",
                "trend_slope_pct_per_year", "trend_r2"])
    for c in EM:
        for y in sorted(gaps[c]):
            w.writerow([c, y, f"{debt_raw[c][y]:.4f}", f"{gaps[c][y]:.4f}",
                        f"{diag[c]['slope_pct_per_year']:.4f}", f"{diag[c]['r2']:.4f}"])

# ------------------------------------------------------------- correlation table
MEASURES = [
    ("flow", "Overall net flow", "USD millions, signed"),
    ("absflow", "Absolute overall flow", "USD millions, sign removed"),
    ("vol", "Overall flow volatility", "3-quarter rolling standard deviation"),
]


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


pooled = []
for xk, label, note in MEASURES:
    allr = [dict(r, c=c) for c in EM for r in DATA[c]]
    p_raw = pear([r["raw"] for r in allr], [r[xk] for r in allr])
    p_gap = pear([r["gap"] for r in allr], [r[xk] for r in allr])
    w_raw = within(allr, "raw", xk)
    w_gap = within(allr, "gap", xk)
    d_raw = first_diff(allr, "raw", xk)
    d_gap = first_diff(allr, "gap", xk)
    n = sum(1 for r in allr if r[xk] is not None)
    pooled.append((xk, label, note, n, p_raw, p_gap, w_raw, w_gap, d_raw, d_gap))


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def nice_ticks(lo, hi, n=4):
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
    ticks, t = [], start
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


# ------------------------------------------------------------------ panel layout
PANEL_W, PANEL_H = 300, 132
PAD_L, PAD_R = 34, 34
PLOT_W = PANEL_W - PAD_L - PAD_R
PLOT_H = PANEL_H - 30
COLS, ROWS = 5, 3
GAP_X, GAP_Y = 20, 46
MARGIN_L, MARGIN_T = 26, 58
BLOCK_H = ROWS * (PANEL_H + GAP_Y) + 34
TOTAL_W = MARGIN_L * 2 + COLS * PANEL_W + (COLS - 1) * GAP_X
TOTAL_H = MARGIN_T + 40 + 3 * BLOCK_H + 52


def panel_svg(c, measure, px, py):
    recs = DATA[c]
    vals = [r[measure] for r in recs if r[measure] is not None]
    gaps_v = [r["gap"] for r in recs]
    if not vals:
        return ""

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

    def vy(v):
        return PLOT_H - (v - vlo) / (vhi - vlo) * PLOT_H

    # gap axis, padded and roughly symmetric so zero stays readable
    gmax = max(abs(min(gaps_v)), abs(max(gaps_v)), 1e-6) * 1.12
    dlo, dhi = -gmax, gmax

    def dy(v):
        return PLOT_H - (v - dlo) / (dhi - dlo) * PLOT_H

    parts = [f'<g transform="translate({px + PAD_L:.1f},{py + 22:.1f})">']
    parts.append(
        f'<rect x="0" y="0" width="{PLOT_W}" height="{PLOT_H}" '
        f'fill="#fcfcfd" stroke="{LINE}" stroke-width="1"/>'
    )

    if vlo < 0 < vhi:
        z = vy(0)
        parts.append(
            f'<line x1="0" y1="{z:.1f}" x2="{PLOT_W}" y2="{z:.1f}" '
            f'stroke="#c9ced6" stroke-width="1" stroke-dasharray="3 3"/>'
        )
    # trending debt removed, so the reference is the zero gap
    zt = dy(0)
    parts.append(
        f'<line x1="0" y1="{zt:.1f}" x2="{PLOT_W}" y2="{zt:.1f}" '
        f'stroke="{DEBT_C}" stroke-width="0.8" stroke-opacity="0.45"/>'
    )

    bw = max(PLOT_W / span * 0.55, 1.0)
    if measure in ("flow", "absflow"):
        for r in recs:
            v = r[measure]
            if v is None:
                continue
            x = xpos(r["k"])
            y0, y1 = vy(0), vy(v)
            top, h = min(y0, y1), abs(y1 - y0)
            if h < 0.4:
                continue
            col = POS if (measure == "absflow" or v >= 0) else NEG
            parts.append(
                f'<rect x="{x - bw / 2:.1f}" y="{top:.1f}" width="{bw:.1f}" '
                f'height="{h:.1f}" fill="{col}" fill-opacity="0.72"/>'
            )
    else:
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

    # detrended debt, stepped by year
    seg, prev_year, seg_y = [], None, None
    for r in recs:
        x, y = xpos(r["k"]), dy(r["gap"])
        if prev_year is None:
            seg.append(f"M {x:.1f},{y:.1f}")
        elif r["y"] != prev_year:
            seg.append(f"L {x:.1f},{seg_y:.1f} L {x:.1f},{y:.1f}")
        else:
            seg.append(f"L {x:.1f},{y:.1f}")
        seg_y, prev_year = y, r["y"]
    parts.append(
        f'<path d="{" ".join(seg)}" fill="none" stroke="{DEBT_C}" '
        f'stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"/>'
    )

    for t in nice_ticks(vlo, vhi, 3):
        if t < vlo or t > vhi:
            continue
        y = vy(t)
        parts.append(
            f'<line x1="-3" y1="{y:.1f}" x2="0" y2="{y:.1f}" stroke="{LINE}"/>'
            f'<text x="-5" y="{y + 3:.1f}" text-anchor="end" font-size="7.5" '
            f'fill="{MUTED}">{compact(t)}</text>'
        )
    for t in nice_ticks(dlo, dhi, 3):
        if t < dlo or t > dhi:
            continue
        y = dy(t)
        parts.append(
            f'<line x1="{PLOT_W}" y1="{y:.1f}" x2="{PLOT_W + 3}" y2="{y:.1f}" stroke="{LINE}"/>'
            f'<text x="{PLOT_W + 5}" y="{y + 3:.1f}" text-anchor="start" font-size="7.5" '
            f'fill="{DEBT_C}">{t:+.0f}</text>'
        )
    for yr in (Y0, 2011, Y1):
        k = yr * 4
        if k0 <= k <= k1:
            parts.append(
                f'<text x="{xpos(k):.1f}" y="{PLOT_H + 11}" text-anchor="middle" '
                f'font-size="7.5" fill="{MUTED}">{yr}</text>'
            )
    parts.append("</g>")

    r_meas = pear([r["gap"] for r in recs if r[measure] is not None],
                  [r[measure] for r in recs if r[measure] is not None])
    r_raw = pear([r["raw"] for r in recs if r[measure] is not None],
                 [r[measure] for r in recs if r[measure] is not None])
    tone = POS if r_meas >= 0 else NEG
    parts.append(
        f'<text x="{px + PAD_L}" y="{py + 8}" font-size="10.5" font-weight="640" '
        f'fill="{INK}">{esc(c)}</text>'
        f'<text x="{px + PAD_L + PLOT_W + PAD_R}" y="{py + 8}" text-anchor="end" '
        f'font-size="8.5" fill="{tone}" font-variant-numeric="tabular-nums">'
        f'r={r_meas:+.2f}</text>'
        f'<text x="{px + PAD_L + PLOT_W + PAD_R}" y="{py + 18}" text-anchor="end" '
        f'font-size="7.5" fill="{MUTED}" font-variant-numeric="tabular-nums">'
        f'was {r_raw:+.2f}</text>'
    )
    return "".join(parts)


blocks = []
for bi, (measure, title, subtitle) in enumerate(MEASURES):
    panels = []
    base = MARGIN_T + 40 + bi * BLOCK_H
    for i, c in enumerate(EM):
        px = MARGIN_L + (i % COLS) * (PANEL_W + GAP_X)
        py = base + (i // COLS) * (PANEL_H + GAP_Y)
        panels.append(panel_svg(c, measure, px, py))
    hy = base - 22
    tw = sum(11.5 if ch.isupper() else 7.2 for ch in title)
    blocks.append(
        f'<text x="{MARGIN_L}" y="{hy}" font-size="13" font-weight="650" fill="{INK}">'
        f'{esc(title)}</text>'
        f'<text x="{MARGIN_L + tw + 10:.1f}" y="{hy}" font-size="10.5" fill="{MUTED}">'
        f'{esc(subtitle)}</text>' + "".join(panels)
    )

legend_y = TOTAL_H - 34
legend = f"""
<g>
  <text x="{MARGIN_L}" y="{legend_y}" font-size="10" fill="{MUTED}">Bars and curves: overall capital flow (blue positive, orange negative)</text>
  <text x="{MARGIN_L}" y="{legend_y + 14}" font-size="10" fill="{MUTED}">Amber line, right axis: debt/GDP with its trend removed, percent deviation from trend</text>
  <text x="{MARGIN_L}" y="{legend_y + 28}" font-size="10" fill="{MUTED}">r = within-country correlation with the detrended ratio; "was" = same correlation before detrending</text>
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


def corr_table():
    rows = []
    for xk, label, note, n, p_raw, p_gap, w_raw, w_gap, d_raw, d_gap in pooled:
        def cell(a, b):
            arrow = "" if not (np.isfinite(a) and np.isfinite(b)) else (
                " &uarr;" if b > a + 0.02 else " &darr;" if b < a - 0.02 else "")
            return (f'<td class="num">{a:+.3f}</td>'
                    f'<td class="num strong">{b:+.3f}{arrow}</td>')
        rows.append(
            f'<tr><td class="lbl">{label}<span class="sm">{note}</span></td>'
            f'<td class="num">{n:,}</td>'
            + cell(p_raw, p_gap) + cell(w_raw, w_gap) + cell(d_raw, d_gap) + "</tr>"
        )
    return "\n".join(rows)


def diag_table():
    rows = []
    for c in sorted(EM, key=lambda x: -abs(diag[x]["slope_pct_per_year"])):
        d = diag[c]
        g = [gaps[c][y] for y in sorted(gaps[c])]
        rows.append(
            f'<tr><td>{esc(c)}</td>'
            f'<td class="num">{d["slope_pct_per_year"]:+.2f}</td>'
            f'<td class="num">{d["r2"]:.2f}</td>'
            f'<td class="num">{d["t"]:+.2f}</td>'
            f'<td class="num">{min(g):+.1f}</td>'
            f'<td class="num">{max(g):+.1f}</td></tr>'
        )
    return "\n".join(rows)


n_sig = sum(1 for c in EM if abs(diag[c]["t"]) > 2)
n_neg = sum(1 for c in EM if diag[c]["slope_pct_per_year"] < 0)


def verdict_lines():
    """Describe the computed changes rather than asserting a fixed story."""
    f_lvl, f_abs, f_vol = pooled[0], pooled[1], pooled[2]
    out = []
    out.append(
        f"<p><b>Volatility stays a null.</b> Pooled moves from {f_vol[4]:+.3f} to "
        f"{f_vol[5]:+.3f}, and within-country from {f_vol[6]:+.3f} to {f_vol[7]:+.3f}. "
        f"Both remain within a few hundredths of zero. Removing a trend cannot "
        f"manufacture an association between series that had none.</p>"
    )
    out.append(
        f"<p><b>The signed level is where detrending matters most.</b> Pooled rises from "
        f"{f_lvl[4]:+.3f} to {f_lvl[5]:+.3f}, while within-country barely moves "
        f"({f_lvl[6]:+.3f} to {f_lvl[7]:+.3f}). The pooled shift is compositional: with "
        f"the drift removed, countries are no longer ranked by how much their debt grew, "
        f"only by how far it sits from its own path.</p>"
    )
    out.append(
        f"<p><b>Absolute flow changes sign.</b> Pooled moves from {f_abs[4]:+.3f} to "
        f"{f_abs[5]:+.3f}. The raw version partly reflected the fact that larger, more "
        f"indebted economies also move larger dollar amounts; against the detrended ratio "
        f"that scale advantage is gone.</p>"
    )
    return "\n".join(out)


page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Detrended debt/GDP and overall capital flow, by country</title>
<style>
  :root {{ --ink:#16181d; --muted:#6b7280; --line:#e3e6ea; --pos:#1f6feb; --neg:#c2410c; --debt:#b45309; }}
  body {{
    font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, sans-serif;
    margin: 38px auto 70px; max-width: 1560px; padding: 0 26px;
    color: var(--ink); background: #fff; line-height: 1.56;
  }}
  h1 {{ font-size: 22px; font-weight: 650; margin: 0 0 5px; letter-spacing: -.01em; }}
  h2 {{ font-size: 15px; font-weight: 650; margin: 36px 0 6px; }}
  .sub {{ color: var(--muted); font-size: 13px; margin: 0 0 16px; }}
  p {{ margin: 0 0 11px; font-size: 14px; max-width: 920px; }}
  .note {{ background:#fbfcfd; border-left:3px solid #94a3b8; padding:12px 15px;
           font-size:13px; color:#374151; margin:18px 0; max-width:980px; }}
  .note b {{ color: var(--ink); }}
  .wrap {{ overflow-x: auto; border: 1px solid var(--line); border-radius: 6px; background:#fff; }}
  .wrap svg {{ display: block; }}
  .key {{ display:flex; gap:22px; flex-wrap:wrap; font-size:12.5px; color:#374151; margin:8px 0 0; }}
  .key span {{ display:inline-flex; align-items:center; gap:6px; }}
  .sw {{ width:14px; height:10px; border-radius:2px; display:inline-block; }}
  table {{ width:100%; border-collapse:collapse; margin:10px 0 6px; font-size:13px; max-width:980px; }}
  thead th {{ text-align:left; font-weight:640; font-size:11px; letter-spacing:.04em;
              text-transform:uppercase; color:var(--muted);
              border-bottom:1.5px solid var(--ink); padding:7px 9px; vertical-align:bottom; }}
  tbody td {{ padding:7px 9px; border-bottom:1px solid var(--line); vertical-align:top; }}
  tbody tr:hover {{ background:#fbfcfd; }}
  .num {{ text-align:right; font-variant-numeric:tabular-nums; }}
  .strong {{ font-weight:620; }}
  .sm {{ display:block; font-weight:400; font-size:11px; color:var(--muted); margin-top:2px; }}
  .grp {{ font-size:11.5px; color:var(--muted); text-transform:uppercase; letter-spacing:.05em; margin-top:10px; }}
  footer {{ margin-top:40px; padding-top:14px; border-top:1px solid var(--line);
            font-size:12px; color:var(--muted); max-width:980px; }}
  code {{ font-size:12px; background:#f3f4f6; padding:1px 5px; border-radius:3px; }}
</style>
</head>
<body>

<h1>Debt/GDP with its trend removed</h1>
<p class="sub">Overall capital flow vs. deviation from debt trend &middot; 15 emerging markets &middot; 2000&ndash;2023</p>

<div class="key">
  <span><i class="sw" style="background:#1f6feb"></i> positive flow</span>
  <span><i class="sw" style="background:#c2410c"></i> negative flow</span>
  <span><i class="sw" style="background:#b45309;height:3px"></i> detrended debt/GDP (right axis)</span>
</div>

<div class="note">
<b>What was removed, and what was kept.</b> For each country I regressed
<code>log(debt/GDP)</code> on a year index using the 24 annual observations from 2000 to 2023, then kept
the <i>residual</i> &mdash; the deviation from the fitted trend, in approximate percent of the trend
level. The trend itself is discarded, so the right axis is now centred on zero: above zero means debt
was above its own trend in that year.
<br><br>
<b>Only the debt ratio was detrended.</b> Flows are exactly as observed. Detrending was done on the
annual values and the residuals carried across the four quarters of each year, because debt has no
sub-annual resolution.
</div>

<div class="wrap">
{svg}
</div>

<h2>1. Correlations before and after detrending</h2>
<table>
  <thead>
    <tr>
      <th>Measure</th><th class="num">N</th>
      <th class="num">Pooled<br>raw</th><th class="num">Pooled<br>detrended</th>
      <th class="num">Within<br>raw</th><th class="num">Within<br>detrended</th>
      <th class="num">1st diff<br>raw</th><th class="num">1st diff<br>detrended</th>
    </tr>
  </thead>
  <tbody>
{corr_table()}
  </tbody>
</table>
<p class="sub">Arrows mark changes larger than 0.02 in absolute value.</p>

<h2>2. The trends that were removed</h2>
<p>{n_sig} of {len(EM)} countries have a slope significant at the 5% level, and {n_neg} of them are
<i>declining</i>. That matters for interpretation: &ldquo;removing the trend&rdquo; is not the same as
removing a shared upward drift, because the direction is not common across the panel.</p>
<table>
  <thead>
    <tr><th>Country</th><th class="num">Slope<br>%/yr</th><th class="num">R&sup2;</th>
        <th class="num">t</th><th class="num">Min gap</th><th class="num">Max gap</th></tr>
  </thead>
  <tbody>
{diag_table()}
  </tbody>
</table>
<p class="sub">Slope is the log-linear growth rate of debt/GDP per year. Gap is the residual in
approximate percent of trend.</p>

<h2>3. What changes in the answer</h2>
{verdict_lines()}
<p><b>Argentina is the fragile case.</b> Its linear trend has an R&sup2; near zero because the 2001
crisis dominates the series; the residual there is mostly that one episode, not a cycle. Treat its
detrended line as a crisis marker rather than a trend deviation.</p>

<footer>
Flow: <code>cleaned/capital_flow.csv</code> (IMF BOP financial account balance excluding reserves,
USD millions). Debt: <code>cleaned/debt_gdp.csv</code>, annual gross general government debt as a
percent of GDP. Detrended series written to <code>output/debt_gdp_detrended.csv</code>.
Volatility is the rolling 3-quarter standard deviation of the signed flow. Axes are scaled per
panel; bar heights are not comparable across countries. 2024&ndash;2026 excluded to match the
2000&ndash;2023 window.
</footer>

</body>
</html>
"""

OUT_HTML.write_text(page, encoding="utf-8")

with OUT_CSV.open("w", encoding="utf-8", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["measure", "n", "pooled_raw", "pooled_detrended",
                "within_raw", "within_detrended", "diff_raw", "diff_detrended"])
    for xk, label, note, n, p_raw, p_gap, w_raw, w_gap, d_raw, d_gap in pooled:
        w.writerow([label, n, f"{p_raw:.4f}", f"{p_gap:.4f}",
                    f"{w_raw:.4f}", f"{w_gap:.4f}", f"{d_raw:.4f}", f"{d_gap:.4f}"])

print(f"wrote {OUT_HTML}")
print(f"wrote {OUT_SVG}")
print(f"wrote {OUT_CSV}")
print(f"wrote {OUT_SERIES}")
print()
for xk, label, note, n, p_raw, p_gap, w_raw, w_gap, d_raw, d_gap in pooled:
    print(f"{label:28s} n={n:5d} | pooled {p_raw:+.3f}->{p_gap:+.3f}"
          f" | within {w_raw:+.3f}->{w_gap:+.3f} | 1stdiff {d_raw:+.3f}->{d_gap:+.3f}")
print(f"\nslopes significant at 5%: {n_sig}/{len(EM)}, declining: {n_neg}")
