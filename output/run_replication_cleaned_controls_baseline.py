import csv
import math
import os
from collections import defaultdict
from datetime import date
from html import escape

import numpy as np

import run_equation1_six_institution_aspects as eq1


IN_CSV = os.path.join(eq1.ROOT, "cleaned", "replication_cleaned", "country_month.csv")
OUT_CSV = os.path.join(eq1.OUT_DIR, "replication_cleaned_controls_baseline_results.csv")
OUT_HTML = os.path.join(eq1.OUT_DIR, "replication_cleaned_controls_baseline_results.html")

SAMPLE_START_YEAR = 2000
SAMPLE_END_YEAR = 2023

CONTROLS = [
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
RHS = ["gpr_z"] + CONTROLS


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


def safe_log(v):
    if v is None or v <= 0:
        return None
    return math.log(v)


def parse_date(s):
    y, m, _ = str(s).split("-")
    return date(int(y), int(m), 1)


def prev_month(d):
    y, m = d.year, d.month - 1
    if m == 0:
        y -= 1
        m = 12
    return date(y, m, 1)


def month_key(d):
    return f"{d.year:04d}-{d.month:02d}"


def present(v):
    return v is not None and not (isinstance(v, float) and v != v)


def load_rows():
    rows = []
    with open(IN_CSV, "r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            iso = (r.get("iso") or "").strip()
            if not iso:
                continue
            d = parse_date(r["date"])
            if d.year < SAMPLE_START_YEAR or d.year > SAMPLE_END_YEAR:
                continue
            rows.append(
                {
                    "iso": iso,
                    "country": (r.get("country") or iso).strip(),
                    "group": (r.get("group") or "").strip(),
                    "date": d,
                    "month": month_key(d),
                    "gpr_raw": to_float(r.get("gpr")),
                    "ln_reer": safe_log(to_float(r.get("reer"))),
                    "rate": to_float(r.get("policy_rate")),
                    "ln_ip": safe_log(to_float(r.get("industrial_production"))),
                    "infl": to_float(r.get("inflation")),
                    "ln_oil": safe_log(to_float(r.get("oil_price"))),
                    "ln_vix": safe_log(to_float(r.get("vix"))),
                    "ln_gepu": safe_log(to_float(r.get("gepu"))),
                    "fd": to_float(r.get("financial_development")),
                    "cbi": to_float(r.get("central_bank_independence")),
                    "debt": to_float(r.get("public_debt_gdp")),
                }
            )
    rows.sort(key=lambda x: (x["iso"], x["date"]))
    return rows


def standardize_gpr_within_country(rows):
    by_iso = defaultdict(list)
    for i, r in enumerate(rows):
        if present(r.get("gpr_raw")):
            by_iso[r["iso"]].append(i)
    for idxs in by_iso.values():
        vals = np.array([rows[i]["gpr_raw"] for i in idxs], dtype=float)
        if len(vals) < 2:
            for i in idxs:
                rows[i]["gpr_z"] = None
            continue
        mu = float(np.mean(vals))
        sd = float(np.std(vals, ddof=1))
        if sd == 0 or math.isnan(sd):
            for i in idxs:
                rows[i]["gpr_z"] = None
            continue
        for i in idxs:
            rows[i]["gpr_z"] = (rows[i]["gpr_raw"] - mu) / sd
    for r in rows:
        if "gpr_z" not in r:
            r["gpr_z"] = None


def add_lagged_controls(rows):
    by_iso_date = {}
    for r in rows:
        by_iso_date[(r["iso"], r["date"])] = r
    for r in rows:
        prev = by_iso_date.get((r["iso"], prev_month(r["date"])))
        r["rate_l1"] = prev["rate"] if prev else None
        r["ln_ip_l1"] = prev["ln_ip"] if prev else None
        r["infl_l1"] = prev["infl"] if prev else None
        r["ln_oil_l1"] = prev["ln_oil"] if prev else None
        r["ln_vix_l1"] = prev["ln_vix"] if prev else None
        r["ln_gepu_l1"] = prev["ln_gepu"] if prev else None
        r["fd_l1"] = prev["fd"] if prev else None
        r["cbi_l1"] = prev["cbi"] if prev else None
        r["debt_l1"] = prev["debt"] if prev else None
        r["y_ln_reer"] = r["ln_reer"]


def collect_sample(rows):
    out = []
    for r in rows:
        if not present(r.get("y_ln_reer")):
            continue
        ok = True
        for v in RHS:
            if not present(r.get(v)):
                ok = False
                break
        if ok:
            out.append(r)
    return out


def write_csv(result_blocks, all_rows):
    all_country_names = sorted({r["country"] for r in all_rows})
    effective_country_names = sorted({r["country"] for r in result_blocks[0].get("sample", [])})
    dropped_country_names = sorted(set(all_country_names) - set(effective_country_names))
    fields = [
        "sample_label",
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
        "target_n_country",
        "target_countries",
        "dropped_n_country",
        "dropped_countries",
        "countries",
        "error",
    ]
    with open(OUT_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for blk in result_blocks:
            fit = blk.get("fit")
            sample = blk.get("sample", [])
            months = sorted({r["month"] for r in sample})
            countries = sorted({r["country"] for r in sample})
            if fit is None:
                w.writerow(
                    {
                        "sample_label": blk["label"],
                        "term": "",
                        "coef": "",
                        "se": "",
                        "p": "",
                        "ci95_lo": "",
                        "ci95_hi": "",
                        "n_obs": len(sample),
                        "n_country": len({r["iso"] for r in sample}),
                        "r2": "",
                        "month_min": months[0] if months else "",
                        "month_max": months[-1] if months else "",
                        "target_n_country": len(all_country_names),
                        "target_countries": ", ".join(all_country_names),
                        "dropped_n_country": len(dropped_country_names),
                        "dropped_countries": ", ".join(dropped_country_names),
                        "countries": ", ".join(countries),
                        "error": blk.get("error", "Model failed."),
                    }
                )
                continue
            for term in RHS:
                w.writerow(
                    {
                        "sample_label": blk["label"],
                        "term": term,
                        "coef": float(fit["coef"][term]),
                        "se": float(fit["se"][term]),
                        "p": float(fit["p"][term]),
                        "ci95_lo": float(fit["ci_lo"][term]),
                        "ci95_hi": float(fit["ci_hi"][term]),
                        "n_obs": fit["n_obs"],
                        "n_country": fit["n_country"],
                        "r2": float(fit["r2"]),
                        "month_min": months[0] if months else "",
                        "month_max": months[-1] if months else "",
                        "target_n_country": len(all_country_names),
                        "target_countries": ", ".join(all_country_names),
                        "dropped_n_country": len(dropped_country_names),
                        "dropped_countries": ", ".join(dropped_country_names),
                        "countries": ", ".join(countries),
                        "error": "",
                    }
                )


def fmt_cell(fit, term):
    p = float(fit["p"][term])
    return (
        f"{float(fit['coef'][term]):.4f}{eq1.stars(p)}"
        f"<br><span class='se'>({float(fit['se'][term]):.4f})</span>"
        f"<br><span class='ci'>[{float(fit['ci_lo'][term]):.4f}, {float(fit['ci_hi'][term]):.4f}]</span>"
    )


def write_html(result_blocks, all_rows):
    labels = {
        "gpr_z": "GPR (country-standardized)",
        "rate_l1": "Policy rate (t-1)",
        "ln_ip_l1": "ln(Real industrial production) (t-1)",
        "infl_l1": "Inflation (t-1)",
        "ln_oil_l1": "ln(Oil) (t-1)",
        "ln_vix_l1": "ln(VIX) (t-1)",
        "ln_gepu_l1": "ln(GEPU) (t-1)",
        "fd_l1": "Financial development (t-1)",
        "cbi_l1": "Central bank independence (t-1)",
        "debt_l1": "Debt/GDP (t-1)",
    }
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write("<!doctype html><html lang='en'><head><meta charset='utf-8'>")
        f.write("<title>Replication-cleaned baseline with controls</title>")
        f.write(
            "<style>"
            "body{font:16px/1.5 Georgia,serif;max-width:1200px;margin:2em auto;padding:0 1em;color:#20242a}"
            "table{border-collapse:collapse;width:100%;margin:1em 0;font-size:.92em}"
            "th,td{border-bottom:1px solid #ccc;padding:.45em;text-align:right;vertical-align:top}"
            "th:first-child,td:first-child,td.left{text-align:left}"
            ".note{background:#fff5da;padding:1em;border:1px solid #e6d59d}"
            ".se{color:#555}.ci{color:#555;font-size:.9em}"
            "</style></head><body>"
        )
        f.write("<h1>Replication-cleaned baseline regression with controls</h1>")
        f.write(
            "<div class='note'>"
            "<strong>Dataset</strong>: cleaned/replication_cleaned/country_month.csv<br>"
            "<strong>Window used</strong>: 2000-01 to 2023-12 (monthly)<br>"
            "<strong>Country universe source</strong>: unique countries directly from this dataset only<br>"
            "<strong>Specification</strong>: <code>ln(REER_it) = β·GPR_z_it + γ·X_i,t-1 + δ_i + ε_it</code><br>"
            "<strong>Controls</strong>: policy rate, ln(IP), inflation, ln(oil), ln(VIX), ln(GEPU), FD, CBI, debt/GDP (lagged one month).<br>"
            "<strong>GPR standardization</strong>: within-country z-score (sample SD, ddof=1).<br>"
            "<strong>Estimation</strong>: country FE with clustered SE by country."
            "</div>"
        )
        all_country_names = sorted({r["country"] for r in all_rows})
        effective_country_names = sorted({r["country"] for r in result_blocks[0].get("sample", [])})
        dropped_country_names = sorted(set(all_country_names) - set(effective_country_names))
        f.write(
            "<p>"
            f"<strong>Target countries ({len(all_country_names)})</strong>: {escape(', '.join(all_country_names))}<br>"
            f"<strong>Dropped by complete-case controls ({len(dropped_country_names)})</strong>: "
            f"{escape(', '.join(dropped_country_names)) if dropped_country_names else 'none'}"
            "</p>"
        )
        for idx, blk in enumerate(result_blocks, start=1):
            sample = blk.get("sample", [])
            fit = blk.get("fit")
            months = sorted({r["month"] for r in sample})
            countries = sorted({r["country"] for r in sample})
            f.write(f"<h2>Table {idx}. {escape(blk['label'])}</h2>")
            f.write(
                f"<p><strong>Countries selected</strong>: {escape(', '.join(countries)) if countries else 'none'}<br>"
                f"<strong>Window</strong>: {escape(months[0] if months else '')} to {escape(months[-1] if months else '')}</p>"
            )
            if fit is None:
                f.write(
                    "<p><strong>Model status</strong>: not estimable. "
                    f"{escape(blk.get('error', 'Unknown error'))}</p>"
                )
                continue
            f.write(
                f"<p><strong>N</strong>={fit['n_obs']}, <strong>Countries</strong>={fit['n_country']}, "
                f"<strong>R²</strong>={float(fit['r2']):.4f}</p>"
            )
            f.write("<table><thead><tr><th>Term</th><th>Estimate</th></tr></thead><tbody>")
            for term in RHS:
                f.write(
                    "<tr>"
                    f"<td class='left'>{escape(labels.get(term, term))}</td>"
                    f"<td>{fmt_cell(fit, term)}</td>"
                    "</tr>"
                )
            f.write("</tbody></table>")
        f.write("</body></html>")


def main():
    rows = load_rows()
    standardize_gpr_within_country(rows)
    add_lagged_controls(rows)
    sample = collect_sample(rows)

    # Full sample
    fit_full, err_full = eq1.fit_ols_cluster(sample, RHS, "y_ln_reer")
    full_block = {"label": "Full sample (with controls)", "sample": sample, "fit": fit_full, "error": err_full}

    # Emerging countries
    emerging_sample = [r for r in sample if (r.get("group") or "").lower() == "emerging"]
    fit_em, err_em = eq1.fit_ols_cluster(emerging_sample, RHS, "y_ln_reer")
    em_block = {"label": "Emerging countries only", "sample": emerging_sample, "fit": fit_em, "error": err_em}

    # Remaining countries (non-emerging / advanced)
    remaining_sample = [r for r in sample if (r.get("group") or "").lower() != "emerging"]
    fit_rm, err_rm = eq1.fit_ols_cluster(remaining_sample, RHS, "y_ln_reer")
    rm_block = {"label": "Remaining countries (non-emerging)", "sample": remaining_sample, "fit": fit_rm, "error": err_rm}

    blocks = [full_block, em_block, rm_block]
    write_csv(blocks, rows)
    write_html(blocks, rows)
    print("Generated:")
    print(OUT_CSV)
    print(OUT_HTML)


if __name__ == "__main__":
    main()
