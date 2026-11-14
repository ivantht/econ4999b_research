import csv
import os
import re
from collections import defaultdict
import unicodedata


ROOT = r"C:\0 UST CourseWork\ECON4999B\econ4999b_research"
SRC_CSV = r"C:\Users\wscha\Downloads\dataset_2026-11-11T10_54_13.510249773Z_DEFAULT_INTEGRATION_IMF.STA_PPI_3.0.0.csv"
COUNTRY_CSV = os.path.join(ROOT, "cleaned", "country.csv")
OUT_DIR = os.path.join(ROOT, "output")

SERIES_3NF_CSV = os.path.join(OUT_DIR, "ppi_series_3nf.csv")
VALUES_3NF_CSV = os.path.join(OUT_DIR, "ppi_values_3nf.csv")
LONG_3NF_CSV = os.path.join(OUT_DIR, "ppi_3nf_long.csv")
COUNTRY_DIM_CSV = os.path.join(OUT_DIR, "ppi_country_dim_3nf.csv")
INDICATOR_DIM_CSV = os.path.join(OUT_DIR, "ppi_indicator_dim_3nf.csv")
FREQUENCY_DIM_CSV = os.path.join(OUT_DIR, "ppi_frequency_dim_3nf.csv")
SUMMARY_CSV = os.path.join(OUT_DIR, "ppi_model_country_availability.csv")
SUMMARY_HTML = os.path.join(OUT_DIR, "ppi_model_country_availability.html")

MODEL_START_YEAR = 2000
MODEL_END_YEAR = 2023


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


def load_model_countries():
    out = []
    with open(COUNTRY_CSV, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            c = (row.get("country") or "").strip()
            if c:
                out.append(c)
    return sorted(set(out))


def model_to_imf_name(country):
    aliases = {
        "Egypt": "Egypt, Arab Republic of",
        "South Korea": "Korea, Republic of",
        "Taiwan": "Taiwan Province of China",
        "Turkey": "Turkey, Republic of",
    }
    return aliases.get(country, country)


def normalize_country_name(name):
    s = (name or "").strip()
    s = s.replace("\ufffd", "u")
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-zA-Z ]+", " ", s).lower()
    s = re.sub(r"\s+", " ", s).strip()
    return s


def match_model_country(country_name, model_norm_map):
    n = normalize_country_name(country_name)
    if n in model_norm_map:
        return model_norm_map[n]
    if n.startswith("turkiye") and "turkey republic of" in model_norm_map:
        return model_norm_map["turkey republic of"]
    return None


def frequency_from_time_label(label):
    if re.fullmatch(r"\d{4}", label):
        return "Annual"
    if re.fullmatch(r"\d{4}-Q[1-4]", label):
        return "Quarterly"
    if re.fullmatch(r"\d{4}-M(0[1-9]|1[0-2])", label):
        return "Monthly"
    return None


def expected_periods(freq):
    out = []
    if freq == "Annual":
        for y in range(MODEL_START_YEAR, MODEL_END_YEAR + 1):
            out.append(f"{y:04d}")
    elif freq == "Quarterly":
        for y in range(MODEL_START_YEAR, MODEL_END_YEAR + 1):
            for q in range(1, 5):
                out.append(f"{y:04d}-Q{q}")
    elif freq == "Monthly":
        for y in range(MODEL_START_YEAR, MODEL_END_YEAR + 1):
            for m in range(1, 13):
                out.append(f"{y:04d}-M{m:02d}")
    return out


def time_sort_key(t):
    if "-Q" in t:
        y, q = t.split("-Q")
        return int(y), int(q) * 3
    if "-M" in t:
        y, m = t.split("-M")
        return int(y), int(m)
    return int(t), 0


def next_period(t, freq):
    if freq == "Annual":
        return f"{int(t) + 1:04d}"
    if freq == "Quarterly":
        y, q = t.split("-Q")
        y = int(y)
        q = int(q)
        if q == 4:
            return f"{y+1:04d}-Q1"
        return f"{y:04d}-Q{q+1}"
    y, m = t.split("-M")
    y = int(y)
    m = int(m)
    if m == 12:
        return f"{y+1:04d}-M01"
    return f"{y:04d}-M{m+1:02d}"


def compress_missing(periods, freq):
    if not periods:
        return ""
    ps = sorted(periods, key=time_sort_key)
    ranges = []
    start = ps[0]
    prev = ps[0]
    for cur in ps[1:]:
        if cur == next_period(prev, freq):
            prev = cur
            continue
        ranges.append((start, prev))
        start = cur
        prev = cur
    ranges.append((start, prev))
    out = []
    for a, b in ranges:
        out.append(a if a == b else f"{a} to {b}")
    return "; ".join(out)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    model_countries = load_model_countries()
    model_imf_names = {c: model_to_imf_name(c) for c in model_countries}
    model_norm_map = {normalize_country_name(v): k for k, v in model_imf_names.items()}

    with open(SRC_CSV, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        time_cols = [c for c in fields if frequency_from_time_label(c)]
        meta_cols = [c for c in fields if c not in time_cols]

        series_rows = []
        values_rows = []
        long_rows = []
        country_dim = {}
        indicator_dim = {}
        frequency_dim = {}
        series_id = 0

        availability = defaultdict(set)  # (model_country, series_code, freq, indicator) -> set(periods)

        for row in reader:
            country = (row.get("COUNTRY") or "").strip()
            series_code = (row.get("SERIES_CODE") or "").strip()
            freq = (row.get("FREQUENCY") or "").strip()
            indicator = (row.get("INDICATOR") or "").strip()
            if not country or not series_code:
                continue

            country_dim[country] = {
                "country": country,
                "iso2": (row.get("ISO2_CODE") or "").strip(),
                "iso3": (row.get("ISO3_CODE") or "").strip(),
            }
            indicator_dim[indicator] = {
                "indicator": indicator,
                "index_type": (row.get("INDEX_TYPE") or "").strip(),
                "unit": (row.get("UNIT") or "").strip(),
                "ppi_activity": (row.get("PPI_ACTIVITY") or "").strip(),
                "transformation": (row.get("TRANSFORMATION") or "").strip(),
            }
            frequency_dim[freq] = {"frequency": freq}

            series_id += 1
            srow = {
                "series_id": series_id,
                "country": country,
                "series_code": series_code,
                "indicator": indicator,
                "frequency": freq,
                "unit": (row.get("UNIT") or "").strip(),
                "index_type": (row.get("INDEX_TYPE") or "").strip(),
                "ppi_activity": (row.get("PPI_ACTIVITY") or "").strip(),
                "transformation": (row.get("TRANSFORMATION") or "").strip(),
                "reference_period": (row.get("REFERENCE_PERIOD") or "").strip(),
            }
            series_rows.append(srow)

            model_country = match_model_country(country, model_norm_map)

            for t in time_cols:
                if frequency_from_time_label(t) != freq:
                    continue
                val = to_float(row.get(t))
                if val is None:
                    continue
                values_rows.append({"series_id": series_id, "time": t, "value": val})
                long_rows.append(
                    {
                        "country": country,
                        "series_code": series_code,
                        "indicator": indicator,
                        "frequency": freq,
                        "time": t,
                        "value": val,
                    }
                )
                if model_country is not None:
                    availability[(model_country, series_code, freq, indicator)].add(t)

    with open(SERIES_3NF_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "series_id",
                "country",
                "series_code",
                "indicator",
                "frequency",
                "unit",
                "index_type",
                "ppi_activity",
                "transformation",
                "reference_period",
            ],
        )
        w.writeheader()
        w.writerows(series_rows)

    with open(VALUES_3NF_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["series_id", "time", "value"])
        w.writeheader()
        w.writerows(values_rows)

    with open(LONG_3NF_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["country", "series_code", "indicator", "frequency", "time", "value"],
        )
        w.writeheader()
        w.writerows(long_rows)

    with open(COUNTRY_DIM_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["country", "iso2", "iso3"])
        w.writeheader()
        for c in sorted(country_dim):
            w.writerow(country_dim[c])

    with open(INDICATOR_DIM_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f, fieldnames=["indicator", "index_type", "unit", "ppi_activity", "transformation"]
        )
        w.writeheader()
        for i in sorted(indicator_dim):
            w.writerow(indicator_dim[i])

    with open(FREQUENCY_DIM_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["frequency"])
        w.writeheader()
        for fr in sorted(frequency_dim):
            w.writerow(frequency_dim[fr])

    summary_rows = []
    for model_country in model_countries:
        imf_country = model_imf_names[model_country]
        keys = [k for k in availability if k[0] == model_country]
        if not keys:
            summary_rows.append(
                {
                    "model_country": model_country,
                    "imf_country": imf_country,
                    "series_code": "",
                    "indicator": "",
                    "frequency": "",
                    "observed_count_in_model_window": 0,
                    "expected_count_in_model_window": "",
                    "missing_count_in_model_window": "",
                    "first_available_period": "",
                    "last_available_period": "",
                    "missing_periods_in_model_window": "No series found for this country in dataset.",
                }
            )
            continue

        for _, series_code, freq, indicator in sorted(keys, key=lambda x: (x[2], x[1])):
            observed = sorted(availability[(model_country, series_code, freq, indicator)], key=time_sort_key)
            exp = expected_periods(freq)
            observed_set = set(observed)
            missing = [p for p in exp if p not in observed_set]
            summary_rows.append(
                {
                    "model_country": model_country,
                    "imf_country": imf_country,
                    "series_code": series_code,
                    "indicator": indicator,
                    "frequency": freq,
                    "observed_count_in_model_window": len([p for p in observed if p in set(exp)]),
                    "expected_count_in_model_window": len(exp),
                    "missing_count_in_model_window": len(missing),
                    "first_available_period": observed[0] if observed else "",
                    "last_available_period": observed[-1] if observed else "",
                    "missing_periods_in_model_window": compress_missing(missing, freq),
                }
            )

    with open(SUMMARY_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "model_country",
                "imf_country",
                "series_code",
                "indicator",
                "frequency",
                "observed_count_in_model_window",
                "expected_count_in_model_window",
                "missing_count_in_model_window",
                "first_available_period",
                "last_available_period",
                "missing_periods_in_model_window",
            ],
        )
        w.writeheader()
        w.writerows(summary_rows)

    missing_country_entries = [r for r in summary_rows if r["series_code"] == ""]
    with open(SUMMARY_HTML, "w", encoding="utf-8") as f:
        f.write("<!doctype html><html lang='en'><head><meta charset='utf-8'>")
        f.write("<title>PPI 3NF cleaning and model-country availability summary</title>")
        f.write(
            "<style>"
            "body{font:16px/1.5 Georgia,serif;max-width:1400px;margin:2em auto;padding:0 1em;color:#20242a}"
            "table{border-collapse:collapse;width:100%;margin:1em 0;font-size:.9em}"
            "th,td{border-bottom:1px solid #ccc;padding:.45em;text-align:right;vertical-align:top}"
            "th:first-child,td:first-child,td.left{text-align:left}"
            ".note{background:#fff5da;padding:1em;border:1px solid #e6d59d}"
            ".warn{background:#ffe6e6;padding:.8em;border:1px solid #e0a7a7}"
            "code{font-size:.92em}"
            "</style></head><body>"
        )
        f.write("<h1>PPI/WPI dataset normalized to 3NF + model-country availability</h1>")
        f.write(
            "<div class='note'>"
            "<strong>3NF output files</strong><br>"
            f"Country dimension: <code>{COUNTRY_DIM_CSV}</code><br>"
            f"Indicator dimension: <code>{INDICATOR_DIM_CSV}</code><br>"
            f"Frequency dimension: <code>{FREQUENCY_DIM_CSV}</code><br>"
            f"Series dimension: <code>{SERIES_3NF_CSV}</code><br>"
            f"Observation fact table: <code>{VALUES_3NF_CSV}</code><br>"
            f"Joined convenience long table: <code>{LONG_3NF_CSV}</code><br>"
            "<strong>Model window for missing-period checks:</strong> 2000 to 2023, by each series frequency."
            "</div>"
        )
        if missing_country_entries:
            f.write("<div class='warn'><strong>Model countries with no series in this IMF file:</strong> ")
            f.write(", ".join(r["model_country"] for r in missing_country_entries))
            f.write(".</div>")

        f.write("<h2>Availability by model country and series</h2>")
        f.write(
            "<table><thead><tr>"
            "<th>Model country</th><th>IMF country name</th><th>Series code</th><th>Indicator</th><th>Frequency</th>"
            "<th>Observed (2000-2023)</th><th>Expected (2000-2023)</th><th>Missing count</th>"
            "<th>First available</th><th>Last available</th><th>Missing periods in model window</th>"
            "</tr></thead><tbody>"
        )
        for r in summary_rows:
            f.write(
                "<tr>"
                f"<td class='left'>{r['model_country']}</td>"
                f"<td class='left'>{r['imf_country']}</td>"
                f"<td class='left'>{r['series_code']}</td>"
                f"<td class='left'>{r['indicator']}</td>"
                f"<td>{r['frequency']}</td>"
                f"<td>{r['observed_count_in_model_window']}</td>"
                f"<td>{r['expected_count_in_model_window']}</td>"
                f"<td>{r['missing_count_in_model_window']}</td>"
                f"<td>{r['first_available_period']}</td>"
                f"<td>{r['last_available_period']}</td>"
                f"<td class='left'>{r['missing_periods_in_model_window']}</td>"
                "</tr>"
            )
        f.write("</tbody></table>")
        f.write("</body></html>")

    print("Generated:")
    print(SERIES_3NF_CSV)
    print(VALUES_3NF_CSV)
    print(LONG_3NF_CSV)
    print(COUNTRY_DIM_CSV)
    print(INDICATOR_DIM_CSV)
    print(FREQUENCY_DIM_CSV)
    print(SUMMARY_CSV)
    print(SUMMARY_HTML)


if __name__ == "__main__":
    main()
