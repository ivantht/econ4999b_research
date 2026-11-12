import csv
import os
from collections import defaultdict

from openpyxl import load_workbook


ROOT = r"C:\0 UST CourseWork\ECON4999B\econ4999b_research"
CLEANED_WGI = os.path.join(ROOT, "cleaned", "wgi.csv")
RAW_XLSX = r"C:\Users\wscha\Downloads\wgidataset_with_sourcedata-2026.xlsx"
OUT_DIR = os.path.join(ROOT, "output")
OUT_CSV = os.path.join(OUT_DIR, "wgi_merged_3nf.csv")
OUT_CONFLICTS_CSV = os.path.join(OUT_DIR, "wgi_merged_3nf_conflicts.csv")
OUT_HTML = os.path.join(OUT_DIR, "wgi_merged_3nf_summary.html")

VALID_ASPECTS = {"va", "pv", "ge", "rq", "rl", "cc"}

# Canonicalize workbook country labels to cleaned/wgi.csv style
COUNTRY_ALIASES = {
    "Egypt, Arab Rep.": "Egypt",
    "Korea, Rep.": "South Korea",
    "Taiwan, China": "Taiwan",
    "Viet Nam": "Vietnam",
    "T�rkiye": "Turkey",
    "Türkiye": "Turkey",
}


def to_int(x):
    try:
        return int(x)
    except Exception:
        return None


def to_float(x):
    try:
        return float(x)
    except Exception:
        return None


def norm_country(c):
    c = (c or "").strip()
    return COUNTRY_ALIASES.get(c, c)


def read_cleaned_wgi():
    out = {}
    with open(CLEANED_WGI, "r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            country = norm_country(row.get("country"))
            year = to_int(row.get("year"))
            aspect = (row.get("dimension") or "").strip().lower()
            score = to_float(row.get("estimate"))
            if not country or year is None or aspect not in VALID_ASPECTS or score is None:
                continue
            out[(country, year, aspect)] = score
    return out


def read_raw_wgi_workbook():
    out = {}
    bad_rows = 0
    wb = load_workbook(RAW_XLSX, read_only=True, data_only=True)
    for sheet in wb.sheetnames:
        ws = wb[sheet]
        for row in ws.iter_rows(min_row=2, values_only=True):
            country = norm_country(row[1])
            year = to_int(row[5])
            aspect = (row[6] or "").strip().lower() if row[6] is not None else ""
            score = to_float(row[8])
            if not country or year is None or aspect not in VALID_ASPECTS or score is None:
                bad_rows += 1
                continue
            out[(country, year, aspect)] = score
    return out, bad_rows


def write_outputs(raw_map, cleaned_map):
    # Merge rule: cleaned file takes precedence on overlaps
    merged = dict(raw_map)
    merged.update(cleaned_map)

    # Track conflicts where both exist but values differ
    conflicts = []
    for k, raw_v in raw_map.items():
        if k in cleaned_map:
            c_v = cleaned_map[k]
            if abs(raw_v - c_v) > 1e-12:
                conflicts.append((k[0], k[1], k[2], raw_v, c_v))

    rows = sorted(merged.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2]))
    with open(OUT_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["country", "time", "aspect", "score"])
        for (country, year, aspect), score in rows:
            w.writerow([country, year, aspect, score])

    with open(OUT_CONFLICTS_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["country", "time", "aspect", "raw_score", "cleaned_score"])
        for c, y, a, rv, cv in sorted(conflicts, key=lambda x: (x[0], x[1], x[2])):
            w.writerow([c, y, a, rv, cv])

    # Summary HTML
    raw_countries = {k[0] for k in raw_map}
    cleaned_countries = {k[0] for k in cleaned_map}
    merged_countries = {k[0] for k in merged}
    raw_only = sorted(raw_countries - cleaned_countries)
    cleaned_only = sorted(cleaned_countries - raw_countries)

    per_country_count = defaultdict(int)
    for (country, _, _), _ in merged.items():
        per_country_count[country] += 1

    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write("<!doctype html><html lang='en'><head><meta charset='utf-8'>")
        f.write("<title>WGI 3NF merge summary</title>")
        f.write(
            "<style>"
            "body{font:16px/1.5 Georgia,serif;max-width:1100px;margin:2em auto;padding:0 1em;color:#20242a}"
            "table{border-collapse:collapse;width:100%;margin:1em 0;font-size:.9em}"
            "th,td{border-bottom:1px solid #ccc;padding:.45em;text-align:right}"
            "th:first-child,td:first-child{text-align:left}"
            ".note{background:#fff5da;padding:1em;border:1px solid #e6d59d}"
            "</style></head><body>"
        )
        f.write("<h1>WGI raw + cleaned merge (3NF format)</h1>")
        f.write("<div class='note'>")
        f.write("<p><strong>3NF output format:</strong> one row per <code>(country, time, aspect)</code> with attribute <code>score</code>.</p>")
        f.write("<p><strong>Merge precedence:</strong> cleaned <code>wgi.csv</code> overrides raw workbook on overlapping keys.</p>")
        f.write("</div>")
        f.write("<h2>Summary counts</h2>")
        f.write("<ul>")
        f.write(f"<li>Raw normalized rows: {len(raw_map):,}</li>")
        f.write(f"<li>Cleaned rows: {len(cleaned_map):,}</li>")
        f.write(f"<li>Merged rows: {len(merged):,}</li>")
        f.write(f"<li>Conflicting overlapping values: {len(conflicts):,}</li>")
        f.write(f"<li>Raw countries: {len(raw_countries):,}</li>")
        f.write(f"<li>Cleaned countries: {len(cleaned_countries):,}</li>")
        f.write(f"<li>Merged countries: {len(merged_countries):,}</li>")
        f.write("</ul>")
        f.write("<h2>Country coverage by source</h2>")
        f.write("<p><strong>Countries only in raw:</strong> " + (", ".join(raw_only) if raw_only else "None") + "</p>")
        f.write("<p><strong>Countries only in cleaned:</strong> " + (", ".join(cleaned_only) if cleaned_only else "None") + "</p>")
        f.write("<h2>Merged row count per country</h2>")
        f.write("<table><thead><tr><th>Country</th><th>Rows</th></tr></thead><tbody>")
        for country in sorted(per_country_count):
            f.write(f"<tr><td>{country}</td><td>{per_country_count[country]}</td></tr>")
        f.write("</tbody></table>")
        f.write("</body></html>")

    return len(merged), len(conflicts)


def main():
    if not os.path.exists(RAW_XLSX):
        raise FileNotFoundError(f"Raw file not found: {RAW_XLSX}")
    os.makedirs(OUT_DIR, exist_ok=True)

    cleaned_map = read_cleaned_wgi()
    raw_map, bad_rows = read_raw_wgi_workbook()
    merged_n, conflict_n = write_outputs(raw_map, cleaned_map)

    print("Generated:")
    print(OUT_CSV)
    print(OUT_CONFLICTS_CSV)
    print(OUT_HTML)
    print(f"Rows skipped during raw cleaning: {bad_rows}")
    print(f"Merged rows: {merged_n} | Conflicts: {conflict_n}")


if __name__ == "__main__":
    main()
