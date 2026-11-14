import csv
import math
import os
import sys
from collections import defaultdict
from html import escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_equation1_six_institution_aspects as eq1


INFL_CSV = os.path.join(eq1.ROOT, "cleaned", "inflation.csv")
IP_CSV = os.path.join(eq1.ROOT, "cleaned", "industrial_production.csv")
OUT_HTML = os.path.join(eq1.OUT_DIR, "equation2_equation3_inflation_rgdp_channels.html")
OUT_CSV = os.path.join(eq1.OUT_DIR, "equation2_equation3_inflation_rgdp_channels.csv")

CONTROLS = [
    "rate_l1",
    "infl_l1",
    "ln_oil_l1",
    "ln_vix_l1",
    "ln_gepu_l1",
    "fd_l1",
    "cbi_l1",
    "debt_l1",
]
RHS = ["inst_z_l1", "gpr_z", "gpr_x_inst"] + CONTROLS

COUNTRY_ALIASES = {
    "Korea": "South Korea",
    "Türkiye": "Turkey",
    "T�rkiye": "Turkey",
}


def present(v):
    return v is not None and not (isinstance(v, float) and v != v)


def month_gap(a, b):
    return (b.year - a.year) * 12 + (b.month - a.month)


def add_d_ln_reer(panel):
    by_iso = defaultdict(list)
    for row in panel:
        by_iso[row["iso"]].append(row)
    for rows in by_iso.values():
        rows.sort(key=lambda x: x["date"])
        prev_val = None
        prev_date = None
        for row in rows:
            row["d_ln_reer"] = None
            if (
                prev_val is not None
                and present(row.get("ln_reer"))
                and prev_date is not None
                and month_gap(prev_date, row["date"]) == 1
            ):
                row["d_ln_reer"] = row["ln_reer"] - prev_val
            if present(row.get("ln_reer")):
                prev_val = row["ln_reer"]
                prev_date = row["date"]


def load_monthly_inflation():
    out = defaultdict(dict)
    with open(INFL_CSV, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            country = (row.get("country") or "").strip()
            ym = (row.get("year_month") or "").strip()
            val = eq1.to_float(row.get("value"))
            if country and ym and val is not None:
                out[country][ym] = val
    return out


def load_rgdp_growth_proxy():
    annual = defaultdict(dict)
    with open(IP_CSV, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            country = (row.get("country") or "").strip()
            year_txt = (row.get("year") or "").strip()
            idx = eq1.to_float(row.get("index"))
            if not country or not year_txt or idx is None:
                continue
            try:
                year = int(year_txt)
            except ValueError:
                continue
            annual[country][year] = idx

    growth = defaultdict(dict)
    for country, ymap in annual.items():
        years = sorted(ymap)
        prev = None
        for y in years:
            cur = ymap[y]
            if prev is not None and prev > 0 and cur > 0:
                growth[country][y] = math.log(cur) - math.log(prev)
            prev = cur
    return growth


def load_target_10_panel():
    _, screened_isos, _ = eq1.load_screened_country_set()
    panel_iso_set = set(eq1.load_panel_iso_universe())
    candidate = sorted(iso for iso in screened_isos if iso in panel_iso_set)
    panel = eq1.load_panel(set(candidate))
    # baseline 10-country set used in equation-1 baseline tables
    target = sorted({r["iso"] for r in panel if present(r.get("y_ln_reer"))})
    panel = [r for r in panel if r["iso"] in target]
    add_d_ln_reer(panel)
    return panel, target


def attach_channel_variables(rows, infl_map, rgdp_map):
    for row in rows:
        country = row["country"]
        alt_country = COUNTRY_ALIASES.get(country, country)
        ym = row["month"]
        y = row["year"]
        row["y_infl"] = None
        row["y_rgdp"] = None
        for name in (country, alt_country):
            if row["y_infl"] is None:
                row["y_infl"] = infl_map.get(name, {}).get(ym)
            if row["y_rgdp"] is None:
                row["y_rgdp"] = rgdp_map.get(name, {}).get(y)


def fit_cell(fit, term):
    p = float(fit["p"][term])
    return (
        f"{float(fit['coef'][term]):.4f}{eq1.stars(p)}"
        f"<br><span class='se'>({float(fit['se'][term]):.4f})</span>"
        f"<br><span class='ci'>[{float(fit['ci_lo'][term]):.4f}, {float(fit['ci_hi'][term]):.4f}]</span>"
    )


def write_csv(rows):
    fields = [
        "aspect",
        "aspect_label",
        "stage",
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
        "r2",
        "error",
    ]
    with open(OUT_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def write_html(payload):
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write("<!doctype html><html lang='en'><head><meta charset='utf-8'>")
        f.write("<title>Equation 2/3 channels: inflation and real-GDP proxy</title>")
        f.write(
            "<style>"
            "body{font:16px/1.5 Georgia,serif;max-width:1280px;margin:2em auto;padding:0 1em;color:#20242a}"
            "table{border-collapse:collapse;width:100%;margin:1em 0;font-size:.9em}"
            "th,td{border-bottom:1px solid #ccc;padding:.45em;text-align:right;vertical-align:top}"
            "th:first-child,td:first-child,td.left{text-align:left}"
            ".note{background:#fff5da;padding:1em;border:1px solid #e6d59d}"
            ".warn{background:#ffe6e6;padding:.8em;border:1px solid #e0a7a7}"
            ".se{color:#555}.ci{color:#555;font-size:.9em}"
            "code{font-size:.92em}"
            "</style></head><body>"
        )
        f.write("<h1>Equation (2)/(3) rework: inflation and real-GDP channels</h1>")
        f.write(
            "<div class='note'>"
            "<strong>Sample:</strong> 10-country baseline set from equation-1 tables: "
            f"{escape(', '.join(payload['target_countries']))}. "
            "<strong>WGI standardization:</strong> same as GPR method, within country "
            "<code>(x - country mean) / sample SD</code> (ddof=1)."
            "</div>"
        )
        f.write(
            "<p><strong>Stage 1 channel models</strong> (for each WGI aspect): "
            "<code>channel_it = α + β1·IQ_i,t-1 + β2·GPR_it + β3·(GPR_it×IQ_i,t-1) + ν'Controls_i,t-1 + δ_i + ε_it</code>, "
            "with channels = inflation and real-GDP proxy growth. "
            "<strong>Stage 2</strong>: "
            "<code>Δln(REER_it) = α + γ1·ε̂_infl,it + γ2·ε̂_rgdp,it</code>."
            "</p>"
        )
        f.write(
            "<div class='warn'>"
            "Real-GDP channel uses annual industrial production growth proxy (Δln annual index) repeated within year, "
            "because monthly real GDP is not available in cleaned data. "
            f"Effective overlap window is {escape(payload['month_min'] or 'n/a')} to {escape(payload['month_max'] or 'n/a')}."
            "</div>"
        )

        f.write("<h2>Coverage by country in stage-1 samples</h2>")
        f.write("<table><thead><tr><th>Country</th><th>ISO</th><th>Inflation sample rows</th><th>RGDP proxy sample rows</th></tr></thead><tbody>")
        for row in payload["coverage"]:
            f.write(
                "<tr>"
                f"<td class='left'>{escape(row['country'])}</td>"
                f"<td>{escape(row['iso'])}</td>"
                f"<td>{row['infl_n']}</td>"
                f"<td>{row['rgdp_n']}</td>"
                "</tr>"
            )
        f.write("</tbody></table>")

        f.write("<h2>Stage 1A: Inflation channel regressions (Equation 2 with Y = inflation)</h2>")
        f.write("<table><thead><tr><th>Aspect</th><th>IQ</th><th>GPR</th><th>GPR × IQ</th><th>N</th><th>Countries</th><th>R²</th></tr></thead><tbody>")
        for r in payload["results"]:
            fit = r.get("fit_infl")
            if not fit:
                f.write(f"<tr><td class='left'>{escape(r['aspect_label'])}</td><td class='left' colspan='6'>{escape(r.get('err_infl') or 'Not estimated')}</td></tr>")
                continue
            f.write(
                "<tr>"
                f"<td class='left'>{escape(r['aspect_label'])}</td>"
                f"<td>{fit_cell(fit, 'inst_z_l1')}</td>"
                f"<td>{fit_cell(fit, 'gpr_z')}</td>"
                f"<td>{fit_cell(fit, 'gpr_x_inst')}</td>"
                f"<td>{fit['n_obs']}</td><td>{fit['n_country']}</td><td>{fit['r2']:.3f}</td>"
                "</tr>"
            )
        f.write("</tbody></table>")

        f.write("<h2>Stage 1B: Real-GDP proxy channel regressions (Equation 2 with Y = RGDP proxy)</h2>")
        f.write("<table><thead><tr><th>Aspect</th><th>IQ</th><th>GPR</th><th>GPR × IQ</th><th>N</th><th>Countries</th><th>R²</th></tr></thead><tbody>")
        for r in payload["results"]:
            fit = r.get("fit_rgdp")
            if not fit:
                f.write(f"<tr><td class='left'>{escape(r['aspect_label'])}</td><td class='left' colspan='6'>{escape(r.get('err_rgdp') or 'Not estimated')}</td></tr>")
                continue
            f.write(
                "<tr>"
                f"<td class='left'>{escape(r['aspect_label'])}</td>"
                f"<td>{fit_cell(fit, 'inst_z_l1')}</td>"
                f"<td>{fit_cell(fit, 'gpr_z')}</td>"
                f"<td>{fit_cell(fit, 'gpr_x_inst')}</td>"
                f"<td>{fit['n_obs']}</td><td>{fit['n_country']}</td><td>{fit['r2']:.3f}</td>"
                "</tr>"
            )
        f.write("</tbody></table>")

        f.write("<h2>Stage 2: Δln(REER) on both channel residuals (Equation 3 two-channel test)</h2>")
        f.write("<table><thead><tr><th>Aspect from stage-1</th><th>Residual (inflation)</th><th>Residual (RGDP proxy)</th><th>N</th><th>Countries</th><th>R²</th></tr></thead><tbody>")
        for r in payload["results"]:
            fit = r.get("fit_stage2")
            if not fit:
                f.write(f"<tr><td class='left'>{escape(r['aspect_label'])}</td><td class='left' colspan='5'>{escape(r.get('err_stage2') or 'Not estimated')}</td></tr>")
                continue
            f.write(
                "<tr>"
                f"<td class='left'>{escape(r['aspect_label'])}</td>"
                f"<td>{fit_cell(fit, 'eps_infl')}</td>"
                f"<td>{fit_cell(fit, 'eps_rgdp')}</td>"
                f"<td>{fit['n_obs']}</td><td>{fit['n_country']}</td><td>{fit['r2']:.3f}</td>"
                "</tr>"
            )
        f.write("</tbody></table>")
        f.write("<p><em>Stars:</em> *** p&lt;0.01, ** p&lt;0.05, * p&lt;0.10. SE in parentheses, 95% CI in brackets.</p>")
        f.write("</body></html>")


def main():
    panel, target_isos = load_target_10_panel()
    inst_map = eq1.load_institution_aspect_yearly()
    infl_map = load_monthly_inflation()
    rgdp_map = load_rgdp_growth_proxy()

    results = []
    csv_rows = []
    by_country_infl = defaultdict(int)
    by_country_rgdp = defaultdict(int)
    stage2_months = set()

    for aspect in eq1.ASPECTS:
        rows, _, _, _ = eq1.build_model_data(panel, inst_map, aspect, inst_standardization="within_country")
        attach_channel_variables(rows, infl_map, rgdp_map)

        sample_infl = []
        sample_rgdp = []
        for row in rows:
            if row["iso"] not in target_isos:
                continue
            if present(row.get("y_infl")) and all(present(row.get(v)) for v in RHS):
                sample_infl.append(row)
            if present(row.get("y_rgdp")) and all(present(row.get(v)) for v in RHS):
                sample_rgdp.append(row)

        fit_infl, err_infl = eq1.fit_ols_cluster(sample_infl, RHS, "y_infl", include_fe=True)
        fit_rgdp, err_rgdp = eq1.fit_ols_cluster(sample_rgdp, RHS, "y_rgdp", include_fe=True)

        eps_infl = {}
        eps_rgdp = {}
        if fit_infl:
            for row, resid in zip(sample_infl, fit_infl["resid"]):
                eps_infl[(row["iso"], row["month"])] = float(resid)
                by_country_infl[row["iso"]] += 1
        if fit_rgdp:
            for row, resid in zip(sample_rgdp, fit_rgdp["resid"]):
                eps_rgdp[(row["iso"], row["month"])] = float(resid)
                by_country_rgdp[row["iso"]] += 1

        sample_stage2 = []
        for row in rows:
            key = (row["iso"], row["month"])
            if row["iso"] not in target_isos:
                continue
            if not present(row.get("d_ln_reer")):
                continue
            if key not in eps_infl or key not in eps_rgdp:
                continue
            srow = {"iso": row["iso"], "month": row["month"], "d_ln_reer": row["d_ln_reer"], "eps_infl": eps_infl[key], "eps_rgdp": eps_rgdp[key]}
            sample_stage2.append(srow)
            stage2_months.add(row["month"])

        fit_stage2, err_stage2 = eq1.fit_ols_cluster(sample_stage2, ["eps_infl", "eps_rgdp"], "d_ln_reer", include_fe=False)

        result = {
            "aspect": aspect,
            "aspect_label": eq1.ASPECT_LABELS[aspect],
            "fit_infl": fit_infl,
            "fit_rgdp": fit_rgdp,
            "fit_stage2": fit_stage2,
            "err_infl": err_infl,
            "err_rgdp": err_rgdp,
            "err_stage2": err_stage2,
        }
        results.append(result)

        for stage_name, fit, err, terms in (
            ("eq2_inflation", fit_infl, err_infl, ["inst_z_l1", "gpr_z", "gpr_x_inst"]),
            ("eq2_rgdp_proxy", fit_rgdp, err_rgdp, ["inst_z_l1", "gpr_z", "gpr_x_inst"]),
            ("eq3_two_channel", fit_stage2, err_stage2, ["eps_infl", "eps_rgdp"]),
        ):
            if not fit:
                csv_rows.append(
                    {
                        "aspect": aspect,
                        "aspect_label": eq1.ASPECT_LABELS[aspect],
                        "stage": stage_name,
                        "term": "",
                        "coef": "",
                        "se": "",
                        "p": "",
                        "ci95_lo": "",
                        "ci95_hi": "",
                        "n_obs": len(sample_stage2) if stage_name == "eq3_two_channel" else (len(sample_infl) if stage_name == "eq2_inflation" else len(sample_rgdp)),
                        "n_country": len({r["iso"] for r in sample_stage2}) if stage_name == "eq3_two_channel" else (len({r["iso"] for r in sample_infl}) if stage_name == "eq2_inflation" else len({r["iso"] for r in sample_rgdp})),
                        "month_min": "",
                        "month_max": "",
                        "r2": "",
                        "error": err or "Not estimated",
                    }
                )
                continue
            months = sorted({r["month"] for r in (sample_stage2 if stage_name == "eq3_two_channel" else (sample_infl if stage_name == "eq2_inflation" else sample_rgdp))})
            for term in terms:
                csv_rows.append(
                    {
                        "aspect": aspect,
                        "aspect_label": eq1.ASPECT_LABELS[aspect],
                        "stage": stage_name,
                        "term": term,
                        "coef": float(fit["coef"][term]),
                        "se": float(fit["se"][term]),
                        "p": float(fit["p"][term]),
                        "ci95_lo": float(fit["ci_lo"][term]),
                        "ci95_hi": float(fit["ci_hi"][term]),
                        "n_obs": fit["n_obs"],
                        "n_country": fit["n_country"],
                        "month_min": months[0] if months else "",
                        "month_max": months[-1] if months else "",
                        "r2": float(fit["r2"]),
                        "error": "",
                    }
                )

    coverage = []
    for iso in target_isos:
        coverage.append(
            {
                "country": eq1.ISO_TO_COUNTRY.get(iso, iso),
                "iso": iso,
                "infl_n": by_country_infl.get(iso, 0) // max(len(eq1.ASPECTS), 1),
                "rgdp_n": by_country_rgdp.get(iso, 0) // max(len(eq1.ASPECTS), 1),
            }
        )

    payload = {
        "target_countries": [f"{eq1.ISO_TO_COUNTRY.get(i, i)} ({i})" for i in target_isos],
        "results": results,
        "coverage": coverage,
        "month_min": min(stage2_months) if stage2_months else None,
        "month_max": max(stage2_months) if stage2_months else None,
    }
    write_csv(csv_rows)
    write_html(payload)
    print(OUT_HTML)
    print(OUT_CSV)


if __name__ == "__main__":
    main()

