import csv
import math
import os
from collections import defaultdict
from datetime import date
from html import escape

import numpy as np
from scipy.stats import t as student_t


ROOT = r"C:\0 UST CourseWork\ECON4999B\econ4999b_research"
PANEL_CSV = os.path.join(
    ROOT,
    "econ4999b_literature_review",
    "replication",
    "output",
    "panel.csv",
)
WGI_CSV = os.path.join(ROOT, "cleaned", "wgi.csv")
OUTPUT_DIR = os.path.join(ROOT, "output")

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


def stars(p):
    if p < 0.01:
        return "***"
    if p < 0.05:
        return "**"
    if p < 0.10:
        return "*"
    return ""


def years_to_spans(years):
    if not years:
        return ""
    years = sorted(set(years))
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
        if a == b:
            out.append(str(a))
        else:
            out.append(f"{a}-{b}")
    return ", ".join(out)


def fit_ols_cluster(rows, rhs_vars, target_var):
    countries = sorted({r["iso"] for r in rows})
    if len(countries) < 2:
        return None, "Need at least two countries for FE model."

    y = np.array([r[target_var] for r in rows], dtype=float)
    X_cols = [np.ones(len(rows), dtype=float)]
    names = ["const"]
    for v in rhs_vars:
        X_cols.append(np.array([r[v] for r in rows], dtype=float))
        names.append(v)

    for c in countries[1:]:
        X_cols.append(np.array([1.0 if r["iso"] == c else 0.0 for r in rows], dtype=float))
        names.append(f"fe_{c}")

    X = np.column_stack(X_cols)
    n, k = X.shape
    if n <= k:
        return None, f"Insufficient observations (N={n}, k={k})."

    try:
        xtx_inv = np.linalg.inv(X.T @ X)
    except np.linalg.LinAlgError:
        return None, "Design matrix is singular."

    beta = xtx_inv @ (X.T @ y)
    resid = y - (X @ beta)

    clusters = defaultdict(list)
    for i, r in enumerate(rows):
        clusters[r["iso"]].append(i)
    g = len(clusters)
    if g < 2:
        return None, "Need at least two clusters."

    meat = np.zeros((k, k), dtype=float)
    for idxs in clusters.values():
        xg = X[idxs, :]
        ug = resid[idxs]
        s = xg.T @ ug
        meat += np.outer(s, s)
    v = xtx_inv @ meat @ xtx_inv
    if g > 1 and n > k:
        v *= (g / (g - 1)) * ((n - 1) / (n - k))

    se = np.sqrt(np.clip(np.diag(v), a_min=0.0, a_max=None))
    with np.errstate(divide="ignore", invalid="ignore"):
        tvals = beta / se
    df = g - 1
    pvals = 2 * (1 - student_t.cdf(np.abs(tvals), df=df))

    sst = float(np.sum((y - np.mean(y)) ** 2))
    sse = float(np.sum(resid**2))
    r2 = float(1 - sse / sst) if sst > 0 else float("nan")

    return {
        "coef": dict(zip(names, beta)),
        "se": dict(zip(names, se)),
        "t": dict(zip(names, tvals)),
        "p": dict(zip(names, pvals)),
        "n_obs": n,
        "n_country": g,
        "k_params": k,
        "r2": r2,
    }, None


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


def build_institution():
    accum = defaultdict(list)
    cleaned_country_set = set()
    with open(WGI_CSV, "r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            country_raw = (row.get("country") or "").strip()
            cleaned_country_set.add(country_raw)
            iso = WGI_COUNTRY_TO_ISO.get(country_raw)
            if iso not in ISO_TO_NAME:
                continue
            y = to_float(row.get("year"))
            est = to_float(row.get("estimate"))
            if y is None or est is None:
                continue
            year = int(y)
            if year < START_YEAR or year > END_YEAR:
                continue
            accum[(iso, year)].append(est)

    inst_raw = {}
    for key, vals in accum.items():
        if vals:
            inst_raw[key] = float(sum(vals) / len(vals))

    inst_filled = {}
    fill_source = {}
    for iso in ISO_TO_NAME:
        yvals = {}
        for y in range(START_YEAR, END_YEAR + 1):
            yvals[y] = inst_raw.get((iso, y))

        last = None
        for y in range(START_YEAR, END_YEAR + 1):
            if yvals[y] is not None:
                last = yvals[y]
                continue
            if last is not None:
                yvals[y] = last
                fill_source[(iso, y)] = "ffill"

        nxt = None
        for y in range(END_YEAR, START_YEAR - 1, -1):
            if yvals[y] is not None:
                nxt = yvals[y]
                continue
            if nxt is not None:
                yvals[y] = nxt
                fill_source[(iso, y)] = "bfill"

        for y in range(START_YEAR, END_YEAR + 1):
            val = yvals[y]
            if val is None:
                fill_source[(iso, y)] = "missing"
            elif (iso, y) not in fill_source:
                fill_source[(iso, y)] = "raw"
            inst_filled[(iso, y)] = val

    return inst_raw, inst_filled, fill_source, cleaned_country_set


def add_institution_to_panel(rows, inst_raw, inst_filled):
    by_iso = defaultdict(list)
    for r in rows:
        r["institution_raw_year"] = inst_raw.get((r["iso"], r["year"]))
        r["institution_filled_year"] = inst_filled.get((r["iso"], r["year"]))
        by_iso[r["iso"]].append(r)

    for iso, items in by_iso.items():
        items.sort(key=lambda x: x["date"])
        prev_inst = None
        for row in items:
            row["institution_l1"] = prev_inst
            prev_inst = row["institution_filled_year"]


def standardize_institution(rows):
    vals = [r["institution_l1"] for r in rows if r["institution_l1"] is not None]
    if not vals:
        return None, None
    mean = float(np.mean(vals))
    std = float(np.std(vals))
    if std == 0:
        std = 1.0
    for r in rows:
        if r["institution_l1"] is None:
            r["institution_z_l1"] = None
        else:
            r["institution_z_l1"] = (r["institution_l1"] - mean) / std
    return mean, std


def missing_reports(rows, inst_raw, inst_filled, fill_source, cleaned_country_set):
    article_missing_in_cleaned = []
    country_year_report = []
    for iso, country in sorted(ISO_TO_NAME.items(), key=lambda kv: kv[1]):
        raw_years = [y for y in range(START_YEAR, END_YEAR + 1) if (iso, y) in inst_raw]
        missing_raw_years = [y for y in range(START_YEAR, END_YEAR + 1) if (iso, y) not in inst_raw]
        if not raw_years:
            article_missing_in_cleaned.append(country)
        country_year_report.append(
            {
                "iso": iso,
                "country": country,
                "raw_years": len(raw_years),
                "missing_raw_years": len(missing_raw_years),
                "missing_raw_spans": years_to_spans(missing_raw_years),
                "fill_types": {
                    "raw": sum(1 for y in range(START_YEAR, END_YEAR + 1) if fill_source[(iso, y)] == "raw"),
                    "ffill": sum(1 for y in range(START_YEAR, END_YEAR + 1) if fill_source[(iso, y)] == "ffill"),
                    "bfill": sum(1 for y in range(START_YEAR, END_YEAR + 1) if fill_source[(iso, y)] == "bfill"),
                    "missing": sum(1 for y in range(START_YEAR, END_YEAR + 1) if fill_source[(iso, y)] == "missing"),
                },
            }
        )

    panel_rows_by_iso = defaultdict(list)
    for r in rows:
        panel_rows_by_iso[r["iso"]].append(r)
    panel_missing_report = []
    for iso, country in sorted(ISO_TO_NAME.items(), key=lambda kv: kv[1]):
        items = panel_rows_by_iso.get(iso, [])
        n = len(items)
        miss_raw = sum(1 for r in items if r["institution_raw_year"] is None)
        miss_filled = sum(1 for r in items if r["institution_filled_year"] is None)
        miss_lag = sum(1 for r in items if r["institution_l1"] is None)
        panel_missing_report.append(
            {
                "iso": iso,
                "country": country,
                "panel_rows": n,
                "missing_raw_rows": miss_raw,
                "missing_filled_rows": miss_filled,
                "missing_lag_rows": miss_lag,
            }
        )

    cleaned_not_in_article = sorted(
        c for c in cleaned_country_set if WGI_COUNTRY_TO_ISO.get(c) not in ISO_TO_NAME
    )
    return article_missing_in_cleaned, country_year_report, panel_missing_report, cleaned_not_in_article


def run_regressions(rows):
    outcomes = [
        ("cf_vol", "Capital flow volatility"),
        ("ln_stock_real", "Stock prices (log real)"),
        ("bond", "Long-term bond yield"),
        ("ln_reer", "Exchange rate (log REER)"),
    ]
    controls = [
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

    results = []
    failures = []
    for y, label in outcomes:
        rhs = ["gpr_z", "institution_z_l1"] + controls
        sample = []
        for r in rows:
            if r.get(y) is None:
                continue
            ok = True
            for v in rhs:
                if r.get(v) is None or (isinstance(r.get(v), float) and math.isnan(r.get(v))):
                    ok = False
                    break
            if ok:
                sample.append(r)
        fit, err = fit_ols_cluster(sample, rhs, y)
        if err:
            failures.append({"outcome": label, "error": err, "n_after_filter": len(sample)})
            continue
        results.append(
            {
                "outcome": label,
                "coef_gpr": float(fit["coef"]["gpr_z"]),
                "se_gpr": float(fit["se"]["gpr_z"]),
                "p_gpr": float(fit["p"]["gpr_z"]),
                "coef_inst": float(fit["coef"]["institution_z_l1"]),
                "se_inst": float(fit["se"]["institution_z_l1"]),
                "p_inst": float(fit["p"]["institution_z_l1"]),
                "n_obs": fit["n_obs"],
                "n_country": fit["n_country"],
                "k_params": fit["k_params"],
                "r2": float(fit["r2"]),
            }
        )
    return results, failures


def write_outputs(results, failures, article_missing_in_cleaned, country_year_report, panel_missing_report, cleaned_not_in_article, inst_mean, inst_std):
    csv_path = os.path.join(OUTPUT_DIR, "article_vars_with_cleaned_institution_results.csv")
    html_path = os.path.join(OUTPUT_DIR, "article_vars_with_cleaned_institution_results.html")

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "outcome",
                "coef_gpr_z",
                "se_gpr_z",
                "p_gpr_z",
                "coef_institution_z_l1",
                "se_institution_z_l1",
                "p_institution_z_l1",
                "n_obs",
                "n_country",
                "k_params",
                "r2",
            ]
        )
        for r in results:
            w.writerow(
                [
                    r["outcome"],
                    r["coef_gpr"],
                    r["se_gpr"],
                    r["p_gpr"],
                    r["coef_inst"],
                    r["se_inst"],
                    r["p_inst"],
                    r["n_obs"],
                    r["n_country"],
                    r["k_params"],
                    r["r2"],
                ]
            )

    with open(html_path, "w", encoding="utf-8") as f:
        f.write("<!doctype html><html lang='en'><head><meta charset='utf-8'>")
        f.write("<title>Article-style regression + cleaned institution score</title>")
        f.write(
            "<style>"
            "body{font:16px/1.5 Georgia,serif;max-width:1280px;margin:2em auto;padding:0 1em;color:#20242a}"
            "table{border-collapse:collapse;width:100%;margin:1em 0;font-size:.9em}"
            "th,td{border-bottom:1px solid #ccc;padding:.45em;text-align:right;vertical-align:top}"
            "th:first-child,td:first-child{text-align:left}"
            ".note{background:#fff5da;padding:1em;border:1px solid #e6d59d}"
            ".warn{background:#ffe6e6;padding:.8em;border:1px solid #e0a7a7}"
            "code{font-size:.92em}"
            "</style></head><body>"
        )
        f.write("<h1>Redone regression using article-defined variables + institution score from cleaned dataset</h1>")
        f.write(
            "<p>Base macro/financial variables follow the article-style panel pipeline in "
            "<code>econ4999b_literature_review/replication/raw</code> (via existing panel file), "
            "with one extension: a continuous institution score from <code>cleaned/wgi.csv</code>.</p>"
        )
        f.write("<div class='note'>")
        f.write("<strong>Institution variable construction:</strong> annual country-year mean of available WGI dimension scores in <code>cleaned/wgi.csv</code>; ")
        f.write("merged to monthly panel by year, filled within country-year sequence using forward/backward carry, then lagged one month and standardized (z-score) for regression.")
        if inst_mean is not None:
            f.write(f"<br><strong>Standardization stats:</strong> mean={inst_mean:.6f}, std={inst_std:.6f}.")
        f.write("</div>")

        f.write("<h2>Regression results (country FE, clustered SE by country)</h2>")
        f.write(
            "<table><thead><tr>"
            "<th>Outcome</th><th>β(GPR z)</th><th>SE</th><th>p</th>"
            "<th>β(Institution z, lag1)</th><th>SE</th><th>p</th>"
            "<th>N</th><th>Countries</th><th>R²</th>"
            "</tr></thead><tbody>"
        )
        for r in results:
            f.write(
                "<tr>"
                f"<td>{escape(r['outcome'])}</td>"
                f"<td>{r['coef_gpr']:.4f}{stars(r['p_gpr'])}</td>"
                f"<td>{r['se_gpr']:.4f}</td>"
                f"<td>{r['p_gpr']:.4f}</td>"
                f"<td>{r['coef_inst']:.4f}{stars(r['p_inst'])}</td>"
                f"<td>{r['se_inst']:.4f}</td>"
                f"<td>{r['p_inst']:.4f}</td>"
                f"<td>{r['n_obs']}</td>"
                f"<td>{r['n_country']}</td>"
                f"<td>{r['r2']:.4f}</td>"
                "</tr>"
            )
        if not results:
            f.write("<tr><td colspan='10'>No estimable outcomes.</td></tr>")
        f.write("</tbody></table>")
        f.write("<p><em>Significance stars:</em> *** p&lt;0.01, ** p&lt;0.05, * p&lt;0.10.</p>")

        if failures:
            f.write("<h3>Non-estimable outcomes</h3><div class='warn'>")
            for x in failures:
                f.write(
                    f"<p>{escape(x['outcome'])}: {escape(x['error'])} (N after filter = {x['n_after_filter']})</p>"
                )
            f.write("</div>")

        f.write("<h2>Country mapping and missingness report for institution score</h2>")
        if article_missing_in_cleaned:
            f.write(
                "<div class='warn'><strong>Article countries missing entirely in cleaned WGI mapping:</strong> "
                + escape(", ".join(article_missing_in_cleaned))
                + "</div>"
            )
        else:
            f.write("<p>All article countries are represented in cleaned WGI mapping (at least one year).</p>")

        f.write("<h3>Country-year coverage (2000-2023)</h3>")
        f.write(
            "<table><thead><tr>"
            "<th>Country</th><th>ISO</th><th>Raw years available</th><th>Raw years missing</th><th>Missing year spans</th>"
            "<th>Raw years used</th><th>Forward-filled years</th><th>Backward-filled years</th><th>Still missing years</th>"
            "</tr></thead><tbody>"
        )
        for c in country_year_report:
            ft = c["fill_types"]
            f.write(
                "<tr>"
                f"<td>{escape(c['country'])}</td>"
                f"<td>{escape(c['iso'])}</td>"
                f"<td>{c['raw_years']}</td>"
                f"<td>{c['missing_raw_years']}</td>"
                f"<td style='text-align:left'>{escape(c['missing_raw_spans'])}</td>"
                f"<td>{ft['raw']}</td>"
                f"<td>{ft['ffill']}</td>"
                f"<td>{ft['bfill']}</td>"
                f"<td>{ft['missing']}</td>"
                "</tr>"
            )
        f.write("</tbody></table>")

        f.write("<h3>Monthly panel missingness after merging institution</h3>")
        f.write(
            "<table><thead><tr>"
            "<th>Country</th><th>ISO</th><th>Monthly rows</th><th>Rows missing raw institution</th>"
            "<th>Rows missing filled institution</th><th>Rows missing lagged institution</th>"
            "</tr></thead><tbody>"
        )
        for c in panel_missing_report:
            f.write(
                "<tr>"
                f"<td>{escape(c['country'])}</td>"
                f"<td>{escape(c['iso'])}</td>"
                f"<td>{c['panel_rows']}</td>"
                f"<td>{c['missing_raw_rows']}</td>"
                f"<td>{c['missing_filled_rows']}</td>"
                f"<td>{c['missing_lag_rows']}</td>"
                "</tr>"
            )
        f.write("</tbody></table>")

        f.write("<h3>Countries in cleaned WGI not in article country list</h3>")
        if cleaned_not_in_article:
            f.write("<p>" + escape(", ".join(cleaned_not_in_article)) + "</p>")
        else:
            f.write("<p>None.</p>")

        f.write("</body></html>")

    print("Generated:")
    print(csv_path)
    print(html_path)
    print(f"Estimable outcomes: {len(results)} | Non-estimable outcomes: {len(failures)}")


def main():
    rows = load_panel_rows()
    inst_raw, inst_filled, fill_source, cleaned_country_set = build_institution()
    add_institution_to_panel(rows, inst_raw, inst_filled)
    inst_mean, inst_std = standardize_institution(rows)
    (
        article_missing_in_cleaned,
        country_year_report,
        panel_missing_report,
        cleaned_not_in_article,
    ) = missing_reports(rows, inst_raw, inst_filled, fill_source, cleaned_country_set)
    results, failures = run_regressions(rows)
    write_outputs(
        results,
        failures,
        article_missing_in_cleaned,
        country_year_report,
        panel_missing_report,
        cleaned_not_in_article,
        inst_mean,
        inst_std,
    )


if __name__ == "__main__":
    main()
