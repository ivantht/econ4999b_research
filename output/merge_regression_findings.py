import csv
import os
from html import escape

import run_equation1_six_institution_aspects as eq1
import run_replication_cleaned_controls_baseline as base
import run_replication_cleaned_table2_col4_wgi6 as wgi6
import run_replication_cleaned_inflation_y_wgi6 as infl_y_wgi6


BASELINE_CSV = os.path.join(eq1.OUT_DIR, "replication_cleaned_table2_col4_nofill24_results.csv")
WGI6_CSV = os.path.join(eq1.OUT_DIR, "replication_cleaned_table2_col4_wgi6_results.csv")
INFL_Y_WGI6_CSV = os.path.join(eq1.OUT_DIR, "replication_cleaned_inflation_y_wgi6_results.csv")
OUT_CSV = os.path.join(eq1.OUT_DIR, "replication_cleaned_regression_findings_merged.csv")
OUT_HTML = os.path.join(eq1.OUT_DIR, "replication_cleaned_regression_findings_merged.html")


def to_float(x):
    try:
        return float(x)
    except Exception:
        return None


def stars(p):
    if p is None:
        return ""
    if p < 0.01:
        return "***"
    if p < 0.05:
        return "**"
    if p < 0.10:
        return "*"
    return ""


def read_csv(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def fmt_cell(coef, se, p):
    if coef is None or se is None or p is None:
        return ""
    return f"{coef:.4f}{stars(p)} (SE {se:.4f}, p={p:.4f})"


def main():
    baseline_rows = read_csv(BASELINE_CSV)
    wgi_rows = read_csv(WGI6_CSV)
    infl_y_rows = read_csv(INFL_Y_WGI6_CSV) if os.path.exists(INFL_Y_WGI6_CSV) else []

    baseline_meta = baseline_rows[0] if baseline_rows else {}
    baseline_key_terms = {"gpr_z", "ln_vix_l1", "ln_gepu_l1", "rate_l1", "ln_ip_l1", "infl_l1", "fd_l1", "cbi_l1", "debt_l1"}
    baseline_rows_use = [r for r in baseline_rows if (r.get("term") or "") in baseline_key_terms]

    wgi_key_terms = {"inst_z_l1", "gpr_z", "gpr_x_inst"}
    wgi_rows_use = [r for r in wgi_rows if (r.get("term") or "") in wgi_key_terms]
    infl_rows_use = [r for r in infl_y_rows if (r.get("term") or "") in wgi_key_terms]

    # Additional subgroup runs for merged report (WGI 6-aspect models)
    raw_rows = base.load_rows()
    base.standardize_gpr_within_country(raw_rows)
    base.add_lagged_controls(raw_rows)
    wgi_map = wgi6.load_wgi_yearly()
    rows_em = [r for r in raw_rows if (r.get("group") or "").lower() == "emerging"]
    rows_rm = [r for r in raw_rows if (r.get("group") or "").lower() != "emerging"]
    em_results = [wgi6.run_one_aspect(rows_em, wgi_map, a) for a in wgi6.ASPECTS]
    rm_results = [wgi6.run_one_aspect(rows_rm, wgi_map, a) for a in wgi6.ASPECTS]
    infl_em_results = [infl_y_wgi6.run_one_aspect(rows_em, wgi_map, a) for a in wgi6.ASPECTS]

    merged = []
    for r in baseline_rows_use:
        merged.append(
            {
                "block": "baseline_table2_col4_nofill24",
                "aspect": "",
                "term": r.get("term", ""),
                "coef": r.get("coef", ""),
                "se": r.get("se", ""),
                "p": r.get("p", ""),
                "ci95_lo": r.get("ci95_lo", ""),
                "ci95_hi": r.get("ci95_hi", ""),
                "n_obs": r.get("n_obs", ""),
                "n_country": r.get("n_country", ""),
                "month_min": r.get("month_min", ""),
                "month_max": r.get("month_max", ""),
            }
        )

    for r in wgi_rows_use:
        merged.append(
            {
                "block": "wgi6_interaction",
                "aspect": r.get("aspect", ""),
                "term": r.get("term", ""),
                "coef": r.get("coef", ""),
                "se": r.get("se", ""),
                "p": r.get("p", ""),
                "ci95_lo": r.get("ci95_lo", ""),
                "ci95_hi": r.get("ci95_hi", ""),
                "n_obs": r.get("n_obs", ""),
                "n_country": r.get("n_country", ""),
                "month_min": r.get("month_min", ""),
                "month_max": r.get("month_max", ""),
            }
        )
    for res in em_results:
        fit = res.get("fit")
        if fit is None:
            continue
        for term in ("inst_z_l1", "gpr_z", "gpr_x_inst"):
            merged.append(
                {
                    "block": "wgi6_interaction_emerging",
                    "aspect": res.get("aspect", ""),
                    "term": term,
                    "coef": fit["coef"].get(term, ""),
                    "se": fit["se"].get(term, ""),
                    "p": fit["p"].get(term, ""),
                    "ci95_lo": fit["ci_lo"].get(term, ""),
                    "ci95_hi": fit["ci_hi"].get(term, ""),
                    "n_obs": fit.get("n_obs", ""),
                    "n_country": fit.get("n_country", ""),
                    "month_min": res.get("month_min", ""),
                    "month_max": res.get("month_max", ""),
                }
            )
    for res in rm_results:
        fit = res.get("fit")
        if fit is None:
            continue
        for term in ("inst_z_l1", "gpr_z", "gpr_x_inst"):
            merged.append(
                {
                    "block": "wgi6_interaction_remaining",
                    "aspect": res.get("aspect", ""),
                    "term": term,
                    "coef": fit["coef"].get(term, ""),
                    "se": fit["se"].get(term, ""),
                    "p": fit["p"].get(term, ""),
                    "ci95_lo": fit["ci_lo"].get(term, ""),
                    "ci95_hi": fit["ci_hi"].get(term, ""),
                    "n_obs": fit.get("n_obs", ""),
                    "n_country": fit.get("n_country", ""),
                    "month_min": res.get("month_min", ""),
                    "month_max": res.get("month_max", ""),
                }
            )
    for r in infl_rows_use:
        merged.append(
            {
                "block": "inflation_y_wgi6",
                "aspect": r.get("aspect", ""),
                "term": r.get("term", ""),
                "coef": r.get("coef", ""),
                "se": r.get("se", ""),
                "p": r.get("p", ""),
                "ci95_lo": r.get("ci95_lo", ""),
                "ci95_hi": r.get("ci95_hi", ""),
                "n_obs": r.get("n_obs", ""),
                "n_country": r.get("n_country", ""),
                "month_min": r.get("month_min", ""),
                "month_max": r.get("month_max", ""),
            }
        )
    for res in infl_em_results:
        fit = res.get("fit")
        if fit is None:
            continue
        for term in ("inst_z_l1", "gpr_z", "gpr_x_inst"):
            merged.append(
                {
                    "block": "inflation_y_wgi6_emerging",
                    "aspect": res.get("aspect", ""),
                    "term": term,
                    "coef": fit["coef"].get(term, ""),
                    "se": fit["se"].get(term, ""),
                    "p": fit["p"].get(term, ""),
                    "ci95_lo": fit["ci_lo"].get(term, ""),
                    "ci95_hi": fit["ci_hi"].get(term, ""),
                    "n_obs": fit.get("n_obs", ""),
                    "n_country": fit.get("n_country", ""),
                    "month_min": res.get("month_min", ""),
                    "month_max": res.get("month_max", ""),
                }
            )

    with open(OUT_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "block",
                "aspect",
                "term",
                "coef",
                "se",
                "p",
                "ci95_lo",
                "ci95_hi",
                "n_obs",
                "n_country",
                "month_min",
                "month_max",
            ],
        )
        w.writeheader()
        for r in merged:
            w.writerow(r)

    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write("<!doctype html><html lang='en'><head><meta charset='utf-8'>")
        f.write("<title>Merged regression findings</title>")
        f.write(
            "<style>"
            "body{font:16px/1.5 Georgia,serif;max-width:1200px;margin:2em auto;padding:0 1em;color:#20242a}"
            "table{border-collapse:collapse;width:100%;margin:1em 0;font-size:.92em}"
            "th,td{border-bottom:1px solid #ccc;padding:.45em;text-align:right;vertical-align:top}"
            "th:first-child,td:first-child{text-align:left}"
            ".note{background:#fff5da;padding:1em;border:1px solid #e6d59d}"
            "</style></head><body>"
        )
        f.write("<h1>Merged regression findings</h1>")
        f.write(
            "<div class='note'>"
            "<strong>Baseline block</strong>: Table 2 (4), no FD fill, complete-case 24-country sample.<br>"
            "<strong>Extended block</strong>: six WGI institution-aspect models with institution and GPR×institution terms.<br>"
            "<strong>Additional block</strong>: inflation-as-Y test with inflation removed from controls (6 WGI aspects).<br>"
            "<strong>Source files</strong>: replication_cleaned_table2_col4_nofill24_results.csv, replication_cleaned_table2_col4_wgi6_results.csv, replication_cleaned_inflation_y_wgi6_results.csv."
            "</div>"
        )

        # Baseline section
        f.write("<h2>Section A. Baseline regression findings (Table 2 (4), no FD fill)</h2>")
        f.write(
            f"<p><strong>N</strong>={escape(str(baseline_meta.get('n_obs','')))}, "
            f"<strong>Countries</strong>={escape(str(baseline_meta.get('n_country','')))}, "
            f"<strong>Window</strong>={escape(str(baseline_meta.get('month_min','')))} to {escape(str(baseline_meta.get('month_max','')))}</p>"
        )
        f.write("<table><thead><tr><th>Term</th><th>Estimate</th><th>95% CI</th></tr></thead><tbody>")
        for r in baseline_rows_use:
            coef, se, p = to_float(r.get("coef")), to_float(r.get("se")), to_float(r.get("p"))
            lo, hi = to_float(r.get("ci95_lo")), to_float(r.get("ci95_hi"))
            ci = "" if lo is None or hi is None else f"[{lo:.4f}, {hi:.4f}]"
            f.write(
                "<tr>"
                f"<td>{escape(r.get('term',''))}</td>"
                f"<td>{escape(fmt_cell(coef, se, p))}</td>"
                f"<td>{escape(ci)}</td>"
                "</tr>"
            )
        f.write("</tbody></table>")

        # WGI section
        f.write("<h2>Section B. Extended findings: institution and interaction terms (6 WGI aspects)</h2>")
        f.write(
            "<table><thead><tr>"
            "<th>Aspect</th><th>Inst term</th><th>GPR term</th><th>Interaction term</th><th>N</th><th>Countries</th><th>Window</th>"
            "</tr></thead><tbody>"
        )
        by_aspect = {}
        for r in wgi_rows_use:
            a = r.get("aspect", "")
            by_aspect.setdefault(a, {})[r.get("term", "")] = r
        for aspect in ["va", "pv", "ge", "rq", "rl", "cc"]:
            grp = by_aspect.get(aspect, {})
            ri = grp.get("inst_z_l1", {})
            rg = grp.get("gpr_z", {})
            rx = grp.get("gpr_x_inst", {})
            inst = fmt_cell(to_float(ri.get("coef")), to_float(ri.get("se")), to_float(ri.get("p")))
            gpr = fmt_cell(to_float(rg.get("coef")), to_float(rg.get("se")), to_float(rg.get("p")))
            inter = fmt_cell(to_float(rx.get("coef")), to_float(rx.get("se")), to_float(rx.get("p")))
            n_obs = ri.get("n_obs") or rg.get("n_obs") or rx.get("n_obs") or ""
            n_country = ri.get("n_country") or rg.get("n_country") or rx.get("n_country") or ""
            mmin = ri.get("month_min") or rg.get("month_min") or rx.get("month_min") or ""
            mmax = ri.get("month_max") or rg.get("month_max") or rx.get("month_max") or ""
            f.write(
                "<tr>"
                f"<td>{escape(aspect)}</td>"
                f"<td>{escape(inst)}</td>"
                f"<td>{escape(gpr)}</td>"
                f"<td>{escape(inter)}</td>"
                f"<td>{escape(str(n_obs))}</td>"
                f"<td>{escape(str(n_country))}</td>"
                f"<td>{escape(str(mmin))} to {escape(str(mmax))}</td>"
                "</tr>"
            )
        f.write("</tbody></table>")

        # Emerging table
        f.write("<h2>Section C. Extended findings (Emerging markets)</h2>")
        f.write(
            "<table><thead><tr>"
            "<th>Aspect</th><th>Inst term</th><th>GPR term</th><th>Interaction term</th><th>N</th><th>Countries</th><th>Window</th>"
            "</tr></thead><tbody>"
        )
        for res in em_results:
            fit = res.get("fit")
            if fit is None:
                f.write(
                    "<tr>"
                    f"<td>{escape(res['aspect'])}</td>"
                    f"<td colspan='6'>{escape(res.get('error') or 'Model not estimable')}</td>"
                    "</tr>"
                )
                continue
            f.write(
                "<tr>"
                f"<td>{escape(res['aspect'])}</td>"
                f"<td>{escape(fmt_cell(to_float(fit['coef']['inst_z_l1']), to_float(fit['se']['inst_z_l1']), to_float(fit['p']['inst_z_l1'])))}</td>"
                f"<td>{escape(fmt_cell(to_float(fit['coef']['gpr_z']), to_float(fit['se']['gpr_z']), to_float(fit['p']['gpr_z'])))}</td>"
                f"<td>{escape(fmt_cell(to_float(fit['coef']['gpr_x_inst']), to_float(fit['se']['gpr_x_inst']), to_float(fit['p']['gpr_x_inst'])))}</td>"
                f"<td>{fit['n_obs']}</td>"
                f"<td>{fit['n_country']}</td>"
                f"<td>{escape(res['month_min'])} to {escape(res['month_max'])}</td>"
                "</tr>"
            )
        f.write("</tbody></table>")

        # Remaining table
        f.write("<h2>Section D. Extended findings (Remaining countries)</h2>")
        f.write(
            "<table><thead><tr>"
            "<th>Aspect</th><th>Inst term</th><th>GPR term</th><th>Interaction term</th><th>N</th><th>Countries</th><th>Window</th>"
            "</tr></thead><tbody>"
        )
        for res in rm_results:
            fit = res.get("fit")
            if fit is None:
                f.write(
                    "<tr>"
                    f"<td>{escape(res['aspect'])}</td>"
                    f"<td colspan='6'>{escape(res.get('error') or 'Model not estimable')}</td>"
                    "</tr>"
                )
                continue
            f.write(
                "<tr>"
                f"<td>{escape(res['aspect'])}</td>"
                f"<td>{escape(fmt_cell(to_float(fit['coef']['inst_z_l1']), to_float(fit['se']['inst_z_l1']), to_float(fit['p']['inst_z_l1'])))}</td>"
                f"<td>{escape(fmt_cell(to_float(fit['coef']['gpr_z']), to_float(fit['se']['gpr_z']), to_float(fit['p']['gpr_z'])))}</td>"
                f"<td>{escape(fmt_cell(to_float(fit['coef']['gpr_x_inst']), to_float(fit['se']['gpr_x_inst']), to_float(fit['p']['gpr_x_inst'])))}</td>"
                f"<td>{fit['n_obs']}</td>"
                f"<td>{fit['n_country']}</td>"
                f"<td>{escape(res['month_min'])} to {escape(res['month_max'])}</td>"
                "</tr>"
            )
        f.write("</tbody></table>")

        # Inflation-as-Y table
        f.write("<h2>Section E. New test: Inflation as Y (inflation removed from controls)</h2>")
        f.write(
            "<table><thead><tr>"
            "<th>Aspect</th><th>Inst term</th><th>GPR term</th><th>Interaction term</th><th>N</th><th>Countries</th><th>Window</th>"
            "</tr></thead><tbody>"
        )
        by_aspect_infl = {}
        for r in infl_rows_use:
            a = r.get("aspect", "")
            by_aspect_infl.setdefault(a, {})[r.get("term", "")] = r
        for aspect in ["va", "pv", "ge", "rq", "rl", "cc"]:
            grp = by_aspect_infl.get(aspect, {})
            ri = grp.get("inst_z_l1", {})
            rg = grp.get("gpr_z", {})
            rx = grp.get("gpr_x_inst", {})
            inst = fmt_cell(to_float(ri.get("coef")), to_float(ri.get("se")), to_float(ri.get("p")))
            gpr = fmt_cell(to_float(rg.get("coef")), to_float(rg.get("se")), to_float(rg.get("p")))
            inter = fmt_cell(to_float(rx.get("coef")), to_float(rx.get("se")), to_float(rx.get("p")))
            n_obs = ri.get("n_obs") or rg.get("n_obs") or rx.get("n_obs") or ""
            n_country = ri.get("n_country") or rg.get("n_country") or rx.get("n_country") or ""
            mmin = ri.get("month_min") or rg.get("month_min") or rx.get("month_min") or ""
            mmax = ri.get("month_max") or rg.get("month_max") or rx.get("month_max") or ""
            f.write(
                "<tr>"
                f"<td>{escape(aspect)}</td>"
                f"<td>{escape(inst)}</td>"
                f"<td>{escape(gpr)}</td>"
                f"<td>{escape(inter)}</td>"
                f"<td>{escape(str(n_obs))}</td>"
                f"<td>{escape(str(n_country))}</td>"
                f"<td>{escape(str(mmin))} to {escape(str(mmax))}</td>"
                "</tr>"
            )
        f.write("</tbody></table>")

        # Inflation-as-Y Emerging table
        f.write("<h2>Section F. New test: Inflation as Y (Emerging countries)</h2>")
        f.write(
            "<table><thead><tr>"
            "<th>Aspect</th><th>Inst term</th><th>GPR term</th><th>Interaction term</th><th>N</th><th>Countries</th><th>Window</th>"
            "</tr></thead><tbody>"
        )
        for res in infl_em_results:
            fit = res.get("fit")
            if fit is None:
                f.write(
                    "<tr>"
                    f"<td>{escape(res['aspect'])}</td>"
                    f"<td colspan='6'>{escape(res.get('error') or 'Model not estimable')}</td>"
                    "</tr>"
                )
                continue
            f.write(
                "<tr>"
                f"<td>{escape(res['aspect'])}</td>"
                f"<td>{escape(fmt_cell(to_float(fit['coef']['inst_z_l1']), to_float(fit['se']['inst_z_l1']), to_float(fit['p']['inst_z_l1'])))}</td>"
                f"<td>{escape(fmt_cell(to_float(fit['coef']['gpr_z']), to_float(fit['se']['gpr_z']), to_float(fit['p']['gpr_z'])))}</td>"
                f"<td>{escape(fmt_cell(to_float(fit['coef']['gpr_x_inst']), to_float(fit['se']['gpr_x_inst']), to_float(fit['p']['gpr_x_inst'])))}</td>"
                f"<td>{fit['n_obs']}</td>"
                f"<td>{fit['n_country']}</td>"
                f"<td>{escape(res['month_min'])} to {escape(res['month_max'])}</td>"
                "</tr>"
            )
        f.write("</tbody></table>")
        f.write("</body></html>")

    print("Generated:")
    print(OUT_CSV)
    print(OUT_HTML)


if __name__ == "__main__":
    main()
