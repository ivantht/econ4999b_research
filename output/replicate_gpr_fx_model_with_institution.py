import csv
import math
import os
from collections import defaultdict
from datetime import date
from html import escape

import numpy as np
from openpyxl import load_workbook
from scipy.stats import t as student_t


ROOT = r"C:\0 UST CourseWork\ECON4999B\econ4999b_research"
CLEANED_DIR = os.path.join(ROOT, "cleaned")
OUTPUT_DIR = os.path.join(ROOT, "output")

SHOCK_MONTHS = {
    "E03": "2003-03",
    "E09": "2011-03",
    "E13": "2020-01",
    "E14": "2022-02",
    "E16": "2023-10",
    "E17": "2024-04",
    "E19": "2025-06",
    "E20": "2026-02",
}

COUNTRY_MAP = {"Türkiye": "Turkey"}


def parse_month(s):
    y, m = s.split("-")
    return date(int(y), int(m), 1)


def month_str(d):
    return f"{d.year:04d}-{d.month:02d}"


def add_months(d, n):
    ym = d.year * 12 + d.month - 1 + n
    y = ym // 12
    m = ym % 12 + 1
    return date(y, m, 1)


def stars(p):
    if p < 0.01:
        return "***"
    if p < 0.05:
        return "**"
    if p < 0.10:
        return "*"
    return ""


def read_monthly_country_series(file_name, value_col):
    out = defaultdict(dict)
    with open(os.path.join(CLEANED_DIR, file_name), "r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            c = row["country"].strip()
            m = row["year_month"].strip()
            v = row[value_col].strip()
            if v:
                out[c][m] = float(v)
    return out


def read_monthly_global_series(file_name, value_col):
    out = {}
    with open(os.path.join(CLEANED_DIR, file_name), "r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            m = row["year_month"].strip()
            v = row[value_col].strip()
            if v:
                out[m] = float(v)
    return out


def read_annual_country_series(file_name, year_col, value_col):
    out = defaultdict(dict)
    with open(os.path.join(CLEANED_DIR, file_name), "r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            c = row["country"].strip()
            y = row[year_col].strip()
            v = row[value_col].strip()
            if y and v:
                out[c][int(y)] = float(v)
    return out


def read_wgi_composite_yearly():
    by_country_year = defaultdict(lambda: defaultdict(list))
    with open(os.path.join(CLEANED_DIR, "wgi.csv"), "r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            c = row["country"].strip()
            y = int(row["year"])
            v = row["estimate"].strip()
            if v:
                by_country_year[c][y].append(float(v))

    # composite institution = average of available WGI dimensions in year
    raw = defaultdict(dict)
    for c, ymap in by_country_year.items():
        for y, vals in ymap.items():
            if vals:
                raw[c][y] = float(np.mean(vals))
    return raw


def carryforward_yearly(raw_yearly, target_year_start=2000, target_year_end=2026):
    out = defaultdict(dict)
    for c, ymap in raw_yearly.items():
        years = sorted(ymap.keys())
        if not years:
            continue
        last_val = None
        for y in range(target_year_start, target_year_end + 1):
            if y in ymap:
                last_val = ymap[y]
            if last_val is not None:
                out[c][y] = last_val
    return out


def read_selected_shocks():
    wb = load_workbook(
        os.path.join(CLEANED_DIR, "oil_related_geopolitical_shocks_imf.xlsx"),
        read_only=True,
        data_only=True,
    )
    ws = wb["Selected countries"]
    rows = []
    for row in ws.iter_rows(min_row=7, max_row=400, values_only=True):
        if not row or len(row) < 9:
            continue
        ep = row[0]
        if not ep or ep not in SHOCK_MONTHS:
            continue
        if row[7] != "Selected":
            continue
        country_raw = row[2]
        if not country_raw:
            continue
        country = COUNTRY_MAP.get(country_raw, country_raw)
        signed_jump = row[6]
        if signed_jump is None:
            continue
        rows.append(
            {
                "episode": ep,
                "shock_month": SHOCK_MONTHS[ep],
                "country": country,
                "signed_jump_pp": float(signed_jump),
            }
        )
    return rows


def filter_complete(rows, needed_vars):
    out = []
    for r in rows:
        ok = True
        for v in needed_vars:
            val = r.get(v)
            if val is None or (isinstance(val, float) and math.isnan(val)):
                ok = False
                break
        if ok:
            out.append(r)
    return out


def impute_controls(rows, control_vars):
    country_controls = {
        "inflation_l1",
        "policy_rate_l1",
        "debt_gdp_l1",
        "financial_development_l1",
    }
    imputations = {v: 0 for v in control_vars}

    global_medians = {}
    for v in control_vars:
        vals = [r[v] for r in rows if r.get(v) is not None and not math.isnan(r[v])]
        global_medians[v] = float(np.median(vals)) if vals else 0.0

    country_medians = {v: {} for v in control_vars if v in country_controls}
    countries = sorted({r["country"] for r in rows})
    for v in country_medians.keys():
        for c in countries:
            vals = [r[v] for r in rows if r["country"] == c and r.get(v) is not None and not math.isnan(r[v])]
            country_medians[v][c] = float(np.median(vals)) if vals else global_medians[v]

    for r in rows:
        for v in control_vars:
            if r.get(v) is None or (isinstance(r.get(v), float) and math.isnan(r[v])):
                if v in country_medians:
                    r[v] = country_medians[v].get(r["country"], global_medians[v])
                else:
                    r[v] = global_medians[v]
                imputations[v] += 1
    return imputations


def fit_ols_cluster(rows, rhs_vars, target_var="y"):
    countries = sorted({r["country"] for r in rows})
    if len(countries) < 2:
        return None, "Need at least two countries for FE model."

    y = np.array([r[target_var] for r in rows], dtype=float)
    X_cols = [np.ones(len(rows), dtype=float)]
    names = ["const"]
    for v in rhs_vars:
        X_cols.append(np.array([r[v] for r in rows], dtype=float))
        names.append(v)

    base = countries[0]
    for c in countries[1:]:
        X_cols.append(np.array([1.0 if r["country"] == c else 0.0 for r in rows], dtype=float))
        names.append(f"fe_{c}")

    X = np.column_stack(X_cols)
    n, k = X.shape
    if n <= k:
        return None, f"Insufficient observations (N={n}) for parameter count (k={k})."

    try:
        xtx_inv = np.linalg.inv(X.T @ X)
    except np.linalg.LinAlgError:
        return None, "Design matrix is singular."

    beta = xtx_inv @ (X.T @ y)
    resid = y - (X @ beta)

    clusters = defaultdict(list)
    for i, r in enumerate(rows):
        clusters[r["country"]].append(i)
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
    ci_lo = beta - student_t.ppf(0.975, df=df) * se
    ci_hi = beta + student_t.ppf(0.975, df=df) * se

    sst = float(np.sum((y - np.mean(y)) ** 2))
    sse = float(np.sum(resid**2))
    r2 = float(1 - sse / sst) if sst > 0 else float("nan")

    return {
        "coef": dict(zip(names, beta)),
        "se": dict(zip(names, se)),
        "t": dict(zip(names, tvals)),
        "p": dict(zip(names, pvals)),
        "ci_lo": dict(zip(names, ci_lo)),
        "ci_hi": dict(zip(names, ci_hi)),
        "n_obs": n,
        "n_country": g,
        "k_params": k,
        "df": df,
        "r2": r2,
    }, None


def build_panel():
    fx = read_monthly_country_series("fx_rate.csv", "local_per_usd")
    inflation = read_monthly_country_series("inflation.csv", "value")
    policy = read_monthly_country_series("policy_rate.csv", "value")
    debt = read_annual_country_series("debt_gdp.csv", "period", "debt_gdp_pct")
    fin_dev = read_annual_country_series("financial_development.csv", "year", "fd_fdi_ovrl")
    vix = read_monthly_global_series("vix.csv", "value")
    gepu = read_monthly_global_series("gepu_current.csv", "value")
    inst_raw = carryforward_yearly(read_wgi_composite_yearly(), 2000, 2026)

    selected = read_selected_shocks()
    screened_countries = sorted({r["country"] for r in selected if r["country"] in fx})

    shock_map = defaultdict(list)
    for s in selected:
        shock_map[(s["country"], s["shock_month"])].append(s)

    rows = []
    missing_tracker = defaultdict(int)
    for c in screened_countries:
        for m in sorted(fx[c].keys()):
            d = parse_month(m)
            lag_m = month_str(add_months(d, -1))
            lag_y = add_months(d, -1).year
            fx_t = fx[c].get(m)
            if fx_t is None or fx_t <= 0:
                continue
            y = math.log(fx_t)

            shocks_here = shock_map.get((c, m), [])
            gpr_raw = float(sum(x["signed_jump_pp"] for x in shocks_here)) if shocks_here else 0.0

            vals = {
                "inflation_l1": inflation.get(c, {}).get(lag_m),
                "policy_rate_l1": policy.get(c, {}).get(lag_m),
                "debt_gdp_l1": debt.get(c, {}).get(lag_y),
                "financial_development_l1": fin_dev.get(c, {}).get(lag_y),
                "log_gepu_l1": math.log(gepu.get(lag_m)) if gepu.get(lag_m) is not None and gepu.get(lag_m) > 0 else None,
                "log_vix_l1": math.log(vix.get(lag_m)) if vix.get(lag_m) is not None and vix.get(lag_m) > 0 else None,
                "institution_raw": inst_raw.get(c, {}).get(d.year),
            }
            for k, v in vals.items():
                if v is None:
                    missing_tracker[k] += 1

            row = {
                "country": c,
                "month": m,
                "y": y,
                "gpr_proxy_raw": gpr_raw,
            }
            row.update(vals)
            rows.append(row)

    # standardize gpr within country
    by_country_gpr = defaultdict(list)
    for r in rows:
        by_country_gpr[r["country"]].append(r["gpr_proxy_raw"])
    gpr_stats = {}
    for c, arr in by_country_gpr.items():
        a = np.array(arr, dtype=float)
        gpr_stats[c] = (float(np.mean(a)), float(np.std(a)))
    for r in rows:
        mean, std = gpr_stats[r["country"]]
        r["gpr_proxy_std"] = (r["gpr_proxy_raw"] - mean) / std if std > 0 else 0.0

    # standardize institution pooled (after carryforward)
    inst_vals = [r["institution_raw"] for r in rows if r["institution_raw"] is not None]
    inst_mean = float(np.mean(inst_vals)) if inst_vals else 0.0
    inst_std = float(np.std(inst_vals)) if inst_vals else 1.0
    if inst_std == 0:
        inst_std = 1.0
    for r in rows:
        if r["institution_raw"] is None:
            r["institution_std"] = None
        else:
            r["institution_std"] = (r["institution_raw"] - inst_mean) / inst_std
        if r["gpr_proxy_raw"] is not None and r["institution_std"] is not None:
            r["gpr_x_institution"] = r["gpr_proxy_raw"] * r["institution_std"]
        else:
            r["gpr_x_institution"] = None

    meta = {
        "n_rows": len(rows),
        "n_screened_countries": len(screened_countries),
        "n_selected_country_episode": len(selected),
        "missing_tracker": dict(sorted(missing_tracker.items())),
    }
    return rows, meta


def run():
    rows, meta = build_panel()

    controls = [
        "inflation_l1",
        "policy_rate_l1",
        "debt_gdp_l1",
        "financial_development_l1",
        "log_gepu_l1",
        "log_vix_l1",
    ]
    imputation_counts = impute_controls(rows, controls)

    # institution should be carried-forward and then available; if still missing, impute median
    inst_vals = [r["institution_std"] for r in rows if r["institution_std"] is not None]
    inst_med = float(np.median(inst_vals)) if inst_vals else 0.0
    inst_imputed = 0
    for r in rows:
        if r["institution_std"] is None or (isinstance(r["institution_std"], float) and math.isnan(r["institution_std"])):
            r["institution_std"] = inst_med
            inst_imputed += 1
        if r["gpr_proxy_raw"] is None:
            r["gpr_proxy_raw"] = 0.0
        r["gpr_x_institution"] = r["gpr_proxy_raw"] * r["institution_std"]

    rhs = ["gpr_proxy_raw", "institution_std"] + controls
    sample = filter_complete(rows, rhs)
    fit, err = fit_ols_cluster(sample, rhs)

    csv_path = os.path.join(OUTPUT_DIR, "replicate_gpr_fx_model_institution_no_interaction_results.csv")
    html_path = os.path.join(OUTPUT_DIR, "replicate_gpr_fx_model_institution_no_interaction_results.html")

    if err:
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["status", "error"])
            w.writerow(["failed", err])
        with open(html_path, "w", encoding="utf-8") as f:
            f.write("<html><body><h1>Institution-augmented model failed</h1>")
            f.write(f"<p>{escape(err)}</p></body></html>")
        print("Generated with failure note:")
        print(html_path)
        print(csv_path)
        return

    key_vars = ["gpr_proxy_raw", "institution_std"]
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "variable",
                "coef",
                "se",
                "t",
                "p",
                "ci95_lo",
                "ci95_hi",
                "significance",
                "n_obs",
                "n_country",
                "k_params",
                "r2",
            ]
        )
        for v in key_vars:
            p = float(fit["p"][v])
            w.writerow(
                [
                    v,
                    fit["coef"][v],
                    fit["se"][v],
                    fit["t"][v],
                    p,
                    fit["ci_lo"][v],
                    fit["ci_hi"][v],
                    stars(p),
                    fit["n_obs"],
                    fit["n_country"],
                    fit["k_params"],
                    fit["r2"],
                ]
            )

    with open(html_path, "w", encoding="utf-8") as f:
        f.write("<!doctype html><html lang='en'><head><meta charset='utf-8'>")
        f.write("<title>S2 + institution (no interaction) results</title>")
        f.write(
            "<style>"
            "body{font:16px/1.5 Georgia,serif;max-width:1150px;margin:2em auto;padding:0 1em;color:#20242a}"
            "table{border-collapse:collapse;width:100%;margin:1em 0;font-size:.92em}"
            "th,td{border-bottom:1px solid #ccc;padding:.45em;text-align:right}"
            "th:first-child,td:first-child{text-align:left}"
            ".note{background:#fff5da;padding:1em;border:1px solid #e6d59d}"
            "</style></head><body>"
        )
        f.write("<h1>New section: S2 extended with institution (no interaction)</h1>")
        f.write("<p>Base model follows S2, extended with a standardized institution term only.</p>")
        f.write("<p><code>y_it = β1·GPR_it + β2·Institution_it + γ'Controls + δ_i + ε_it</code></p>")
        f.write("<ul>")
        f.write("<li><strong>Institution level:</strong> yearly WGI composite (mean across available six dimensions), then carried forward by country for missing years.</li>")
        f.write("<li><strong>Institution standardization:</strong> pooled z-score over the panel.</li>")
        f.write("<li><strong>Controls:</strong> inflation, policy rate, debt/GDP, financial development, log GEPU, log VIX (industrial production excluded).</li>")
        f.write("</ul>")
        f.write(
            "<div class='note'><strong>Missing-data handling:</strong> no rows dropped for control missingness; "
            "controls imputed with country/global medians. Institution missing years are carry-forwarded first, then any residual missing uses median imputation.</div>"
        )

        f.write("<h2>Results (key terms)</h2>")
        f.write(
            "<table><thead><tr><th>Variable</th><th>Coefficient</th><th>SE</th><th>t</th><th>p</th><th>95% CI</th></tr></thead><tbody>"
        )
        for v in key_vars:
            p = float(fit["p"][v])
            f.write(
                "<tr>"
                f"<td>{escape(v)}</td>"
                f"<td>{fit['coef'][v]:.6f}{stars(p)}</td>"
                f"<td>{fit['se'][v]:.6f}</td>"
                f"<td>{fit['t'][v]:.3f}</td>"
                f"<td>{p:.4f}</td>"
                f"<td>[{fit['ci_lo'][v]:.6f}, {fit['ci_hi'][v]:.6f}]</td>"
                "</tr>"
            )
        f.write("</tbody></table>")

        f.write("<h2>Main-effect interpretation</h2>")
        p_inst = float(fit["p"]["institution_std"])
        if p_inst < 0.10:
            f.write(
                f"<p><strong>Institution main effect is statistically meaningful</strong> (p={p_inst:.4f}).</p>"
            )
        else:
            f.write(
                f"<p><strong>Institution main effect is not statistically significant</strong> at conventional levels (p={p_inst:.4f}).</p>"
            )

        f.write("<h2>Sample and diagnostics</h2>")
        f.write("<ul>")
        f.write(f"<li>Rows used: {fit['n_obs']}</li>")
        f.write(f"<li>Countries: {fit['n_country']}</li>")
        f.write(f"<li>Parameters: {fit['k_params']}</li>")
        f.write(f"<li>R²: {fit['r2']:.4f}</li>")
        f.write(f"<li>Initial panel rows: {meta['n_rows']}</li>")
        f.write(f"<li>Selected country-episode shocks: {meta['n_selected_country_episode']}</li>")
        f.write("</ul>")

        f.write("<h3>Control imputation counts</h3>")
        f.write("<table><thead><tr><th>Variable</th><th>Imputed rows</th></tr></thead><tbody>")
        for k, v in imputation_counts.items():
            f.write(f"<tr><td>{escape(k)}</td><td>{v}</td></tr>")
        f.write(f"<tr><td>institution_std</td><td>{inst_imputed}</td></tr>")
        f.write("</tbody></table>")
        f.write("</body></html>")

    print("Generated:")
    print(html_path)
    print(csv_path)
    print("Institution main-effect p-value:", fit["p"]["institution_std"])


if __name__ == "__main__":
    run()
