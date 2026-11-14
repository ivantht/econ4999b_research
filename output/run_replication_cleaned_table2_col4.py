import csv
import os
from html import escape

import run_equation1_six_institution_aspects as eq1
import run_replication_cleaned_controls_baseline as base


OUT_CSV = os.path.join(eq1.OUT_DIR, "replication_cleaned_table2_col4_results.csv")
OUT_HTML = os.path.join(eq1.OUT_DIR, "replication_cleaned_table2_col4_results.html")


def carry_forward_financial_development(rows):
    by_iso = {}
    for r in rows:
        by_iso.setdefault(r["iso"], []).append(r)
    for iso_rows in by_iso.values():
        iso_rows.sort(key=lambda x: x["date"])
        last_fd = None
        for r in iso_rows:
            if base.present(r.get("fd")):
                last_fd = r["fd"]
            elif last_fd is not None:
                r["fd"] = last_fd


def fmt_cell(fit, term):
    p = float(fit["p"][term])
    return (
        f"{float(fit['coef'][term]):.4f}{eq1.stars(p)}"
        f"<br><span class='se'>({float(fit['se'][term]):.4f})</span>"
        f"<br><span class='ci'>[{float(fit['ci_lo'][term]):.4f}, {float(fit['ci_hi'][term]):.4f}]</span>"
        f"<br><span class='p'>p={p:.4f}</span>"
    )


def write_csv(sample, fit, error):
    countries_all = sorted({r["country"] for r in sample})
    months = sorted({r["month"] for r in sample})
    fields = [
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
        if fit is None:
            w.writerow(
                {
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
                    "countries": ", ".join(countries_all),
                    "error": error or "Model failed.",
                }
            )
            return
        for term in base.RHS:
            w.writerow(
                {
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
                    "countries": ", ".join(countries_all),
                    "error": "",
                }
            )


def write_html(all_rows, sample, fit, error):
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
    countries_all = sorted({r["country"] for r in all_rows})
    countries_used = sorted({r["country"] for r in sample})
    dropped = sorted(set(countries_all) - set(countries_used))
    months = sorted({r["month"] for r in sample})

    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write("<!doctype html><html lang='en'><head><meta charset='utf-8'>")
        f.write("<title>Replication-cleaned Table 2 (4)</title>")
        f.write(
            "<style>"
            "body{font:16px/1.5 Georgia,serif;max-width:1100px;margin:2em auto;padding:0 1em;color:#20242a}"
            "table{border-collapse:collapse;width:100%;margin:1em 0;font-size:.92em}"
            "th,td{border-bottom:1px solid #ccc;padding:.45em;text-align:right;vertical-align:top}"
            "th:first-child,td:first-child,td.left{text-align:left}"
            ".note{background:#fff5da;padding:1em;border:1px solid #e6d59d}"
            ".se,.ci,.p{color:#555;font-size:.92em}"
            "</style></head><body>"
        )
        f.write("<h1>Table 2 (4) replication: Exchange rate equation</h1>")
        f.write(
            "<div class='note'>"
            "<strong>Data source</strong>: cleaned/replication_cleaned/country_month.csv only<br>"
            "<strong>Dependent variable</strong>: ln(REER)<br>"
            "<strong>Specification</strong>: <code>ln(REER_it)=β·GPR_z_it+γ·X_i,t-1+δ_i+ε_it</code><br>"
            "<strong>Controls</strong>: policy rate, ln(IP), inflation, ln(oil), ln(VIX), ln(GEPU), FD, CBI, debt/GDP (all lagged one month)<br>"
            "<strong>FD treatment</strong>: missing financial development values are filled by country-level last observation carried forward.<br>"
            "<strong>VIX handling</strong>: raw VIX level in input is log-transformed once, then lagged.<br>"
            "<strong>Estimation</strong>: country FE with clustered SE by country."
            "</div>"
        )
        f.write(
            f"<p><strong>Target countries in file</strong>: {len(countries_all)}<br>"
            f"<strong>Countries used in estimation</strong>: {len(countries_used)}<br>"
            f"<strong>Dropped by complete-case controls</strong>: {escape(', '.join(dropped)) if dropped else 'none'}<br>"
            f"<strong>Estimation window</strong>: {escape(months[0]) if months else ''} to {escape(months[-1]) if months else ''}</p>"
        )
        if fit is None:
            f.write(f"<p><strong>Model status</strong>: not estimable. {escape(error or 'Unknown error')}</p>")
        else:
            f.write(
                f"<p><strong>N</strong>={fit['n_obs']}, <strong>Countries</strong>={fit['n_country']}, "
                f"<strong>R²</strong>={float(fit['r2']):.4f}</p>"
            )
            f.write("<table><thead><tr><th>Term</th><th>Estimate</th></tr></thead><tbody>")
            for term in base.RHS:
                f.write(
                    "<tr>"
                    f"<td class='left'>{escape(labels.get(term, term))}</td>"
                    f"<td>{fmt_cell(fit, term)}</td>"
                    "</tr>"
                )
            f.write("</tbody></table>")
        f.write("</body></html>")


def main():
    rows = base.load_rows()
    carry_forward_financial_development(rows)
    base.standardize_gpr_within_country(rows)
    base.add_lagged_controls(rows)
    sample = base.collect_sample(rows)
    fit, error = eq1.fit_ols_cluster(sample, base.RHS, "y_ln_reer", include_fe=True)
    write_csv(sample, fit, error)
    write_html(rows, sample, fit, error)
    print("Generated:")
    print(OUT_CSV)
    print(OUT_HTML)


if __name__ == "__main__":
    main()
