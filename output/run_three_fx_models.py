"""Three exchange-rate models on the replication countries except Ukraine and Thailand.

Model 1 is the paper's log real-exchange-rate equation plus one WGI dimension
and its interaction with GPR. Model 2 uses the fitted nominal-export component.
Model 3 fits inflation and the real-export component, passes both into the
nominal-export component, and passes that fitted export into the exchange rate.

The default run uses the Hodrick-Prescott log trend. Pass "cycle" to use the
log cycle instead and write a separate results page.
"""

import csv
import os
import sys
from collections import defaultdict
from html import escape

import numpy as np
import openpyxl

import run_export_reer_2sls as est


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUTPUT = os.path.join(ROOT, "output")
CLEANED = os.path.join(ROOT, "cleaned")
PANEL = os.path.join(CLEANED, "replication_cleaned", "country_month.csv")
IMPORT_GDP = os.path.join(CLEANED, "import_gdp.csv")
REAL_EXPORT_TREND = os.path.join(CLEANED, "real_export_hp_trend.csv")
REAL_EXPORT_CYCLE = os.path.join(CLEANED, "real_export_hp_cycle.csv")
TOTAL_IMPORT_CYCLE = os.path.join(CLEANED, "total_import_hp_cycle.csv")
NOMINAL_GDP_CYCLE = os.path.join(CLEANED, "nominal_gdp_hp_cycle.csv")
NOMINAL_EXPORT_HP = os.path.join(CLEANED, "monthly nominal export hp.xlsx")

PANEL_NAME = {"Turkiye": "Turkey", "Korea": "South Korea"}
DROP = {"Ukraine", "Thailand"}
DIMENSIONS = [
    ("rl", "Rule of law"),
    ("ge", "Government effectiveness"),
    ("rq", "Regulatory quality"),
]

M1 = [
    "gpr", "wgi_l1", "wgi_x_gpr",
    "policy_rate_l1", "inflation_l1", "log_oil_l1", "log_vix_l1", "log_gepu_l1",
    "financial_development_l1", "debt_gdp_l1",
]
M2_FIRST = ["gpr", "wgi_l1", "wgi_x_gpr", "log_vix_l1", "log_gepu_l1", "ip_growth_l1"]
M2_EXCLUDED = ["gpr", "wgi_l1", "wgi_x_gpr", "ip_growth_l1"]
M2_SECOND = [
    "export_trend_hat", "policy_rate_l1", "inflation_l1", "log_oil_l1",
    "log_vix_l1", "log_gepu_l1", "financial_development_l1", "debt_gdp_l1",
]
M3_INFLATION = [
    "import_gdp_l1", "policy_rate_l1", "log_oil_l1", "gpr", "wgi_l1", "wgi_x_gpr",
]
# Policy rate and oil are also absent from the next stage. They are left out of
# this test because five country clusters cannot support a six-restriction Wald test.
M3_INFLATION_EXCLUDED = ["import_gdp_l1", "gpr", "wgi_l1", "wgi_x_gpr"]
M3_EXPORT = [
    "ip_growth_l1", "log_vix_l1", "log_gepu_l1", "gpr", "wgi_l1", "wgi_x_gpr",
]
M3_EXPORT_EXCLUDED = ["gpr", "wgi_l1", "wgi_x_gpr"]
M3_NOMINAL = [
    "inflation_hat", "real_export_hat", "log_vix_l1", "log_gepu_l1", "ip_growth_l1",
]
M3_NOMINAL_EXCLUDED = ["inflation_hat", "real_export_hat", "ip_growth_l1"]
M3_REER = [
    "export_trend_hat", "policy_rate_l1", "log_oil_l1", "log_vix_l1", "log_gepu_l1",
    "financial_development_l1", "debt_gdp_l1",
]

LABELS = {
    "gpr": "GPR",
    "wgi_l1": "WGI",
    "wgi_x_gpr": "WGI × GPR",
    "policy_rate_l1": "Policy rate",
    "inflation_l1": "Inflation",
    "log_oil_l1": "Log oil price",
    "log_vix_l1": "Log VIX",
    "log_gepu_l1": "Log global EPU",
    "financial_development_l1": "Financial development",
    "debt_gdp_l1": "Debt/GDP",
    "ip_growth_l1": "Industrial-production growth",
    "export_trend_hat": "Fitted nominal-export trend",
    "import_gdp_l1": "Import share of GDP",
    "inflation_hat": "Fitted inflation",
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
        "+ lagged log global EPU + lagged industrial-production growth + country effects"
    ),
    "m2_second": (
        "log(REER) = fitted nominal-export trend + lagged policy rate + lagged inflation "
        "+ lagged log oil + lagged log VIX + lagged log global EPU "
        "+ lagged financial development + lagged debt/GDP + country effects"
    ),
    "m3_inflation": (
        "Inflation = lagged import share of GDP + lagged policy rate + lagged log oil "
        "+ GPR + lagged WGI + WGI × GPR + country effects"
    ),
    "m3_export": (
        "Real-export log trend = lagged industrial-production growth "
        "+ lagged log VIX + lagged log global EPU + GPR + lagged WGI "
        "+ WGI × GPR + country effects"
    ),
    "m3_nominal": (
        "Nominal-export log trend = fitted inflation + fitted real-export trend "
        "+ lagged log VIX + lagged log global EPU + lagged industrial-production growth "
        "+ country effects"
    ),
    "m3_reer": (
        "log(REER) = fitted nominal-export trend + lagged policy rate + lagged log oil "
        "+ lagged log VIX + lagged log global EPU + lagged financial development "
        "+ lagged debt/GDP + country effects"
    ),
}

EQUATIONS_CYCLE = {
    "m1": EQUATIONS["m1"],
    "m2_first": (
        "Nominal-export log cycle = GPR + lagged WGI + WGI × GPR + lagged log VIX "
        "+ lagged log global EPU + lagged industrial-production growth + country effects"
    ),
    "m2_second": (
        "log(REER) = fitted nominal-export cycle + lagged policy rate + lagged inflation "
        "+ lagged log oil + lagged log VIX + lagged log global EPU "
        "+ lagged financial development + lagged debt/GDP + country effects"
    ),
    "m3_inflation": (
        "Inflation = lagged cyclical import-to-GDP ratio + lagged policy rate + lagged log oil "
        "+ GPR + lagged WGI + WGI × GPR + country effects"
    ),
    "m3_export": (
        "Real-export log cycle = lagged industrial-production growth "
        "+ lagged log VIX + lagged log global EPU + GPR + lagged WGI "
        "+ WGI × GPR + country effects"
    ),
    "m3_nominal": (
        "Nominal-export log cycle = fitted inflation + fitted real-export cycle "
        "+ lagged log VIX + lagged log global EPU + lagged industrial-production growth "
        "+ country effects"
    ),
    "m3_reer": (
        "log(REER) = fitted nominal-export cycle + lagged policy rate + lagged log oil "
        "+ lagged log VIX + lagged log global EPU + lagged financial development "
        "+ lagged debt/GDP + country effects"
    ),
}

LABELS_CYCLE = {
    **LABELS,
    "export_trend_hat": "Fitted nominal-export cycle",
    "import_gdp_l1": "Cyclical import-to-GDP ratio",
    "real_export_hat": "Fitted real-export cycle",
}

TREND_NOTE = (
    "<p>Ukraine and Thailand are dropped. GPR is contemporaneous and standardized within country. "
    "The other controls, including WGI, use the previous month. WGI is centered before it is multiplied by GPR. "
    "Each cell shows the coefficient, the country-clustered standard error in parentheses, and the 95% confidence interval. "
    "Standard errors after the first stage use the structural residual. *** p&lt;0.01, ** p&lt;0.05, * p&lt;0.10.</p>"
    "<p>Industrial-production growth is the year-over-year percent change in the replication file, lagged one month. "
    "There is no monthly GDP series. The import share is the annual trend ratio of imports to nominal GDP, "
    "repeated within the year, and January uses the previous year. The nominal-export outcome and the real-export "
    "outcome are Hodrick-Prescott log trends, so they are not logged again.</p>"
)

CYCLE_NOTE = (
    "<p>Ukraine and Thailand are dropped. GPR is contemporaneous and standardized within country. "
    "The other controls, including WGI, use the previous month. WGI is centered before it is multiplied by GPR. "
    "Each cell shows the coefficient, the country-clustered standard error in parentheses, and the 95% confidence interval. "
    "Standard errors after the first stage use the structural residual. *** p&lt;0.01, ** p&lt;0.05, * p&lt;0.10.</p>"
    "<p>This page uses the Hodrick-Prescott log cycle, the deviation from the smooth trend. "
    "Industrial-production growth is the year-over-year percent change in the replication file, lagged one month. "
    "There is no monthly GDP series. The import term is the annual ratio of the import cycle to the GDP cycle, "
    "exp(import cycle − GDP cycle), repeated within the year, and January uses the previous year. "
    "The nominal-export outcome and the real-export outcome are Hodrick-Prescott log cycles, so they are not logged again.</p>"
)


def num(text):
    if text is None:
        return None
    text = str(text).strip()
    if not text:
        return None
    return float(text)


def load_import_share():
    out = defaultdict(dict)
    with open(IMPORT_GDP, encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            value = num(row["import_gdp"])
            if value is not None:
                out[row["country"].strip()][int(row["year"])] = value
    return out


def load_annual_cycle(path):
    out = defaultdict(dict)
    with open(path, encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            value = num(row["y"])
            if value is not None:
                out[row["country"].strip()][int(row["year"])] = value
    return out


def load_cycle_import_ratio():
    imports = load_annual_cycle(TOTAL_IMPORT_CYCLE)
    gdp = load_annual_cycle(NOMINAL_GDP_CYCLE)
    out = defaultdict(dict)
    for country, years in imports.items():
        for year, import_cycle in years.items():
            gdp_cycle = gdp.get(country, {}).get(year)
            if gdp_cycle is None:
                continue
            out[country][year] = float(np.exp(import_cycle - gdp_cycle))
    return out


def load_export_component(sheet):
    wb = openpyxl.load_workbook(NOMINAL_EXPORT_HP, read_only=True, data_only=True)
    ws = wb[sheet]
    out = defaultdict(dict)
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or row[0] is None or row[1] is None or row[2] is None:
            continue
        out[str(row[0]).strip()][str(row[1]).strip()] = float(row[2])
    wb.close()
    return out


def import_share_l1(shares, country, month):
    lag = est.add_months(month, -1)
    return shares.get(country, {}).get(int(lag[:4]))


def load_named_month(path, column):
    out = defaultdict(dict)
    with open(path, encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            value = num(row[column])
            if value is not None:
                out[row["country"].strip()][row["year_month"].strip()] = value
    return out


def load_replication():
    index = {}
    countries = []
    seen = set()
    with open(PANEL, encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            country = PANEL_NAME.get(row["country"].strip(), row["country"].strip())
            index[(country, row["date"][:7])] = row
            if country not in seen:
                seen.add(country)
                countries.append(country)
    return index, countries


def lagged_controls(source):
    if source is None:
        return {name: None for name in (
            "policy_rate_l1", "inflation_l1", "log_oil_l1", "log_vix_l1",
            "log_gepu_l1", "financial_development_l1", "debt_gdp_l1",
        )}
    return {
        "policy_rate_l1": num(source["policy_rate"]),
        "inflation_l1": num(source["inflation"]),
        "log_oil_l1": est.positive_log(num(source["oil_price"])),
        "log_vix_l1": est.positive_log(num(source["vix"])),
        "log_gepu_l1": est.positive_log(num(source["gepu"])),
        "financial_development_l1": num(source["financial_development"]),
        "debt_gdp_l1": num(source["public_debt_gdp"]),
    }


def ip_growth(index, country, month):
    lag = est.add_months(month, -1)
    earlier = est.add_months(lag, -12)
    current = index.get((country, lag))
    previous = index.get((country, earlier))
    if current is None or previous is None:
        return None
    now = num(current["industrial_production"])
    base = num(previous["industrial_production"])
    if now is None or base is None or base <= 0:
        return None
    return (now / base - 1.0) * 100.0


def has_any_ip(index, country):
    return any(
        (source.get("industrial_production") or "").strip()
        for (name, _month), source in index.items()
        if name == country
    )


def shape_instruments(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["country"]].append(row["gpr_raw"])
    moments = {}
    for country, values in grouped.items():
        array = np.array(values, dtype=float)
        sd = float(array.std(ddof=1)) if len(array) > 1 else float("nan")
        moments[country] = (float(array.mean()), sd)
    kept = []
    for row in rows:
        mean, sd = moments[row["country"]]
        if not np.isfinite(sd) or sd == 0:
            continue
        row["gpr"] = (row["gpr_raw"] - mean) / sd
        kept.append(row)
    if not kept:
        raise RuntimeError("No complete cases after standardizing GPR.")
    center = float(np.mean([row["wgi_raw"] for row in kept]))
    for row in kept:
        row["wgi_l1"] = row["wgi_raw"] - center
        row["wgi_x_gpr"] = row["wgi_l1"] * row["gpr"]
    return kept


def collect(index, countries, wgi, needed, extra):
    rows = []
    present = []
    for country in countries:
        if country in DROP:
            continue
        country_rows = []
        for (name, month), source in index.items():
            if name != country:
                continue
            lag = est.add_months(month, -1)
            lagged = index.get((country, lag))
            record = {
                "country": country,
                "year_month": month,
                "log_reer": est.positive_log(num(source.get("reer"))),
                "gpr_raw": num(source.get("gpr")),
                "wgi_raw": wgi.get(country, {}).get(int(lag[:4])),
                "inflation": num(source.get("inflation")),
            }
            record.update(lagged_controls(lagged))
            record.update(extra(country, month, source))
            if any(record.get(name) is None for name in needed):
                continue
            country_rows.append(record)
        if country_rows:
            rows.extend(country_rows)
            present.append(country)
    return shape_instruments(rows), present


def drop_list(panel_countries, present, index, outside):
    dropped = []
    for country in panel_countries:
        if country in DROP:
            dropped.append((country, "dropped by request"))
        elif country not in present:
            if not has_any_ip(index, country):
                dropped.append((country, "no industrial production in the replication file"))
            else:
                dropped.append((country, "no month with every required series"))
    for country in outside:
        dropped.append((country, "not in the replication file"))
    return dropped


def sample_info(rows):
    countries = []
    seen = set()
    for row in rows:
        if row["country"] not in seen:
            seen.add(row["country"])
            countries.append(row["country"])
    return {
        "countries": countries,
        "n_obs": len(rows),
        "n_country": len(countries),
        "month_min": min(row["year_month"] for row in rows),
        "month_max": max(row["year_month"] for row in rows),
    }


def partial_f(beta, variance, names, excluded, df2):
    indexes = [names.index(name) for name in excluded if name in names]
    q = len(indexes)
    restriction = beta[indexes]
    cov = variance[np.ix_(indexes, indexes)]
    wald = float(restriction.T @ np.linalg.inv(cov) @ restriction)
    f_stat = wald / q
    return f_stat, float(est.f_sf(f_stat, q, df2)), q


def fit_ols(rows, columns, outcome):
    countries = sorted({row["country"] for row in rows})
    y = np.array([row[outcome] for row in rows], dtype=float)
    matrix, names, base = est.design_matrix(rows, columns, countries)
    n, k = matrix.shape
    grouped = est.cluster_indices(rows)
    beta = np.linalg.lstsq(matrix, y, rcond=None)[0]
    residual = y - matrix @ beta
    variance, _ = est.cluster_variance(matrix, residual, grouped, n, k)
    return {
        "stats": est.inference(names, beta, variance, len(grouped)),
        "base": base,
        "sample": sample_info(rows),
    }


def demean_within(values, grouped):
    out = np.array(values, dtype=float, copy=True)
    for indexes in grouped.values():
        out[indexes] -= out[indexes].mean()
    return out


def fit_system(rows, stages, second_exog, second_names, outcome):
    countries = sorted({row["country"] for row in rows})
    y = np.array([row[outcome] for row in rows], dtype=float)
    n = len(rows)
    grouped = est.cluster_indices(rows)
    g = len(grouped)
    exog, exog_names, base = est.design_matrix(rows, second_exog, countries)
    fitted = []
    actual = []
    first = []
    for endog_key, columns, excluded, label in stages:
        matrix, names, _ = est.design_matrix(rows, columns, countries)
        endog = np.array([row[endog_key] for row in rows], dtype=float)
        beta = np.linalg.lstsq(matrix, endog, rcond=None)[0]
        residual = endog - matrix @ beta
        variance, _ = est.cluster_variance(matrix, residual, grouped, n, matrix.shape[1])
        f_stat, f_p, f_df1 = partial_f(beta, variance, names, excluded, g - 1)
        # Country effects are in both stages. Remove the country mean from the
        # fitted and actual series so the second stage is not collinear.
        fitted.append(demean_within(matrix @ beta, grouped))
        actual.append(demean_within(endog, grouped))
        first.append({
            "label": label,
            "stats": est.inference(names, beta, variance, g),
            "columns": columns,
            "partial_f": f_stat,
            "partial_f_p": f_p,
            "partial_f_df1": f_df1,
            "partial_f_df2": g - 1,
        })
    tail = exog[:, 1:]
    xhat = np.column_stack([np.ones(n), *fitted, tail])
    x_struct = np.column_stack([np.ones(n), *actual, tail])
    x_names = ["const", *second_names, *exog_names[1:]]
    beta = np.linalg.lstsq(xhat, y, rcond=None)[0]
    structural = y - x_struct @ beta
    variance, _ = est.cluster_variance(xhat, structural, grouped, n, xhat.shape[1])
    return {
        "first": first,
        "second": est.inference(x_names, beta, variance, g),
        "base": base,
        "sample": sample_info(rows),
    }


def stage_record(beta, variance, names, excluded, g):
    f_stat, f_p, f_df1 = partial_f(beta, variance, names, excluded, g - 1)
    return {
        "stats": est.inference(names, beta, variance, g),
        "partial_f": f_stat,
        "partial_f_p": f_p,
        "partial_f_df1": f_df1,
        "partial_f_df2": g - 1,
    }


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
        fitted.append(demean_within(matrix @ beta, grouped))
        actual.append(demean_within(endog, grouped))
        first.append(stage_record(beta, variance, names, excluded, g))

    nominal_columns = ["log_vix_l1", "log_gepu_l1", "ip_growth_l1"]
    exog, exog_names, _ = est.design_matrix(rows, nominal_columns, countries)
    xhat = np.column_stack([np.ones(n), *fitted, exog[:, 1:]])
    x_struct = np.column_stack([np.ones(n), *actual, exog[:, 1:]])
    nominal_names = ["const", "inflation_hat", "real_export_hat", *exog_names[1:]]
    nominal = np.array([row["ytrend"] for row in rows], dtype=float)
    beta = np.linalg.lstsq(xhat, nominal, rcond=None)[0]
    structural = nominal - x_struct @ beta
    variance, _ = est.cluster_variance(xhat, structural, grouped, n, xhat.shape[1])
    nominal_stage = stage_record(beta, variance, nominal_names, M3_NOMINAL_EXCLUDED, g)

    reer_columns = [
        "policy_rate_l1", "log_oil_l1", "log_vix_l1", "log_gepu_l1",
        "financial_development_l1", "debt_gdp_l1",
    ]
    reer_exog, reer_names, _ = est.design_matrix(rows, reer_columns, countries)
    nominal_hat = demean_within(xhat @ beta, grouped)
    nominal_actual = demean_within(nominal, grouped)
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
        "sample": sample_info(rows),
    }


def stat_fields(stat):
    return {key: f"{stat[key]:.10g}" for key in ("coef", "se", "t", "p", "ci_lo", "ci_hi")}


def write_csv(path, blocks, labels):
    fields = [
        "model", "stage", "outcome", "dimension", "dimension_label", "variable", "label",
        "coef", "se", "t", "p", "ci_lo", "ci_hi",
        "n_obs", "n_country", "month_min", "month_max", "countries", "dropped",
        "partial_f", "partial_f_p", "partial_f_df1", "partial_f_df2",
    ]
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for block in blocks:
            for code, label, fit in block["results"]:
                shared = {
                    "model": block["model"],
                    "stage": block["stage"],
                    "outcome": block["outcome"],
                    "dimension": code,
                    "dimension_label": label,
                    "n_obs": fit["sample"]["n_obs"],
                    "n_country": fit["sample"]["n_country"],
                    "month_min": fit["sample"]["month_min"],
                    "month_max": fit["sample"]["month_max"],
                    "countries": "; ".join(fit["sample"]["countries"]),
                    "dropped": "; ".join(f"{country}: {reason}" for country, reason in block["dropped"]),
                    "partial_f": "" if fit.get("partial_f") is None else f"{fit['partial_f']:.10g}",
                    "partial_f_p": "" if fit.get("partial_f_p") is None else f"{fit['partial_f_p']:.10g}",
                    "partial_f_df1": fit.get("partial_f_df1", ""),
                    "partial_f_df2": fit.get("partial_f_df2", ""),
                }
                for variable in block["columns"]:
                    writer.writerow({
                        **shared,
                        "variable": variable,
                        "label": labels[variable],
                        **stat_fields(fit["stats"][variable]),
                    })


def cell(stat):
    return (
        f"{est.fmt(stat['coef'])}{est.stars(stat['p'])}<br>"
        f"({est.fmt(stat['se'])})<br>"
        f"[{est.fmt(stat['ci_lo'])}, {est.fmt(stat['ci_hi'])}]"
    )


def write_html(path, blocks, labels, page_title, note):
    parts = []
    for block in blocks:
        header = "".join(f"<th>{escape(label)}</th>" for _, label, _ in block["results"])
        body = []
        for variable in block["columns"]:
            cells = "".join(
                f"<td>{cell(fit['stats'][variable])}</td>" for _, _, fit in block["results"]
            )
            body.append(f"<tr><td>{escape(labels[variable])}</td>{cells}</tr>")
        sample = "".join(
            "<td>{n}<br>{g} countries<br>{start} to {end}</td>".format(
                n=fit["sample"]["n_obs"],
                g=fit["sample"]["n_country"],
                start=escape(fit["sample"]["month_min"]),
                end=escape(fit["sample"]["month_max"]),
            )
            for _, _, fit in block["results"]
        )
        extra = ""
        if block["results"][0][2].get("partial_f") is not None:
            extra = "<tr><td>Partial F on the excluded instruments</td>" + "".join(
                f"<td>{est.fmt(fit['partial_f'], 2)}<br>p={est.fmt(fit['partial_f_p'])}<br>"
                f"F({fit['partial_f_df1']}, {fit['partial_f_df2']})</td>"
                for _, _, fit in block["results"]
            ) + "</tr>"
        kept = "".join(
            f"<li>{escape(label)}: {escape(', '.join(fit['sample']['countries']))}</li>"
            for _, label, fit in block["results"]
        )
        dropped = "".join(
            f"<li>{escape(country)}: {escape(reason)}</li>" for country, reason in block["dropped"]
        )
        parts.append(
            f"<h2>{escape(block['title'])}</h2>"
            f"<p class=\"equation\">{escape(block['equation'])}</p>"
            f"<p><strong>Y:</strong> {escape(block['outcome'])}</p>"
            "<table><thead><tr><th>Variable</th>"
            f"{header}</tr></thead><tbody>{''.join(body)}"
            f"<tr><td>Observations</td>{sample}</tr>{extra}</tbody></table>"
            "<h3>Countries that remain</h3><ul>"
            f"{kept}</ul><h3>Countries that drop</h3><ul>{dropped}</ul>"
        )
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{escape(page_title)}</title>
<style>
body {{ font: 16px/1.5 Georgia, serif; max-width: 1100px; margin: 2em auto; padding: 0 1em; color: #20242a; }}
table {{ border-collapse: collapse; width: 100%; margin: 1em 0; font-size: .92em; }}
th, td {{ border-bottom: 1px solid #ccc; padding: .45em; text-align: right; vertical-align: top; }}
th:first-child, td:first-child {{ text-align: left; }}
.equation {{ background: #f4f6f8; padding: .8em 1em; }}
.note {{ background: #fff5da; padding: 1em; border: 1px solid #e6d59d; }}
</style>
</head>
<body>
<h1>{escape(page_title)}</h1>
<div class="note">
{note}
</div>
{''.join(parts)}
</body>
</html>
"""
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(html)


def empty_extra(_country, _month, _source):
    return {}


def main(mode="trend"):
    if mode not in ("trend", "cycle"):
        raise SystemExit("Use trend or cycle.")
    index, panel_countries = load_replication()
    if mode == "cycle":
        export_trend = load_export_component("y")
        real_export = load_named_month(REAL_EXPORT_CYCLE, "y")
        import_share = load_cycle_import_ratio()
        labels = LABELS_CYCLE
        equations = EQUATIONS_CYCLE
        export_outcome = "Hodrick-Prescott log cycle of nominal exports"
        real_outcome = "Real-export log cycle"
        nominal_outcome = "Nominal-export log cycle"
        page_title = "Three exchange-rate models, Hodrick-Prescott cycle"
        note = CYCLE_NOTE
        html_name = "three_fx_models_cycle_results.html"
        csv_name = "three_fx_models_cycle_results.csv"
    else:
        export_trend = est.read_export_trend()
        real_export = load_named_month(REAL_EXPORT_TREND, "ytrend")
        import_share = load_import_share()
        labels = LABELS
        equations = EQUATIONS
        export_outcome = "Hodrick-Prescott log trend of nominal exports"
        real_outcome = "Real-export log trend"
        nominal_outcome = "Nominal-export log trend"
        page_title = "Three exchange-rate models"
        note = TREND_NOTE
        html_name = "three_fx_models_results.html"
        csv_name = "three_fx_models_results.csv"
    outside_export = sorted(set(export_trend) - set(panel_countries))
    blocks = []

    def run_dimension(title, equation, outcome, columns, needed, extra, estimator, stage):
        results = []
        dropped = None
        present = None
        for code, label in DIMENSIONS:
            rows, kept = collect(index, panel_countries, est.read_wgi(code), needed, extra)
            fit = estimator(rows)
            fit["sample"] = sample_info(rows)
            results.append((code, label, fit))
            present = kept
            dropped = drop_list(panel_countries, kept, index, outside_export if extra is not empty_extra else [])
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
        equations["m1"],
        "Log real effective exchange rate",
        M1,
        ["log_reer", "gpr_raw", "wgi_raw", "policy_rate_l1", "inflation_l1", "log_oil_l1",
         "log_vix_l1", "log_gepu_l1", "financial_development_l1", "debt_gdp_l1"],
        empty_extra,
        lambda rows: fit_ols(rows, M1, "log_reer"),
        ("1", "equation"),
    )

    def export_extra(country, month, _source):
        return {
            "ytrend": export_trend.get(country, {}).get(month),
            "ip_growth_l1": ip_growth(index, country, month),
        }

    def model2(rows):
        fitted = fit_system(
            rows,
            [("ytrend", M2_FIRST, M2_EXCLUDED, export_outcome)],
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
        equations["m2_second"],
        "Log real effective exchange rate",
        M2_SECOND,
        ["log_reer", "gpr_raw", "wgi_raw", "ytrend", "ip_growth_l1", "policy_rate_l1",
         "inflation_l1", "log_oil_l1", "log_vix_l1", "log_gepu_l1",
         "financial_development_l1", "debt_gdp_l1"],
        export_extra,
        model2,
        ("2", "second"),
    )
    # Attach the matching first stage from the second-stage fits.
    second = blocks[-1]
    blocks.insert(-1, {
        "model": "2",
        "stage": "first",
        "title": "Model 2. First stage",
        "equation": equations["m2_first"],
        "outcome": export_outcome,
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
            "inflation": num(source.get("inflation")),
            "real_export": real_export.get(country, {}).get(month),
            "ytrend": export_trend.get(country, {}).get(month),
            "import_gdp_l1": import_share_l1(import_share, country, month),
            "ip_growth_l1": ip_growth(index, country, month),
        }

    def model3(rows):
        return fit_chain(rows)

    run_dimension(
        "Model 3. Third stage",
        equations["m3_reer"],
        "Log real effective exchange rate",
        M3_REER,
        ["log_reer", "gpr_raw", "wgi_raw", "inflation", "real_export", "ytrend",
         "import_gdp_l1", "ip_growth_l1", "policy_rate_l1", "log_oil_l1",
         "log_vix_l1", "log_gepu_l1", "financial_development_l1", "debt_gdp_l1"],
        channel_extra,
        model3,
        ("3", "third"),
    )
    third = blocks[-1]
    earlier = [
        ("inflation", M3_INFLATION, equations["m3_inflation"], "Inflation", "first, inflation"),
        ("real_export", M3_EXPORT, equations["m3_export"], real_outcome, "first, real export"),
        ("nominal", M3_NOMINAL, equations["m3_nominal"], nominal_outcome, "second"),
    ]
    for offset, (key, columns, equation, outcome, stage_name) in enumerate(earlier):
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

    # Model 2 and 3 should not call Indonesia's missing IP a generic reason when
    # the country was already classified. Model 1 has IP available for those
    # countries, so rebuild its drop list without the IP reason.
    model1 = blocks[0]
    model1["dropped"] = [
        (country, "dropped by request" if country in DROP else "no month with every required series")
        for country, _reason in model1["dropped"]
        if country in DROP or country not in model1["present"]
    ]

    write_csv(os.path.join(OUTPUT, csv_name), blocks, labels)
    write_html(os.path.join(OUTPUT, html_name), blocks, labels, page_title, note)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "trend")
