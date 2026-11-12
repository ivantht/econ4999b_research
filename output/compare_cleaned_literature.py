"""Compare cleaned exchange-rate series with the literature-review panel.

The panel is the public-source replication in
econ4999b_literature_review/replication/output/panel.csv. Overlap is the nine
emerging economies that appear in both, for 2000-01 through 2023-12.
"""

import csv
import math
import os
from collections import defaultdict
from html import escape

import numpy as np

import run_export_reer_2sls as est


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PANEL = os.path.join(
    ROOT, "econ4999b_literature_review", "replication", "output", "panel.csv"
)
OUTPUT = os.path.join(ROOT, "output")

SHARED = {
    "Chile": "CL",
    "Hungary": "HU",
    "India": "IN",
    "Indonesia": "ID",
    "Mexico": "MX",
    "Philippines": "PH",
    "South Africa": "ZA",
    "Thailand": "TH",
    "Turkey": "TR",
}
ISO_TO_NAME = {iso: name for name, iso in SHARED.items()}
LITERATURE_ONLY = ["Brazil", "China", "Colombia", "Malaysia", "Poland", "Ukraine"]
CLEANED_ONLY = ["Argentina", "Peru"]


def num(text):
    text = (text or "").strip()
    if not text:
        return None
    return float(text)


def load_panel():
    rows = []
    with open(PANEL, encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            month = row["date"][:7]
            if not ("2000-01" <= month <= "2023-12"):
                continue
            if row["iso"] not in ISO_TO_NAME:
                continue
            rows.append(row)
    return rows


def index_panel(rows, column):
    out = {}
    for row in rows:
        value = num(row.get(column))
        if value is None:
            continue
        out[(row["iso"], row["date"][:7])] = value
    return out


def annual_from_monthly(rows, column, how):
    grouped = defaultdict(list)
    for row in rows:
        value = num(row.get(column))
        if value is None:
            continue
        grouped[(row["iso"], int(row["date"][:4]))].append((row["date"][:7], value))
    out = {}
    for key, pairs in grouped.items():
        if how == "mean":
            out[key] = float(np.mean([value for _, value in pairs]))
        elif how == "december":
            december = [value for month, value in pairs if month.endswith("-12")]
            if december:
                out[key] = december[-1]
    return out


def unique_month(rows, column):
    found = {}
    for row in rows:
        value = num(row.get(column))
        if value is None:
            continue
        found.setdefault(row["date"][:7], value)
    return found


def correlation(left, right):
    left = np.asarray(left, dtype=float)
    right = np.asarray(right, dtype=float)
    if len(left) < 3 or float(left.std()) == 0 or float(right.std()) == 0:
        return None
    return float(np.corrcoef(left, right)[0, 1])


def measure(pairs):
    if not pairs:
        return None
    left = np.array([a for a, _ in pairs], dtype=float)
    right = np.array([b for _, b in pairs], dtype=float)
    return {
        "n": len(pairs),
        "corr": correlation(left, right),
        "mean_cleaned": float(left.mean()),
        "mean_literature": float(right.mean()),
        "mean_abs_gap": float(np.mean(np.abs(left - right))),
    }


def judgment(stats, preset=None):
    if preset:
        return preset
    if stats is None or stats["corr"] is None:
        return "not comparable"
    corr = stats["corr"]
    rel = stats["mean_abs_gap"] / abs(stats["mean_literature"])
    ratio = stats["mean_cleaned"] / stats["mean_literature"]
    if corr >= 0.995 and rel < 0.02:
        return "same measure"
    if corr >= 0.98 and (ratio > 5 or ratio < 0.2):
        return "same concept, different units"
    if corr >= 0.95:
        return "close, not the same vintage"
    return "different path"


def paired_country_month(cleaned_by_country, literature):
    pairs = []
    for name, iso in SHARED.items():
        for month, value in cleaned_by_country.get(name, {}).items():
            if not ("2000-01" <= month <= "2023-12"):
                continue
            other = literature.get((iso, month))
            if other is None or value is None:
                continue
            pairs.append((value, other))
    return pairs


def paired_annual(cleaned, literature):
    pairs = []
    for name, iso in SHARED.items():
        for year, value in cleaned.get(name, {}).items():
            if not (2000 <= year <= 2023) or value is None:
                continue
            other = literature.get((iso, year))
            if other is None:
                continue
            pairs.append((value, other))
    return pairs


def paired_global(cleaned, literature):
    pairs = []
    for month, value in cleaned.items():
        if not ("2000-01" <= month <= "2023-12") or value is None:
            continue
        other = literature.get(month)
        if other is None:
            continue
        pairs.append((value, other))
    return pairs


def log_pairs(pairs):
    out = []
    for left, right in pairs:
        if left > 0 and right > 0:
            out.append((math.log(left), math.log(right)))
    return out


def within_country_gpr(global_gpr, country_gpr):
    corrs = []
    for iso in ISO_TO_NAME:
        left = []
        right = []
        for month, value in global_gpr.items():
            if not ("2000-01" <= month <= "2023-12"):
                continue
            other = country_gpr.get((iso, month))
            if other is None:
                continue
            left.append(value)
            right.append(other)
        corr = correlation(left, right)
        if corr is not None:
            corrs.append(corr)
    return corrs


def row(series, comparison, stats, definition, note=""):
    return {
        "series": series,
        "comparison": comparison,
        "definition": definition,
        "n": "" if stats is None else stats["n"],
        "corr": "" if stats is None or stats["corr"] is None else f"{stats['corr']:.10g}",
        "mean_cleaned": "" if stats is None else f"{stats['mean_cleaned']:.10g}",
        "mean_literature": "" if stats is None else f"{stats['mean_literature']:.10g}",
        "mean_abs_gap": "" if stats is None else f"{stats['mean_abs_gap']:.10g}",
        "note": note,
    }


def fmt(value, digits=3):
    if value is None or value == "":
        return ""
    return f"{float(value):.{digits}f}"


def build():
    panel = load_panel()
    reer = est.read_reer()
    policy = est.read_monthly_country("policy_rate.csv", "value")
    inflation = est.read_monthly_country("inflation.csv", "value")
    ip = est.read_annual("industrial_production.csv", "year", "index")
    fd = est.read_annual("financial_development.csv", "year", "fd_fdi_ovrl")
    debt = est.read_annual("debt_gdp.csv", "period", "debt_gdp_pct", frequency="Annual")
    gpr = est.read_monthly_global("gpr_index.csv", "value", series="GPR")
    oil = est.read_monthly_global("oil_price.csv", "wti_spot")
    vix = est.read_monthly_global("vix.csv", "value")
    gepu = est.read_monthly_global("gepu_current.csv", "value")

    lit_reer = index_panel(panel, "reer")
    lit_rate = index_panel(panel, "rate")
    lit_infl = index_panel(panel, "infl")
    lit_gpr = index_panel(panel, "gpr")
    lit_gpr_z = index_panel(panel, "gpr_z")
    lit_ip = annual_from_monthly(panel, "AIP_IX", "mean")
    lit_fd = annual_from_monthly(panel, "fd", "mean")
    lit_debt = annual_from_monthly(panel, "debt", "mean")
    lit_cbi_n = len(annual_from_monthly(panel, "cbi", "mean"))
    lit_oil = unique_month(panel, "oil")
    lit_vix = unique_month(panel, "vix")
    lit_gepu = unique_month(panel, "gepu")

    reer_pairs = paired_country_month(reer, lit_reer)
    rate_pairs = paired_country_month(policy, lit_rate)
    infl_pairs = paired_country_month(inflation, lit_infl)
    oil_pairs = paired_global(oil, lit_oil)
    vix_pairs = paired_global(vix, lit_vix)
    gepu_pairs = paired_global(gepu, lit_gepu)
    gpr_pairs = paired_country_month(
        {name: gpr for name in SHARED}, lit_gpr
    )
    gpr_z_pairs = paired_country_month(
        {name: gpr for name in SHARED}, lit_gpr_z
    )
    fd_pairs = paired_annual(fd, lit_fd)
    debt_pairs = paired_annual(debt, lit_debt)
    ip_pairs = paired_annual(ip, lit_ip)
    gpr_within = within_country_gpr(gpr, lit_gpr)

    records = [
        ("Real effective exchange rate", "level", measure(reer_pairs), None,
         "BIS broad real index in the literature panel."),
        ("Real effective exchange rate", "log", measure(log_pairs(reer_pairs)), None,
         "The regression uses the log. A constant rebase is absorbed by country fixed effects."),
        ("Policy rate", "level", measure(rate_pairs), None,
         "Literature panel uses the BIS policy rate."),
        ("Inflation", "year-on-year percent", measure(infl_pairs), None,
         "Literature panel uses IMF IFS year-on-year CPI. The mean absolute gap is about 0.2 percentage points."),
        ("Oil price", "level", measure(oil_pairs), None,
         "One observation per month. Literature panel uses EIA WTI."),
        ("Oil price", "log", measure(log_pairs(oil_pairs)), None, ""),
        ("VIX", "level", measure(vix_pairs), "same concept, different monthly aggregation",
         "The monthly means almost match, and the month-by-month gap is about 1.9 index points. The literature panel is the average of the daily close."),
        ("VIX", "log", measure(log_pairs(vix_pairs)), "same concept, different monthly aggregation",
         "The regression uses the log. This aggregation gap changes the control slightly. It does not replace the GPR regressor."),
        ("Global EPU", "level", measure(gepu_pairs), None,
         "Literature panel uses GEPU_current."),
        ("Global EPU", "log", measure(log_pairs(gepu_pairs)), None, ""),
        ("GPR", "global index vs country index", measure(gpr_pairs), "different definition",
         "Cleaned GPR is one global index near 100. The literature panel is the country article-share index."),
        ("GPR", "global index vs within-country z-score", measure(gpr_z_pairs), "different definition",
         f"Mean within-country correlation of the global index with the country index is {float(np.mean(gpr_within)):.3f} across {len(gpr_within)} countries. The z-score is that country index standardized within the country, which is the regressor in the literature panel."),
        ("Financial development", "annual", measure(fd_pairs), "different definition",
         "Cleaned fd_fdi_ovrl is not the IMF 0-to-1 Financial Development Index used in the literature panel."),
        ("Debt/GDP", "annual percent", measure(debt_pairs), None,
         "Literature panel uses IMF WEO general-government gross debt."),
        ("Industrial production", "annual index vs mean of monthly IMF index", measure(ip_pairs), "different definition",
         "Cleaned industrial production is annual. The literature panel uses monthly IMF IFS AIP_IX. This row compares the annual index with the average of the monthly index in that year."),
        ("Industrial production", "log of that annual comparison", measure(log_pairs(ip_pairs)), "different definition",
         "The literature regression uses the log of the monthly index, not this annual average."),
        ("Central bank independence", "annual", None, "not in cleaned",
         f"Romelli CBIE is in the literature panel for {lit_cbi_n} shared country-years. It is not in cleaned."),
    ]
    return [row(series, comparison, stats, judgment(stats, preset), note)
            for series, comparison, stats, preset, note in records]


def write_csv(path, records):
    fields = [
        "series", "comparison", "definition", "n", "corr",
        "mean_cleaned", "mean_literature", "mean_abs_gap", "note",
    ]
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)
        writer.writerow({
            "series": "Country set",
            "comparison": "shared emerging economies",
            "definition": "overlap",
            "n": len(SHARED),
            "note": "; ".join(SHARED),
        })
        writer.writerow({
            "series": "Country set",
            "comparison": "in the literature emerging sample only",
            "definition": "coverage",
            "n": len(LITERATURE_ONLY),
            "note": "; ".join(LITERATURE_ONLY),
        })
        writer.writerow({
            "series": "Country set",
            "comparison": "in the cleaned emerging exchange-rate sample only",
            "definition": "coverage",
            "n": len(CLEANED_ONLY),
            "note": "; ".join(CLEANED_ONLY) + ". South Korea is in cleaned and is classified as advanced in the literature panel. Taiwan is in neither the paper nor that panel.",
        })


def write_html(path, records):
    body = []
    for record in records:
        body.append(
            "<tr>"
            f"<td>{escape(record['series'])}</td>"
            f"<td>{escape(record['comparison'])}</td>"
            f"<td>{escape(record['definition'])}</td>"
            f"<td>{escape(str(record['n']))}</td>"
            f"<td>{escape(fmt(record['corr']))}</td>"
            f"<td>{escape(fmt(record['mean_cleaned']))}</td>"
            f"<td>{escape(fmt(record['mean_literature']))}</td>"
            f"<td>{escape(fmt(record['mean_abs_gap']))}</td>"
            "</tr>"
        )
    notes = []
    for record in records:
        if record["note"]:
            notes.append(f"<li><strong>{escape(record['series'])}, {escape(record['comparison'])}.</strong> {escape(record['note'])}</li>")
    movers = [
        "GPR is a different variable. The cleaned file is one global index. The literature panel, and the paper, use a country article-share index standardized within each country. A global index has no country-specific spike, so it cannot reproduce the within-country GPR variation that identifies the exchange-rate coefficient.",
        "The country set differs. Brazil, China, Colombia, Malaysia, Poland, and Ukraine are in the literature emerging sample and have no row in the cleaned exchange-rate file. Argentina and Peru are in the cleaned emerging sample and are not in the paper. South Korea is advanced in the literature-review split.",
        "Industrial production is annual in cleaned and monthly in the literature panel, and the cleaned emerging regression leaves it out. Central bank independence is in the literature regression and missing from cleaned. Financial development is a different series, so it does not absorb the same variation.",
    ]
    same = [record["series"] + " (" + record["comparison"] + ")"
            for record in records if record["definition"] == "same measure"]
    same_text = ", ".join(same) if same else "none of the overlapping series"
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Cleaned data and the literature-review panel</title>
<style>
body {{ font: 16px/1.5 Georgia, serif; max-width: 1080px; margin: 2em auto; padding: 0 1em; color: #20242a; }}
table {{ border-collapse: collapse; width: 100%; margin: 1em 0; font-size: .88em; }}
th, td {{ border-bottom: 1px solid #ccc; padding: .4em; text-align: right; vertical-align: top; }}
th:nth-child(-n+3), td:nth-child(-n+3) {{ text-align: left; }}
.note {{ background: #fff5da; padding: 1em; border: 1px solid #e6d59d; }}
</style>
</head>
<body>
<h1>Cleaned data and the literature-review panel</h1>
<div class="note">
<p>The literature-review panel is the public-source file behind Tables 2 and 3. On its own emerging exchange-rate regression, GPR is 0.0008 and not significant. The paper's emerging coefficient is −0.010. The published sign is already absent from that closer panel, before any comparison with <code>cleaned/</code>.</p>
<p>The numbers below are the overlap of that panel with <code>cleaned/</code> for Chile, Hungary, India, Indonesia, Mexico, the Philippines, South Africa, Thailand, and Turkey, from 2000-01 through 2023-12. Global series use one observation per month.</p>
</div>
<h2>Overlap</h2>
<table>
<thead><tr><th>Series</th><th>Comparison</th><th>Definition</th><th>N</th><th>Correlation</th><th>Cleaned mean</th><th>Literature mean</th><th>Mean absolute gap</th></tr></thead>
<tbody>
{''.join(body)}
</tbody>
</table>
<h2>What the gap is</h2>
<ul>
{''.join(notes)}
<li><strong>Same measure on the overlap:</strong> {escape(same_text)}. A series that is the same measure is not why the GPR sign differs.</li>
</ul>
<h2>What can move the exchange-rate coefficient</h2>
<ul>
{''.join(f'<li>{escape(item)}</li>' for item in movers)}
</ul>
<h2>Countries</h2>
<p>Shared emerging economies: {escape(', '.join(SHARED))}.</p>
<p>In the literature emerging sample only: {escape(', '.join(LITERATURE_ONLY))}.</p>
<p>In the cleaned emerging exchange-rate sample only: {escape(', '.join(CLEANED_ONLY))}. South Korea is in cleaned and is advanced in the literature panel. Taiwan is in neither the paper nor that panel.</p>
</body>
</html>
"""
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(html)


def main():
    records = build()
    write_csv(os.path.join(OUTPUT, "cleaned_vs_literature_data.csv"), records)
    write_html(os.path.join(OUTPUT, "cleaned_vs_literature_data.html"), records)
    for record in records:
        print(
            record["series"], "|", record["comparison"], "|", record["definition"],
            "| n", record["n"], "| corr", record["corr"],
            "| gap", record["mean_abs_gap"],
        )


if __name__ == "__main__":
    main()
