import csv
import os
from html import escape

import run_equation1_six_institution_aspects as eq1
import run_replication_cleaned_controls_baseline as base
import run_replication_cleaned_table2_col4_wgi6 as wgi6


OUT_CSV = os.path.join(eq1.OUT_DIR, "replication_cleaned_inflation_y_wgi6_results.csv")
OUT_HTML = os.path.join(eq1.OUT_DIR, "replication_cleaned_inflation_y_wgi6_results.html")


def collect_sample(rows, rhs, target):
    out = []
    for r in rows:
        if not base.present(r.get(target)):
            continue
        ok = True
        for v in rhs:
            if not base.present(r.get(v)):
                ok = False
                break
        if ok:
            out.append(r)
    return out


def run_one_aspect(base_rows, wgi_map, aspect):
    rows = [dict(r) for r in base_rows]
    wgi6.build_inst_for_aspect(rows, wgi_map, aspect)
    wgi6.standardize_within_country(rows, "inst_l1", "inst_z_l1")
    for r in rows:
        if base.present(r.get("gpr_z")) and base.present(r.get("inst_z_l1")):
            r["gpr_x_inst"] = r["gpr_z"] * r["inst_z_l1"]
        else:
            r["gpr_x_inst"] = None
        r["y_inflation"] = r.get("infl")

    controls = [c for c in base.CONTROLS if c != "infl_l1"]
    rhs = ["inst_z_l1", "gpr_z", "gpr_x_inst"] + controls
    sample = collect_sample(rows, rhs, "y_inflation")
    fit, err = eq1.fit_ols_cluster(sample, rhs, "y_inflation", include_fe=True)
    months = sorted({r["month"] for r in sample})
    countries = sorted({r["country"] for r in sample})
    return {
        "aspect": aspect,
        "aspect_label": wgi6.ASPECT_LABELS.get(aspect, aspect),
        "rhs": rhs,
        "sample": sample,
        "fit": fit,
        "error": err,
        "month_min": months[0] if months else "",
        "month_max": months[-1] if months else "",
        "countries": countries,
    }


def write_csv(results):
    fields = [
        "aspect",
        "aspect_label",
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
            fit = res["fit"]
            if fit is None:
                w.writerow(
                    {
                        "aspect": res["aspect"],
                        "aspect_label": res["aspect_label"],
                        "term": "",
                        "coef": "",
                        "se": "",
                        "p": "",
                        "ci95_lo": "",
                        "ci95_hi": "",
                        "n_obs": len(res["sample"]),
                        "n_country": len({r["iso"] for r in res["sample"]}),
                        "r2": "",
                        "month_min": res["month_min"],
                        "month_max": res["month_max"],
                        "countries": ", ".join(res["countries"]),
                        "error": res["error"] or "Model failed.",
                    }
                )
                continue
            for term in res["rhs"]:
                w.writerow(
                    {
                        "aspect": res["aspect"],
                        "aspect_label": res["aspect_label"],
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
                        "countries": ", ".join(res["countries"]),
                        "error": "",
                    }
                )


def fmt_cell(fit, term):
    p = float(fit["p"][term])
    return (
        f"{float(fit['coef'][term]):.4f}{eq1.stars(p)}"
        f"<br><span class='se'>({float(fit['se'][term]):.4f})</span>"
        f"<br><span class='ci'>[{float(fit['ci_lo'][term]):.4f}, {float(fit['ci_hi'][term]):.4f}]</span>"
        f"<br><span class='p'>p={p:.4f}</span>"
    )


def write_html(all_rows, results):
    all_countries = sorted({r["country"] for r in all_rows})
    labels = {
        "inst_z_l1": "Institution aspect (z, t-1)",
        "gpr_z": "GPR (country-standardized)",
        "gpr_x_inst": "GPR × Institution interaction",
    }
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write("<!doctype html><html lang='en'><head><meta charset='utf-8'>")
        f.write("<title>Inflation-Y model with WGI interactions (6 aspects)</title>")
        f.write(
            "<style>"
            "body{font:16px/1.5 Georgia,serif;max-width:1200px;margin:2em auto;padding:0 1em;color:#20242a}"
            "table{border-collapse:collapse;width:100%;margin:1em 0;font-size:.92em}"
            "th,td{border-bottom:1px solid #ccc;padding:.45em;text-align:right;vertical-align:top}"
            "th:first-child,td:first-child,td.left{text-align:left}"
            ".note{background:#fff5da;padding:1em;border:1px solid #e6d59d}"
            ".se,.ci,.p{color:#555;font-size:.92em}"
            "</style></head><body>"
        )
        f.write("<h1>New test: Inflation as dependent variable (6 WGI aspects)</h1>")
        f.write(
            "<div class='note'>"
            "<strong>Data for macro/financial variables</strong>: cleaned/replication_cleaned/country_month.csv<br>"
            "<strong>Institution data</strong>: cleaned/wgi.csv<br>"
            "<strong>Dependent variable</strong>: inflation (current month)<br>"
            "<strong>Change requested</strong>: inflation removed from controls and used as Y.<br>"
            "<strong>Specification</strong>: Inflation_it = β1·Inst_z_i,t-1 + β2·GPR_z_it + β3·(GPR_z_it×Inst_z_i,t-1) + γ·X_i,t-1 + δ_i + ε_it.<br>"
            "<strong>Controls retained</strong>: policy rate, ln(IP), ln(oil), ln(VIX), ln(GEPU), FD, CBI, debt/GDP (lagged one month).<br>"
            "<strong>Estimation</strong>: country FE with clustered SE by country."
            "</div>"
        )
        f.write(
            "<table><thead><tr>"
            "<th>Aspect</th><th>N</th><th>Countries</th><th>Window</th>"
            "<th>Inst (z, t-1)</th><th>GPR</th><th>GPR×Inst</th>"
            "</tr></thead><tbody>"
        )
        for res in results:
            fit = res["fit"]
            win = f"{res['month_min']} to {res['month_max']}" if res["month_min"] else ""
            if fit is None:
                f.write(
                    "<tr>"
                    f"<td class='left'>{escape(res['aspect_label'])}</td>"
                    f"<td>{len(res['sample'])}</td>"
                    f"<td>{len({r['iso'] for r in res['sample']})}</td>"
                    f"<td>{escape(win)}</td>"
                    f"<td colspan='3' class='left'>{escape(res['error'] or 'Model failed')}</td>"
                    "</tr>"
                )
                continue
            f.write(
                "<tr>"
                f"<td class='left'>{escape(res['aspect_label'])}</td>"
                f"<td>{fit['n_obs']}</td>"
                f"<td>{fit['n_country']}</td>"
                f"<td>{escape(win)}</td>"
                f"<td>{fmt_cell(fit, 'inst_z_l1')}</td>"
                f"<td>{fmt_cell(fit, 'gpr_z')}</td>"
                f"<td>{fmt_cell(fit, 'gpr_x_inst')}</td>"
                "</tr>"
            )
        f.write("</tbody></table>")

        for idx, res in enumerate(results, start=1):
            fit = res["fit"]
            used_countries = sorted({r["country"] for r in res["sample"]})
            dropped = sorted(set(all_countries) - set(used_countries))
            f.write(f"<h3>Model {idx}: {escape(res['aspect_label'])}</h3>")
            f.write(
                f"<p><strong>Countries used</strong> ({len(used_countries)}): {escape(', '.join(used_countries)) if used_countries else 'none'}<br>"
                f"<strong>Dropped by complete-case + institution availability</strong>: {escape(', '.join(dropped)) if dropped else 'none'}<br>"
                f"<strong>Window</strong>: {escape(res['month_min'])} to {escape(res['month_max'])}</p>"
            )
            if fit is None:
                f.write(f"<p><strong>Model status</strong>: not estimable. {escape(res['error'] or '')}</p>")
                continue
            f.write(f"<p><strong>N</strong>={fit['n_obs']}, <strong>Countries</strong>={fit['n_country']}, <strong>R²</strong>={float(fit['r2']):.4f}</p>")
            f.write("<table><thead><tr><th>Term</th><th>Estimate</th></tr></thead><tbody>")
            for term in ["inst_z_l1", "gpr_z", "gpr_x_inst"] + [c for c in base.CONTROLS if c != "infl_l1"]:
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
    base.standardize_gpr_within_country(rows)
    base.add_lagged_controls(rows)
    wgi_map = wgi6.load_wgi_yearly()
    results = [run_one_aspect(rows, wgi_map, a) for a in wgi6.ASPECTS]
    write_csv(results)
    write_html(rows, results)
    print("Generated:")
    print(OUT_CSV)
    print(OUT_HTML)


if __name__ == "__main__":
    main()
