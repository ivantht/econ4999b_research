"""Three exchange-rate models with all six WGI dimensions.

Countries are the replication panel except Ukraine and Thailand. Model 1 copies
the paper's log real-exchange-rate controls plus one WGI score and its
interaction with GPR. Model 2 fits the nominal-export log trend on GPR, WGI,
the interaction, lagged log VIX, and lagged industrial-production growth, then
passes the fitted export into the exchange rate. Model 3 fits inflation and the
real-export log trend, passes both into the nominal-export log trend, and
passes that fitted export into the exchange rate.

Nominal exports come from the cleaned Hodrick-Prescott log trend of the monthly
nominal-export workbook. Real exports come from the cleaned Hodrick-Prescott
log trend. The import share is cleaned/import_gdp.csv.
"""

import os

import numpy as np

import run_export_reer_2sls as est
import run_three_fx_models as base


OUTPUT = base.OUTPUT
DIMENSIONS = [
    ("va", "Voice and accountability"),
    ("pv", "Political stability"),
    ("ge", "Government effectiveness"),
    ("rq", "Regulatory quality"),
    ("rl", "Rule of law"),
    ("cc", "Control of corruption"),
]

M1 = [
    "gpr", "wgi_l1", "wgi_x_gpr",
    "policy_rate_l1", "inflation_l1", "log_oil_l1", "log_vix_l1", "log_gepu_l1",
    "financial_development_l1", "debt_gdp_l1",
]
M2_FIRST = ["gpr", "wgi_l1", "wgi_x_gpr", "log_vix_l1", "ip_growth_l1"]
M2_EXCLUDED = ["gpr", "wgi_l1", "wgi_x_gpr", "ip_growth_l1"]
M2_SECOND = [
    "export_trend_hat", "policy_rate_l1", "inflation_l1", "log_oil_l1",
    "log_vix_l1", "log_gepu_l1", "financial_development_l1", "debt_gdp_l1",
]
M3_INFLATION = ["import_gdp_l1", "policy_rate_l1", "gpr", "wgi_l1", "wgi_x_gpr"]
# Policy rate is also absent from the next stage. It is left out of this test
# because five country clusters cannot support a five-restriction Wald test.
M3_INFLATION_EXCLUDED = ["import_gdp_l1", "gpr", "wgi_l1", "wgi_x_gpr"]
M3_EXPORT = ["ip_growth_l1", "log_vix_l1", "gpr", "wgi_l1", "wgi_x_gpr"]
M3_EXPORT_EXCLUDED = ["gpr", "wgi_l1", "wgi_x_gpr"]
M3_NOMINAL = ["inflation_hat", "real_export_hat", "log_vix_l1", "ip_growth_l1"]
M3_NOMINAL_EXCLUDED = ["inflation_hat", "real_export_hat", "ip_growth_l1"]
M3_REER = [
    "export_trend_hat", "policy_rate_l1", "inflation_l1", "log_oil_l1",
    "log_vix_l1", "log_gepu_l1", "financial_development_l1", "debt_gdp_l1",
]

LABELS = {
    **base.LABELS,
    "export_trend_hat": "Fitted nominal-export trend",
    "real_export_hat": "Fitted real-export trend",
}

EQUATIONS = {
    "m1": (
        "log(REER) = GPR + lagged policy rate + lagged inflation + lagged log oil "
        "+ lagged log VIX + lagged log global EPU + lagged financial development "
        "+ lagged debt/GDP + lagged WGI + WGI × GPR + country effects"
    ),
    "m2_first": (
        "Nominal-export log trend = GPR + lagged WGI + WGI × GPR + lagged log VIX "
        "+ lagged industrial-production growth + country effects"
    ),
    "m2_second": (
        "log(REER) = fitted nominal-export trend + lagged policy rate + lagged inflation "
        "+ lagged log oil + lagged log VIX + lagged log global EPU "
        "+ lagged financial development + lagged debt/GDP + country effects"
    ),
    "m3_inflation": (
        "Inflation = lagged import share of GDP + lagged policy rate + GPR "
        "+ lagged WGI + WGI × GPR + country effects"
    ),
    "m3_export": (
        "Real-export log trend = lagged industrial-production growth "
        "+ lagged log VIX + GPR + lagged WGI + WGI × GPR + country effects"
    ),
    "m3_nominal": (
        "Nominal-export log trend = fitted inflation + fitted real-export trend "
        "+ lagged log VIX + lagged industrial-production growth + country effects"
    ),
    "m3_reer": (
        "log(REER) = fitted nominal-export trend + lagged policy rate + lagged inflation "
        "+ lagged log oil + lagged log VIX + lagged log global EPU "
        "+ lagged financial development + lagged debt/GDP + country effects"
    ),
}

NOTE = (
    "<p>Ukraine and Thailand are dropped. Each column is one of the six Worldwide "
    "Governance Indicators. GPR is contemporaneous and standardized within country. "
    "The other controls, including WGI, use the previous month. WGI is centered before "
    "it is multiplied by GPR. Each cell shows the coefficient, the country-clustered "
    "standard error in parentheses, and the 95% confidence interval. Standard errors "
    "after the first stage use the structural residual. *** p&lt;0.01, ** p&lt;0.05, "
    "* p&lt;0.10.</p>"
    "<p>Industrial-production growth is the year-over-year percent change in the "
    "replication file, lagged one month. There is no monthly GDP series. The import "
    "share is the annual trend ratio of imports to nominal GDP, repeated within the "
    "year, and January uses the previous year. The nominal-export outcome is the "
    "Hodrick-Prescott log trend of the monthly nominal-export workbook. The real-export "
    "outcome is the Hodrick-Prescott log trend. Neither series is logged again. Oil, "
    "VIX, and global EPU enter as logs, as in Equation (2).</p>"
)


def fit_chain(rows):
    countries = sorted({row["country"] for row in rows})
    n = len(rows)
    grouped = est.cluster_indices(rows)
    g = len(grouped)
    fitted = []
    actual = []
    first = []
    for endog_key, columns, excluded in (
        ("inflation", M3_INFLATION, M3_INFLATION_EXCLUDED),
        ("real_export", M3_EXPORT, M3_EXPORT_EXCLUDED),
    ):
        matrix, names, _ = est.design_matrix(rows, columns, countries)
        endog = np.array([row[endog_key] for row in rows], dtype=float)
        beta = np.linalg.lstsq(matrix, endog, rcond=None)[0]
        residual = endog - matrix @ beta
        variance, _ = est.cluster_variance(matrix, residual, grouped, n, matrix.shape[1])
        fitted.append(base.demean_within(matrix @ beta, grouped))
        actual.append(base.demean_within(endog, grouped))
        first.append(base.stage_record(beta, variance, names, excluded, g))

    nominal_columns = ["log_vix_l1", "ip_growth_l1"]
    exog, exog_names, _ = est.design_matrix(rows, nominal_columns, countries)
    xhat = np.column_stack([np.ones(n), *fitted, exog[:, 1:]])
    x_struct = np.column_stack([np.ones(n), *actual, exog[:, 1:]])
    nominal_names = ["const", "inflation_hat", "real_export_hat", *exog_names[1:]]
    nominal = np.array([row["ytrend"] for row in rows], dtype=float)
    beta = np.linalg.lstsq(xhat, nominal, rcond=None)[0]
    structural = nominal - x_struct @ beta
    variance, _ = est.cluster_variance(xhat, structural, grouped, n, xhat.shape[1])
    nominal_stage = base.stage_record(beta, variance, nominal_names, M3_NOMINAL_EXCLUDED, g)

    reer_columns = [
        "policy_rate_l1", "inflation_l1", "log_oil_l1", "log_vix_l1", "log_gepu_l1",
        "financial_development_l1", "debt_gdp_l1",
    ]
    reer_exog, reer_names, _ = est.design_matrix(rows, reer_columns, countries)
    nominal_hat = base.demean_within(xhat @ beta, grouped)
    nominal_actual = base.demean_within(nominal, grouped)
    y = np.array([row["log_reer"] for row in rows], dtype=float)
    xhat3 = np.column_stack([np.ones(n), nominal_hat, reer_exog[:, 1:]])
    x_struct3 = np.column_stack([np.ones(n), nominal_actual, reer_exog[:, 1:]])
    reer_x_names = ["const", "export_trend_hat", *reer_names[1:]]
    beta3 = np.linalg.lstsq(xhat3, y, rcond=None)[0]
    structural3 = y - x_struct3 @ beta3
    variance3, _ = est.cluster_variance(xhat3, structural3, grouped, n, xhat3.shape[1])
    return {
        "inflation": first[0],
        "real_export": first[1],
        "nominal": nominal_stage,
        "stats": est.inference(reer_x_names, beta3, variance3, g),
        "sample": base.sample_info(rows),
    }


def main():
    index, panel_countries = base.load_replication()
    export_trend = est.read_export_trend()
    real_export = base.load_named_month(base.REAL_EXPORT_TREND, "ytrend")
    import_share = base.load_import_share()
    outside_export = sorted(set(export_trend) - set(panel_countries))
    blocks = []

    def run_dimension(title, equation, outcome, columns, needed, extra, estimator, stage):
        results = []
        dropped = None
        present = None
        for code, label in DIMENSIONS:
            rows, kept = base.collect(index, panel_countries, est.read_wgi(code), needed, extra)
            fit = estimator(rows)
            fit["sample"] = base.sample_info(rows)
            results.append((code, label, fit))
            present = kept
            dropped = base.drop_list(
                panel_countries, kept, index, outside_export if extra is not base.empty_extra else []
            )
            print(title, label, "N", fit["sample"]["n_obs"], fit["sample"]["n_country"],
                  fit["sample"]["month_min"], fit["sample"]["month_max"])
        blocks.append({
            "model": stage[0],
            "stage": stage[1],
            "title": title,
            "equation": equation,
            "outcome": outcome,
            "columns": columns,
            "results": results,
            "dropped": dropped,
            "present": present,
        })

    run_dimension(
        "Model 1. Exchange rate",
        EQUATIONS["m1"],
        "Log real effective exchange rate",
        M1,
        ["log_reer", "gpr_raw", "wgi_raw", "policy_rate_l1", "inflation_l1", "log_oil_l1",
         "log_vix_l1", "log_gepu_l1", "financial_development_l1", "debt_gdp_l1"],
        base.empty_extra,
        lambda rows: base.fit_ols(rows, M1, "log_reer"),
        ("1", "equation"),
    )

    def export_extra(country, month, _source):
        return {
            "ytrend": export_trend.get(country, {}).get(month),
            "ip_growth_l1": base.ip_growth(index, country, month),
        }

    def model2(rows):
        fitted = base.fit_system(
            rows,
            [("ytrend", M2_FIRST, M2_EXCLUDED, "Nominal-export log trend")],
            [name for name in M2_SECOND if name != "export_trend_hat"],
            ["export_trend_hat"],
            "log_reer",
        )
        first = fitted["first"][0]
        return {
            "stats": fitted["second"],
            "sample": fitted["sample"],
            "partial_f": first["partial_f"],
            "partial_f_p": first["partial_f_p"],
            "partial_f_df1": first["partial_f_df1"],
            "partial_f_df2": first["partial_f_df2"],
            "first": first,
        }

    run_dimension(
        "Model 2. Second stage",
        EQUATIONS["m2_second"],
        "Log real effective exchange rate",
        M2_SECOND,
        ["log_reer", "gpr_raw", "wgi_raw", "ytrend", "ip_growth_l1", "policy_rate_l1",
         "inflation_l1", "log_oil_l1", "log_vix_l1", "log_gepu_l1",
         "financial_development_l1", "debt_gdp_l1"],
        export_extra,
        model2,
        ("2", "second"),
    )
    second = blocks[-1]
    blocks.insert(-1, {
        "model": "2",
        "stage": "first",
        "title": "Model 2. First stage",
        "equation": EQUATIONS["m2_first"],
        "outcome": "Hodrick-Prescott log trend of nominal exports",
        "columns": M2_FIRST,
        "dropped": second["dropped"],
        "results": [
            (code, label, {
                "stats": fit["first"]["stats"],
                "sample": fit["sample"],
                "partial_f": fit["partial_f"],
                "partial_f_p": fit["partial_f_p"],
                "partial_f_df1": fit["partial_f_df1"],
                "partial_f_df2": fit["partial_f_df2"],
            })
            for code, label, fit in second["results"]
        ],
    })
    for _, _, fit in second["results"]:
        for key in ("partial_f", "partial_f_p", "partial_f_df1", "partial_f_df2"):
            fit.pop(key, None)

    def channel_extra(country, month, source):
        return {
            "inflation": base.num(source.get("inflation")),
            "real_export": real_export.get(country, {}).get(month),
            "ytrend": export_trend.get(country, {}).get(month),
            "import_gdp_l1": base.import_share_l1(import_share, country, month),
            "ip_growth_l1": base.ip_growth(index, country, month),
        }

    run_dimension(
        "Model 3. Third stage",
        EQUATIONS["m3_reer"],
        "Log real effective exchange rate",
        M3_REER,
        ["log_reer", "gpr_raw", "wgi_raw", "inflation", "real_export", "ytrend",
         "import_gdp_l1", "ip_growth_l1", "policy_rate_l1", "inflation_l1", "log_oil_l1",
         "log_vix_l1", "log_gepu_l1", "financial_development_l1", "debt_gdp_l1"],
        channel_extra,
        fit_chain,
        ("3", "third"),
    )
    third = blocks[-1]
    earlier = [
        ("inflation", M3_INFLATION, EQUATIONS["m3_inflation"], "Inflation", "first, inflation"),
        ("real_export", M3_EXPORT, EQUATIONS["m3_export"], "Real-export log trend", "first, real export"),
        ("nominal", M3_NOMINAL, EQUATIONS["m3_nominal"], "Nominal-export log trend", "second"),
    ]
    for key, columns, equation, outcome, stage_name in earlier:
        blocks.insert(-1, {
            "model": "3",
            "stage": stage_name,
            "title": f"Model 3. {outcome}",
            "equation": equation,
            "outcome": outcome,
            "columns": columns,
            "dropped": third["dropped"],
            "results": [
                (code, label, {
                    "stats": fit[key]["stats"],
                    "sample": fit["sample"],
                    "partial_f": fit[key]["partial_f"],
                    "partial_f_p": fit[key]["partial_f_p"],
                    "partial_f_df1": fit[key]["partial_f_df1"],
                    "partial_f_df2": fit[key]["partial_f_df2"],
                })
                for code, label, fit in third["results"]
            ],
        })

    model1 = blocks[0]
    model1["dropped"] = [
        (country, "dropped by request" if country in base.DROP else "no month with every required series")
        for country, _reason in model1["dropped"]
        if country in base.DROP or country not in model1["present"]
    ]

    html_path = os.path.join(OUTPUT, "three_fx_models_all_aspects_results.html")
    csv_path = os.path.join(OUTPUT, "three_fx_models_all_aspects_results.csv")
    base.write_csv(csv_path, blocks, LABELS)
    base.write_html(
        html_path,
        blocks,
        LABELS,
        "Three exchange-rate models, all six WGI dimensions",
        NOTE,
    )
    with open(html_path, encoding="utf-8") as handle:
        html = handle.read().replace("max-width: 1100px", "max-width: 1500px")
        html = html.replace("font-size: .92em", "font-size: .82em")
    with open(html_path, "w", encoding="utf-8") as handle:
        handle.write(html)


if __name__ == "__main__":
    main()
