import csv
import json
import math
from collections import defaultdict
from html import escape
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLEANED = ROOT / "cleaned"
OUTPUT = ROOT / "output"
WGI_CSV = CLEANED / "wgi.csv"
GPR_CSV = CLEANED / "gpr_country.csv"
EXPORT_TREND_CSV = CLEANED / "real_export_hp_trend.csv"
CAPITAL_FLOW_CSV = CLEANED / "replication_cleaned" / "country_month.csv"
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
CORE_VARIABLES = ("wgi", "gpr", "export_log_trend")
VARIABLE_LABELS = {
    "wgi": "WGI",
    "gpr": "Country GPR",
    "export_log_trend": "Nominal-export HP log trend",
    "capital_flow_volatility": "Capital-flow volatility",
}
CORRELATION_PAIRS = (
    ("wgi", "gpr"),
    ("wgi", "export_log_trend"),
    ("gpr", "export_log_trend"),
    ("wgi", "capital_flow_volatility"),
    ("gpr", "capital_flow_volatility"),
    ("export_log_trend", "capital_flow_volatility"),
)
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


def correlation_rows(wgi, gpr, export_trend, volatility, volatility_months):
    countries = sorted(
        {country for country, _, _ in wgi}
        & {country for country, _ in gpr}
        & {country for country, _ in export_trend}
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
                    "export_log_trend": export_trend.get((country, year)),
                    "capital_flow_volatility": volatility.get((country, year)),
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
    with HTML_OUT.open("w", encoding="utf-8") as output:
        output.write(
            "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            "<title>Country WGI, GPR, export trend, and capital-flow volatility</title>"
            "<script src='https://cdn.plot.ly/plotly-2.35.2.min.js'></script>"
            "<style>body{font:16px/1.5 Georgia,serif;max-width:1250px;margin:2em auto;padding:0 1em;color:#20242a}"
            ".controls{display:flex;flex-wrap:wrap;gap:1em;margin:1em 0}.controls label{display:grid;gap:.3em}"
            "select{font:inherit;padding:.35em;min-width:16em}.note{background:#f3f6fa;padding:.8em 1em;border-left:4px solid #526b83}"
            "#chart,#volatility-chart{height:520px}.table-wrap{overflow-x:auto}table{border-collapse:collapse;margin:1em 0}"
            "th,td{border:1px solid #cbd1d8;padding:.5em .8em;text-align:right}th:first-child,td:first-child{text-align:left}"
            "small,.muted{color:#555;font-size:.92em}</style></head><body>"
            "<h1>WGI, country GPR, nominal-export log trend, and capital-flow volatility</h1>"
            "<p class='note'>The x-axis is fixed to the requested 2001–2023 frame. WGI is annual; GPR, the HP log trend of nominal exports, "
            "and capital-flow volatility are annual means of monthly values. Each series is indexed independently from its first available value "
            "inside the frame; a change equal to its full observed range is 100 index points. This is not a percent-growth index. "
            "Values are plotted wherever available, and gaps are not imputed. Correlations use unindexed annual values and pairwise-complete observations.</p>"
            "<div class='controls'><label>Country<select id='country'>"
            f"{country_options}</select></label><label>Institution aspect<select id='aspect'>{aspect_options}</select></label></div>"
            "<div id='chart' aria-label='Interactive four-series base-100 annual time series chart'></div>"
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
            "const colors={wgi:'#2563eb',gpr:'#e67e22',export_log_trend:'#16a34a',capital_flow_volatility:'#9333ea'};"
            "const countrySelect=document.getElementById('country');const aspectSelect=document.getElementById('aspect');"
            "const volatilityCountrySelect=document.getElementById('volatility-country');"
            "function fmt(value){return value===null||value===undefined?'—':Number(value).toFixed(3)}"
            "function render(){const country=countrySelect.value;const aspect=aspectSelect.value;const key=country+'|'+aspect;"
            "const points=chartData[key]||[];const names=['wgi','gpr','export_log_trend','capital_flow_volatility'];"
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
            "const keys=['wgi','gpr','export_log_trend','capital_flow_volatility'];"
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
            "countrySelect.addEventListener('change',render);aspectSelect.addEventListener('change',render);"
            "volatilityCountrySelect.addEventListener('change',renderVolatility);render();renderVolatility();"
            "</script></body></html>"
        )


def main():
    wgi = read_wgi(WGI_CSV)
    gpr = read_monthly_annual_means(GPR_CSV, "value")
    export_trend = read_monthly_annual_means(EXPORT_TREND_CSV, "ytrend")
    volatility, volatility_months = read_capital_flow_volatility(CAPITAL_FLOW_CSV)
    countries, volatility_countries, observations, correlations, pooled_correlations = correlation_rows(
        wgi, gpr, export_trend, volatility, volatility_months
    )
    if not countries or not correlations:
        raise RuntimeError("No country/aspect observations are available in the requested model frame.")
    for points in observations.values():
        for variable in (*CORE_VARIABLES, "capital_flow_volatility"):
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
    )
    print(
        f"Wrote {HTML_OUT}, {CORRELATION_OUT}, and {ASPECT_CORRELATION_OUT}: "
        f"{len(countries)} core countries, {len(volatility_countries)} volatility countries, "
        f"{len(correlations)} country/aspect matrices, {len(pooled_correlations)} aspect/pair correlations."
    )


if __name__ == "__main__":
    main()
