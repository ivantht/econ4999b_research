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
        shock_type = row[8]
        if signed_jump is None:
            continue
        rows.append(
            {
                "episode": ep,
                "shock_month": SHOCK_MONTHS[ep],
                "country": country,
                "signed_jump_pp": float(signed_jump),
                "shock_type": str(shock_type or "").strip(),
            }
        )
    return rows


def fit_ols_cluster(rows, rhs_vars, target_var="y"):
    countries = sorted({r["country"] for r in rows})
    if len(countries) < 2:
        return None, "Need at least two countries for country fixed effects."

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
        return None, "Need at least two clusters for clustered standard errors."

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

    out = {
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
    }
    return out, None


def build_panel():
    fx = read_monthly_country_series("fx_rate.csv", "local_per_usd")
    inflation = read_monthly_country_series("inflation.csv", "value")
    policy = read_monthly_country_series("policy_rate.csv", "value")
    debt = read_annual_country_series("debt_gdp.csv", "period", "debt_gdp_pct")
    fin_dev = read_annual_country_series("financial_development.csv", "year", "fd_fdi_ovrl")
    vix = read_monthly_global_series("vix.csv", "value")
    gepu = read_monthly_global_series("gepu_current.csv", "value")
    ind_prod = read_annual_country_series("industrial_production.csv", "year", "index")

    selected = read_selected_shocks()
    screened_countries = sorted({r["country"] for r in selected if r["country"] in fx})

    shock_map = defaultdict(list)
    for s in selected:
        c = s["country"]
        m = s["shock_month"]
        shock_map[(c, m)].append(s)

    rows = []
    missing_tracker = defaultdict(int)
    for c in screened_countries:
        months_sorted = sorted(fx[c].keys())
        month_dates = [parse_month(m) for m in months_sorted]
        for d in month_dates:
            m = month_str(d)
            lag_m = month_str(add_months(d, -1))
            lag_y = add_months(d, -1).year
            fx_t = fx[c].get(m)
            if fx_t is None or fx_t <= 0:
                continue
            y_log_fx_level = math.log(fx_t)

            shocks_here = shock_map.get((c, m), [])
            gpr_proxy_raw = float(sum(x["signed_jump_pp"] for x in shocks_here)) if shocks_here else 0.0

            vals = {
                "log_industrial_production_l1": (
                    math.log(ind_prod.get(c, {}).get(lag_y))
                    if ind_prod.get(c, {}).get(lag_y) is not None and ind_prod.get(c, {}).get(lag_y) > 0
                    else None
                ),
                "inflation_l1": inflation.get(c, {}).get(lag_m),
                "policy_rate_l1": policy.get(c, {}).get(lag_m),
                "debt_gdp_l1": debt.get(c, {}).get(lag_y),
                "financial_development_l1": fin_dev.get(c, {}).get(lag_y),
                "log_vix_l1": math.log(vix.get(lag_m)) if vix.get(lag_m) is not None and vix.get(lag_m) > 0 else None,
                "log_gepu_l1": math.log(gepu.get(lag_m)) if gepu.get(lag_m) is not None and gepu.get(lag_m) > 0 else None,
            }
            for k, v in vals.items():
                if v is None:
                    missing_tracker[k] += 1

            row = {
                "country": c,
                "month": m,
                "y": y_log_fx_level,
                "gpr_proxy_raw": gpr_proxy_raw,
            }
            row.update(vals)
            rows.append(row)

    # country-standardized GPR proxy, following paper's country-standardized GPR treatment
    by_country = defaultdict(list)
    for r in rows:
        by_country[r["country"]].append(r["gpr_proxy_raw"])
    stats = {}
    for c, arr in by_country.items():
        a = np.array(arr, dtype=float)
        mean = float(np.mean(a))
        std = float(np.std(a))
        stats[c] = (mean, std)
    for r in rows:
        mean, std = stats[r["country"]]
        if std > 0:
            r["gpr_proxy_std"] = (r["gpr_proxy_raw"] - mean) / std
        else:
            r["gpr_proxy_std"] = None

    meta = {
        "screened_countries": screened_countries,
        "n_shocks_country_episode": len(selected),
        "n_screened_countries": len(screened_countries),
        "missing_tracker": dict(sorted(missing_tracker.items())),
    }
    return rows, meta


def filter_complete(rows, needed_vars):
    out = []
    for r in rows:
        ok = True
        for v in needed_vars:
            if r.get(v) is None or (isinstance(r.get(v), float) and math.isnan(r.get(v))):
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
            was_imputed = 0
            if r.get(v) is None or (isinstance(r.get(v), float) and math.isnan(r[v])):
                if v in country_medians:
                    r[v] = country_medians[v].get(r["country"], global_medians[v])
                else:
                    r[v] = global_medians[v]
                imputations[v] += 1
                was_imputed = 1
            r[f"{v}_imputed"] = was_imputed

    return imputations


def run():
    rows, meta = build_panel()
    full_controls = [
        "inflation_l1",
        "policy_rate_l1",
        "debt_gdp_l1",
        "financial_development_l1",
        "log_gepu_l1",
        "log_vix_l1",
    ]
    for r in rows:
        r["gpr_event_dummy"] = 1.0 if r["gpr_proxy_raw"] > 0 else 0.0
    imputation_counts = impute_controls(rows, full_controls)

    specs = [
        {
            "name": "S1",
            "label": "Standardized GPR proxy + controls (excl. industrial production) + country FE",
            "shock_var": "gpr_proxy_std",
            "controls": full_controls,
        },
        {
            "name": "S2",
            "label": "Raw intensity proxy + controls (excl. industrial production) + country FE",
            "shock_var": "gpr_proxy_raw",
            "controls": full_controls,
        },
        {
            "name": "S3",
            "label": "Binary event-month proxy + controls (excl. industrial production) + country FE",
            "shock_var": "gpr_event_dummy",
            "controls": full_controls,
        },
    ]

    results = []
    limits = []

    for s in specs:
        needed = [s["shock_var"]] + s["controls"]
        sample = filter_complete(rows, needed)
        fit, err = fit_ols_cluster(sample, [s["shock_var"]] + s["controls"])
        if err:
            limits.append(
                {
                    "spec": s["name"],
                    "label": s["label"],
                    "reason": err,
                    "n_after_filter": len(sample),
                }
            )
            continue

        shock = s["shock_var"]
        results.append(
            {
                "spec": s["name"],
                "label": s["label"],
                "shock_var": shock,
                "coef": float(fit["coef"][shock]),
                "se": float(fit["se"][shock]),
                "t": float(fit["t"][shock]),
                "p": float(fit["p"][shock]),
                "ci_lo": float(fit["ci_lo"][shock]),
                "ci_hi": float(fit["ci_hi"][shock]),
                "n_obs": fit["n_obs"],
                "n_country": fit["n_country"],
                "k_params": fit["k_params"],
                "r2": float(fit["r2"]),
                "controls": ";".join(s["controls"]),
            }
        )

    csv_path = os.path.join(OUTPUT_DIR, "replicate_gpr_fx_model_results.csv")
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "spec",
                "label",
                "shock_var",
                "coef",
                "se",
                "t",
                "p",
                "ci95_lo",
                "ci95_hi",
                "n_obs",
                "n_country",
                "k_params",
                "r2",
                "controls",
            ]
        )
        for r in results:
            w.writerow(
                [
                    r["spec"],
                    r["label"],
                    r["shock_var"],
                    r["coef"],
                    r["se"],
                    r["t"],
                    r["p"],
                    r["ci_lo"],
                    r["ci_hi"],
                    r["n_obs"],
                    r["n_country"],
                    r["k_params"],
                    r["r2"],
                    r["controls"],
                ]
            )

    html_path = os.path.join(OUTPUT_DIR, "replicate_gpr_fx_model_results.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write("<!doctype html><html lang='en'><head><meta charset='utf-8'>")
        f.write("<title>Replication: GPR and FX model</title>")
        f.write(
            "<style>"
            "body{font:16px/1.5 Georgia,serif;max-width:1200px;margin:2em auto;padding:0 1em;color:#20242a}"
            "table{border-collapse:collapse;width:100%;margin:1em 0;font-size:.9em}"
            "th,td{border-bottom:1px solid #ccc;padding:.45em;text-align:right}"
            "th:first-child,td:first-child{text-align:left}"
            ".note{background:#fff5da;padding:1em;border:1px solid #e6d59d}"
            ".warn{background:#ffe6e6;padding:.8em;border:1px solid #e0a7a7}"
            "code{font-size:.92em}"
            "</style></head><body>"
        )
        f.write("<h1>Replication of paper-style panel model: exchange-rate level response to geopolitical shocks</h1>")
        f.write(
            "<p>This report follows the panel-regression structure in <code>doc/how GRP affect FX and capital flow.pdf</code>, "
            "but uses repository shocks and screened countries.</p>"
        )
        f.write("<h2>Model used</h2>")
        f.write("<p><code>y_it = β·GPR_it + γ'X_i,t-1 + φ'Z_t-1 + δ_i + ε_it</code></p>")
        f.write("<ul>")
        f.write("<li><code>y_it</code>: log exchange-rate level proxy, <code>ln(local_per_usd_t)</code>, matching the paper's level-log setup for exchange rates.</li>")
        f.write("<li><code>GPR_it</code>: repository shock proxy (event-month signed jump), including country-standardized proxy in paper-style specifications.</li>")
        f.write("<li><code>X_i,t−1</code>: lagged domestic controls available here: log industrial production, inflation, policy rate, debt-to-GDP, financial development.</li>")
        f.write("<li><code>Z_t−1</code>: lagged global controls per paper style: log GEPU and log VIX.</li>")
        f.write("<li><code>δ_i</code>: country fixed effects; SE clustered by country.</li>")
        f.write("</ul>")
        f.write(
            "<div class='note'><strong>Missing-data handling:</strong> no rows are dropped for missing controls. "
            "Industrial production is excluded from controls, and remaining missing controls are imputed "
            "using country-median (country controls) or global-median (global controls) values.</div>"
        )
        f.write(
            "<div class='note'><strong>Alignment note:</strong> The paper uses monthly country GPR index levels and real effective exchange rate. "
            "This repository has shock episodes and bilateral local-per-USD FX; therefore <code>GPR_it</code> and exchange-rate measure are proxies, but the formula structure now matches Equation (2).</div>"
        )

        f.write("<h2>Table: shock coefficient estimates (paper-style summary)</h2>")
        f.write(
            "<table><thead><tr>"
            "<th>Spec</th><th>Shock variable</th><th>β estimate</th><th>SE</th><th>t</th><th>p</th><th>95% CI</th>"
            "<th>N obs</th><th>N countries</th><th>R²</th><th>Controls</th>"
            "</tr></thead><tbody>"
        )
        if results:
            for r in results:
                f.write(
                    "<tr>"
                    f"<td>{escape(r['spec'])}: {escape(r['label'])}</td>"
                    f"<td>{escape(r['shock_var'])}</td>"
                    f"<td>{r['coef']:.4f}{stars(r['p'])}</td>"
                    f"<td>{r['se']:.4f}</td>"
                    f"<td>{r['t']:.3f}</td>"
                    f"<td>{r['p']:.4f}</td>"
                    f"<td>[{r['ci_lo']:.4f}, {r['ci_hi']:.4f}]</td>"
                    f"<td>{r['n_obs']}</td>"
                    f"<td>{r['n_country']}</td>"
                    f"<td>{r['r2']:.4f}</td>"
                    f"<td style='text-align:left'>{escape(r['controls'])}</td>"
                    "</tr>"
                )
        else:
            f.write("<tr><td colspan='11'>No estimable specifications.</td></tr>")
        f.write("</tbody></table>")
        f.write("<p><em>Significance stars:</em> *** p&lt;0.01, ** p&lt;0.05, * p&lt;0.10.</p>")

        f.write("<h2>Sample and data constraints</h2>")
        f.write("<ul>")
        f.write(f"<li>Screened countries in estimation universe: {meta['n_screened_countries']}.</li>")
        f.write(f"<li>Selected country-episode shocks loaded: {meta['n_shocks_country_episode']}.</li>")
        f.write("</ul>")

        f.write("<h3>Missing-control counts (before imputation)</h3>")
        f.write("<table><thead><tr><th>Variable</th><th>Missing rows</th></tr></thead><tbody>")
        for k, v in meta["missing_tracker"].items():
            f.write(f"<tr><td>{escape(k)}</td><td>{v}</td></tr>")
        f.write("</tbody></table>")
        f.write("<h3>Imputation counts applied</h3>")
        f.write("<table><thead><tr><th>Variable</th><th>Imputed rows</th></tr></thead><tbody>")
        for k, v in imputation_counts.items():
            f.write(f"<tr><td>{escape(k)}</td><td>{v}</td></tr>")
        f.write("</tbody></table>")

        f.write("<h3>Non-estimable specifications</h3>")
        if limits:
            f.write("<table><thead><tr><th>Spec</th><th>Rows after filter</th><th>Reason</th></tr></thead><tbody>")
            for l in limits:
                f.write(
                    "<tr>"
                    f"<td>{escape(l['spec'])}: {escape(l['label'])}</td>"
                    f"<td>{l['n_after_filter']}</td>"
                    f"<td style='text-align:left'>{escape(l['reason'])}</td>"
                    "</tr>"
                )
            f.write("</tbody></table>")
        else:
            f.write("<p>All planned specifications were estimable.</p>")

        f.write("</body></html>")

    print("Generated:")
    print(html_path)
    print(csv_path)
    print(f"Estimable specs: {len(results)} | Non-estimable specs: {len(limits)}")
    print(f"Rows used in regressions: {len(rows)} (no row dropping for missing controls)")


if __name__ == "__main__":
    run()
