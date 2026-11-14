import csv
import math
import os
from collections import defaultdict
from html import escape

import numpy as np

import run_equation1_six_institution_aspects as eq1
import run_replication_cleaned_controls_baseline as base


WGI_CSV = os.path.join(eq1.ROOT, "cleaned", "wgi.csv")
OUT_CSV = os.path.join(eq1.OUT_DIR, "replication_cleaned_table2_col4_wgi6_results.csv")
OUT_HTML = os.path.join(eq1.OUT_DIR, "replication_cleaned_table2_col4_wgi6_results.html")

ASPECTS = ["va", "pv", "ge", "rq", "rl", "cc"]
ASPECT_LABELS = {
    "va": "Voice and Accountability",
    "pv": "Political Stability and Absence of Violence/Terrorism",
    "ge": "Government Effectiveness",
    "rq": "Regulatory Quality",
    "rl": "Rule of Law",
    "cc": "Control of Corruption",
}
WGI_COUNTRY_ALIASES = {
    "Korea": "South Korea",
    "Turkiye": "Turkey",
}


def standardize_within_country(rows, value_key, out_key):
    by_iso = defaultdict(list)
    for i, r in enumerate(rows):
        v = r.get(value_key)
        if v is None or (isinstance(v, float) and math.isnan(v)):
            continue
        by_iso[r["iso"]].append(i)
    for idxs in by_iso.values():
        vals = np.array([rows[i][value_key] for i in idxs], dtype=float)
        if len(vals) < 2:
            for i in idxs:
                rows[i][out_key] = None
            continue
        mu = float(np.mean(vals))
        sd = float(np.std(vals, ddof=1))
        if sd == 0 or math.isnan(sd):
            for i in idxs:
                rows[i][out_key] = None
            continue
        for i in idxs:
            rows[i][out_key] = (rows[i][value_key] - mu) / sd
    for r in rows:
        if out_key not in r:
            r[out_key] = None


def load_wgi_yearly():
    out = {}
    with open(WGI_CSV, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            country = (row.get("country") or "").strip()
            dim = (row.get("dimension") or "").strip().lower()
            y = (row.get("year") or "").strip()
            if not country or dim not in ASPECTS:
                continue
            try:
                year = int(y)
            except ValueError:
                continue
            v = base.to_float(row.get("estimate"))
            if v is not None:
                out[(country, year, dim)] = v
    return out


def build_inst_for_aspect(rows, wgi_map, aspect):
    by_iso = defaultdict(list)
    for r in rows:
        by_iso[r["iso"]].append(r)

    for iso_rows in by_iso.values():
        iso_rows.sort(key=lambda x: x["date"])
        country_src = iso_rows[0]["country"] if iso_rows else ""
        country = WGI_COUNTRY_ALIASES.get(country_src, country_src)

        years = sorted({r["date"].year for r in iso_rows})
        yvals = {}
        for y in years:
            yvals[y] = wgi_map.get((country, y, aspect))

        # fill annual gaps within country: forward then backward
        last = None
        for y in years:
            if yvals[y] is not None:
                last = yvals[y]
            elif last is not None:
                yvals[y] = last
        nextv = None
        for y in reversed(years):
            if yvals[y] is not None:
                nextv = yvals[y]
            elif nextv is not None:
                yvals[y] = nextv

        prev_inst = None
        for r in iso_rows:
            y = r["date"].year
            inst_y = yvals.get(y)
            r["inst_raw_year"] = wgi_map.get((country, y, aspect))
            r["inst_filled_year"] = inst_y
            r["inst_l1"] = prev_inst
            if inst_y is not None:
                prev_inst = inst_y


def collect_sample(rows, rhs):
    out = []
    for r in rows:
        if not base.present(r.get("y_ln_reer")):
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
    build_inst_for_aspect(rows, wgi_map, aspect)
    standardize_within_country(rows, "inst_l1", "inst_z_l1")
    for r in rows:
        if base.present(r.get("gpr_z")) and base.present(r.get("inst_z_l1")):
            r["gpr_x_inst"] = r["gpr_z"] * r["inst_z_l1"]
        else:
            r["gpr_x_inst"] = None

    rhs = ["inst_z_l1", "gpr_z", "gpr_x_inst"] + list(base.CONTROLS)
    sample = collect_sample(rows, rhs)
    fit, err = eq1.fit_ols_cluster(sample, rhs, "y_ln_reer", include_fe=True)
    months = sorted({r["month"] for r in sample})
    countries = sorted({r["country"] for r in sample})
    return {
        "aspect": aspect,
        "aspect_label": ASPECT_LABELS.get(aspect, aspect),
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
        f.write("<title>Table 2(4) + institution interaction (6 WGI aspects)</title>")
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
        f.write("<h1>Extended Table 2 (4): Institution and interaction terms</h1>")
        f.write(
            "<div class='note'>"
            "<strong>Data for macro/financial variables</strong>: cleaned/replication_cleaned/country_month.csv<br>"
            "<strong>Institution data</strong>: cleaned/wgi.csv (6 aspects: va, pv, ge, rq, rl, cc)<br>"
            "<strong>Specification</strong>: ln(REER_it)=β1·Inst_z_i,t-1 + β2·GPR_z_it + β3·(GPR_z_it×Inst_z_i,t-1) + γ·X_i,t-1 + δ_i + ε_it<br>"
            "<strong>Institution processing</strong>: yearly values mapped to monthly by country with within-country forward/backward annual fill, then lagged one month and standardized within-country.<br>"
            "<strong>Controls</strong>: same as current Table 2 (4) run (policy rate, ln(IP), inflation, ln(oil), ln(VIX), ln(GEPU), FD, CBI, debt/GDP; lagged one month).<br>"
            "<strong>Estimation</strong>: country FE with clustered SE by country."
            "</div>"
        )

        f.write("<h2>Summary of key terms across six aspects</h2>")
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
            for term in ["inst_z_l1", "gpr_z", "gpr_x_inst"] + list(base.CONTROLS):
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
    wgi_map = load_wgi_yearly()

    results = []
    for a in ASPECTS:
        results.append(run_one_aspect(rows, wgi_map, a))

    write_csv(results)
    write_html(rows, results)
    print("Generated:")
    print(OUT_CSV)
    print(OUT_HTML)


if __name__ == "__main__":
    main()
