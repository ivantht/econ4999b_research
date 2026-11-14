import csv
import os
import sys
from collections import defaultdict
from html import escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_equation1_six_institution_aspects as eq1


EXPORT_CSV = (
    r"C:\0 UST CourseWork\ECON4999B\MacroEconResearch_GPR-FX-Institution"
    r"\cleaned\exports_three_category.csv"
)
OUT_HTML = os.path.join(eq1.OUT_DIR, "equation2_equation3_two_stage.html")
OUT_CSV = os.path.join(eq1.OUT_DIR, "equation2_equation3_two_stage.csv")

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
ALL_EXPORT_CATS = [
    "food_agri",
    "crude_ores",
    "fuels",
    "chemicals",
    "machinery_transport",
    "other_manuf_residual",
]


def present(v):
    return v is not None and not (isinstance(v, float) and v != v)


def months_apart(a, b):
    return (b.year - a.year) * 12 + (b.month - a.month)


def country_name(iso):
    return eq1.ISO_TO_COUNTRY.get(iso, iso)


def add_delta_ln_reer(panel):
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
                and months_apart(prev_date, row["date"]) == 1
            ):
                row["d_ln_reer"] = row["ln_reer"] - prev_val
            if present(row.get("ln_reer")):
                prev_val = row["ln_reer"]
                prev_date = row["date"]


def load_export_totals():
    name_to_iso = dict(eq1.SCREENED_COUNTRY_TO_ISO)
    name_to_iso.update(eq1.ARTICLE_COUNTRIES)
    raw = defaultdict(lambda: defaultdict(dict))
    unknown = set()
    with open(EXPORT_CSV, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            name = (row.get("country") or "").strip()
            iso = name_to_iso.get(name)
            if not iso:
                unknown.add(name)
                continue
            ym = (row.get("year_month") or "").strip()
            cat = (row.get("category") or "").strip()
            val = eq1.to_float(row.get("value"))
            if not ym or not cat or val is None:
                continue
            raw[iso][ym][cat] = val

    totals = {}
    baskets = {}
    month_counts = {}
    for iso, months in raw.items():
        n_months = len(months)
        counts = defaultdict(int)
        for cats in months.values():
            for cat in cats:
                counts[cat] += 1
        basket = [c for c in ALL_EXPORT_CATS if counts.get(c) == n_months]
        baskets[iso] = basket
        month_counts[iso] = n_months
        if not basket:
            continue
        for ym, cats in months.items():
            if any(c not in cats for c in basket):
                continue
            totals[(iso, ym)] = sum(cats[c] for c in basket)
    return totals, baskets, month_counts, sorted(unknown)


def complete_case_isos(panel, inst_map):
    by_aspect = {}
    for aspect in eq1.ASPECTS:
        rows, _, _, _ = eq1.build_model_data(
            panel, inst_map, aspect, inst_standardization="within_country"
        )
        isos = set()
        for row in rows:
            if not present(row.get("y_ln_reer")):
                continue
            if all(present(row.get(v)) for v in RHS):
                isos.add(row["iso"])
        by_aspect[aspect] = isos
    common = set.intersection(*by_aspect.values()) if by_aspect else set()
    return common, by_aspect


def fit_cell(fit, name):
    if fit is None or name not in fit["coef"]:
        return ""
    p = float(fit["p"][name])
    return (
        f"{float(fit['coef'][name]):.4f}{eq1.stars(p)}"
        f"<br><span class='se'>({float(fit['se'][name]):.4f})</span>"
        f"<br><span class='ci'>[{float(fit['ci_lo'][name]):.4f}, {float(fit['ci_hi'][name]):.4f}]</span>"
    )


def write_csv(results):
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
        "countries",
        "month_min",
        "month_max",
        "r2",
        "error",
    ]
    with open(OUT_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in results:
            w.writerow(row)


def write_html(payload):
    target = payload["target_countries"]
    dropped = payload["dropped_no_export"]
    used = payload["used_countries"]
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write("<!doctype html><html lang='en'><head><meta charset='utf-8'>")
        f.write("<title>Equations 2 and 3: two-stage export and exchange-rate test</title>")
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
        f.write("<h1>Equations 2 and 3: two-stage test</h1>")
        f.write(
            "<div class='warn'><strong>The requested 10-country, 2000-2023 test cannot be conducted.</strong> "
            "Merchandise-export data are not in this project's cleaned folder. The only located series is "
            f"<code>{escape(EXPORT_CSV)}</code>. It covers Chile, Indonesia, Malaysia, Peru, Philippines, "
            "South Africa, and Thailand, from 2018. Malaysia and Peru are outside the 10-country sample "
            "and are not added. Of the 10 equation-1 countries, only "
            f"{escape(', '.join(used) if used else 'none')} have an export series. "
            f"Dropped for missing exports: {escape(', '.join(dropped) if dropped else 'none')}. "
            "Even for those five countries, the estimable window is "
            f"{escape(payload['month_min'] or 'n/a')} to {escape(payload['month_max'] or 'n/a')}, not 2000-2023. "
            "It ends in January 2022 because lagged financial development in the article replication panel is missing from February 2022. "
            "Later financial-development values in the cleaned file were not substituted, so the controls stay the same as equation 1. "
            "Indonesia, the Philippines, South Africa, and Thailand also have no export observation in January 2018. "
            "The estimates below are a partial overlap test, not the requested full-sample result."
            "</div>"
        )
        f.write("<h2>What is estimated</h2>")
        f.write(
            "<p>Target sample: the equation-1 complete-case countries "
            f"({escape(', '.join(target))}). WGI is standardized within country by the article GPR method: "
            "<code>(x - country mean) / sample SD</code>, with sample standard deviation (<code>ddof=1</code>), "
            "on the lagged monthly institution value over 2000-2023. There is no separate IQ series, so IQ is "
            "that standardized WGI aspect. The interaction uses the same standardized aspect.</p>"
        )
        f.write(
            "<div class='note'><strong>Equation 2</strong>: "
            "<code>ln(Export_it) = α + β1·IQ_i,t-1 + β2·GPR_it + β3·(GPR_it×IQ_i,t-1) + ν'Controls_i,t-1 + δ_i + ε_it</code><br>"
            "<strong>Equation 3</strong>: "
            "<code>Δln(REER_it) = α + β1·ε̂_it</code>, using the equation-2 residual. "
            "Equation 3 has no extra controls and no country fixed effects, matching the written equation. "
            "Both stages use country-clustered standard errors and 95% confidence intervals. "
            "Stars: * 10%, ** 5%, *** 1%.</div>"
        )
        f.write("<h2>Export construction</h2>")
        f.write(
            "<p><code>Export</code> is the sum, in USD millions, of merchandise categories that are present in "
            "every observed month for that country. The regression uses <code>ln(Export)</code>. "
            "A raw export level is not used, because country fixed effects would otherwise be dominated by scale. "
            "The basket is not the same in every country.</p>"
        )
        f.write("<table><thead><tr><th>Country</th><th>ISO</th><th>Status</th><th>Consistent categories</th><th>Months used</th></tr></thead><tbody>")
        for row in payload["coverage"]:
            f.write(
                "<tr>"
                f"<td class='left'>{escape(row['country'])}</td>"
                f"<td>{escape(row['iso'])}</td>"
                f"<td class='left'>{escape(row['status'])}</td>"
                f"<td class='left'>{escape(row['basket'])}</td>"
                f"<td>{escape(row['months'])}</td>"
                "</tr>"
            )
        f.write("</tbody></table>")
        f.write(
            "<p>Chile has no fuels or machinery series, and South Africa has no fuels series. "
            "South Africa's machinery category is also missing in some months, so it is excluded from South Africa's "
            "consistent basket. The export total is therefore a partial goods basket, not a complete merchandise total.</p>"
        )
        f.write("<h2>What the partial test shows</h2><ul>")
        for line in payload["findings"]:
            f.write(f"<li>{line}</li>")
        f.write("</ul>")

        f.write("<h2>Equation 2: ln(export)</h2>")
        f.write(
            "<table><thead><tr><th>Institution aspect (IQ)</th><th>IQ</th><th>GPR</th>"
            "<th>GPR × IQ</th><th>N</th><th>Countries</th><th>R²</th></tr></thead><tbody>"
        )
        for res in payload["stage_results"]:
            if res.get("error"):
                f.write(
                    f"<tr><td class='left'>{escape(res['aspect_label'])}</td>"
                    f"<td class='left' colspan='6'>{escape(res['error'])}</td></tr>"
                )
                continue
            fit = res["stage1"]
            f.write(
                "<tr>"
                f"<td class='left'>{escape(res['aspect_label'])}</td>"
                f"<td>{fit_cell(fit, 'inst_z_l1')}</td>"
                f"<td>{fit_cell(fit, 'gpr_z')}</td>"
                f"<td>{fit_cell(fit, 'gpr_x_inst')}</td>"
                f"<td>{fit['n_obs']}</td>"
                f"<td>{fit['n_country']}</td>"
                f"<td>{fit['r2']:.3f}</td>"
                "</tr>"
            )
        f.write("</tbody></table>")
        f.write("<p>Standard errors are in parentheses. Brackets are 95% confidence intervals. Controls and country fixed effects are included but not shown.</p>")

        f.write("<h2>Equation 3: change in ln(REER) on the equation-2 residual</h2>")
        f.write(
            "<table><thead><tr><th>Institution aspect used in stage 1</th><th>Residual</th>"
            "<th>N</th><th>Countries</th><th>R²</th><th>Significant at 10%?</th></tr></thead><tbody>"
        )
        for res in payload["stage_results"]:
            fit = res.get("stage2")
            if not fit:
                f.write(
                    f"<tr><td class='left'>{escape(res['aspect_label'])}</td>"
                    f"<td class='left' colspan='5'>{escape(res.get('stage2_error') or res.get('error') or 'Not estimated')}</td></tr>"
                )
                continue
            p = float(fit["p"]["eps_hat"])
            f.write(
                "<tr>"
                f"<td class='left'>{escape(res['aspect_label'])}</td>"
                f"<td>{fit_cell(fit, 'eps_hat')}</td>"
                f"<td>{fit['n_obs']}</td>"
                f"<td>{fit['n_country']}</td>"
                f"<td>{fit['r2']:.3f}</td>"
                f"<td>{'Yes' if p < 0.10 else 'No'}</td>"
                "</tr>"
            )
        f.write("</tbody></table>")
        f.write(
            "<p>With five clusters, the country-clustered t distribution has 4 degrees of freedom. "
            "Confidence intervals are wide, and a failure to reject zero is not strong evidence that the residual channel is absent.</p>"
        )

        f.write("<h2>Variable alignment</h2>")
        f.write("<table><thead><tr><th>Requested term</th><th>Data used</th><th>Limitation</th></tr></thead><tbody>")
        for left, mid, right in payload["alignment"]:
            f.write(
                "<tr>"
                f"<td class='left'>{left}</td>"
                f"<td class='left'>{mid}</td>"
                f"<td class='left'>{right}</td>"
                "</tr>"
            )
        f.write("</tbody></table>")
        f.write("</body></html>")


def main():
    if not os.path.exists(EXPORT_CSV):
        raise FileNotFoundError(EXPORT_CSV)

    screened_names, screened_isos, _ = eq1.load_screened_country_set()
    panel_iso_set = set(eq1.load_panel_iso_universe())
    target_isos = sorted(iso for iso in screened_isos if iso in panel_iso_set)
    panel = eq1.load_panel(set(target_isos))
    add_delta_ln_reer(panel)
    inst_map = eq1.load_institution_aspect_yearly()
    common_isos, by_aspect = complete_case_isos(panel, inst_map)
    target_complete = sorted(common_isos)
    totals, baskets, month_counts, unknown_export_names = load_export_totals()

    export_isos = set(baskets)
    used_isos = [iso for iso in target_complete if iso in export_isos]
    dropped_isos = [iso for iso in target_complete if iso not in export_isos]

    stage_results = []
    csv_rows = []
    coverage_counts = {iso: 0 for iso in used_isos}
    month_min = None
    month_max = None

    for aspect in eq1.ASPECTS:
        rows, _, _, _ = eq1.build_model_data(
            panel, inst_map, aspect, inst_standardization="within_country"
        )
        sample = []
        for row in rows:
            if row["iso"] not in used_isos:
                continue
            total = totals.get((row["iso"], row["month"]))
            row["ln_export"] = eq1.safe_log(total)
            if not present(row["ln_export"]) or not present(row.get("d_ln_reer")):
                continue
            if not all(present(row.get(v)) for v in RHS):
                continue
            sample.append(row)

        label = eq1.ASPECT_LABELS[aspect]
        countries = sorted({r["iso"] for r in sample})
        months = sorted({r["month"] for r in sample})
        fit1, err1 = eq1.fit_ols_cluster(sample, RHS, "ln_export", include_fe=True)
        result = {
            "aspect": aspect,
            "aspect_label": label,
            "error": err1,
            "stage1": fit1,
            "stage2": None,
            "stage2_error": None,
        }
        if err1:
            stage_results.append(result)
            csv_rows.append(
                {
                    "aspect": aspect,
                    "aspect_label": label,
                    "stage": "equation2",
                    "term": "",
                    "coef": "",
                    "se": "",
                    "p": "",
                    "ci95_lo": "",
                    "ci95_hi": "",
                    "n_obs": len(sample),
                    "n_country": len(countries),
                    "countries": " ".join(countries),
                    "month_min": months[0] if months else "",
                    "month_max": months[-1] if months else "",
                    "r2": "",
                    "error": err1,
                }
            )
            continue

        for row, resid in zip(sample, fit1["resid"]):
            row["eps_hat"] = float(resid)
            coverage_counts[row["iso"]] = coverage_counts.get(row["iso"], 0) + 1
        if months:
            month_min = months[0] if month_min is None else min(month_min, months[0])
            month_max = months[-1] if month_max is None else max(month_max, months[-1])

        fit2, err2 = eq1.fit_ols_cluster(sample, ["eps_hat"], "d_ln_reer", include_fe=False)
        result["stage2"] = fit2
        result["stage2_error"] = err2
        stage_results.append(result)

        for stage_name, fit, term_names, err in (
            ("equation2", fit1, ["inst_z_l1", "gpr_z", "gpr_x_inst"], None),
            ("equation3", fit2, ["eps_hat"], err2),
        ):
            if fit is None:
                csv_rows.append(
                    {
                        "aspect": aspect,
                        "aspect_label": label,
                        "stage": stage_name,
                        "term": "",
                        "coef": "",
                        "se": "",
                        "p": "",
                        "ci95_lo": "",
                        "ci95_hi": "",
                        "n_obs": len(sample),
                        "n_country": len(countries),
                        "countries": " ".join(countries),
                        "month_min": months[0] if months else "",
                        "month_max": months[-1] if months else "",
                        "r2": "",
                        "error": err or "",
                    }
                )
                continue
            for term in term_names:
                csv_rows.append(
                    {
                        "aspect": aspect,
                        "aspect_label": label,
                        "stage": stage_name,
                        "term": term,
                        "coef": float(fit["coef"][term]),
                        "se": float(fit["se"][term]),
                        "p": float(fit["p"][term]),
                        "ci95_lo": float(fit["ci_lo"][term]),
                        "ci95_hi": float(fit["ci_hi"][term]),
                        "n_obs": fit["n_obs"],
                        "n_country": fit["n_country"],
                        "countries": " ".join(countries),
                        "month_min": months[0],
                        "month_max": months[-1],
                        "r2": fit["r2"],
                        "error": "",
                    }
                )

    coverage = []
    for iso in target_complete:
        if iso in dropped_isos:
            coverage.append(
                {
                    "country": country_name(iso),
                    "iso": iso,
                    "status": "Dropped: no merchandise-export series",
                    "basket": "—",
                    "months": "0",
                }
            )
            continue
        n_used = coverage_counts.get(iso, 0) // len(eq1.ASPECTS)
        coverage.append(
            {
                "country": country_name(iso),
                "iso": iso,
                "status": "Used in the partial test" if n_used else "Export file exists, but no complete regression month",
                "basket": ", ".join(baskets.get(iso, [])) or "—",
                "months": str(n_used),
            }
        )

    alignment = [
        (
            "Equation 2 outcome: Export",
            "ln(sum of consistently available merchandise-export categories), USD millions",
            "Only five of the ten countries, and only January 2018 to January 2022. Baskets differ by country.",
        ),
        (
            "Equation 3 outcome: change in exchange rate",
            "First difference of ln(REER)",
            "REER is used, not a nominal bilateral exchange rate. This is the monthly change, not a shock-window mean.",
        ),
        (
            "IQ and institution",
            "Within-country standardized lagged WGI aspect, one regression for each of six aspects",
            "No separate IQ index is available. IQ and the interaction institution term are the same standardized WGI series.",
        ),
        (
            "GPR",
            "Country-standardized monthly GPR from the article replication panel",
            "The ten target countries are in that panel, so no global GPR proxy is used here.",
        ),
        (
            "Controls",
            "Lagged policy rate, inflation, log oil price, log VIX, log GEPU, financial development, central-bank independence, and debt/GDP",
            "Same controls as the reworked equation 1. Real industrial production remains dropped.",
        ),
        (
            "10-country sample",
            escape(", ".join(country_name(i) + " (" + i + ")" for i in target_complete)),
            "Equation 2 and equation 3 are estimated only for countries with export data.",
        ),
    ]
    if unknown_export_names:
        alignment.append(
            (
                "Unmapped export names",
                escape(", ".join(unknown_export_names)),
                "These names were in the export file but had no ISO mapping.",
            )
        )

    findings = []
    eq2_sig = []
    eq3_sig = []
    for res in stage_results:
        fit1 = res.get("stage1")
        fit2 = res.get("stage2")
        if not fit1 or not fit2:
            findings.append(f"{escape(res['aspect_label'])}: not estimated ({escape(res.get('error') or res.get('stage2_error') or 'unknown error')}).")
            continue
        sig_terms = []
        for term, label in (
            ("inst_z_l1", "IQ"),
            ("gpr_z", "GPR"),
            ("gpr_x_inst", "GPR × IQ"),
        ):
            if float(fit1["p"][term]) < 0.10:
                sig_terms.append(f"{label} (p={float(fit1['p'][term]):.3f})")
        if sig_terms:
            eq2_sig.append(f"{escape(res['aspect_label'])}: {', '.join(sig_terms)}")
        if float(fit2["p"]["eps_hat"]) < 0.10:
            eq3_sig.append(
                f"{escape(res['aspect_label'])} (coef={float(fit2['coef']['eps_hat']):.4f}, p={float(fit2['p']['eps_hat']):.3f})"
            )
    if eq2_sig:
        findings.append("Equation 2 terms significant at 10%: " + "; ".join(eq2_sig) + ".")
    else:
        findings.append("In equation 2, IQ, GPR, and GPR × IQ are not significant at 10% for any of the six aspects.")
    if eq3_sig:
        findings.append(
            "Equation 3 residual is significant at 10% for: " + "; ".join(eq3_sig) + ". None of these reaches 5% in this run."
            if all(float(res["stage2"]["p"]["eps_hat"]) >= 0.05 for res in stage_results if res.get("stage2"))
            else "Equation 3 residual is significant at 10% for: " + "; ".join(eq3_sig) + "."
        )
    else:
        findings.append("Equation 3 residual is not significant at 10% for any aspect.")
    findings.append(
        f"Each estimated regression uses {stage_results[0]['stage1']['n_obs'] if stage_results and stage_results[0].get('stage1') else 'n/a'} "
        "country-months and 5 countries. Clustered inference uses 4 degrees of freedom."
    )

    payload = {
        "target_countries": [f"{country_name(i)} ({i})" for i in target_complete],
        "dropped_no_export": [f"{country_name(i)} ({i})" for i in dropped_isos],
        "used_countries": [f"{country_name(i)} ({i})" for i in used_isos],
        "findings": findings,
        "coverage": coverage,
        "stage_results": stage_results,
        "alignment": alignment,
        "aspect_country_counts": {k: sorted(v) for k, v in by_aspect.items()},
        "screened_names": screened_names,
        "month_min": month_min,
        "month_max": month_max,
        "export_month_counts": month_counts,
    }
    write_csv(csv_rows)
    write_html(payload)
    print("target", payload["target_countries"])
    print("used", payload["used_countries"])
    print("dropped", payload["dropped_no_export"])
    print("window", month_min, month_max)
    for res in stage_results:
        fit1 = res.get("stage1")
        fit2 = res.get("stage2")
        if not fit1 or not fit2:
            print(res["aspect"], "FAILED", res.get("error"), res.get("stage2_error"))
            continue
        print(
            res["aspect"],
            "N",
            fit1["n_obs"],
            "G",
            fit1["n_country"],
            "eq2_int_p",
            round(float(fit1["p"]["gpr_x_inst"]), 4),
            "eq3_p",
            round(float(fit2["p"]["eps_hat"]), 4),
            "eq3_b",
            round(float(fit2["coef"]["eps_hat"]), 4),
        )
    print(OUT_HTML)
    print(OUT_CSV)


if __name__ == "__main__":
    main()
