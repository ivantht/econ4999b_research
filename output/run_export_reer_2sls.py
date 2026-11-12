"""2SLS of log REER on the HP log trend of nominal exports.

The first stage projects the export trend on the excluded instruments and
country fixed effects. The second stage uses only that fitted trend, plus
the same country fixed effects. One regression is run for each WGI dimension.
"""

import csv
import math
import os
from collections import defaultdict
from html import escape

import numpy as np
import openpyxl


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CLEANED = os.path.join(ROOT, "cleaned")
OUTPUT = os.path.join(ROOT, "output")

DIMENSIONS = [
    ("rq", "Regulatory quality"),
    ("ge", "Government effectiveness"),
    ("rl", "Rule of law"),
]

INSTRUMENTS = [
    "wgi_l1",
    "log_vix_l1",
    "policy_rate_l1",
    "log_oil_l1",
    "inflation_l1",
    "gpr",
    "log_gepu_l1",
    "financial_development_l1",
    "debt_gdp_l1",
]


def add_months(ym, k):
    year, month = map(int, ym.split("-"))
    month += k
    while month > 12:
        year += 1
        month -= 12
    while month < 1:
        year -= 1
        month += 12
    return f"{year:04d}-{month:02d}"


def stars(p):
    if p < 0.01:
        return "***"
    if p < 0.05:
        return "**"
    if p < 0.10:
        return "*"
    return ""


def log_beta(a, b):
    return math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)


def betacf(a, b, x):
    am = 1.0
    bm = 1.0
    az = 1.0
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    bz = 1.0 - qab * x / qap
    a_old = 0.0
    for m in range(1, 201):
        em = float(m)
        tem = em + em
        d = em * (b - em) * x / ((qam + tem) * (a + tem))
        ap = az + d * am
        bp = bz + d * bm
        d = -(a + em) * (qab + em) * x / ((a + tem) * (qap + tem))
        app = ap + d * az
        bpp = bp + d * bz
        a_old = az
        am = ap / bpp
        bm = bp / bpp
        az = app / bpp
        bz = 1.0
        if abs(az - a_old) < 3e-14 * abs(az):
            return az
    raise RuntimeError("Continued fraction for the incomplete beta did not converge.")


def regularized_beta(a, b, x):
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    ln_front = a * math.log(x) + b * math.log(1.0 - x) - log_beta(a, b)
    if x < (a + 1.0) / (a + b + 2.0):
        return math.exp(ln_front) * betacf(a, b, x) / a
    return 1.0 - math.exp(ln_front) * betacf(b, a, 1.0 - x) / b


def student_t_cdf(t, df):
    x = df / (df + t * t)
    tail = 0.5 * regularized_beta(0.5 * df, 0.5, x)
    if t >= 0.0:
        return 1.0 - tail
    return tail


def student_t_sf_two_tail(t, df):
    return 2.0 * (1.0 - student_t_cdf(abs(float(t)), df))


def student_t_ppf(p, df):
    lo, hi = -100.0, 100.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if student_t_cdf(mid, df) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def f_sf(f_stat, d1, d2):
    if f_stat <= 0.0:
        return 1.0
    x = d2 / (d2 + d1 * f_stat)
    return regularized_beta(0.5 * d2, 0.5 * d1, x)


def read_country_order():
    path = os.path.join(CLEANED, "country.csv")
    with open(path, encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    return [row[0].strip() for row in rows[1:] if row and row[0].strip()]


def read_export_trend():
    path = os.path.join(CLEANED, "monthly nominal export hp.xlsx")
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb["ytrend"]
    out = defaultdict(dict)
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or row[0] is None or row[1] is None or row[2] is None:
            continue
        out[str(row[0]).strip()][str(row[1]).strip()] = float(row[2])
    wb.close()
    return out


def read_reer():
    path = os.path.join(CLEANED, "real effective exchange rate.xlsx")
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = ws.iter_rows(values_only=True)
    header = [None if cell is None else str(cell).strip() for cell in next(rows)]
    countries = header[1:]
    out = defaultdict(dict)
    for row in rows:
        if not row or row[0] is None:
            continue
        month = str(row[0]).strip()
        for country, value in zip(countries, row[1:]):
            if country and value is not None and value != "" and float(value) > 0:
                out[country][month] = float(value)
    wb.close()
    return out


def read_monthly_country(file_name, value_col):
    out = defaultdict(dict)
    with open(os.path.join(CLEANED, file_name), encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            value = (row.get(value_col) or "").strip()
            if value:
                out[row["country"].strip()][row["year_month"].strip()] = float(value)
    return out


def read_monthly_global(file_name, value_col, series=None):
    out = {}
    with open(os.path.join(CLEANED, file_name), encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if series is not None and row.get("series", "").strip() != series:
                continue
            value = (row.get(value_col) or "").strip()
            if value:
                out[row["year_month"].strip()] = float(value)
    return out


def read_annual(file_name, year_col, value_col, frequency=None):
    out = defaultdict(dict)
    with open(os.path.join(CLEANED, file_name), encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if frequency is not None and row.get("frequency", "").strip() != frequency:
                continue
            year = (row.get(year_col) or "").strip()
            value = (row.get(value_col) or "").strip()
            if not year or not value:
                continue
            country = row["country"].strip()
            year = int(year)
            number = float(value)
            if year in out[country] and out[country][year] != number:
                raise ValueError(f"Conflicting {file_name} values for {country} {year}.")
            out[country][year] = number
    return out


def read_wgi(dimension):
    out = defaultdict(dict)
    with open(os.path.join(CLEANED, "wgi.csv"), encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["dimension"].strip().lower() != dimension:
                continue
            value = (row.get("estimate") or "").strip()
            if value:
                out[row["country"].strip()][int(row["year"])] = float(value)
    return out


def positive_log(value):
    if value is None or value <= 0:
        return None
    return math.log(value)


def build_panel(dimension, sources):
    rows = []
    for country in sources["countries"]:
        months = sorted(sources["trend"].get(country, {}))
        for month in months:
            lag = add_months(month, -1)
            lag_year = int(lag[:4])
            record = {
                "country": country,
                "year_month": month,
                "ytrend": sources["trend"][country][month],
                "log_reer": positive_log(sources["reer"].get(country, {}).get(month)),
                "wgi_l1": sources["wgi"].get(country, {}).get(lag_year),
                "log_vix_l1": positive_log(sources["vix"].get(lag)),
                "policy_rate_l1": sources["policy"].get(country, {}).get(lag),
                "log_oil_l1": positive_log(sources["oil"].get(lag)),
                "inflation_l1": sources["inflation"].get(country, {}).get(lag),
                "gpr": sources["gpr"].get(month),
                "log_gepu_l1": positive_log(sources["gepu"].get(lag)),
                "financial_development_l1": sources["fd"].get(country, {}).get(lag_year),
                "debt_gdp_l1": sources["debt"].get(country, {}).get(lag_year),
            }
            if any(record[name] is None for name in ["log_reer", *INSTRUMENTS]):
                continue
            rows.append(record)
    return rows


def design_matrix(rows, columns, countries):
    pieces = [np.ones(len(rows), dtype=float)]
    names = ["const"]
    for name in columns:
        pieces.append(np.array([row[name] for row in rows], dtype=float))
        names.append(name)
    base = countries[0]
    for country in countries[1:]:
        pieces.append(np.array([1.0 if row["country"] == country else 0.0 for row in rows], dtype=float))
        names.append(f"fe_{country}")
    return np.column_stack(pieces), names, base


def cluster_indices(rows):
    grouped = defaultdict(list)
    for index, row in enumerate(rows):
        grouped[row["country"]].append(index)
    return grouped


def cluster_variance(regressor, residual, grouped, n, k):
    g = len(grouped)
    xtx_inv = np.linalg.inv(regressor.T @ regressor)
    meat = np.zeros((regressor.shape[1], regressor.shape[1]), dtype=float)
    for indexes in grouped.values():
        score = regressor[indexes, :].T @ residual[indexes]
        meat += np.outer(score, score)
    variance = xtx_inv @ meat @ xtx_inv
    if g > 1 and n > k:
        variance *= (g / (g - 1.0)) * ((n - 1.0) / (n - k))
    return variance, xtx_inv


def inference(names, beta, variance, g):
    se = np.sqrt(np.clip(np.diag(variance), 0.0, None))
    df = g - 1
    with np.errstate(divide="ignore", invalid="ignore"):
        t_stat = beta / se
    critical = student_t_ppf(0.975, df)
    return {
        name: {
            "coef": float(beta[i]),
            "se": float(se[i]),
            "t": float(t_stat[i]),
            "p": float(student_t_sf_two_tail(t_stat[i], df)),
            "ci_lo": float(beta[i] - critical * se[i]),
            "ci_hi": float(beta[i] + critical * se[i]),
        }
        for i, name in enumerate(names)
    }


def partial_f(beta, variance, names, df2):
    indexes = [names.index(name) for name in INSTRUMENTS]
    q = len(indexes)
    restriction = beta[indexes]
    cov = variance[np.ix_(indexes, indexes)]
    wald = float(restriction.T @ np.linalg.inv(cov) @ restriction)
    f_stat = wald / q
    return f_stat, float(f_sf(f_stat, q, df2))


def fit_2sls(rows):
    countries = sorted({row["country"] for row in rows})
    if len(countries) < 2:
        raise RuntimeError("Need at least two countries for country fixed effects.")
    y = np.array([row["log_reer"] for row in rows], dtype=float)
    endog = np.array([row["ytrend"] for row in rows], dtype=float)
    z_matrix, z_names, base = design_matrix(rows, INSTRUMENTS, countries)
    fe_start = 1 + len(INSTRUMENTS)
    x_matrix = np.column_stack([np.ones(len(rows)), endog, z_matrix[:, fe_start:]])
    x_names = ["const", "ytrend_hat", *z_names[fe_start:]]
    n, k_z = z_matrix.shape
    k_x = x_matrix.shape[1]
    if n <= k_z or n <= k_x:
        raise RuntimeError(f"Insufficient observations (N={n}) for the parameter count.")
    grouped = cluster_indices(rows)
    g = len(grouped)

    first_beta = np.linalg.lstsq(z_matrix, endog, rcond=None)[0]
    first_fitted = z_matrix @ first_beta
    first_resid = endog - first_fitted
    first_var, _ = cluster_variance(z_matrix, first_resid, grouped, n, k_z)
    first_stats = inference(z_names, first_beta, first_var, g)
    f_stat, f_p = partial_f(first_beta, first_var, z_names, g - 1)

    xhat = z_matrix @ np.linalg.lstsq(z_matrix, x_matrix, rcond=None)[0]
    beta = np.linalg.lstsq(xhat, y, rcond=None)[0]
    structural = y - x_matrix @ beta
    second_var, _ = cluster_variance(xhat, structural, grouped, n, k_x)
    second_stats = inference(x_names, beta, second_var, g)

    sst = float(np.sum((endog - np.mean(endog)) ** 2))
    first_r2 = float(1.0 - np.sum(first_resid**2) / sst) if sst > 0 else float("nan")
    return {
        "countries": countries,
        "base_country": base,
        "n_obs": n,
        "n_country": g,
        "month_min": min(row["year_month"] for row in rows),
        "month_max": max(row["year_month"] for row in rows),
        "partial_f": f_stat,
        "partial_f_p": f_p,
        "partial_f_df1": len(INSTRUMENTS),
        "partial_f_df2": g - 1,
        "first_r2": first_r2,
        "first": first_stats,
        "second": second_stats,
    }


def fmt(value, digits=4):
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return ""
    return f"{value:.{digits}f}"


def write_csv(path, results):
    fields = [
        "dimension",
        "dimension_label",
        "stage",
        "variable",
        "coef",
        "se",
        "t",
        "p",
        "ci_lo",
        "ci_hi",
        "n_obs",
        "n_country",
        "partial_f",
        "partial_f_p",
        "partial_f_df1",
        "partial_f_df2",
        "first_stage_r2",
        "month_min",
        "month_max",
        "countries",
    ]
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for code, label, fit in results:
            shared = {
                "dimension": code,
                "dimension_label": label,
                "n_obs": fit["n_obs"],
                "n_country": fit["n_country"],
                "partial_f": f"{fit['partial_f']:.10g}",
                "partial_f_p": f"{fit['partial_f_p']:.10g}",
                "partial_f_df1": fit["partial_f_df1"],
                "partial_f_df2": fit["partial_f_df2"],
                "first_stage_r2": f"{fit['first_r2']:.10g}",
                "month_min": fit["month_min"],
                "month_max": fit["month_max"],
                "countries": "; ".join(fit["countries"]),
            }
            for variable in ["ytrend_hat"]:
                stat = fit["second"][variable]
                writer.writerow({**shared, "stage": "second", "variable": variable, **{k: f"{stat[k]:.10g}" for k in ("coef", "se", "t", "p", "ci_lo", "ci_hi")}})
            for variable in INSTRUMENTS:
                stat = fit["first"][variable]
                writer.writerow({**shared, "stage": "first", "variable": variable, **{k: f"{stat[k]:.10g}" for k in ("coef", "se", "t", "p", "ci_lo", "ci_hi")}})


def cell(stat):
    return (
        f"{fmt(stat['coef'])}{stars(stat['p'])}<br>"
        f"({fmt(stat['se'])})<br>"
        f"[{fmt(stat['ci_lo'])}, {fmt(stat['ci_hi'])}]"
    )


def write_html(path, results, reer_countries):
    header = "".join(f"<th>{escape(label)}</th>" for _, label, _ in results)
    second_cells = "".join(
        f"<td>{cell(fit['second']['ytrend_hat'])}<br>p={fmt(fit['second']['ytrend_hat']['p'], 4)}</td>"
        for _, _, fit in results
    )
    sample_cells = "".join(
        f"<td>{fit['n_obs']}<br>{fit['n_country']} countries<br>{escape(fit['month_min'])} to {escape(fit['month_max'])}</td>"
        for _, _, fit in results
    )
    f_cells = "".join(
        f"<td>{fmt(fit['partial_f'], 2)}<br>p={fmt(fit['partial_f_p'], 4)}<br>F({fit['partial_f_df1']}, {fit['partial_f_df2']})</td>"
        for _, _, fit in results
    )
    instrument_rows = []
    labels = {
        "wgi_l1": "WGI, lagged",
        "log_vix_l1": "Log VIX, lagged",
        "policy_rate_l1": "Policy rate, lagged",
        "log_oil_l1": "Log oil price, lagged",
        "inflation_l1": "Inflation, lagged",
        "gpr": "GPR, contemporaneous",
        "log_gepu_l1": "Log global EPU, lagged",
        "financial_development_l1": "Financial development, lagged",
        "debt_gdp_l1": "Debt/GDP, lagged",
    }
    for name in INSTRUMENTS:
        cells = "".join(f"<td>{cell(fit['first'][name])}</td>" for _, _, fit in results)
        instrument_rows.append(f"<tr><td>{escape(labels[name])}</td>{cells}</tr>")
    country_items = []
    for _, label, fit in results:
        country_items.append(f"<li>{escape(label)}: {escape(', '.join(fit['countries']))}</li>")
    missing = [country for country in read_country_order() if country not in reer_countries]
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Export trend and real effective exchange rate, 2SLS</title>
<style>
body {{ font: 16px/1.5 Georgia, serif; max-width: 1100px; margin: 2em auto; padding: 0 1em; color: #20242a; }}
table {{ border-collapse: collapse; width: 100%; margin: 1em 0; font-size: .92em; }}
th, td {{ border-bottom: 1px solid #ccc; padding: .45em; text-align: right; vertical-align: top; }}
th:first-child, td:first-child {{ text-align: left; }}
.note {{ background: #fff5da; padding: 1em; border: 1px solid #e6d59d; }}
code {{ font-size: .92em; }}
</style>
</head>
<body>
<h1>Export trend and the real effective exchange rate</h1>
<div class="note">
<p>Second stage: <code>log(REER)</code> on the fitted Hodrick-Prescott log trend of nominal exports and country fixed effects.</p>
<p>First stage: the export trend on the excluded instruments and country fixed effects. The instruments do not enter the second stage. GPR is contemporaneous. Every other instrument is lagged one month. Annual series use the year of that lagged month, so January uses the previous year.</p>
<p>The monthly export trend uses lambda 129600. That scaling is not from the lecture. Standard errors are clustered by country and use the 2SLS structural residual. Each cell shows the coefficient, the standard error in parentheses, and the 95% confidence interval.</p>
<p>Countries with no real effective exchange rate are omitted: {escape(", ".join(missing))}.</p>
</div>
<h2>Second stage</h2>
<table>
<thead><tr><th></th>{header}</tr></thead>
<tbody>
<tr><td>Fitted export trend</td>{second_cells}</tr>
<tr><td>Observations</td>{sample_cells}</tr>
<tr><td>First-stage partial F</td>{f_cells}</tr>
</tbody>
</table>
<p><em>Significance:</em> *** p&lt;0.01, ** p&lt;0.05, * p&lt;0.10.</p>
<h2>First stage</h2>
<table>
<thead><tr><th>Instrument</th>{header}</tr></thead>
<tbody>
{"".join(instrument_rows)}
</tbody>
</table>
<h2>Countries in each regression</h2>
<ul>
{"".join(country_items)}
</ul>
</body>
</html>
"""
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(html)


def main():
    if abs(student_t_ppf(0.975, 12) - 2.1788128296666256) > 1e-6:
        raise RuntimeError("The t critical value does not match the reference.")
    reer = read_reer()
    sources_common = {
        "countries": read_country_order(),
        "trend": read_export_trend(),
        "reer": reer,
        "vix": read_monthly_global("vix.csv", "value"),
        "policy": read_monthly_country("policy_rate.csv", "value"),
        "oil": read_monthly_global("oil_price.csv", "wti_spot"),
        "inflation": read_monthly_country("inflation.csv", "value"),
        "gpr": read_monthly_global("gpr_index.csv", "value", series="GPR"),
        "gepu": read_monthly_global("gepu_current.csv", "value"),
        "fd": read_annual("financial_development.csv", "year", "fd_fdi_ovrl"),
        "debt": read_annual("debt_gdp.csv", "period", "debt_gdp_pct", frequency="Annual"),
    }
    results = []
    for code, label in DIMENSIONS:
        sources = dict(sources_common)
        sources["wgi"] = read_wgi(code)
        rows = build_panel(code, sources)
        fit = fit_2sls(rows)
        results.append((code, label, fit))
        print(
            label,
            "N",
            fit["n_obs"],
            "countries",
            fit["n_country"],
            "b",
            fit["second"]["ytrend_hat"]["coef"],
            "F",
            fit["partial_f"],
        )
    write_csv(os.path.join(OUTPUT, "export_reer_2sls_results.csv"), results)
    write_html(os.path.join(OUTPUT, "export_reer_2sls_results.html"), results, set(reer))


if __name__ == "__main__":
    main()
