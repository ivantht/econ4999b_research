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
INSTITUTION_CSV = os.path.join(ROOT, "output", "wgi_merged_3nf.csv")
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
ISO_TO_ARTICLE_COUNTRY = {v: k for k, v in ARTICLE_COUNTRIES.items()}

INST_COUNTRY_ALIASES = {
    "Korea": "South Korea",
    "Türkiye": "Turkey",
}
VALID_ASPECTS = {"va", "pv", "ge", "rq", "rl", "cc"}


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
            if iso not in ISO_TO_ARTICLE_COUNTRY:
                continue
            d = parse_month(row["date"])
            if d.year < START_YEAR or d.year > END_YEAR:
                continue
            rows.append(
                {
                    "iso": iso,
                    "country": ISO_TO_ARTICLE_COUNTRY[iso],
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


def read_institution_yearly_mean():
    per_key = defaultdict(list)
    with open(INSTITUTION_CSV, "r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            country = (row.get("country") or "").strip()
            if not country:
                continue
            year = int(row.get("time"))
            aspect = (row.get("aspect") or "").strip().lower()
            score = to_float(row.get("score"))
            if score is None or aspect not in VALID_ASPECTS:
                continue
            per_key[(country, year)].append(score)

    yearly = {}
    for key, vals in per_key.items():
        yearly[key] = float(np.mean(np.array(vals, dtype=float)))
    return yearly


def add_institution(rows, inst_yearly):
    by_iso = defaultdict(list)
    for r in rows:
        article_country = r["country"]
        inst_country = INST_COUNTRY_ALIASES.get(article_country, article_country)
        r["institution_raw_year"] = inst_yearly.get((inst_country, r["year"]))
        by_iso[r["iso"]].append(r)

    # yearly carry-forward/backward by country
    for iso, items in by_iso.items():
        years = list(range(START_YEAR, END_YEAR + 1))
        article_country = ISO_TO_ARTICLE_COUNTRY[iso]
        inst_country = INST_COUNTRY_ALIASES.get(article_country, article_country)
        ymap = {y: inst_yearly.get((inst_country, y)) for y in years}

        last = None
        for y in years:
            if ymap[y] is not None:
                last = ymap[y]
            elif last is not None:
                ymap[y] = last
        nxt = None
        for y in reversed(years):
            if ymap[y] is not None:
                nxt = ymap[y]
            elif nxt is not None:
                ymap[y] = nxt

        items.sort(key=lambda x: x["date"])
        prev_inst = None
        for row in items:
            row["institution_filled_year"] = ymap[row["year"]]
            row["institution_l1"] = prev_inst
            prev_inst = row["institution_filled_year"]

    vals = [r["institution_l1"] for r in rows if r["institution_l1"] is not None]
    if not vals:
        return None, None
    mean = float(np.mean(np.array(vals, dtype=float)))
    std = float(np.std(np.array(vals, dtype=float)))
    if std == 0:
        std = 1.0

    for r in rows:
        if r["institution_l1"] is None:
            r["institution_z_l1"] = None
            r["gpr_x_inst"] = None
            continue
        r["institution_z_l1"] = (r["institution_l1"] - mean) / std
        if r["gpr_z"] is None:
            r["gpr_x_inst"] = None
        else:
            r["gpr_x_inst"] = r["gpr_z"] * r["institution_z_l1"]
    return mean, std


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
    rhs = ["gpr_z", "institution_z_l1", "gpr_x_inst"] + controls

    results = []
    failed = []
    for y, label in outcomes:
        sample = []
        for r in rows:
            if r.get(y) is None:
                continue
            ok = True
            for v in rhs:
                val = r.get(v)
                if val is None or (isinstance(val, float) and math.isnan(val)):
                    ok = False
                    break
            if ok:
                sample.append(r)
        fit, err = fit_ols_cluster(sample, rhs, y)
        if err:
            failed.append({"outcome": label, "error": err, "n_after_filter": len(sample)})
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
                "coef_int": float(fit["coef"]["gpr_x_inst"]),
                "se_int": float(fit["se"]["gpr_x_inst"]),
                "p_int": float(fit["p"]["gpr_x_inst"]),
                "n_obs": fit["n_obs"],
                "n_country": fit["n_country"],
                "k_params": fit["k_params"],
                "r2": float(fit["r2"]),
            }
        )
    return results, failed


def write_outputs(results, failed, rows, inst_mean, inst_std):
    csv_path = os.path.join(OUTPUT_DIR, "article_vars_cleaned_inst_interaction_results.csv")
    html_path = os.path.join(OUTPUT_DIR, "article_vars_cleaned_inst_interaction_results.html")

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
                "coef_gpr_x_inst",
                "se_gpr_x_inst",
                "p_gpr_x_inst",
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
                    r["coef_int"],
                    r["se_int"],
                    r["p_int"],
                    r["n_obs"],
                    r["n_country"],
                    r["k_params"],
                    r["r2"],
                ]
            )

    panel_countries = sorted({x["iso"] for x in rows})
    with open(html_path, "w", encoding="utf-8") as f:
        f.write("<!doctype html><html lang='en'><head><meta charset='utf-8'>")
        f.write("<title>Article variables + cleaned institution interaction</title>")
        f.write(
            "<style>"
            "body{font:16px/1.5 Georgia,serif;max-width:1250px;margin:2em auto;padding:0 1em;color:#20242a}"
            "table{border-collapse:collapse;width:100%;margin:1em 0;font-size:.9em}"
            "th,td{border-bottom:1px solid #ccc;padding:.45em;text-align:right;vertical-align:top}"
            "th:first-child,td:first-child{text-align:left}"
            ".note{background:#fff5da;padding:1em;border:1px solid #e6d59d}"
            ".warn{background:#ffe6e6;padding:.8em;border:1px solid #e0a7a7}"
            "</style></head><body>"
        )
        f.write("<h1>Article-style regressions with cleaned institution score and interaction term</h1>")
        f.write(
            "<p>Specification includes <code>gpr_z</code>, <code>institution_z_l1</code>, and interaction "
            "<code>gpr_z × institution_z_l1</code>, plus article controls and country fixed effects.</p>"
        )
        f.write("<div class='note'>")
        f.write("<strong>Institution source:</strong> <code>output/wgi_merged_3nf.csv</code> (cleaned+raw merged). ")
        f.write("Institution level is annual mean across aspects (va,pv,ge,rq,rl,cc), carry-forward/backward filled by country-year, then lagged 1 month and z-standardized.")
        if inst_mean is not None:
            f.write(f"<br><strong>Institution lag mean/std before standardization:</strong> {inst_mean:.6f} / {inst_std:.6f}.")
        f.write("</div>")

        f.write("<h2>Regression results</h2>")
        f.write(
            "<table><thead><tr>"
            "<th>Outcome</th>"
            "<th>β(GPR z)</th><th>SE</th><th>p</th>"
            "<th>β(Institution z, lag1)</th><th>SE</th><th>p</th>"
            "<th>β(GPR × Institution)</th><th>SE</th><th>p</th>"
            "<th>N</th><th>Countries</th><th>R²</th>"
            "</tr></thead><tbody>"
        )
        for r in results:
            f.write(
                "<tr>"
                f"<td>{escape(r['outcome'])}</td>"
                f"<td>{r['coef_gpr']:.4f}{stars(r['p_gpr'])}</td><td>{r['se_gpr']:.4f}</td><td>{r['p_gpr']:.4f}</td>"
                f"<td>{r['coef_inst']:.4f}{stars(r['p_inst'])}</td><td>{r['se_inst']:.4f}</td><td>{r['p_inst']:.4f}</td>"
                f"<td>{r['coef_int']:.4f}{stars(r['p_int'])}</td><td>{r['se_int']:.4f}</td><td>{r['p_int']:.4f}</td>"
                f"<td>{r['n_obs']}</td><td>{r['n_country']}</td><td>{r['r2']:.4f}</td>"
                "</tr>"
            )
        if not results:
            f.write("<tr><td colspan='13'>No estimable outcomes.</td></tr>")
        f.write("</tbody></table>")
        f.write("<p><em>Significance stars:</em> *** p&lt;0.01, ** p&lt;0.05, * p&lt;0.10.</p>")

        if failed:
            f.write("<h3>Non-estimable outcomes</h3><div class='warn'>")
            for x in failed:
                f.write(f"<p>{escape(x['outcome'])}: {escape(x['error'])} (N after filter={x['n_after_filter']})</p>")
            f.write("</div>")

        f.write("<h2>Sample coverage</h2>")
        f.write("<ul>")
        f.write(f"<li>Article countries present in panel source: {len(panel_countries)} ({', '.join(panel_countries)})</li>")
        f.write("</ul>")
        f.write("</body></html>")

    print("Generated:")
    print(csv_path)
    print(html_path)
    print(f"Estimable outcomes: {len(results)} | Non-estimable outcomes: {len(failed)}")


def main():
    rows = load_panel_rows()
    inst_yearly = read_institution_yearly_mean()
    inst_mean, inst_std = add_institution(rows, inst_yearly)
    results, failed = run_regressions(rows)
    write_outputs(results, failed, rows, inst_mean, inst_std)


if __name__ == "__main__":
    main()
