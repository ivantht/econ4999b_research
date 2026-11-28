"""Replication audit: the paper's Table 2 column 1 on the cleaned monthly panel.

Question: can the paper's positive, significant GPR coefficient in the
capital-flow-volatility equation be reproduced from
cleaned/replication_cleaned/country_month.csv?

The audit varies three things and reports the GPR coefficient in each cell:

  1. How capital-flow volatility is built from portfolio_inflow. The stored
     column needs three observed months; the paper's Table 1 reports a minimum
     of exactly zero, which suggests missing inflows are treated as zero.
  2. How GPR is standardized. The paper says "standardized by country".
  3. Whether country fixed effects are included.

Every other element is held fixed: the control set from equation (2), all
controls lagged one month, country-clustered standard errors.

Writes output/replication_scan.csv and output/replication_scan.html.
"""

import csv
import math
import os
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_export_reer_2sls as est

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PANEL = os.path.join(ROOT, "cleaned", "replication_cleaned", "country_month.csv")
OUT_CSV = os.path.join(ROOT, "output", "replication_scan.csv")
OUT_HTML = os.path.join(ROOT, "output", "replication_scan.html")

# Controls, in the paper's order, with the raw column each one comes from.
CONTROLS = [
    ("rate", "policy_rate", "Policy rate"),
    ("ln_ip", "industrial_production", "Real industrial production"),
    ("infl", "inflation", "Inflation"),
    ("ln_oil", "oil_price", "Oil price"),
    ("ln_vix", "vix", "VIX"),
    ("ln_gepu", "gepu", "Global EPU index"),
    ("fd", "financial_development", "Financial development"),
    ("cbi", "central_bank_independence", "Central bank independence"),
    ("debt", "public_debt_gdp", "Public debt/GDP"),
]
LOG_CONTROLS = {"ln_ip", "ln_oil", "ln_vix", "ln_gepu"}

PAPER = {
    "n_obs": 4779,
    "r2": 0.058,
    "gpr_coef": 0.867,
    "gpr_se": 0.382,
}


def to_float(text):
    value = (text or "").strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def safe_log(value):
    return math.log(value) if (value is not None and value > 0) else None


def month_index(label):
    year, month = map(int, label.split("-"))
    return year * 12 + month


def month_label(index):
    year, month = divmod(index - 1, 12)
    return f"{year:04d}-{month + 1:02d}"


def window_labels(index):
    """The paper's 3-month rolling window: current month and two prior months."""
    return [month_label(index + offset) for offset in (0, -1, -2)]


def load_raw():
    """All rows, oldest first. The year window is applied in prepare(), not here:
    the 3-month outcome window for an early row reaches back before 2000."""
    rows = []
    with open(PANEL, encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            month = row["date"][:7]
            rows.append(
                {
                    "iso": row["iso"].strip(),
                    "country": row["country"].strip(),
                    "group": row["group"].strip(),
                    "month": month,
                    "gpr_raw": to_float(row.get("gpr")),
                    "gpr_z_stored": to_float(row.get("gpr_z")),
                    "cfv_stored": to_float(row.get("capital_flow_volatility")),
                    "inflow": to_float(row.get("portfolio_inflow")),
                    **{key: to_float(row.get(source)) for key, source, _ in CONTROLS},
                }
            )
    rows.sort(key=lambda item: (item["iso"], item["month"]))
    return rows


def build_cfv(rows, mode, ddof=1):
    """Return {(iso, month): value} under one construction rule."""
    if mode == "stored":
        # Use the column as stored. Recomputing it from inflows cannot reproduce
        # the earliest months: the stored series was built from source data that
        # includes 1999, which this panel does not carry.
        return {
            (row["iso"], row["month"]): row["cfv_stored"]
            for row in rows
            if row["cfv_stored"] is not None
        }

    inflows = defaultdict(dict)
    for row in rows:
        inflows[row["iso"]][row["month"]] = row["inflow"]

    out = {}
    for iso, series in inflows.items():
        for month in series:
            values = [series.get(label) for label in window_labels(month_index(month))]
            observed = [value for value in values if value is not None]
            if mode == "zero_fill":
                filled = np.array([0.0 if v is None else v for v in values])
                out[(iso, month)] = float(np.std(filled, ddof=ddof))
            elif mode == "two_observed":
                if len(observed) < 2:
                    continue
                out[(iso, month)] = float(np.std(np.array(observed), ddof=ddof))
            else:
                raise ValueError(mode)
    return out


def prepare(rows, cfv_map, gpr_mode, year_from=2000, year_to=2023):
    """Attach the outcome, lagged controls, and the chosen GPR measure."""
    use_rows = []
    for row in rows:
        year = int(row["month"][:4])
        if not year_from <= year <= year_to:
            continue
        record = dict(row)
        record["cfv"] = cfv_map.get((row["iso"], row["month"]))
        use_rows.append(record)

    lookup = {(row["iso"], row["month"]): row for row in use_rows}
    for row in use_rows:
        previous = lookup.get((row["iso"], month_label(month_index(row["month"]) - 1)))
        for key, _, _ in CONTROLS:
            value = previous[key] if previous else None
            if key in LOG_CONTROLS and value is not None:
                value = safe_log(value)
            row[key + "_l1"] = value

    if gpr_mode == "by_country":
        grouped = defaultdict(list)
        for index, row in enumerate(use_rows):
            if row["gpr_raw"] is not None:
                grouped[row["iso"]].append(index)
        for indexes in grouped.values():
            values = np.array([use_rows[i]["gpr_raw"] for i in indexes], dtype=float)
            mean = values.mean()
            sd = values.std(ddof=1) if len(values) > 1 else 0.0
            for i in indexes:
                use_rows[i]["gpr_z"] = (use_rows[i]["gpr_raw"] - mean) / sd if sd > 0 else None
    elif gpr_mode == "pooled":
        values = np.array(
            [row["gpr_raw"] for row in use_rows if row["gpr_raw"] is not None], dtype=float
        )
        mean, sd = values.mean(), values.std(ddof=1)
        for row in use_rows:
            row["gpr_z"] = (row["gpr_raw"] - mean) / sd if row["gpr_raw"] is not None else None
    else:
        raise ValueError(gpr_mode)

    for row in use_rows:
        row.setdefault("gpr_z", None)
    return use_rows


def rhs_names(include_ip=True):
    names = ["gpr_z"] + [key + "_l1" for key, _, _ in CONTROLS]
    if not include_ip:
        names = [name for name in names if name != "ln_ip_l1"]
    return names


def demean(values, groups):
    totals = defaultdict(float)
    counts = defaultdict(int)
    for value, group in zip(values, groups):
        totals[group] += value
        counts[group] += 1
    return values - np.array([totals[group] / counts[group] for group in groups])


def fit(rows, rhs, fixed_effects=True):
    countries = sorted({row["country"] for row in rows})
    y = np.array([row["cfv"] for row in rows], dtype=float)

    if fixed_effects:
        matrix, names, _ = est.design_matrix(rows, rhs, countries)
    else:
        matrix = np.column_stack(
            [np.ones(len(rows), dtype=float)]
            + [np.array([row[name] for row in rows], dtype=float) for name in rhs]
        )
        names = ["const"] + list(rhs)

    beta = np.linalg.lstsq(matrix, y, rcond=None)[0]
    residual = y - matrix @ beta

    grouped = est.cluster_indices(rows)
    variance, _ = est.cluster_variance(matrix, residual, grouped, len(rows), matrix.shape[1])
    inference = est.inference(names, beta, variance, len(grouped))

    r2 = 1.0 - float(np.sum(residual**2)) / float(np.sum((y - y.mean()) ** 2))

    # Within R-squared: demean the outcome and the regressors by country.
    groups = [row["country"] for row in rows]
    y_within = demean(y, groups)
    if fixed_effects:
        regressors = matrix[:, 1 : 1 + len(rhs)]
    else:
        regressors = matrix[:, 1:]
    x_within = np.column_stack([demean(regressors[:, j], groups) for j in range(regressors.shape[1])])
    beta_within = np.linalg.lstsq(x_within, y_within, rcond=None)[0]
    residual_within = y_within - x_within @ beta_within
    within_r2 = 1.0 - float(np.sum(residual_within**2)) / float(np.sum(y_within**2))

    return {
        "n_obs": len(rows),
        "n_country": len(countries),
        "r2": r2,
        "within_r2": within_r2,
        "stat": inference["gpr_z"],
    }


def select(rows, rhs):
    needed = ["cfv"] + list(rhs)
    return [row for row in rows if all(row.get(name) is not None for name in needed)]


def scan(rows):
    records = []
    base_rhs = rhs_names()

    # 1. Construction audit, holding GPR by country and fixed effects on.
    constructions = [
        ("stored", "Three observed months (the stored column)", 1),
        ("zero_fill", "Missing inflow as zero, ddof = 1", 1),
        ("zero_fill", "Missing inflow as zero, ddof = 0", 0),
        ("two_observed", "At least two observed months", 1),
    ]
    for mode, label, ddof in constructions:
        cfv_map = build_cfv(rows, mode, ddof)
        prepared = prepare(rows, cfv_map, "by_country")
        sample = select(prepared, base_rhs)
        result = fit(sample, base_rhs, fixed_effects=True)
        values = np.array(list(cfv_map.values()), dtype=float)
        records.append(
            {
                "block": "construction",
                "variant": label,
                "n_values": len(values),
                "mean": float(values.mean()),
                "sd": float(values.std(ddof=1)),
                "minimum": float(values.min()),
                "maximum": float(values.max()),
                **result,
            }
        )

    # 2. Standardization x fixed effects grid.
    for mode, label in [("by_country", "By country"), ("pooled", "Pooled")]:
        cfv_map = build_cfv(rows, "stored", 1)
        prepared = prepare(rows, cfv_map, mode)
        sample = select(prepared, base_rhs)
        for fixed_effects in (True, False):
            result = fit(sample, base_rhs, fixed_effects=fixed_effects)
            records.append(
                {
                    "block": "grid",
                    "variant": f"GPR {label} + {'country FE' if fixed_effects else 'no FE'}",
                    "n_values": len(sample),
                    "mean": float("nan"),
                    "sd": float("nan"),
                    "minimum": float("nan"),
                    "maximum": float("nan"),
                    **result,
                }
            )

    # 3. Window scan, GPR by country and fixed effects on.
    for year_from, year_to in [(2000, 2023), (2002, 2023), (2000, 2021), (2000, 2019)]:
        cfv_map = build_cfv(rows, "stored", 1)
        prepared = prepare(rows, cfv_map, "by_country", year_from, year_to)
        sample = select(prepared, base_rhs)
        result = fit(sample, base_rhs, fixed_effects=True)
        records.append(
            {
                "block": "window",
                "variant": f"{year_from} to {year_to}",
                "n_values": len(sample),
                "mean": float("nan"),
                "sd": float("nan"),
                "minimum": float("nan"),
                "maximum": float("nan"),
                **result,
            }
        )

    # 4. Country coverage of the estimation sample.
    cfv_map = build_cfv(rows, "stored", 1)
    prepared = prepare(rows, cfv_map, "by_country")
    sample = select(prepared, base_rhs)
    used = {row["country"] for row in sample}
    all_countries = sorted({row["country"] for row in rows})
    coverage = {
        "used": sorted(used),
        "dropped": [name for name in all_countries if name not in used],
        "counts": {
            name: sum(1 for row in sample if row["country"] == name) for name in all_countries
        },
    }
    return records, coverage


def write_csv(records):
    fields = [
        "block",
        "variant",
        "n_obs",
        "n_country",
        "r2",
        "within_r2",
        "gpr_coef",
        "gpr_se",
        "gpr_p",
        "n_values",
        "mean",
        "sd",
        "minimum",
        "maximum",
    ]
    with open(OUT_CSV, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for record in records:
            stat = record["stat"]
            writer.writerow(
                {
                    "block": record["block"],
                    "variant": record["variant"],
                    "n_obs": record["n_obs"],
                    "n_country": record["n_country"],
                    "r2": f"{record['r2']:.6f}",
                    "within_r2": f"{record['within_r2']:.6f}",
                    "gpr_coef": f"{stat['coef']:.6f}",
                    "gpr_se": f"{stat['se']:.6f}",
                    "gpr_p": f"{stat['p']:.6f}",
                    "n_values": record["n_values"],
                    "mean": "" if math.isnan(record["mean"]) else f"{record['mean']:.6f}",
                    "sd": "" if math.isnan(record["sd"]) else f"{record['sd']:.6f}",
                    "minimum": "" if math.isnan(record["minimum"]) else f"{record['minimum']:.6f}",
                    "maximum": "" if math.isnan(record["maximum"]) else f"{record['maximum']:.6f}",
                }
            )


def write_html(records, coverage):
    from html import escape

    construction = [r for r in records if r["block"] == "construction"]
    grid = [r for r in records if r["block"] == "grid"]
    windows = [r for r in records if r["block"] == "window"]

    def sig(p):
        return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""

    def cell(record):
        stat = record["stat"]
        cls = "pos" if stat["coef"] > 0 else "neg"
        return (
            f'<td class="{cls}">{stat["coef"]:+.3f}{sig(stat["p"])}'
            f'<span class="se">({stat["se"]:.3f})</span>'
            f'<span class="se">p = {stat["p"]:.3f}</span></td>'
        )

    construction_rows = []
    for record in construction:
        construction_rows.append(
            "<tr>"
            f"<th>{escape(record['variant'])}</th>"
            f"<td>{record['n_values']:,}</td>"
            f"<td>{record['mean']:.2f}</td>"
            f"<td>{record['sd']:.2f}</td>"
            f"<td>{record['minimum']:.3f}</td>"
            f"<td>{record['maximum']:.1f}</td>"
            f"<td>{record['n_obs']:,}</td>"
            f"<td>{record['r2']:.3f}</td>"
            f"<td>{record['within_r2']:.4f}</td>"
            f"{cell(record)}"
            "</tr>"
        )
    construction_rows.append(
        "<tr class='paper'>"
        "<th>Paper, Table 2 column 1</th>"
        "<td>&mdash;</td><td>7.22</td><td>19.62</td><td>0.000</td><td>528.4</td>"
        f"<td>{PAPER['n_obs']:,}</td><td>&mdash;</td><td>{PAPER['r2']:.3f}</td>"
        f"<td class=\"pos\">{PAPER['gpr_coef']:+.3f}**"
        f"<span class=\"se\">({PAPER['gpr_se']:.3f})</span></td>"
        "</tr>"
    )

    grid_rows = []
    for record in grid:
        grid_rows.append(
            "<tr>"
            f"<th>{escape(record['variant'])}</th>"
            f"<td>{record['n_obs']:,}</td>"
            f"<td>{record['n_country']}</td>"
            f"<td>{record['r2']:.3f}</td>"
            f"<td>{record['within_r2']:.3f}</td>"
            f"{cell(record)}"
            "</tr>"
        )

    window_rows = []
    for record in windows:
        window_rows.append(
            "<tr>"
            f"<th>{escape(record['variant'])}</th>"
            f"<td>{record['n_obs']:,}</td>"
            f"<td>{record['n_country']}</td>"
            f"{cell(record)}"
            "</tr>"
        )

    dropped_rows = "".join(
        f"<tr><th>{escape(name)}</th><td>{coverage['counts'][name]}</td></tr>"
        for name in coverage["dropped"]
    )

    negative = [r for r in records if r["stat"]["coef"] < 0]
    positive = [r for r in records if r["stat"]["coef"] > 0]
    positive_labels = ", ".join(escape(r["variant"]) for r in positive) or "none"

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Replication audit: Table 2 column 1</title>
<style>
:root {{ --ink:#1c2530; --muted:#5b6b7b; --line:#d3dde5; --pale:#f6f9fb; --orange:#c2571f; }}
body {{ font: 16px/1.55 Georgia, "Times New Roman", serif; color: var(--ink);
  max-width: 1120px; margin: 2.5em auto; padding: 0 1.2em; }}
h1 {{ font-size: 1.55em; margin: 0 0 .2em; line-height: 1.25; }}
h2 {{ font-size: 1.1em; margin: 2em 0 .5em; padding-bottom: .3em;
  border-bottom: 2px solid var(--line); }}
.sub {{ color: var(--muted); margin: 0 0 1.5em; }}
.note {{ background: var(--pale); border-left: 4px solid var(--orange);
  padding: .9em 1.1em; margin: 1.2em 0; font-size: .93em; }}
.note p {{ margin: .35em 0; }}
table {{ border-collapse: collapse; width: 100%; margin: .8em 0 1.2em; font-size: .84em; }}
th, td {{ border-bottom: 1px solid var(--line); padding: .45em .5em; text-align: right;
  vertical-align: top; font-variant-numeric: tabular-nums; }}
thead th {{ background: var(--pale); text-align: center; font-size: .95em; line-height: 1.3; }}
tbody th {{ text-align: left; font-weight: normal; width: 20em; }}
td.pos {{ color: #1f5c8a; font-weight: 700; }}
td.neg {{ color: #b04a1c; font-weight: 700; }}
td .se {{ display: block; font-weight: 400; color: var(--muted); font-size: .92em; }}
tr.paper td, tr.paper th {{ background: #fff5da; }}
.verdict {{ background: #fdf1ec; border-left: 4px solid var(--orange);
  padding: 1em 1.2em; margin: 1.4em 0; }}
.verdict p {{ margin: .4em 0; }}
code {{ font-size: .92em; background: var(--pale); padding: .05em .3em; }}
ul {{ margin: .5em 0; }} li {{ margin: .4em 0; }}
</style>
</head>
<body>
<h1>Replication audit: capital-flow volatility on GPR</h1>
<p class="sub">Paper Table 2, column 1, estimated on
<code>cleaned/replication_cleaned/country_month.csv</code></p>

<div class="note">
<p><strong>Target.</strong> The paper reports a GPR coefficient of
+{PAPER['gpr_coef']:.3f} ({PAPER['gpr_se']:.3f}), significant at 5 percent, with
N = {PAPER['n_obs']:,} and R-squared = {PAPER['r2']:.3f}.</p>
<p><strong>Specification held fixed.</strong> Equation (2): the outcome on
standardized GPR plus the nine controls, every control lagged one month, country
fixed effects, and standard errors clustered by country.</p>
<p><strong>What varies.</strong> Only the three choices below: how the outcome is
built, how GPR is standardized, and whether fixed effects are included.</p>
</div>

<h2>1. How the outcome is built</h2>
<p>The panel stores capital-flow volatility as the standard deviation of
portfolio inflows over the current and two prior months, requiring three observed
months. Inflows are blank in 1,813 of 8,352 rows, and 17 of 29 countries have at
least one gap. The paper's Table 1 reports a minimum of exactly zero, which no
observed inflow series produces, so it likely fills gaps with zero.</p>
<table>
<thead><tr>
<th></th><th>Values</th><th>Mean</th><th>SD</th><th>Min</th><th>Max</th>
<th>Est. N</th><th>R&sup2;</th><th>Within R&sup2;</th><th>GPR coefficient</th>
</tr></thead>
<tbody>{''.join(construction_rows)}</tbody>
</table>
<p class="sub">GPR by country and country fixed effects in every row above.</p>

<h2>2. Standardization and fixed effects</h2>
<p>The paper says GPR is "standardized by country". Standardizing within country
sets each country's mean to zero, so adding country fixed effects on top removes
almost nothing further. That makes these four cells close to only two distinct
estimates, and it is why the sign does not respond to the fixed-effect choice on
its own.</p>
<table>
<thead><tr>
<th></th><th>Est. N</th><th>Countries</th><th>R&sup2;</th><th>Within R&sup2;</th>
<th>GPR coefficient</th>
</tr></thead>
<tbody>{''.join(grid_rows)}</tbody>
</table>

<h2>3. Window</h2>
<p>Narrowing the window is the only lever left that changes the sample without
changing the specification. None of these windows reaches the paper's
N = {PAPER['n_obs']:,}.</p>
<table>
<thead><tr><th></th><th>Est. N</th><th>Countries</th><th>GPR coefficient</th></tr></thead>
<tbody>{''.join(window_rows)}</tbody>
</table>

<h2>4. Countries the baseline cannot use</h2>
<p>Five emerging economies contribute no observations at all, because their
industrial production series is empty in this panel. The paper's baseline is
stated over 29 countries, but this panel supports at most 24.</p>
<table>
<thead><tr><th>Country</th><th>Observations in the estimation sample</th></tr></thead>
<tbody>{dropped_rows}</tbody>
</table>

<h2>Verdict</h2>
<div class="verdict">
<p><strong>The GPR coefficient is negative in {len(negative)} of {len(records)}
specifications.</strong> The only positive cells are: {positive_labels}.</p>
<p>The sign is therefore not a matter of the outcome's construction, the
standardization choice, the window, or the fixed-effect choice taken
individually. It turns positive only when GPR is pooled-standardized and country
fixed effects are dropped at the same time, which sets aside two parts of the
paper's stated method.</p>
<p>That cell is also the wrong comparison for a different reason: with no fixed
effects, the coefficient is identified off cross-country differences in GPR
levels, which is precisely the variation that fixed effects exist to remove.</p>
</div>

<p class="sub">Generated by <code>output/run_replication_scan.py</code>. Numbers in
<code>output/replication_scan.csv</code>. *** p&lt;0.01, ** p&lt;0.05, * p&lt;0.10.</p>
</body>
</html>
"""
    with open(OUT_HTML, "w", encoding="utf-8") as handle:
        handle.write(html)


def main():
    rows = load_raw()
    records, coverage = scan(rows)
    write_csv(records)
    write_html(records, coverage)

    print(f"Wrote {OUT_CSV}")
    print(f"Wrote {OUT_HTML}")
    print()
    for block in ("construction", "grid", "window"):
        print(f"== {block} ==")
        for record in records:
            if record["block"] != block:
                continue
            stat = record["stat"]
            print(
                f"  {record['variant']:48s} N={record['n_obs']:5d} "
                f"R2w={record['within_r2']:.4f} GPR={stat['coef']:+7.3f} "
                f"({stat['se']:.3f}) p={stat['p']:.3f}"
            )
    print()
    print(f"countries used: {len(coverage['used'])}")
    print(f"countries dropped: {', '.join(coverage['dropped'])}")


if __name__ == "__main__":
    main()
