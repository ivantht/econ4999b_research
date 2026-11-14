import csv
import math
import os
from datetime import date
from html import escape

import numpy as np

import run_equation1_six_institution_aspects as eq1


IN_CSV = os.path.join(eq1.ROOT, "cleaned", "replication_cleaned", "country_month.csv")
OUT_HTML = os.path.join(eq1.OUT_DIR, "replication_cleaned_table1_summary_stats.html")
OUT_CSV = os.path.join(eq1.OUT_DIR, "replication_cleaned_table1_summary_stats.csv")

START_YEAR = 2000
END_YEAR = 2023


def to_float(x):
    if x is None:
        return None
    s = str(x).strip()
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_date(s):
    y, m, _ = str(s).split("-")
    return date(int(y), int(m), 1)


def safe_log(v):
    if v is None or v <= 0:
        return None
    return math.log(v)


def summarize(values):
    arr = np.array([v for v in values if v is not None and not math.isnan(v)], dtype=float)
    if arr.size == 0:
        return None
    return {
        "n_obs": int(arr.size),
        "mean": float(np.mean(arr)),
        "sd": float(np.std(arr, ddof=1)) if arr.size > 1 else 0.0,
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
    }


def fmt(v):
    return "" if v is None else f"{v:.2f}"


def main():
    records = []
    with open(IN_CSV, "r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            iso = (r.get("iso") or "").strip()
            if not iso:
                continue
            d = parse_date(r["date"])
            if d.year < START_YEAR or d.year > END_YEAR:
                continue
            records.append(
                {
                    "iso": iso,
                    "country": (r.get("country") or iso).strip(),
                    "group": (r.get("group") or "").strip(),
                    "date": d,
                    "capital_flow_volatility": to_float(r.get("capital_flow_volatility")),
                    "share_price_log": safe_log(to_float(r.get("share_price"))),
                    "bond_yield": to_float(r.get("bond_yield")),
                    "reer_log": safe_log(to_float(r.get("reer"))),
                    "gpr": to_float(r.get("gpr")),
                    "policy_rate": to_float(r.get("policy_rate")),
                    "industrial_production_log": safe_log(to_float(r.get("industrial_production"))),
                    "inflation": to_float(r.get("inflation")),
                    "oil_price_log": safe_log(to_float(r.get("oil_price"))),
                    "vix_log": safe_log(to_float(r.get("vix"))),
                    "vix_level": to_float(r.get("vix")),
                    "gepu_level": to_float(r.get("gepu")),
                    "financial_development": to_float(r.get("financial_development")),
                    "cbi": to_float(r.get("central_bank_independence")),
                    "debt_gdp": to_float(r.get("public_debt_gdp")),
                }
            )

    table1_vars = [
        ("Capital flow volatility (SD)", "capital_flow_volatility"),
        ("Real stock prices (log)", "share_price_log"),
        ("Long-term bond yield (%)", "bond_yield"),
        ("Real effective exchange rate (log)", "reer_log"),
        ("Geopolitical risk (index)", "gpr"),
        ("Policy rate (%)", "policy_rate"),
        ("Real industrial production (log)", "industrial_production_log"),
        ("Inflation (%)", "inflation"),
        ("Oil price (log)", "oil_price_log"),
        ("VIX (log)", "vix_log"),
        ("Global economic policy uncertainty (index)", "gepu_level"),
        ("Financial development (index)", "financial_development"),
        ("Central bank independence (index)", "cbi"),
        ("Public debt to GDP (%)", "debt_gdp"),
    ]

    rows = []
    for label, key in table1_vars:
        vals = [r[key] for r in records]
        countries = sorted({r["country"] for r in records if r[key] is not None})
        s = summarize(vals)
        rows.append(
            {
                "variable": label,
                "n_obs": 0 if s is None else s["n_obs"],
                "n_countries": len(countries),
                "mean": None if s is None else s["mean"],
                "sd": None if s is None else s["sd"],
                "min": None if s is None else s["min"],
                "max": None if s is None else s["max"],
            }
        )

    # Alignment check panel for VIX definition in case of log/level mismatch.
    vix_level_stats = summarize([r["vix_level"] for r in records])
    vix_level_row = {
        "variable": "VIX (level, alignment check)",
        "n_obs": 0 if vix_level_stats is None else vix_level_stats["n_obs"],
        "n_countries": len({r["country"] for r in records if r["vix_level"] is not None}),
        "mean": None if vix_level_stats is None else vix_level_stats["mean"],
        "sd": None if vix_level_stats is None else vix_level_stats["sd"],
        "min": None if vix_level_stats is None else vix_level_stats["min"],
        "max": None if vix_level_stats is None else vix_level_stats["max"],
    }

    with open(OUT_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["variable", "n_obs", "n_countries", "mean", "sd", "min", "max"],
        )
        w.writeheader()
        for row in rows:
            w.writerow(row)
        w.writerow(vix_level_row)

    countries_all = sorted({r["country"] for r in records})
    months = sorted({f"{r['date'].year:04d}-{r['date'].month:02d}" for r in records}) if records else []
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write("<!doctype html><html lang='en'><head><meta charset='utf-8'>")
        f.write("<title>Replication-cleaned Table 1 summary statistics</title>")
        f.write(
            "<style>"
            "body{font:16px/1.5 Georgia,serif;max-width:1100px;margin:2em auto;padding:0 1em;color:#20242a}"
            "table{border-collapse:collapse;width:100%;margin:1em 0;font-size:.95em}"
            "th,td{border-bottom:1px solid #ccc;padding:.45em;text-align:right;vertical-align:top}"
            "th:first-child,td:first-child{text-align:left}"
            ".note{background:#fff5da;padding:1em;border:1px solid #e6d59d}"
            "</style></head><body>"
        )
        f.write("<h1>Table 1-style Summary Statistics (Replication-cleaned data)</h1>")
        f.write(
            "<div class='note'>"
            "<strong>Source</strong>: cleaned/replication_cleaned/country_month.csv<br>"
            "<strong>Window</strong>: 2000-01 to 2023-12 (monthly)<br>"
            f"<strong>Countries in dataset window</strong>: {len(countries_all)}<br>"
            f"<strong>Month range observed</strong>: {escape(months[0]) if months else ''} to {escape(months[-1]) if months else ''}"
            "</div>"
        )
        f.write("<h2>Panel A. Article-style variable set</h2>")
        f.write(
            "<table><thead><tr>"
            "<th>Variable</th><th>N</th><th>Countries</th><th>Mean</th><th>SD</th><th>Min.</th><th>Max.</th>"
            "</tr></thead><tbody>"
        )
        for row in rows:
            f.write(
                "<tr>"
                f"<td>{escape(row['variable'])}</td>"
                f"<td>{row['n_obs']}</td>"
                f"<td>{row['n_countries']}</td>"
                f"<td>{fmt(row['mean'])}</td>"
                f"<td>{fmt(row['sd'])}</td>"
                f"<td>{fmt(row['min'])}</td>"
                f"<td>{fmt(row['max'])}</td>"
                "</tr>"
            )
        f.write("</tbody></table>")

        f.write("<h2>Panel B. Alignment check</h2>")
        f.write(
            "<table><thead><tr>"
            "<th>Variable</th><th>N</th><th>Countries</th><th>Mean</th><th>SD</th><th>Min.</th><th>Max.</th>"
            "</tr></thead><tbody>"
        )
        f.write(
            "<tr>"
            f"<td>{escape(vix_level_row['variable'])}</td>"
            f"<td>{vix_level_row['n_obs']}</td>"
            f"<td>{vix_level_row['n_countries']}</td>"
            f"<td>{fmt(vix_level_row['mean'])}</td>"
            f"<td>{fmt(vix_level_row['sd'])}</td>"
            f"<td>{fmt(vix_level_row['min'])}</td>"
            f"<td>{fmt(vix_level_row['max'])}</td>"
            "</tr>"
        )
        f.write("</tbody></table>")
        f.write(
            "<p><em>Notes:</em> Panel A follows the article-style variable labels and transformations "
            "(log transforms where indicated). Panel B reports VIX in level terms to help compare data-processing alignment.</p>"
        )
        f.write("</body></html>")

    print("Generated:")
    print(OUT_HTML)
    print(OUT_CSV)


if __name__ == "__main__":
    main()
