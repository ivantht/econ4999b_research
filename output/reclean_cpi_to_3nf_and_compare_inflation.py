import csv
import math
import os
from collections import defaultdict
from datetime import datetime


ROOT = r"C:\0 UST CourseWork\ECON4999B\econ4999b_research"
IN_XLSX = os.path.join(ROOT, "input", "monthly CPI.xlsx")
EXISTING_INFL_CSV = os.path.join(ROOT, "cleaned", "inflation.csv")

OUT_CPI_COUNTRY_DIM = os.path.join(ROOT, "cleaned", "cpi_country_dim_3nf.csv")
OUT_CPI_TIME_DIM = os.path.join(ROOT, "cleaned", "cpi_time_dim_3nf.csv")
OUT_CPI_FACT = os.path.join(ROOT, "cleaned", "cpi_values_3nf.csv")
OUT_NEW_INFL = os.path.join(ROOT, "cleaned", "CPI-calculated inflation.csv")
OUT_STATS = os.path.join(ROOT, "cleaned", "cpi_inflation_comparison_stats.csv")
OUT_DIFF = os.path.join(ROOT, "cleaned", "cpi_inflation_difference_stats.csv")


def to_float(v):
    if v is None:
        return None
    try:
        return float(v)
    except Exception:
        return None


def prev_12(ym):
    y = int(ym[:4])
    m = int(ym[5:7])
    y2 = y - 1
    return f"{y2:04d}-{m:02d}"


def mean(vals):
    return sum(vals) / len(vals) if vals else None


def sd_sample(vals):
    n = len(vals)
    if n < 2:
        return None
    mu = mean(vals)
    return math.sqrt(sum((x - mu) ** 2 for x in vals) / (n - 1))


def load_monthly_cpi():
    from openpyxl import load_workbook

    wb = load_workbook(IN_XLSX, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]

    rows = ws.iter_rows(min_row=1, values_only=True)
    header = [str(x).strip() if x is not None else "" for x in next(rows)]
    base_row = [str(x).strip() if x is not None else "" for x in next(rows)]
    countries = header[1:]
    bases = base_row[1:]

    country_dim = []
    for c, b in zip(countries, bases):
        if c:
            country_dim.append(
                {
                    "country": c,
                    "cpi_base_label": b,
                    "source_file": "input/monthly CPI.xlsx",
                }
            )

    fact = []
    time_seen = set()
    for row in rows:
        ym = row[0]
        if ym is None:
            continue
        ym = str(ym).strip()
        try:
            datetime.strptime(ym, "%Y-%m")
        except ValueError:
            continue
        for i, c in enumerate(countries, start=1):
            if not c:
                continue
            v = to_float(row[i] if i < len(row) else None)
            if v is None:
                continue
            fact.append({"country": c, "year_month": ym, "cpi_index": v})
            time_seen.add(ym)

    time_dim = []
    for ym in sorted(time_seen):
        time_dim.append({"year_month": ym, "year": int(ym[:4]), "month": int(ym[5:7])})

    return country_dim, time_dim, fact


def build_cpi_calculated_inflation(cpi_fact):
    by_country = defaultdict(dict)
    for r in cpi_fact:
        by_country[r["country"]][r["year_month"]] = r["cpi_index"]

    out = []
    for country, cmap in by_country.items():
        for ym in sorted(cmap):
            p12 = prev_12(ym)
            if p12 not in cmap:
                continue
            c_t = cmap[ym]
            c_l12 = cmap[p12]
            if c_l12 is None or c_l12 == 0:
                continue
            infl = ((c_t - c_l12) / c_l12) * 100.0
            out.append({"country": country, "year_month": ym, "value": infl})
    return out


def load_existing_inflation():
    out = []
    with open(EXISTING_INFL_CSV, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            c = (row.get("country") or "").strip()
            ym = (row.get("year_month") or "").strip()
            v = to_float(row.get("value"))
            if c and ym and v is not None:
                out.append({"country": c, "year_month": ym, "value": v})
    return out


def summary_stats(rows, label, scope):
    vals = [r["value"] for r in rows]
    countries = sorted({r["country"] for r in rows})
    months = sorted({r["year_month"] for r in rows})
    return {
        "scope": scope,
        "series": label,
        "n_obs": len(vals),
        "n_country": len(countries),
        "month_min": months[0] if months else "",
        "month_max": months[-1] if months else "",
        "min": min(vals) if vals else None,
        "max": max(vals) if vals else None,
        "mean": mean(vals),
        "sd_sample": sd_sample(vals),
    }


def intersection_rows(a_rows, b_rows):
    a_map = {(r["country"], r["year_month"]): r["value"] for r in a_rows}
    b_map = {(r["country"], r["year_month"]): r["value"] for r in b_rows}
    keys = sorted(set(a_map).intersection(set(b_map)))
    a_out = [{"country": c, "year_month": ym, "value": a_map[(c, ym)]} for (c, ym) in keys]
    b_out = [{"country": c, "year_month": ym, "value": b_map[(c, ym)]} for (c, ym) in keys]
    diffs = [{"country": c, "year_month": ym, "value": a_map[(c, ym)] - b_map[(c, ym)]} for (c, ym) in keys]
    return a_out, b_out, diffs


def write_csv(path, fieldnames, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main():
    country_dim, time_dim, cpi_fact = load_monthly_cpi()
    cpi_infl = build_cpi_calculated_inflation(cpi_fact)
    existing_infl = load_existing_inflation()

    # 3NF tables
    write_csv(
        OUT_CPI_COUNTRY_DIM,
        ["country", "cpi_base_label", "source_file"],
        country_dim,
    )
    write_csv(
        OUT_CPI_TIME_DIM,
        ["year_month", "year", "month"],
        time_dim,
    )
    write_csv(
        OUT_CPI_FACT,
        ["country", "year_month", "cpi_index"],
        cpi_fact,
    )
    write_csv(
        OUT_NEW_INFL,
        ["country", "year_month", "value"],
        cpi_infl,
    )

    # stats
    new_aligned, old_aligned, diff_rows = intersection_rows(cpi_infl, existing_infl)
    stats = [
        summary_stats(cpi_infl, "CPI_calculated_inflation", "all_values"),
        summary_stats(existing_infl, "existing_inflation", "all_values"),
        summary_stats(new_aligned, "CPI_calculated_inflation", "intersection_only"),
        summary_stats(old_aligned, "existing_inflation", "intersection_only"),
    ]
    write_csv(
        OUT_STATS,
        ["scope", "series", "n_obs", "n_country", "month_min", "month_max", "min", "max", "mean", "sd_sample"],
        stats,
    )
    write_csv(
        OUT_DIFF,
        ["country", "year_month", "value"],
        diff_rows,
    )

    print("Generated:")
    print(OUT_CPI_COUNTRY_DIM)
    print(OUT_CPI_TIME_DIM)
    print(OUT_CPI_FACT)
    print(OUT_NEW_INFL)
    print(OUT_STATS)
    print(OUT_DIFF)


if __name__ == "__main__":
    main()

