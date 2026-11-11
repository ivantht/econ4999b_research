import csv
import os
from collections import defaultdict
from datetime import date
from html import escape

import numpy as np


ROOT = r"C:\0 UST CourseWork\ECON4999B\econ4999b_research"
PANEL_CSV = os.path.join(
    ROOT,
    "econ4999b_literature_review",
    "replication",
    "output",
    "panel.csv",
)
WGI_CSV = os.path.join(ROOT, "cleaned", "wgi.csv")
OUTPUT_HTML = os.path.join(ROOT, "output", "formula_variable_coverage_all_countries.html")

START_YEAR = 2000
END_YEAR = 2023

ARTICLE_COUNTRIES = {
    "Belgium": "BE",
    "Brazil": "BR",
    "Canada": "CA",
    "Chile": "CL",
    "China": "CN",
    "Colombia": "CO",
    "Germany": "DE",
    "Denmark": "DK",
    "Spain": "ES",
    "Finland": "FI",
    "France": "FR",
    "Hungary": "HU",
    "Indonesia": "ID",
    "India": "IN",
    "Italy": "IT",
    "Japan": "JP",
    "Korea": "KR",
    "Mexico": "MX",
    "Malaysia": "MY",
    "Netherlands": "NL",
    "Philippines": "PH",
    "Poland": "PL",
    "Portugal": "PT",
    "Sweden": "SE",
    "Thailand": "TH",
    "Türkiye": "TR",
    "Ukraine": "UA",
    "United States": "US",
    "South Africa": "ZA",
}
ISO_TO_NAME = {v: k for k, v in ARTICLE_COUNTRIES.items()}

WGI_COUNTRY_TO_ISO = {
    "Belgium": "BE",
    "Brazil": "BR",
    "Canada": "CA",
    "Chile": "CL",
    "China": "CN",
    "People's Republic of China": "CN",
    "Colombia": "CO",
    "Germany": "DE",
    "Denmark": "DK",
    "Spain": "ES",
    "Finland": "FI",
    "France": "FR",
    "Hungary": "HU",
    "Indonesia": "ID",
    "India": "IN",
    "Italy": "IT",
    "Japan": "JP",
    "Korea": "KR",
    "Korea, Republic of": "KR",
    "Republic of Korea": "KR",
    "Mexico": "MX",
    "Malaysia": "MY",
    "Netherlands": "NL",
    "Philippines": "PH",
    "Poland": "PL",
    "Portugal": "PT",
    "Sweden": "SE",
    "Thailand": "TH",
    "Turkey": "TR",
    "Türkiye": "TR",
    "Türkiye, Republic of": "TR",
    "Ukraine": "UA",
    "United States": "US",
    "United States of America": "US",
    "South Africa": "ZA",
}

RHS_VARS = [
    "gpr_z",
    "institution_z_l1",
    "rate_l1",
    "ln_ip_l1",
    "infl_l1",
    "ln_oil_l1",
    "ln_vix_l1",
    "ln_gepu_l1",
    "fd_l1",
    "cbi_l1",
    "debt_l1",
]

OUTCOME_VARS = ["cf_vol", "ln_stock_real", "bond", "ln_reer"]


def parse_month(s):
    y, m, _ = s.split("-")
    return date(int(y), int(m), 1)


def to_float(x):
    if x is None:
        return None
    s = str(x).strip()
    if s == "" or s.lower() == "nan":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def pct(a, b):
    if b == 0:
        return "0.0%"
    return f"{(100.0 * a / b):.1f}%"


def years_to_spans(years):
    years = sorted(set(years))
    if not years:
        return ""
    spans = []
    start = years[0]
    prev = years[0]
    for y in years[1:]:
        if y == prev + 1:
            prev = y
            continue
        spans.append((start, prev))
        start = y
        prev = y
    spans.append((start, prev))
    out = []
    for a, b in spans:
        out.append(str(a) if a == b else f"{a}-{b}")
    return ", ".join(out)


def load_panel_rows():
    rows = []
    with open(PANEL_CSV, "r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            iso = (row.get("iso") or "").strip()
            if iso not in ISO_TO_NAME:
                continue
            d = parse_month(row["date"])
            if d.year < START_YEAR or d.year > END_YEAR:
                continue
            rows.append(
                {
                    "iso": iso,
                    "country": ISO_TO_NAME[iso],
                    "date": d,
                    "year": d.year,
                    "gpr_z": to_float(row.get("gpr_z")),
                    "cf_vol": to_float(row.get("cf_vol")),
                    "ln_stock_real": to_float(row.get("ln_stock_real")),
                    "bond": to_float(row.get("bond")),
                    "ln_reer": to_float(row.get("ln_reer")),
                    "rate_l1": to_float(row.get("rate_l1")),
                    "ln_ip_l1": to_float(row.get("ln_ip_l1")),
                    "infl_l1": to_float(row.get("infl_l1")),
                    "ln_oil_l1": to_float(row.get("ln_oil_l1")),
                    "ln_vix_l1": to_float(row.get("ln_vix_l1")),
                    "ln_gepu_l1": to_float(row.get("ln_gepu_l1")),
                    "fd_l1": to_float(row.get("fd_l1")),
                    "cbi_l1": to_float(row.get("cbi_l1")),
                    "debt_l1": to_float(row.get("debt_l1")),
                }
            )
    rows.sort(key=lambda x: (x["iso"], x["date"]))
    return rows


def load_institution_yearly():
    accum = defaultdict(list)
    with open(WGI_CSV, "r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            iso = WGI_COUNTRY_TO_ISO.get((row.get("country") or "").strip())
            if iso not in ISO_TO_NAME:
                continue
            y = to_float(row.get("year"))
            est = to_float(row.get("estimate"))
            if y is None or est is None:
                continue
            year = int(y)
            if START_YEAR <= year <= END_YEAR:
                accum[(iso, year)].append(est)
    inst_raw = {}
    for key, vals in accum.items():
        inst_raw[key] = float(sum(vals) / len(vals))
    return inst_raw


def fill_institution_yearly(inst_raw):
    inst_filled = {}
    fill_type = {}
    for iso in ISO_TO_NAME:
        yvals = {y: inst_raw.get((iso, y)) for y in range(START_YEAR, END_YEAR + 1)}
        last = None
        for y in range(START_YEAR, END_YEAR + 1):
            if yvals[y] is not None:
                last = yvals[y]
            elif last is not None:
                yvals[y] = last
                fill_type[(iso, y)] = "ffill"
        nxt = None
        for y in range(END_YEAR, START_YEAR - 1, -1):
            if yvals[y] is not None:
                nxt = yvals[y]
            elif nxt is not None:
                yvals[y] = nxt
                fill_type[(iso, y)] = "bfill"
        for y in range(START_YEAR, END_YEAR + 1):
            inst_filled[(iso, y)] = yvals[y]
            if (iso, y) not in fill_type:
                fill_type[(iso, y)] = "raw" if yvals[y] is not None else "missing"
    return inst_filled, fill_type


def add_institution_lag(rows, inst_raw, inst_filled):
    by_iso = defaultdict(list)
    for r in rows:
        r["institution_raw_year"] = inst_raw.get((r["iso"], r["year"]))
        r["institution_filled_year"] = inst_filled.get((r["iso"], r["year"]))
        by_iso[r["iso"]].append(r)

    for iso, items in by_iso.items():
        items.sort(key=lambda x: x["date"])
        prev = None
        for r in items:
            r["institution_l1"] = prev
            prev = r["institution_filled_year"]

    vals = [r["institution_l1"] for r in rows if r["institution_l1"] is not None]
    if vals:
        mean = float(np.mean(vals))
        std = float(np.std(vals))
        if std == 0:
            std = 1.0
        for r in rows:
            r["institution_z_l1"] = None if r["institution_l1"] is None else (r["institution_l1"] - mean) / std
    else:
        for r in rows:
            r["institution_z_l1"] = None


def build_coverage(rows, inst_raw, fill_type):
    by_iso = defaultdict(list)
    for r in rows:
        by_iso[r["iso"]].append(r)

    coverage = []
    for iso, country in sorted(ISO_TO_NAME.items(), key=lambda kv: kv[1]):
        items = by_iso.get(iso, [])
        total = len(items)
        entry = {"iso": iso, "country": country, "total_rows": total, "vars": {}, "complete_rhs_rows": 0}
        for v in RHS_VARS + OUTCOME_VARS:
            present = sum(1 for r in items if r.get(v) is not None and not (isinstance(r.get(v), float) and np.isnan(r.get(v))))
            missing = total - present
            entry["vars"][v] = {"present": present, "missing": missing}

        # complete RHS rows for formula
        for r in items:
            ok = True
            for v in RHS_VARS:
                val = r.get(v)
                if val is None or (isinstance(val, float) and np.isnan(val)):
                    ok = False
                    break
            if ok:
                entry["complete_rhs_rows"] += 1

        missing_raw_years = [y for y in range(START_YEAR, END_YEAR + 1) if (iso, y) not in inst_raw]
        entry["inst_missing_year_spans"] = years_to_spans(missing_raw_years)
        entry["inst_fill_counts"] = {
            "raw": sum(1 for y in range(START_YEAR, END_YEAR + 1) if fill_type[(iso, y)] == "raw"),
            "ffill": sum(1 for y in range(START_YEAR, END_YEAR + 1) if fill_type[(iso, y)] == "ffill"),
            "bfill": sum(1 for y in range(START_YEAR, END_YEAR + 1) if fill_type[(iso, y)] == "bfill"),
            "missing": sum(1 for y in range(START_YEAR, END_YEAR + 1) if fill_type[(iso, y)] == "missing"),
        }
        coverage.append(entry)
    return coverage


def render_html(coverage):
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write("<!doctype html><html lang='en'><head><meta charset='utf-8'>")
        f.write("<title>All-country formula variable coverage report</title>")
        f.write(
            "<style>"
            "body{font:16px/1.5 Georgia,serif;max-width:1400px;margin:2em auto;padding:0 1em;color:#20242a}"
            "table{border-collapse:collapse;width:100%;margin:1em 0;font-size:.86em}"
            "th,td{border-bottom:1px solid #ccc;padding:.4em;text-align:right;vertical-align:top}"
            "th:first-child,td:first-child{text-align:left}"
            ".note{background:#fff5da;padding:1em;border:1px solid #e6d59d}"
            ".muted{color:#5f6880}"
            "</style></head><body>"
        )
        f.write("<h1>All-country data coverage and missingness by formula variables</h1>")
        f.write(
            "<p class='muted'>Scope: article country list (29 economies), monthly rows in 2000-2023 from "
            "<code>econ4999b_literature_review/replication/output/panel.csv</code>, plus institution score built from "
            "<code>cleaned/wgi.csv</code> using annual mean, fill, lag, and z-standardization.</p>"
        )
        f.write("<div class='note'>")
        f.write("<strong>Missing types shown in this report:</strong> ")
        f.write("panel-variable missing (blank/NaN in monthly panel), raw institution year missing (no WGI year), ")
        f.write("institution filled by forward/backward carry, and still-missing institution after fill.")
        f.write("</div>")

        # Summary
        f.write("<h2>Country-level summary</h2>")
        f.write(
            "<table><thead><tr>"
            "<th>Country</th><th>ISO</th><th>Monthly rows</th>"
            "<th>Complete RHS rows</th><th>Complete RHS share</th>"
            "<th>Institution raw years</th><th>Institution ffill years</th><th>Institution bfill years</th><th>Institution still-missing years</th>"
            "<th>Institution raw missing year spans</th>"
            "</tr></thead><tbody>"
        )
        for c in coverage:
            inst = c["inst_fill_counts"]
            f.write(
                "<tr>"
                f"<td>{escape(c['country'])}</td>"
                f"<td>{escape(c['iso'])}</td>"
                f"<td>{c['total_rows']}</td>"
                f"<td>{c['complete_rhs_rows']}</td>"
                f"<td>{pct(c['complete_rhs_rows'], c['total_rows'])}</td>"
                f"<td>{inst['raw']}</td>"
                f"<td>{inst['ffill']}</td>"
                f"<td>{inst['bfill']}</td>"
                f"<td>{inst['missing']}</td>"
                f"<td style='text-align:left'>{escape(c['inst_missing_year_spans'])}</td>"
                "</tr>"
            )
        f.write("</tbody></table>")

        # Formula RHS variables
        f.write("<h2>Formula RHS variables: data exists vs missing</h2>")
        f.write(
            "<table><thead><tr>"
            "<th>Country</th><th>ISO</th>"
            + "".join(f"<th>{escape(v)} present</th><th>{escape(v)} missing</th><th>{escape(v)} coverage</th>" for v in RHS_VARS)
            + "</tr></thead><tbody>"
        )
        for c in coverage:
            f.write(f"<tr><td>{escape(c['country'])}</td><td>{escape(c['iso'])}</td>")
            for v in RHS_VARS:
                present = c["vars"][v]["present"]
                missing = c["vars"][v]["missing"]
                f.write(f"<td>{present}</td><td>{missing}</td><td>{pct(present, c['total_rows'])}</td>")
            f.write("</tr>")
        f.write("</tbody></table>")

        # Outcomes
        f.write("<h2>Outcome variables: data exists vs missing</h2>")
        f.write(
            "<table><thead><tr>"
            "<th>Country</th><th>ISO</th>"
            + "".join(f"<th>{escape(v)} present</th><th>{escape(v)} missing</th><th>{escape(v)} coverage</th>" for v in OUTCOME_VARS)
            + "</tr></thead><tbody>"
        )
        for c in coverage:
            f.write(f"<tr><td>{escape(c['country'])}</td><td>{escape(c['iso'])}</td>")
            for v in OUTCOME_VARS:
                present = c["vars"][v]["present"]
                missing = c["vars"][v]["missing"]
                f.write(f"<td>{present}</td><td>{missing}</td><td>{pct(present, c['total_rows'])}</td>")
            f.write("</tr>")
        f.write("</tbody></table>")

        f.write("</body></html>")


def main():
    rows = load_panel_rows()
    inst_raw = load_institution_yearly()
    inst_filled, fill_type = fill_institution_yearly(inst_raw)
    add_institution_lag(rows, inst_raw, inst_filled)
    coverage = build_coverage(rows, inst_raw, fill_type)
    render_html(coverage)
    print("Generated:")
    print(OUTPUT_HTML)


if __name__ == "__main__":
    main()
