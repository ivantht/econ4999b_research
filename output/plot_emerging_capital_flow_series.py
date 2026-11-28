"""Time-series charts for emerging-economy capital flows.

Emerging economies are the countries with group Emerging in
cleaned/replication_cleaned/country_month.csv. Turkey in capital_flow.csv
is drawn as Turkiye. Source files are only read.
"""

import csv
import json
from pathlib import Path

ROOT = Path(r"c:\Users\ASUS\econ4999b_research")
CAPITAL_FLOW = ROOT / "cleaned" / "capital_flow.csv"
COUNTRY_MONTH = ROOT / "cleaned" / "replication_cleaned" / "country_month.csv"
OUTPUT = ROOT / "output"

PANEL_NAME = {"Turkey": "Turkiye", "Türkiye": "Turkiye"}
QUARTER_MONTH = {"1": "01", "2": "04", "3": "07", "4": "10"}
LINE_COLOR = "#1f4e79"


def join_names(names):
    names = list(names)
    if len(names) < 2:
        return ", ".join(names)
    return ", ".join(names[:-1]) + ", and " + names[-1]


def panel_name(country):
    return PANEL_NAME.get(country, country)


def number(text):
    text = (text or "").strip()
    if text == "":
        return None
    return float(text)


def quarter_start(year_quarter):
    year, quarter = year_quarter.split("-Q")
    return f"{int(year):04d}-{QUARTER_MONTH[quarter]}-01"


def read_emerging():
    countries = set()
    with COUNTRY_MONTH.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["group"] == "Emerging":
                countries.add(row["country"])
    return countries


def rows_by_country(path, value_name, date_name, date_of, label_of, emerging):
    grouped = {country: {} for country in emerging}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            country = panel_name(row["country"])
            if country not in emerging:
                continue
            stamp = date_of(row[date_name])
            value = number(row[value_name])
            label = label_of(row[date_name])
            if stamp in grouped[country] and grouped[country][stamp][0] != value:
                raise ValueError(f"Conflicting {value_name} for {country} on {stamp}")
            grouped[country][stamp] = (value, label)
    series = []
    for country in sorted(grouped):
        points = grouped[country]
        dates = sorted(points)
        series.append(
            {
                "country": country,
                "dates": dates,
                "values": [points[stamp][0] for stamp in dates],
                "labels": [points[stamp][1] for stamp in dates],
            }
        )
    return series


def capital_flow_series(emerging):
    present = set()
    all_names = set()
    with CAPITAL_FLOW.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            all_names.add(panel_name(row["country"]))
            if panel_name(row["country"]) in emerging:
                present.add(panel_name(row["country"]))
    series = rows_by_country(
        CAPITAL_FLOW,
        "usd_millions",
        "year_quarter",
        quarter_start,
        lambda year_quarter: year_quarter,
        present,
    )
    return series, sorted(all_names - emerging), sorted(emerging - present)


def write_chart(path, title, note, unit, tick_format, series):
    payload = []
    observed_dates = []
    for item in series:
        values = item["values"]
        observed = sum(value is not None for value in values)
        observed_dates.extend(
            stamp for stamp, value in zip(item["dates"], values) if value is not None
        )
        payload.append(
            {
                "country": item["country"],
                "x": item["dates"],
                "y": values,
                "label": item["labels"],
                "n": observed,
            }
        )
    if not observed_dates:
        raise ValueError(f"No observed values for {path.name}")
    document = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
html, body {{ background: #ffffff; }}
body {{ margin: 24px; color: #1a1a1a; font-family: "Segoe UI", Arial, sans-serif; }}
h1 {{ font-size: 22px; font-weight: 600; margin: 0 0 8px; }}
p {{ max-width: 980px; line-height: 1.45; margin: 0 0 18px; }}
.grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px 12px; }}
.panel {{ height: 250px; }}
@media (max-width: 1100px) {{ .grid {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<h1>{title}</h1>
<p>{note}</p>
<div class="grid" id="grid"></div>
<script>
const series = {json.dumps(payload, ensure_ascii=False)};
const xRange = {json.dumps([min(observed_dates), max(observed_dates)])};
const unit = {json.dumps(unit)};
const tickFormat = {json.dumps(tick_format)};
const panels = [];
let syncing = false;
let ready = false;
for (const item of series) {{
  const div = document.createElement("div");
  div.className = "panel";
  div.id = "panel-" + item.country.replace(/\\s+/g, "-");
  document.getElementById("grid").appendChild(div);
  const trace = {{
    x: item.x,
    y: item.y,
    customdata: item.label,
    type: "scatter",
    mode: "lines",
    connectgaps: false,
    line: {{color: "{LINE_COLOR}", width: 1.5}},
    hovertemplate: "%{{customdata}}<br>%{{y:,.3f}} " + unit + "<extra>" + item.country + "</extra>"
  }};
  const layout = {{
    title: {{text: item.country + " (" + item.n + ")", font: {{size: 14}}}},
    margin: {{l: 64, r: 14, t: 36, b: 36}},
    paper_bgcolor: "white",
    plot_bgcolor: "white",
    showlegend: false,
    hovermode: "closest",
    xaxis: {{
      type: "date",
      range: xRange,
      tickformat: "%Y",
      dtick: "M60",
      showgrid: true,
      gridcolor: "#eeeeee",
      zeroline: false
    }},
    yaxis: {{
      title: {{text: unit, font: {{size: 11}}}},
      tickformat: tickFormat,
      zeroline: true,
      zerolinecolor: "#666666",
      showgrid: true,
      gridcolor: "#eeeeee"
    }}
  }};
  Plotly.newPlot(div, [trace], layout, {{responsive: true, displayModeBar: false}});
  div.on("plotly_relayout", (event) => {{
    if (!ready || syncing) return;
    const update = {{}};
    if (event["xaxis.range[0]"] !== undefined) {{
      update["xaxis.range[0]"] = event["xaxis.range[0]"];
      update["xaxis.range[1]"] = event["xaxis.range[1]"];
    }} else if (event["xaxis.autorange"] === true) {{
      update["xaxis.autorange"] = true;
    }} else {{
      return;
    }}
    syncing = true;
    Promise.all(panels.filter((panel) => panel !== div).map((panel) => Plotly.relayout(panel, update)))
      .finally(() => {{ syncing = false; }});
  }});
  panels.push(div);
}}
ready = true;
</script>
</body>
</html>
"""
    path.write_text(document, encoding="utf-8")


def main():
    emerging = read_emerging()
    flows, outside, absent = capital_flow_series(emerging)
    monthly_volatility = rows_by_country(
        COUNTRY_MONTH,
        "capital_flow_volatility",
        "date",
        lambda stamp: stamp,
        lambda stamp: stamp[:7],
        emerging,
    )
    monthly_inflow = rows_by_country(
        COUNTRY_MONTH,
        "portfolio_inflow",
        "date",
        lambda stamp: stamp,
        lambda stamp: stamp[:7],
        emerging,
    )
    outside_text = join_names(outside)
    absent_text = join_names(absent)
    flow_note = (
        "Each panel is one emerging economy that appears in capital_flow.csv. "
        "Turkey is labeled Turkiye. "
        f"{outside_text} are in that file and outside the emerging sample, so they are omitted. "
        f"{absent_text} are emerging and have no capital-flow row. "
        "The number after each country is the count of observed quarters. "
        "Each panel has its own vertical scale. The horizontal line is zero. "
        "Zooming one panel moves the time window on the others."
    )
    volatility_note = (
        "Fifteen emerging economies. Capital-flow volatility is the standard deviation "
        "of portfolio inflows over the current month and the previous two months, in billion US dollars. "
        "Blank months stay blank. "
        "The number after each country is the count of observed months. "
        "Each panel has its own vertical scale. The horizontal line is zero. "
        "Zooming one panel moves the time window on the others."
    )
    inflow_note = (
        "Fifteen emerging economies. Portfolio inflow is in billion US dollars. "
        "Blank months stay blank. "
        "The number after each country is the count of observed months. "
        "Each panel has its own vertical scale. The horizontal line is zero. "
        "Zooming one panel moves the time window on the others."
    )
    charts = [
        (
            OUTPUT / "emerging_capital_flow.html",
            "Capital flow, emerging economies",
            flow_note,
            "Million USD",
            ",.0f",
            flows,
        ),
        (
            OUTPUT / "emerging_capital_flow_volatility.html",
            "Capital-flow volatility, emerging economies",
            volatility_note,
            "Billion USD",
            ",.2f",
            monthly_volatility,
        ),
        (
            OUTPUT / "emerging_portfolio_inflow.html",
            "Portfolio inflow, emerging economies",
            inflow_note,
            "Billion USD",
            ",.2f",
            monthly_inflow,
        ),
    ]
    for path, title, note, unit, tick_format, series in charts:
        write_chart(path, title, note, unit, tick_format, series)
        counts = [
            (item["country"], sum(value is not None for value in item["values"]))
            for item in series
        ]
        print(path.name)
        for country, count in counts:
            print(f"  {country}: {count}")


if __name__ == "__main__":
    main()
