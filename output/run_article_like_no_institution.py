import csv
import os
import sys
from html import escape
import math
from collections import defaultdict

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_equation1_six_institution_aspects as eq1


OUT_CSV = os.path.join(eq1.OUT_DIR, "article_like_no_institution_results.csv")
OUT_HTML = os.path.join(eq1.OUT_DIR, "article_like_no_institution_results.html")
RAW_GPR_XLS = os.path.join(
    eq1.ROOT,
    "econ4999b_literature_review",
    "replication",
    "raw",
    "gpr_export.xls",
)
INFL_CPI_CALC_CSV = os.path.join(eq1.ROOT, "cleaned", "CPI-calculated inflation.csv")

CONTROLS = [
    "rate_l1",
    "infl_l1",
    "ln_oil_l1",
    "ln_vix_l1",
    "ln_gepu_l1",
    "cbi_l1",
    "debt_l1",
]
RHS = ["gpr_z"] + CONTROLS

ADVANCED = {"BE", "CA", "DK", "FI", "FR", "DE", "IT", "JP", "KR", "NL", "PT", "ES", "SE", "US"}

ISO2_TO_ISO3 = {
    "AR": "ARG",
    "CL": "CHL",
    "EG": "EGY",
    "HU": "HUN",
    "ID": "IDN",
    "IN": "IND",
    "KR": "KOR",
    "MX": "MEX",
    "PE": "PER",
    "PH": "PHL",
    "TH": "THA",
    "TR": "TUR",
    "TW": "TWN",
    "TN": "TUN",
    "UA": "UKR",
    "VN": "VNM",
    "ZA": "ZAF",
}


def present(v):
    return v is not None and not (isinstance(v, float) and v != v)


def load_country_specific_gpr_z():
    # Caldara-Iacoviello country GPR (GPRC_*) standardized within country.
    df = pd.read_excel(RAW_GPR_XLS, engine="xlrd")
    if "month" not in df.columns:
        return {}
    out = {}
    month_vals = pd.to_datetime(df["month"], errors="coerce")
    for iso2, iso3 in ISO2_TO_ISO3.items():
        col = f"GPRC_{iso3}"
        if col not in df.columns:
            continue
        pairs = []
        for d, v in zip(month_vals, df[col]):
            if pd.isna(d) or pd.isna(v):
                continue
            if d.year < eq1.START_YEAR or d.year > eq1.END_YEAR:
                continue
            pairs.append((f"{d.year:04d}-{d.month:02d}", float(v)))
        if len(pairs) < 2:
            continue
        arr = np.array([v for _, v in pairs], dtype=float)
        mean = float(np.mean(arr))
        std = float(np.std(arr, ddof=1))
        if std == 0 or math.isnan(std):
            continue
        for ym, val in pairs:
            out[(iso2, ym)] = (val - mean) / std
    return out


def enforce_country_specific_gpr(panel, gpr_map):
    for row in panel:
        row["gpr_z"] = gpr_map.get((row["iso"], row["month"]))


def load_cpi_calculated_inflation():
    out = defaultdict(dict)
    with open(INFL_CPI_CALC_CSV, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            c = (row.get("country") or "").strip()
            ym = (row.get("year_month") or "").strip()
            v = row.get("value")
            if not c or not ym or v is None or str(v).strip() == "":
                continue
            out[c][ym] = float(v)
    return out


def enforce_cpi_inflation_lag(panel, infl_map):
    aliases = {
        "Korea": "South Korea",
        "Türkiye": "Turkey",
    }
    for row in panel:
        country = row["country"]
        c2 = aliases.get(country, country)
        prev_ym = eq1.month_key(eq1.previous_month(row["date"]))
        row["infl_l1"] = None
        if prev_ym in infl_map.get(country, {}):
            row["infl_l1"] = infl_map[country][prev_ym]
        elif prev_ym in infl_map.get(c2, {}):
            row["infl_l1"] = infl_map[c2][prev_ym]


def collect_complete_case_sample(panel):
    sample = []
    for row in panel:
        if not present(row.get("y_ln_reer")):
            continue
        ok = True
        for var in RHS:
            if not present(row.get(var)):
                ok = False
                break
        if ok:
            sample.append(row)
    return sample


def fit_sample_rows(sample_rows, sample_label, rule):
    fit, err = eq1.fit_ols_cluster(sample_rows, RHS, "y_ln_reer")
    used_isos = sorted({r["iso"] for r in sample_rows})
    used_countries = [eq1.ISO_TO_COUNTRY.get(i, i) for i in used_isos]
    months = sorted({r["month"] for r in sample_rows})
    return {
        "sample_label": sample_label,
        "rule": rule,
        "used_isos": used_isos,
        "used_countries": used_countries,
        "month_min": months[0] if months else "",
        "month_max": months[-1] if months else "",
        "fit": fit,
        "error": err,
        "sample_rows": sample_rows,
    }


def run_one_sample(expanded_target):
    _, screened_isos, _ = eq1.load_screened_country_set()
    panel_isos = set(eq1.load_panel_iso_universe())
    if expanded_target:
        allowed_isos = sorted(set(screened_isos))
        label = "Expanded screened-country sample"
    else:
        allowed_isos = sorted({iso for iso in screened_isos if iso in panel_isos})
        label = "Baseline 10-country sample"
    panel = eq1.load_panel(set(allowed_isos))
    gpr_map = load_country_specific_gpr_z()
    enforce_country_specific_gpr(panel, gpr_map)
    infl_map = load_cpi_calculated_inflation()
    enforce_cpi_inflation_lag(panel, infl_map)
    sample_rows = collect_complete_case_sample(panel)
    out = fit_sample_rows(sample_rows, label, "Full sample")
    out["allowed_isos"] = allowed_isos
    return out


def country_means(sample_rows, varname):
    by_iso = {}
    for row in sample_rows:
        if not present(row.get(varname)):
            continue
        by_iso.setdefault(row["iso"], []).append(float(row[varname]))
    return {iso: float(np.mean(vals)) for iso, vals in by_iso.items() if vals}


def subset_rows_by_iso(sample_rows, iso_set):
    return [r for r in sample_rows if r["iso"] in iso_set]


def build_categorized_results(expanded_sample_rows):
    results = []

    # 1) Emerging vs advanced
    em_isos = sorted({r["iso"] for r in expanded_sample_rows if r["iso"] not in ADVANCED})
    ad_isos = sorted({r["iso"] for r in expanded_sample_rows if r["iso"] in ADVANCED})
    results.append(
        fit_sample_rows(
            subset_rows_by_iso(expanded_sample_rows, set(em_isos)),
            "Emerging economies",
            "Paper Table 3 rule: non-advanced economies",
        )
    )
    results.append(
        fit_sample_rows(
            subset_rows_by_iso(expanded_sample_rows, set(ad_isos)),
            "Advanced economies",
            "Paper Table 3 rule: advanced economies",
        )
    )

    # 2-4) Top/bottom quartile by country averages
    for var, label in [
        ("fd_l1", "Financial development"),
        ("cbi_l1", "Central bank independence"),
        ("debt_l1", "Public debt/GDP"),
    ]:
        means = country_means(expanded_sample_rows, var)
        vals = np.array(list(means.values()), dtype=float) if means else np.array([])
        if len(vals) == 0:
            q25 = None
            q75 = None
            low_isos = []
            high_isos = []
        else:
            q25 = float(np.quantile(vals, 0.25))
            q75 = float(np.quantile(vals, 0.75))
            low_isos = sorted([iso for iso, v in means.items() if v <= q25])
            high_isos = sorted([iso for iso, v in means.items() if v >= q75])

        results.append(
            fit_sample_rows(
                subset_rows_by_iso(expanded_sample_rows, set(high_isos)),
                f"High {label}",
                f"Paper top-25% rule by country mean {var} (threshold >= {q75})",
            )
        )
        results.append(
            fit_sample_rows(
                subset_rows_by_iso(expanded_sample_rows, set(low_isos)),
                f"Low {label}",
                f"Paper bottom-25% rule by country mean {var} (threshold <= {q25})",
            )
        )
    return results


def fmt_cell(fit, term):
    p = float(fit["p"][term])
    return (
        f"{float(fit['coef'][term]):.4f}{eq1.stars(p)}"
        f"<br><span class='se'>({float(fit['se'][term]):.4f})</span>"
        f"<br><span class='ci'>[{float(fit['ci_lo'][term]):.4f}, {float(fit['ci_hi'][term]):.4f}]</span>"
    )


def write_csv(results):
    fields = [
        "sample_label",
        "rule",
        "term",
        "coef",
        "se",
        "p",
        "ci95_lo",
        "ci95_hi",
        "n_obs",
        "n_country",
        "r2",
        "month_min",
        "month_max",
        "countries",
        "error",
    ]
    with open(OUT_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for res in results:
            fit = res.get("fit")
            if fit is None:
                w.writerow(
                    {
                        "sample_label": res["sample_label"],
                        "rule": res["rule"],
                        "error": res.get("error", "Model failed."),
                        "month_min": res["month_min"],
                        "month_max": res["month_max"],
                        "countries": ", ".join(res["used_countries"]),
                    }
                )
                continue
            for term in RHS:
                w.writerow(
                    {
                        "sample_label": res["sample_label"],
                        "rule": res["rule"],
                        "term": term,
                        "coef": float(fit["coef"][term]),
                        "se": float(fit["se"][term]),
                        "p": float(fit["p"][term]),
                        "ci95_lo": float(fit["ci_lo"][term]),
                        "ci95_hi": float(fit["ci_hi"][term]),
                        "n_obs": fit["n_obs"],
                        "n_country": fit["n_country"],
                        "r2": float(fit["r2"]),
                        "month_min": res["month_min"],
                        "month_max": res["month_max"],
                        "countries": ", ".join(res["used_countries"]),
                        "error": "",
                    }
                )


def write_one_table(f, res, idx):
    f.write(f"<h2>Table {idx}. {escape(res['sample_label'])}</h2>")
    f.write(f"<p><strong>Rule</strong>: {escape(res['rule'])}</p>")
    if res.get("fit") is None:
        f.write(
            "<div class='warn'>Model could not be estimated: "
            f"{escape(res.get('error') or 'Unknown error')}.</div>"
        )
        return
    fit = res["fit"]
    f.write(
        "<p><strong>Countries used</strong>: "
        f"{escape(', '.join(res['used_countries']))}<br>"
        f"<strong>Effective window</strong>: {escape(res['month_min'])} to {escape(res['month_max'])}<br>"
        f"<strong>N</strong>={fit['n_obs']}, <strong>Countries</strong>={fit['n_country']}, <strong>R²</strong>={float(fit['r2']):.4f}</p>"
    )
    f.write("<table><thead><tr><th>Term</th><th>Estimate</th></tr></thead><tbody>")
    labels = {
        "gpr_z": "GPR (standardized)",
        "rate_l1": "Policy rate (t-1)",
        "infl_l1": "Inflation from CPI-calculated series (t-1)",
        "ln_oil_l1": "ln(Oil) (t-1)",
        "ln_vix_l1": "ln(VIX) (t-1)",
        "ln_gepu_l1": "ln(GEPU) (t-1)",
        "cbi_l1": "Central bank independence (t-1)",
        "debt_l1": "Debt/GDP (t-1)",
    }
    for term in RHS:
        f.write(
            "<tr>"
            f"<td class='left'>{escape(labels.get(term, term))}</td>"
            f"<td>{fmt_cell(fit, term)}</td>"
            "</tr>"
        )
    f.write("</tbody></table>")


def write_html(main_results, categorized_results):
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write("<!doctype html><html lang='en'><head><meta charset='utf-8'>")
        f.write("<title>Article-like model (no institution)</title>")
        f.write(
            "<style>"
            "body{font:16px/1.5 Georgia,serif;max-width:1300px;margin:2em auto;padding:0 1em;color:#20242a}"
            "table{border-collapse:collapse;width:100%;margin:1em 0;font-size:.9em}"
            "th,td{border-bottom:1px solid #ccc;padding:.45em;text-align:right;vertical-align:top}"
            "th:first-child,td:first-child,td.left{text-align:left}"
            ".note{background:#fff5da;padding:1em;border:1px solid #e6d59d}"
            ".warn{background:#ffe6e6;padding:.8em;border:1px solid #e0a7a7}"
            ".se{color:#555}.ci{color:#555;font-size:.9em}"
            "</style></head><body>"
        )
        f.write("<h1>Article-like replication model using project data (no institution terms)</h1>")
        f.write(
            "<div class='note'>"
            "<strong>Specification</strong>: "
            "<code>ln(REER_it) = α + β·GPR_z_it + ν'Controls_i,t-1 + δ_i + ε_it</code><br>"
            "<strong>GPR source</strong>: country-specific Caldara-Iacoviello series "
            "<code>GPRC_*</code> from <code>replication/raw/gpr_export.xls</code>, standardized within country "
            "(mean 0, sample SD 1).<br>"
            "<strong>Controls</strong>: policy rate, ln(oil), ln(VIX), ln(GEPU), CBI, debt/GDP (all lagged where applicable).<br>"
            "<strong>Inflation control source</strong>: <code>cleaned/CPI-calculated inflation.csv</code>, "
            "with <code>infl_l1</code> backed out from CPI as "
            "<code>((CPI_t - CPI_t-12) / CPI_t-12) * 100</code> and then lagged one month in the regression.<br>"
            "<strong>Frequency</strong>: monthly; <strong>window</strong>: 2000-01 to 2023-12.<br>"
            "<strong>Fixed effects</strong>: country FE; <strong>SE</strong>: clustered by country."
            "</div>"
        )
        f.write("<p>Institution level and interaction terms are intentionally excluded as requested.</p>")

        idx = 1
        for res in main_results:
            write_one_table(f, res, idx)
            idx += 1

        f.write("<h2>Paper-rule categorized regressions (applied to expanded sample)</h2>")
        f.write(
            "<p>Applied rules from the article: Emerging vs Advanced; "
            "and top/bottom 25% for financial development, central bank independence, and public debt. "
            "Top/bottom 25% are implemented using country-mean levels within the expanded complete-case sample.</p>"
        )
        for res in categorized_results:
            write_one_table(f, res, idx)
            idx += 1

        f.write("</body></html>")


def main():
    baseline = run_one_sample(expanded_target=False)
    expanded = run_one_sample(expanded_target=True)
    categorized = build_categorized_results(expanded["sample_rows"])
    all_results = [baseline, expanded] + categorized
    write_csv(all_results)
    write_html([baseline, expanded], categorized)
    print("Generated:")
    print(OUT_CSV)
    print(OUT_HTML)


if __name__ == "__main__":
    main()
