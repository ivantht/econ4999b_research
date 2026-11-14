"""Emerging-market replication of the paper's capital-flow-volatility column.

The first regression is Equation (2): capital-flow volatility on GPR and the
paper's lagged controls, with country fixed effects. The next three regressions
add one centered WGI score and its interaction with GPR.
"""

import csv
import os
from collections import defaultdict
from datetime import datetime
from html import escape

import numpy as np
import openpyxl

import run_export_reer_2sls as est


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUTPUT = os.path.join(ROOT, "output")
PANEL = os.path.join(ROOT, "cleaned", "replication_cleaned", "country_month.csv")
OECD = os.path.join(ROOT, "input", "OECD-monthly-capital-flow-dataset.xlsx")

PANEL_NAME = {"Turkiye": "Turkey", "Korea": "South Korea"}
OECD_NAME = {"Türkiye": "Turkey", "Korea": "South Korea"}
CONTROLS = [
    "policy_rate_l1", "log_ip_l1", "inflation_l1", "log_oil_l1", "log_vix_l1",
    "log_gepu_l1", "financial_development_l1", "cbi_l1", "debt_gdp_l1",
]
AUTHOR_COLUMNS = ["gpr", *CONTROLS]
WGI_COLUMNS = ["gpr", "wgi_l1", "wgi_x_gpr", *CONTROLS]
DIMENSIONS = [
    ("rl", "Rule of law"),
    ("ge", "Government effectiveness"),
    ("rq", "Regulatory quality"),
]
LABELS = {
    "gpr": "GPR",
    "wgi_l1": "WGI",
    "wgi_x_gpr": "WGI x GPR",
    "policy_rate_l1": "Policy rate",
    "log_ip_l1": "Real industrial production",
    "inflation_l1": "Inflation",
    "log_oil_l1": "Oil price",
    "log_vix_l1": "VIX",
    "log_gepu_l1": "Global EPU",
    "financial_development_l1": "Financial development",
    "cbi_l1": "Central bank independence",
    "debt_gdp_l1": "Debt/GDP",
}
EQUATION = (
    "Capital-flow volatility = GPR + lagged policy rate + lagged log industrial production "
    "+ lagged inflation + lagged log oil + lagged log VIX + lagged log global EPU "
    "+ lagged financial development + lagged central-bank independence + lagged debt/GDP "
    "+ country effects"
)
WGI_EQUATION = EQUATION.replace(
    "+ country effects",
    "+ lagged WGI + lagged WGI x GPR + country effects",
)
PAPER_GPR = 3.144
PAPER_SE = 1.840
PAPER_N = 1569
PAPER_R2 = 0.011
OUTCOME = "Capital-flow volatility, billion US dollars"


def num(text):
    if text is None:
        return None
    text = str(text).strip()
    if not text:
        return None
    return float(text)


def load_panel():
    index = {}
    countries = []
    seen = set()
    with open(PANEL, encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["group"].strip() != "Emerging":
                continue
            country = PANEL_NAME.get(row["country"].strip(), row["country"].strip())
            index[(country, row["date"][:7])] = row
            if country not in seen:
                seen.add(country)
                countries.append(country)
    return index, countries


def lagged_controls(source):
    names = CONTROLS
    if source is None:
        return {name: None for name in names}
    return {
        "policy_rate_l1": num(source.get("policy_rate")),
        "log_ip_l1": est.positive_log(num(source.get("industrial_production"))),
        "inflation_l1": num(source.get("inflation")),
        "log_oil_l1": est.positive_log(num(source.get("oil_price"))),
        "log_vix_l1": est.positive_log(num(source.get("vix"))),
        "log_gepu_l1": est.positive_log(num(source.get("gepu"))),
        "financial_development_l1": num(source.get("financial_development")),
        "cbi_l1": num(source.get("central_bank_independence")),
        "debt_gdp_l1": num(source.get("public_debt_gdp")),
    }


def load_oecd_volatility():
    workbook = openpyxl.load_workbook(OECD, read_only=True, data_only=True)
    sheet = workbook["panel"]
    levels = defaultdict(dict)
    header = None
    for index, row in enumerate(sheet.iter_rows(values_only=True)):
        if index == 0:
            header = [str(cell).strip() if cell else "" for cell in row]
            continue
        record = dict(zip(header, row))
        country = record.get("country")
        if not country:
            continue
        country = OECD_NAME.get(country, country)
        month = record.get("month")
        if isinstance(month, datetime):
            year_month = month.strftime("%Y-%m")
        else:
            year_month = str(month)[:7]
        value = record.get("port_inf")
        if value in (None, ""):
            continue
        levels[country][year_month] = float(value)
    volatility = {}
    for country, series in levels.items():
        for month in series:
            window = []
            complete = True
            for lag in (0, -1, -2):
                earlier = series.get(est.add_months(month, lag))
                if earlier is None:
                    complete = False
                    break
                window.append(earlier)
            if complete:
                volatility[(country, month)] = float(np.std(window, ddof=1))
    return volatility


def any_filled(index, country, column):
    return any(
        (source.get(column) or "").strip()
        for (name, _month), source in index.items()
        if name == country
    )


def base_rows(index, countries, volatility):
    rows = []
    present = []
    for country in countries:
        country_rows = []
        for (name, month), source in index.items():
            if name != country:
                continue
            lag = est.add_months(month, -1)
            record = {
                "country": country,
                "year_month": month,
                "outcome": volatility.get((country, month)),
                "gpr_raw": num(source.get("gpr")),
                "lag_year": int(lag[:4]),
            }
            record.update(lagged_controls(index.get((country, lag))))
            needed = ["outcome", "gpr_raw", *CONTROLS]
            if any(record.get(name) is None for name in needed):
                continue
            country_rows.append(record)
        if country_rows:
            rows.extend(country_rows)
            present.append(country)
    return rows, present


def with_wgi(rows, wgi):
    if wgi is None:
        return [dict(row) for row in rows], None
    kept = []
    for row in rows:
        raw = wgi.get(row["country"], {}).get(row["lag_year"])
        if raw is None:
            continue
        record = dict(row)
        record["wgi_raw"] = raw
        kept.append(record)
    return kept, None


def standardize(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["country"]].append(row["gpr_raw"])
    moments = {}
    for country, values in grouped.items():
        array = np.array(values, dtype=float)
        deviation = float(array.std(ddof=1)) if len(array) > 1 else float("nan")
        moments[country] = (float(array.mean()), deviation)
    kept = []
    for row in rows:
        mean, deviation = moments[row["country"]]
        if not np.isfinite(deviation) or deviation == 0:
            continue
        row["gpr"] = (row["gpr_raw"] - mean) / deviation
        kept.append(row)
    if not kept:
        raise RuntimeError("No complete cases after standardizing GPR.")
    center = None
    if kept and "wgi_raw" in kept[0]:
        center = float(np.mean([row["wgi_raw"] for row in kept]))
        for row in kept:
            row["wgi_l1"] = row["wgi_raw"] - center
            row["wgi_x_gpr"] = row["wgi_l1"] * row["gpr"]
    return kept, center


def drop_reason(index, country):
    if not any_filled(index, country, "industrial_production"):
        return "no industrial production in the replication file"
    if not any_filled(index, country, "policy_rate"):
        return "no policy rate in the replication file"
    return "no month with every required series"


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


def within_r2(rows, columns):
    countries = np.array([row["country"] for row in rows])
    outcome = np.array([row["outcome"] for row in rows], dtype=float)
    regressors = np.column_stack([
        np.array([row[name] for row in rows], dtype=float) for name in columns
    ])
    for country in set(countries):
        mask = countries == country
        outcome[mask] -= outcome[mask].mean()
        regressors[mask] -= regressors[mask].mean(axis=0)
    fitted = np.linalg.lstsq(regressors, outcome, rcond=None)[0]
    residual = outcome - regressors @ fitted
    total = float(outcome @ outcome)
    if total == 0:
        return 0.0
    return float(1.0 - (residual @ residual) / total)


def fit_ols(rows, columns):
    countries = sorted({row["country"] for row in rows})
    outcome = np.array([row["outcome"] for row in rows], dtype=float)
    matrix, names, _base = est.design_matrix(rows, columns, countries)
    count, width = matrix.shape
    grouped = est.cluster_indices(rows)
    coefficient = np.linalg.lstsq(matrix, outcome, rcond=None)[0]
    residual = outcome - matrix @ coefficient
    variance, _ = est.cluster_variance(matrix, residual, grouped, count, width)
    return {
        "stats": est.inference(names, coefficient, variance, len(grouped)),
        "sample": sample_info(rows),
        "r2": within_r2(rows, columns),
        "columns": columns,
        "center": float(np.mean([row["wgi_raw"] for row in rows])) if "wgi_raw" in rows[0] else None,
    }


def stat_fields(stat):
    return {key: f"{stat[key]:.10g}" for key in ("coef", "se", "t", "p", "ci_lo", "ci_hi")}


def write_csv(path, blocks, dropped):
    fields = [
        "specification", "dimension", "variable", "label",
        "paper_gpr", "paper_se", "paper_n", "paper_r2",
        "coef", "se", "t", "p", "ci_lo", "ci_hi",
        "n_obs", "n_country", "r2", "month_min", "month_max", "countries", "dropped",
        "wgi_center",
    ]
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for block in blocks:
            fitted = block["fit"]
            shared = {
                "specification": block["title"],
                "dimension": block["code"],
                "paper_gpr": f"{PAPER_GPR:.3f}",
                "paper_se": f"{PAPER_SE:.3f}",
                "paper_n": PAPER_N,
                "paper_r2": f"{PAPER_R2:.3f}",
                "n_obs": fitted["sample"]["n_obs"],
                "n_country": fitted["sample"]["n_country"],
                "r2": f"{fitted['r2']:.10g}",
                "month_min": fitted["sample"]["month_min"],
                "month_max": fitted["sample"]["month_max"],
                "countries": "; ".join(fitted["sample"]["countries"]),
                "dropped": "; ".join(f"{country}: {reason}" for country, reason in dropped),
                "wgi_center": "" if fitted["center"] is None else f"{fitted['center']:.10g}",
            }
            for variable in fitted["columns"]:
                writer.writerow({
                    **shared,
                    "variable": variable,
                    "label": LABELS[variable],
                    **stat_fields(fitted["stats"][variable]),
                })


def cell(stat):
    if stat is None:
        return ""
    return (
        f"{est.fmt(stat['coef'])}{est.stars(stat['p'])}<br>"
        f"({est.fmt(stat['se'])})<br>"
        f"[{est.fmt(stat['ci_lo'])}, {est.fmt(stat['ci_hi'])}]"
    )


def write_html(path, blocks, dropped):
    header = "".join(f"<th>{escape(block['title'])}</th>" for block in blocks)
    body = []
    for variable in WGI_COLUMNS:
        cells = []
        for block in blocks:
            stat = block["fit"]["stats"].get(variable) if variable in block["fit"]["columns"] else None
            reference = ""
            if variable == "gpr" and block["code"] == "author":
                reference = "<br>Paper Table 3: 3.144*<br>(1.840)"
            cells.append(f"<td>{cell(stat)}{reference}</td>")
        body.append(f"<tr><td>{escape(LABELS[variable])}</td>{''.join(cells)}</tr>")
    sample = "".join(
        "<td>{n}<br>{g} countries<br>{start} to {end}<br>Within R2 {r2}{center}</td>".format(
            n=block["fit"]["sample"]["n_obs"],
            g=block["fit"]["sample"]["n_country"],
            start=escape(block["fit"]["sample"]["month_min"]),
            end=escape(block["fit"]["sample"]["month_max"]),
            r2=est.fmt(block["fit"]["r2"]),
            center=(
                "" if block["fit"]["center"] is None
                else f"<br>WGI center {est.fmt(block['fit']['center'])}"
            ),
        )
        for block in blocks
    )
    kept = "".join(
        f"<li>{escape(block['title'])}: {escape(', '.join(block['fit']['sample']['countries']))}</li>"
        for block in blocks
    )
    dropped_items = "".join(
        f"<li>{escape(country)}: {escape(reason)}</li>" for country, reason in dropped
    )
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Emerging-market volatility replication</title>
<style>
body {{ font: 16px/1.5 Georgia, serif; max-width: 1200px; margin: 2em auto; padding: 0 1em; color: #20242a; }}
table {{ border-collapse: collapse; width: 100%; margin: 1em 0; font-size: .92em; }}
th, td {{ border-bottom: 1px solid #ccc; padding: .45em; text-align: right; vertical-align: top; }}
th:first-child, td:first-child {{ text-align: left; }}
.equation {{ background: #f4f6f8; padding: .8em 1em; }}
.note {{ background: #fff5da; padding: 1em; border: 1px solid #e6d59d; }}
</style>
</head>
<body>
<h1>Emerging-market capital-flow volatility</h1>
<div class="note">
<p>The sample is the emerging economies in the replication file. The outcome is the three-month standard deviation of gross portfolio inflows, column port_inf in the September 2026 OECD Monthly Capital Flow Dataset, in billion US dollars. On the 6,505 months from 2000 through 2023, that series matches capital_flow_volatility in the replication file. Months before 2000 or after the controls end do not enter. GPR is contemporaneous and standardized within country on the months in that column. The other controls use the previous month. Oil, VIX, global EPU, and industrial production are logged. Each cell shows the coefficient, the country-clustered standard error in parentheses, and the 95% confidence interval. *** p&lt;0.01, ** p&lt;0.05, * p&lt;0.10.</p>
<p>The first column is Equation (2), with no WGI term. Table 3's emerging GPR coefficient is 3.144 (standard error 1.840), with 1,569 observations and an R-squared of 0.011. This OECD extract's volatility reaches 412, while Table 1's maximum is 528. The other columns add one centered WGI score and its interaction with GPR. WGI is the calendar year of the lagged month, and a missing year drops that month from that column only.</p>
</div>
<h2>Capital-flow volatility</h2>
<p><strong>Outcome:</strong> {escape(OUTCOME)}</p>
<p class="equation">{escape(EQUATION)}</p>
<p class="equation">{escape(WGI_EQUATION)}</p>
<table><thead><tr><th>Variable</th>{header}</tr></thead>
<tbody>{''.join(body)}<tr><td>Observations</td>{sample}</tr></tbody></table>
<h3>Emerging countries that remain</h3>
<ul>{kept}</ul>
<h3>Emerging countries that drop</h3>
<ul>{dropped_items}</ul>
</body>
</html>
"""
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(html)


def main():
    index, countries = load_panel()
    prepared, present = base_rows(index, countries, load_oecd_volatility())
    author_rows, _center = standardize(with_wgi(prepared, None)[0])
    author = fit_ols(author_rows, AUTHOR_COLUMNS)
    blocks = [{
        "code": "author",
        "title": "Author equation",
        "fit": author,
    }]
    print(
        "Author", "N", author["sample"]["n_obs"], author["sample"]["n_country"],
        "R2", round(author["r2"], 4),
        author["sample"]["month_min"], author["sample"]["month_max"],
    )
    stat = author["stats"]["gpr"]
    print("  gpr", round(stat["coef"], 4), "se", round(stat["se"], 4), "p", round(stat["p"], 4))
    for code, label in DIMENSIONS:
        rows, center = standardize(with_wgi(prepared, est.read_wgi(code))[0])
        fitted = fit_ols(rows, WGI_COLUMNS)
        blocks.append({"code": code, "title": label, "fit": fitted})
        print(
            label, "N", fitted["sample"]["n_obs"], "R2", round(fitted["r2"], 4),
            "center", round(center, 4),
        )
        for variable in ("gpr", "wgi_l1", "wgi_x_gpr"):
            item = fitted["stats"][variable]
            print(
                " ", variable, round(item["coef"], 4),
                "p", round(item["p"], 4), est.stars(item["p"]),
            )
    dropped = [
        (country, drop_reason(index, country))
        for country in countries
        if country not in present
    ]
    write_csv(
        os.path.join(OUTPUT, "emerging_volatility_replication_results.csv"),
        blocks,
        dropped,
    )
    write_html(
        os.path.join(OUTPUT, "emerging_volatility_replication_results.html"),
        blocks,
        dropped,
    )
    for country, reason in dropped:
        print("drop", country, reason)


if __name__ == "__main__":
    main()
