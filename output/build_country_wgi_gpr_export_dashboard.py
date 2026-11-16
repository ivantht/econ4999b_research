import csv
import json
import math
from collections import defaultdict
from html import escape
from itertools import combinations
from pathlib import Path

import openpyxl


ROOT = Path(__file__).resolve().parents[1]
CLEANED = ROOT / "cleaned"
OUTPUT = ROOT / "output"
WGI_CSV = CLEANED / "wgi.csv"
GPR_CSV = CLEANED / "gpr_country.csv"
EXPORT_XLSX = ROOT / "input" / "monthly nominal export.xlsx"
REER_XLSX = CLEANED / "real effective exchange rate.xlsx"
CAPITAL_FLOW_CSV = CLEANED / "replication_cleaned" / "country_month.csv"
GLOBAL_CONTROL_SOURCES = {
    "oil": (CLEANED / "oil_price.csv", "wti_spot"),
    "vix": (CLEANED / "vix.csv", "value"),
    "gepu": (CLEANED / "gepu_current.csv", "value"),
}
COUNTRY_CONTROL_LABELS = {
    "policy_rate": "Policy rate (%)",
    "inflation": "Inflation (%)",
    "debt_gdp": "Government debt / GDP (%)",
    "financial_development": "Financial development index",
}
GLOBAL_CONTROL_LABELS = {
    "oil": "ln(oil price)",
    "vix": "ln(VIX)",
    "gepu": "ln(GEPU)",
}
GLOBAL_CHANGE_LABELS = {
    "vix": "ln(VIX)",
    "gepu_change": "Change in ln(GEPU)",
    "oil_change": "Change in ln(oil price)",
}
HTML_OUT = OUTPUT / "country_wgi_gpr_export_dashboard.html"
CORRELATION_OUT = OUTPUT / "country_wgi_gpr_export_correlations.csv"
ASPECT_CORRELATION_OUT = OUTPUT / "wgi_aspect_pooled_correlations.csv"

MODEL_START_YEAR = 2001
MODEL_END_YEAR = 2023
ASPECTS = ("va", "pv", "ge", "rq", "rl", "cc")
ASPECT_LABELS = {
    "va": "Voice and Accountability",
    "pv": "Political Stability and Absence of Violence/Terrorism",
    "ge": "Government Effectiveness",
    "rq": "Regulatory Quality",
    "rl": "Rule of Law",
    "cc": "Control of Corruption",
}
CORE_VARIABLES = ("wgi", "gpr", "export_log_change")
VARIABLES = (*CORE_VARIABLES, "capital_flow_volatility", "reer_log_change")
VARIABLE_LABELS = {
    "wgi": "WGI",
    "gpr": "Country GPR",
    "export_log_change": "Change in ln(nominal exports)",
    "capital_flow_volatility": "Capital-flow volatility",
    "reer_log_change": "Change in ln(REER)",
}
CORRELATION_PAIRS = tuple(combinations(VARIABLES, 2))
CAPITAL_FLOW_COUNTRY_ALIASES = {"Turkiye": "Turkey", "Korea": "South Korea"}


def parse_value(raw, path, line_number):
    value = raw.strip()
    if not value:
        return None
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError(f"Invalid numeric value in {path} at line {line_number}: {raw!r}") from exc
    if not math.isfinite(parsed):
        return None
    return parsed


def read_wgi(path):
    values = {}
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        required = {"country", "year", "dimension", "estimate"}
        if not required.issubset(reader.fieldnames or ()):
            raise ValueError(f"{path} must contain columns: {', '.join(sorted(required))}")
        for line_number, row in enumerate(reader, start=2):
            country = (row["country"] or "").strip()
            aspect = (row["dimension"] or "").strip().lower()
            if not country or aspect not in ASPECTS:
                continue
            score = parse_value(row["estimate"] or "", path, line_number)
            if score is None:
                continue
            key = (country, int(row["year"]), aspect)
            if key in values:
                raise ValueError(f"Duplicate WGI observation in {path} at line {line_number}: {key}")
            values[key] = score
    return values


def read_monthly_annual_means(path, value_column):
    grouped = defaultdict(list)
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        required = {"country", "year_month", value_column}
        if not required.issubset(reader.fieldnames or ()):
            raise ValueError(f"{path} must contain columns: {', '.join(sorted(required))}")
        seen = set()
        for line_number, row in enumerate(reader, start=2):
            country = (row["country"] or "").strip()
            month = (row["year_month"] or "").strip()
            if not country or not month:
                continue
            key = (country, month)
            if key in seen:
                raise ValueError(f"Duplicate monthly observation in {path} at line {line_number}: {key}")
            seen.add(key)
            value = parse_value(row[value_column] or "", path, line_number)
            if value is not None:
                grouped[(country, int(month[:4]))].append(value)
    return {key: sum(values) / len(values) for key, values in grouped.items() if values}


def read_workbook_annual_means(path):
    grouped = defaultdict(list)
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        rows = workbook.active.iter_rows(values_only=True)
        header = next(rows)
        if header[0] != "month":
            raise ValueError(f"{path} must have a month column")
        countries = [str(value).strip() if value is not None else "" for value in header[1:]]
        if not all(countries) or len(set(countries)) != len(countries):
            raise ValueError(f"{path} has missing or duplicate country columns")
        seen = set()
        for line_number, row in enumerate(rows, start=2):
            if row[0] is None:
                continue
            month = str(row[0]).strip()
            if len(month) != 7 or month[4] != "-" or not month[:4].isdigit() or not month[5:].isdigit() or not 1 <= int(month[5:]) <= 12:
                raise ValueError(f"Invalid month in {path} at row {line_number}: {month!r}")
            if month in seen:
                raise ValueError(f"Duplicate month in {path} at row {line_number}: {month}")
            seen.add(month)
            for country, value in zip(countries, row[1:]):
                if value is None or value == "":
                    continue
                numeric = parse_value(str(value), path, line_number)
                if numeric is None or numeric <= 0:
                    raise ValueError(f"Non-positive or non-finite value in {path} at row {line_number}: {country}")
                grouped[(country, int(month[:4]))].append(numeric)
    finally:
        workbook.close()
    return {key: sum(values) / len(values) for key, values in grouped.items()}


def annual_log_changes(annual_values):
    return {
        (country, year): math.log(value) - math.log(annual_values[(country, year - 1)])
        for (country, year), value in annual_values.items()
        if (country, year - 1) in annual_values
    }


def read_global_annual_log_means(path, value_column):
    grouped = defaultdict(list)
    seen = set()
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if not {"year_month", value_column}.issubset(reader.fieldnames or ()):
            raise ValueError(f"{path} must contain year_month and {value_column}")
        for line_number, row in enumerate(reader, start=2):
            month = (row["year_month"] or "").strip()
            if not month:
                raise ValueError(f"Missing month in {path} at line {line_number}")
            if month in seen:
                raise ValueError(f"Duplicate month in {path} at line {line_number}: {month}")
            seen.add(month)
            value = parse_value(row[value_column] or "", path, line_number)
            if value is not None:
                if value <= 0:
                    raise ValueError(f"Non-positive value in {path} at line {line_number}")
                grouped[int(month[:4])].append(math.log(value))
    return {year: sum(values) / len(values) for year, values in grouped.items()}


def annual_changes(values):
    return {
        year: value - values[year - 1]
        for year, value in values.items()
        if year - 1 in values
    }


def read_annual_country_values(path, year_column, value_column, annual_only=False):
    values = {}
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        required = {"country", year_column, value_column}
        if annual_only:
            required.add("frequency")
        if not required.issubset(reader.fieldnames or ()):
            raise ValueError(f"{path} must contain columns: {', '.join(sorted(required))}")
        for line_number, row in enumerate(reader, start=2):
            if annual_only and row["frequency"] != "Annual":
                continue
            country = (row["country"] or "").strip()
            if not country or not row[year_column]:
                raise ValueError(f"Missing country or year in {path} at line {line_number}")
            key = (country, int(row[year_column]))
            if key in values:
                raise ValueError(f"Duplicate annual observation in {path} at line {line_number}: {key}")
            value = parse_value(row[value_column] or "", path, line_number)
            if value is not None:
                values[key] = value
    return values


def read_financial_development_index(path):
    grouped = defaultdict(list)
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        required = {"country", "date", "financial_development"}
        if not required.issubset(reader.fieldnames or ()):
            raise ValueError(f"{path} must contain columns: {', '.join(sorted(required))}")
        seen = set()
        for line_number, row in enumerate(reader, start=2):
            country = (row["country"] or "").strip()
            country = CAPITAL_FLOW_COUNTRY_ALIASES.get(country, country)
            date = (row["date"] or "").strip()
            if not country or not date:
                raise ValueError(f"Missing country or date in {path} at line {line_number}")
            month_key = (country, date[:7])
            if month_key in seen:
                raise ValueError(f"Duplicate monthly observation in {path} at line {line_number}: {month_key}")
            seen.add(month_key)
            value = parse_value(row["financial_development"] or "", path, line_number)
            if value is not None:
                grouped[(country, int(date[:4]))].append(value)
    result = {}
    for key, values in grouped.items():
        if any(value != values[0] for value in values):
            raise ValueError(f"Financial-development index varies within {key} in {path}")
        result[key] = values[0]
    return result


def control_points(series, country=None):
    points = []
    for year in range(MODEL_START_YEAR, MODEL_END_YEAR + 1):
        key = (country, year) if country is not None else year
        point = {"year": year}
        point.update({name: values.get(key) for name, values in series.items()})
        points.append(point)
    for name in series:
        available = [point for point in points if point[name] is not None]
        for point in points:
            point[f"index_{name}"] = None
        if available:
            for point, index in zip(available, base_100_index([point[name] for point in available])):
                point[f"index_{name}"] = index
    return points


def read_capital_flow_volatility(path):
    grouped = defaultdict(list)
    seen = set()
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        required = {"country", "date", "capital_flow_volatility"}
        if not required.issubset(reader.fieldnames or ()):
            raise ValueError(f"{path} must contain columns: {', '.join(sorted(required))}")
        for line_number, row in enumerate(reader, start=2):
            country = CAPITAL_FLOW_COUNTRY_ALIASES.get(
                (row["country"] or "").strip(), (row["country"] or "").strip()
            )
            date = (row["date"] or "").strip()
            if not country or not date:
                continue
            month = date[:7]
            key = (country, month)
            if key in seen:
                raise ValueError(f"Duplicate monthly volatility observation in {path} at line {line_number}: {key}")
            seen.add(key)
            value = parse_value(row["capital_flow_volatility"] or "", path, line_number)
            if value is not None:
                grouped[(country, int(date[:4]))].append(value)
    means = {key: sum(values) / len(values) for key, values in grouped.items() if values}
    counts = {key: len(values) for key, values in grouped.items() if values}
    return means, counts


def pearson(left, right):
    if len(left) != len(right) or len(left) < 2:
        return None
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    left_centered = [value - left_mean for value in left]
    right_centered = [value - right_mean for value in right]
    left_ss = sum(value * value for value in left_centered)
    right_ss = sum(value * value for value in right_centered)
    if left_ss == 0 or right_ss == 0:
        return None
    return sum(a * b for a, b in zip(left_centered, right_centered)) / math.sqrt(left_ss * right_ss)


def z_scores(values):
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1) if len(values) > 1 else 0
    if variance == 0:
        return [0.0] * len(values)
    standard_deviation = math.sqrt(variance)
    return [(value - mean) / standard_deviation for value in values]


def base_100_index(values):
    low, high = min(values), max(values)
    value_range = high - low
    base = values[0]
    if value_range == 0:
        return [100.0] * len(values)
    return [100.0 + 100.0 * (value - base) / value_range for value in values]


def correlation_rows(wgi, gpr, export_change, volatility, volatility_months, reer_change):
    countries = sorted(
        {country for country, _, _ in wgi}
        & {country for country, _ in gpr}
        & {country for country, _ in export_change}
    )
    volatility_countries = sorted({country for country, _ in volatility})
    observations = {}
    correlations = []
    for country in countries:
        for aspect in ASPECTS:
            years = range(MODEL_START_YEAR, MODEL_END_YEAR + 1)
            if not any((country, year, aspect) in wgi for year in years):
                continue
            points = [
                {
                    "year": year,
                    "wgi": wgi.get((country, year, aspect)),
                    "gpr": gpr.get((country, year)),
                    "export_log_change": export_change.get((country, year)),
                    "capital_flow_volatility": volatility.get((country, year)),
                    "reer_log_change": reer_change.get((country, year)),
                    "volatility_months": volatility_months.get((country, year), 0),
                }
                for year in years
            ]
            if not points:
                continue
            key = f"{country}|{aspect}"
            observations[key] = points
            pair_correlations = {}
            for left, right in CORRELATION_PAIRS:
                complete = [point for point in points if point[left] is not None and point[right] is not None]
                pair_key = f"{left}|{right}"
                pair_correlations[pair_key] = {
                    "r": pearson(
                        [point[left] for point in complete],
                        [point[right] for point in complete],
                    ),
                    "n": len(complete),
                }
            correlations.append(
                {
                    "country": country,
                    "aspect": aspect,
                    "n_model_horizon_years": len(points),
                    "start_year": MODEL_START_YEAR,
                    "end_year": MODEL_END_YEAR,
                    "pairs": pair_correlations,
                }
            )
    pooled_correlations = []
    for aspect in ASPECTS:
        for left, right in CORRELATION_PAIRS:
            pooled_left = []
            pooled_right = []
            country_count = 0
            for country in countries:
                points = observations.get(f"{country}|{aspect}", [])
                complete = [point for point in points if point[left] is not None and point[right] is not None]
                if len(complete) < 2:
                    continue
                left_values = [point[left] for point in complete]
                right_values = [point[right] for point in complete]
                if len(set(left_values)) < 2 or len(set(right_values)) < 2:
                    continue
                pooled_left.extend(z_scores(left_values))
                pooled_right.extend(z_scores(right_values))
                country_count += 1
            pooled_correlations.append(
                {
                    "aspect": aspect,
                    "left": left,
                    "right": right,
                    "r": pearson(pooled_left, pooled_right),
                    "n_country_years": len(pooled_left),
                    "n_countries": country_count,
                }
            )
    return countries, volatility_countries, observations, correlations, pooled_correlations


def json_for_script(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def pair_column(left, right, prefix):
    return f"{prefix}_{left}_{right}"


def write_correlation_csv(rows):
    columns = ["country", "wgi_aspect", "n_model_horizon_years", "start_year", "end_year"]
    for left, right in CORRELATION_PAIRS:
        columns.extend((pair_column(left, right, "corr"), pair_column(left, right, "n")))
    with CORRELATION_OUT.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            output_row = {
                "country": row["country"],
                "wgi_aspect": row["aspect"],
                "n_model_horizon_years": row["n_model_horizon_years"],
                "start_year": row["start_year"],
                "end_year": row["end_year"],
            }
            for left, right in CORRELATION_PAIRS:
                pair = row["pairs"][f"{left}|{right}"]
                output_row[pair_column(left, right, "corr")] = pair["r"]
                output_row[pair_column(left, right, "n")] = pair["n"]
            writer.writerow(output_row)


def write_aspect_correlation_csv(rows):
    fields = [
        "wgi_aspect",
        "variable_1",
        "variable_2",
        "pearson_r",
        "country_year_observations",
        "countries",
        "pooling_method",
    ]
    with ASPECT_CORRELATION_OUT.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "wgi_aspect": row["aspect"],
                    "variable_1": row["left"],
                    "variable_2": row["right"],
                    "pearson_r": row["r"],
                    "country_year_observations": row["n_country_years"],
                    "countries": row["n_countries"],
                    "pooling_method": "Within-country sample z-scores, then pooled across country-years",
                }
            )


def write_dashboard(
    countries,
    volatility_countries,
    observations,
    correlations,
    pooled_correlations,
    volatility,
    volatility_months,
    global_controls,
    country_controls,
):
    correlation_lookup = {f"{row['country']}|{row['aspect']}": row for row in correlations}
    aspect_options = "".join(
        f"<option value='{aspect}'>{escape(ASPECT_LABELS[aspect])}</option>" for aspect in ASPECTS
    )
    default_country = next(
        (
            country
            for country in countries
            if any(
                point["capital_flow_volatility"] is not None
                for aspect in ASPECTS
                for point in observations.get(f"{country}|{aspect}", [])
            )
        ),
        countries[0],
    )
    country_options = "".join(
        f"<option{' selected' if country == default_country else ''}>{escape(country)}</option>"
        for country in countries
    )
    volatility_country_options = "".join(
        f"<option>{escape(country)}</option>" for country in volatility_countries
    )
    volatility_overlap = len(set(countries) & set(volatility_countries))
    volatility_data = {}
    for country in volatility_countries:
        points = [
            {"year": year, "value": value, "months": volatility_months[(country, year)]}
            for (point_country, year), value in volatility.items()
            if point_country == country and MODEL_START_YEAR <= year <= MODEL_END_YEAR
        ]
        points.sort(key=lambda point: point["year"])
        for point, index in zip(points, base_100_index([point["value"] for point in points])):
            point["index"] = index
        volatility_data[country] = points

    pooled_lookup = {
        (row["aspect"], row["left"], row["right"]): row for row in pooled_correlations
    }
    summary_headers = "".join(
        f"<th>{escape(VARIABLE_LABELS[left])} × {escape(VARIABLE_LABELS[right])}</th>"
        for left, right in CORRELATION_PAIRS
    )
    summary_rows = []
    for aspect in ASPECTS:
        cells = []
        for left, right in CORRELATION_PAIRS:
            row = pooled_lookup[(aspect, left, right)]
            coefficient = "—" if row["r"] is None else f"{row['r']:.3f}"
            cells.append(
                f"<td>{coefficient}<br><small>n={row['n_country_years']}, "
                f"countries={row['n_countries']}</small></td>"
            )
        summary_rows.append(
            f"<tr><th>{escape(ASPECT_LABELS[aspect])}</th>{''.join(cells)}</tr>"
        )
    summary_table = (
        "<div class='table-wrap'><table><thead><tr><th>WGI aspect</th>"
        f"{summary_headers}</tr></thead><tbody>{''.join(summary_rows)}</tbody></table></div>"
    )
    chart_json = json_for_script(observations)
    volatility_json = json_for_script(volatility_data)
    correlation_json = json_for_script(correlation_lookup)
    variable_labels_json = json_for_script(VARIABLE_LABELS)
    global_controls_json = json_for_script(control_points(global_controls))
    global_change_json = json_for_script(control_points({
        "vix": global_controls["vix"],
        "gepu_change": annual_changes(global_controls["gepu"]),
        "oil_change": annual_changes(global_controls["oil"]),
    }))
    country_controls_json = json_for_script({
        country: control_points(country_controls, country) for country in countries
    })
    country_control_options = "".join(
        f"<option value='{escape(name)}'>{escape(label)}</option>"
        for name, label in COUNTRY_CONTROL_LABELS.items()
    )
    with HTML_OUT.open("w", encoding="utf-8") as output:
        output.write(
            "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            "<title>Country WGI, GPR, export and REER changes, and capital-flow volatility</title>"
            "<script src='https://cdn.plot.ly/plotly-2.35.2.min.js'></script>"
            "<style>body{font:16px/1.5 Georgia,serif;max-width:1250px;margin:2em auto;padding:0 1em;color:#20242a}"
            ".controls{display:flex;flex-wrap:wrap;gap:1em;margin:1em 0}.controls label{display:grid;gap:.3em}"
            "select{font:inherit;padding:.35em;min-width:16em}.note{background:#f3f6fa;padding:.8em 1em;border-left:4px solid #526b83}"
            "#chart,#volatility-chart,#global-controls-chart,#global-changes-chart{height:520px}"
            "#country-controls-chart{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:1em}"
            ".country-control-plot{height:280px;min-width:0}.table-wrap{overflow-x:auto}table{border-collapse:collapse;margin:1em 0}"
            "th,td{border:1px solid #cbd1d8;padding:.5em .8em;text-align:right}th:first-child,td:first-child{text-align:left}"
            "small,.muted{color:#555;font-size:.92em}</style></head><body>"
            "<h1>WGI, country GPR, export and REER log changes, and capital-flow volatility</h1>"
            "<p class='note'>The x-axis is fixed to the 2001–2023 frame. WGI is annual; GPR and capital-flow volatility are annual means of monthly values. "
            "Export and real effective exchange rate (REER) changes are ln(annual mean in year t) − ln(annual mean in year t−1), "
            "using available monthly observations in each year. Nominal exports are in domestic currency. "
            "Sources: <code>input/monthly nominal export.xlsx</code> and <code>cleaned/real effective exchange rate.xlsx</code>. "
            "Missing years are not bridged; REER is unavailable for some countries. Each series is indexed independently from its first available value "
            "inside the frame; a change equal to its full observed range is 100 index points. This is not a percent-growth index. "
            "Values are plotted wherever available, and gaps are not imputed. Correlations use unindexed annual values and pairwise-complete observations.</p>"
            "<div class='controls'><label>Country<select id='country'>"
            f"{country_options}</select></label><label>Institution aspect<select id='aspect'>{aspect_options}</select></label></div>"
            "<div id='chart' aria-label='Interactive five-series base-100 annual time series chart'></div>"
            "<p id='series-availability' class='muted'></p>"
            "<h2>Country-specific correlation matrix</h2>"
            "<p id='matrix-meta' class='muted'></p><div id='matrix'></div>"
            f"<p><a href='{CORRELATION_OUT.name}'>Download country/aspect/pair correlations</a></p>"
            "<h2>Pooled correlations by six WGI institution aspects</h2>"
            "<p class='muted'>Each country-series is standardized within country before pooling, so coefficients reflect within-country "
            "co-movement rather than cross-country level differences. n and country counts can vary by pair. "
            f"Capital-flow volatility overlaps with {volatility_overlap} of {len(countries)} countries in the main panel.</p>"
            f"{summary_table}"
            f"<p><a href='{ASPECT_CORRELATION_OUT.name}'>Download the six-aspect pooled correlation coefficients</a></p>"
            "<h1>Global controls</h1>"
            "<p class='note'>Annual means of monthly natural logs of WTI oil price, VIX and current-price GEPU. "
            "Sources: <code>cleaned/oil_price.csv</code>, <code>cleaned/vix.csv</code> and <code>cleaned/gepu_current.csv</code>. "
            "Each series is full-range scaled to 100 in its first available year; hover to see the unindexed log value. Missing observations are not imputed.</p>"
            "<div id='global-controls-chart' aria-label='Global controls annual time series chart'></div>"
            "<p id='global-controls-availability' class='muted'></p>"
            "<h2>Global controls: log changes</h2>"
            "<p class='note'>VIX is the annual mean of monthly ln(VIX). For GEPU and oil, change is the annual mean of monthly logs in year t "
            "minus the annual mean in year t−1; 2000 is used to calculate the 2001 change. Missing years are not bridged. "
            "Each series is full-range scaled to 100 in its first available year; hover to see the unindexed value.</p>"
            "<div id='global-changes-chart' aria-label='Global controls log changes annual time series chart'></div>"
            "<p id='global-changes-availability' class='muted'></p>"
            "<h1>Country-specific controls</h1>"
            "<p class='note'>Policy rate and year-on-year inflation are annual means of available monthly observations; "
            "government gross debt/GDP and the IMF financial-development index are annual. Sources: "
            "<code>cleaned/policy_rate.csv</code>, <code>cleaned/inflation.csv</code>, <code>cleaned/debt_gdp.csv</code> and "
            "<code>cleaned/replication_cleaned/country_month.csv</code>. The IMF index is unavailable for some countries and ends in 2021. "
            "Select a variable to see one chart per dashboard country with data. Each chart uses original values and its own y-axis scale; "
            "missing observations are not imputed.</p>"
            "<div class='controls'><label>Control variable<select id='controls-variable'>"
            f"{country_control_options}</select></label></div>"
            "<p id='country-controls-availability' class='muted'></p>"
            "<div id='country-controls-chart' aria-label='Country-specific control charts by country'></div>"
            "<h1>Country-specific capital-flow volatility</h1>"
            "<p class='note'>Source: <code>cleaned/replication_cleaned/country_month.csv</code>, the monthly standard deviation of portfolio inflows over three months. "
            "The plotted annual value is the mean of available monthly volatility observations; the base-100 index uses the first available year "
            "for that country and the full-period range.</p>"
            "<div class='controls'><label>Volatility country<select id='volatility-country'>"
            f"{volatility_country_options}</select></label></div>"
            "<div id='volatility-chart' aria-label='Interactive annual capital-flow volatility chart'></div>"
            "<script>"
            f"const chartData={chart_json};const volatilityData={volatility_json};"
            f"const correlations={correlation_json};const variableLabels={variable_labels_json};"
            f"const globalControls={global_controls_json};const globalChanges={global_change_json};const countryControls={country_controls_json};"
            f"const globalLabels={json_for_script(GLOBAL_CONTROL_LABELS)};const globalChangeLabels={json_for_script(GLOBAL_CHANGE_LABELS)};const countryLabels={json_for_script(COUNTRY_CONTROL_LABELS)};"
            "const colors={wgi:'#2563eb',gpr:'#e67e22',export_log_change:'#16a34a',capital_flow_volatility:'#9333ea',reer_log_change:'#dc2626'};"
            f"const names={json_for_script(VARIABLES)};"
            "const countrySelect=document.getElementById('country');const aspectSelect=document.getElementById('aspect');"
            "const volatilityCountrySelect=document.getElementById('volatility-country');"
            "const controlsVariableSelect=document.getElementById('controls-variable');"
            "function fmt(value){return value===null||value===undefined?'—':Number(value).toFixed(3)}"
            "function render(){const country=countrySelect.value;const aspect=aspectSelect.value;const key=country+'|'+aspect;"
            "const points=chartData[key]||[];"
            "document.getElementById('series-availability').textContent=names.map(name=>{"
            "const available=points.filter(p=>p[name]!==null&&p[name]!==undefined);"
            "return variableLabels[name]+': '+(available.length?available.length+' observations ('+available[0].year+'–'+available[available.length-1].year+')':'no observations');"
            "}).join(' | ');"
            "const traces=names.map(name=>({x:points.map(p=>p.year),y:points.map(p=>p['index_'+name]),"
            "customdata:points.map(p=>p[name]),type:'scatter',mode:'lines+markers',name:variableLabels[name],"
            "line:{color:colors[name],width:2.5},marker:{size:5},"
            "hovertemplate:'Year %{x}<br>'+variableLabels[name]+': %{customdata:.4f}<br>Base-100 index: %{y:.2f}<extra></extra>'}));"
            "Plotly.react('chart',traces,{title:country+' — '+aspectSelect.options[aspectSelect.selectedIndex].text,"
            f"xaxis:{{title:'Year',range:[{MODEL_START_YEAR},{MODEL_END_YEAR}],dtick:2,tick0:{MODEL_START_YEAR}}},"
            "yaxis:{title:'Base-100 index (full-range scaled)'},"
            "legend:{orientation:'h',y:-0.2},margin:{t:60,r:30,b:80,l:70},hovermode:'x unified'},"
            "{responsive:true,displaylogo:false});"
            "const item=correlations[key];const container=document.getElementById('matrix');"
            "if(!item){document.getElementById('matrix-meta').textContent='No common observations for this selection.';container.innerHTML='';return;}"
            "document.getElementById('matrix-meta').textContent='Pearson correlations on annual values ('+item.start_year+'–'+item.end_year+'); "
            "sample size n is shown for each variable pair.';"
            "const keys=names;"
            "const matrixRows=keys.map(r=>'<tr><th>'+variableLabels[r]+'</th>'+keys.map(c=>{"
            "if(r===c){const n=points.filter(p=>p[r]!==null&&p[r]!==undefined).length;return '<td>'+(n>1?'1.000':'—')+'<br><small>n='+n+'</small></td>';}"
            "const pair=item.pairs[r+'|'+c]||item.pairs[c+'|'+r];"
            "return '<td>'+fmt(pair?pair.r:null)+(pair?'<br><small>n='+pair.n+'</small>':'')+'</td>';}).join('')+'</tr>').join('');"
            "container.innerHTML='<div class=\"table-wrap\"><table><thead><tr><th>Variable</th>'+keys.map(k=>'<th>'+variableLabels[k]+'</th>').join('')+'</tr></thead><tbody>'+matrixRows+'</tbody></table></div>';}"
            "function renderVolatility(){const country=volatilityCountrySelect.value;const points=volatilityData[country]||[];"
            "const trace={x:points.map(p=>p.year),y:points.map(p=>p.index),customdata:points.map(p=>[p.value,p.months]),"
            "type:'scatter',mode:'lines+markers',name:variableLabels.capital_flow_volatility,line:{color:colors.capital_flow_volatility,width:2.5},"
            "marker:{size:5},hovertemplate:'Year %{x}<br>Base-100 index: %{y:.2f}<br>Annual mean volatility: %{customdata[0]:.4f}<br>"
            "Monthly observations: %{customdata[1]}<extra></extra>'};"
            "Plotly.react('volatility-chart',[trace],{title:country+' — '+variableLabels.capital_flow_volatility,"
            f"xaxis:{{title:'Year',range:[{MODEL_START_YEAR},{MODEL_END_YEAR}],dtick:2,tick0:{MODEL_START_YEAR}}},"
            "yaxis:{title:'Base-100 index (full-range scaled)'},"
            "margin:{t:60,r:30,b:60,l:70},hovermode:'x unified'},{responsive:true,displaylogo:false});}"
            "function renderControls(id,points,labels,title){"
            "const colors=['#2563eb','#e67e22','#16a34a','#9333ea'];const names=Object.keys(labels);"
            "document.getElementById(id+'-availability').textContent=names.map(name=>{"
            "const available=points.filter(p=>p[name]!==null&&p[name]!==undefined);"
            "return labels[name]+': '+(available.length?available.length+' observations ('+available[0].year+'–'+available[available.length-1].year+')':'no observations');"
            "}).join(' | ');"
            "const traces=names.map((name,i)=>({x:points.map(p=>p.year),y:points.map(p=>p['index_'+name]),"
            "customdata:points.map(p=>p[name]),type:'scatter',mode:'lines+markers',name:labels[name],"
            "line:{color:colors[i],width:2.5},marker:{size:5},"
            "hovertemplate:'Year %{x}<br>'+labels[name]+': %{customdata:.4f}<br>Base-100 index: %{y:.2f}<extra></extra>'}));"
            "Plotly.react(id+'-chart',traces,{title:title,"
            f"xaxis:{{title:'Year',range:[{MODEL_START_YEAR},{MODEL_END_YEAR}],dtick:2,tick0:{MODEL_START_YEAR}}},"
            "yaxis:{title:'Base-100 index (full-range scaled)'},legend:{orientation:'h',y:-0.2},"
            "margin:{t:60,r:30,b:80,l:70},hovermode:'x unified'},{responsive:true,displaylogo:false});}"
            "function renderCountryControls(){const name=controlsVariableSelect.value;const countries=Object.keys(countryControls);"
            "const palette=['#2563eb','#e67e22','#16a34a','#9333ea','#dc2626','#0891b2','#be185d','#4d7c0f','#a16207','#4338ca','#0f766e','#b45309','#c026d3','#475569','#65a30d','#9f1239','#0284c7'];"
            "const container=document.getElementById('country-controls-chart');"
            "container.querySelectorAll('.country-control-plot').forEach(chart=>Plotly.purge(chart));container.replaceChildren();"
            "const missing=[];let shown=0;countries.forEach((country,i)=>{const points=countryControls[country];"
            "if(!points.some(p=>p[name]!==null&&p[name]!==undefined)){missing.push(country);return;}"
            "shown++;const chart=document.createElement('div');chart.className='country-control-plot';"
            "chart.setAttribute('aria-label',country+' — '+countryLabels[name]);container.appendChild(chart);"
            "const trace={x:points.map(p=>p.year),y:points.map(p=>p[name]),type:'scatter',mode:'lines+markers',name:country,"
            "line:{color:palette[i],width:2},marker:{size:4},"
            "hovertemplate:country+'<br>Year %{x}<br>'+countryLabels[name]+': %{y:.4f}<extra></extra>'};"
            "Plotly.newPlot(chart,[trace],{title:{text:country,font:{size:16}},"
            f"xaxis:{{title:'Year',range:[{MODEL_START_YEAR},{MODEL_END_YEAR}],dtick:5,tick0:{MODEL_START_YEAR}}},"
            "yaxis:{title:countryLabels[name],automargin:true},showlegend:false,"
            "margin:{t:45,r:15,b:55,l:75},hovermode:'closest'},{responsive:true,displaylogo:false});});"
            "document.getElementById('country-controls-availability').textContent=shown+' countries shown.'+"
            "(missing.length?' No observations: '+missing.join(', '):'');}"
            "countrySelect.addEventListener('change',render);aspectSelect.addEventListener('change',render);"
            "volatilityCountrySelect.addEventListener('change',renderVolatility);"
            "controlsVariableSelect.addEventListener('change',renderCountryControls);"
            "render();renderVolatility();renderControls('global-controls',globalControls,globalLabels,'Global controls');"
            "renderControls('global-changes',globalChanges,globalChangeLabels,'Global controls: log changes');renderCountryControls();"
            "</script></body></html>"
        )


def main():
    wgi = read_wgi(WGI_CSV)
    gpr = read_monthly_annual_means(GPR_CSV, "value")
    export_change = annual_log_changes(read_workbook_annual_means(EXPORT_XLSX))
    reer_change = annual_log_changes(read_workbook_annual_means(REER_XLSX))
    volatility, volatility_months = read_capital_flow_volatility(CAPITAL_FLOW_CSV)
    global_controls = {
        name: read_global_annual_log_means(path, column)
        for name, (path, column) in GLOBAL_CONTROL_SOURCES.items()
    }
    country_controls = {
        "policy_rate": read_monthly_annual_means(CLEANED / "policy_rate.csv", "value"),
        "inflation": read_monthly_annual_means(CLEANED / "inflation.csv", "value"),
        "debt_gdp": read_annual_country_values(CLEANED / "debt_gdp.csv", "period", "debt_gdp_pct", annual_only=True),
        "financial_development": read_financial_development_index(CAPITAL_FLOW_CSV),
    }
    countries, volatility_countries, observations, correlations, pooled_correlations = correlation_rows(
        wgi, gpr, export_change, volatility, volatility_months, reer_change
    )
    if not countries or not correlations:
        raise RuntimeError("No country/aspect observations are available in the requested model frame.")
    for points in observations.values():
        for variable in VARIABLES:
            available_points = [point for point in points if point[variable] is not None]
            for point in points:
                point[f"index_{variable}"] = None
            if available_points:
                values = [point[variable] for point in available_points]
                for point, indexed in zip(available_points, base_100_index(values)):
                    point[f"index_{variable}"] = indexed
    write_correlation_csv(correlations)
    write_aspect_correlation_csv(pooled_correlations)
    write_dashboard(
        countries,
        volatility_countries,
        observations,
        correlations,
        pooled_correlations,
        volatility,
        volatility_months,
        global_controls,
        country_controls,
    )
    print(
        f"Wrote {HTML_OUT}, {CORRELATION_OUT}, and {ASPECT_CORRELATION_OUT}: "
        f"{len(countries)} core countries, {len(volatility_countries)} volatility countries, "
        f"{len(correlations)} country/aspect matrices, {len(pooled_correlations)} aspect/pair correlations."
    )


if __name__ == "__main__":
    main()
