import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent.parent
PANEL_CSV = ROOT / "cleaned" / "replication_cleaned" / "country_month.csv"
WGI_CSV = ROOT / "cleaned" / "wgi.csv"
ASPECT_LABELS = {
    "va": "Voice and Accountability",
    "pv": "Political Stability and Absence of Violence/Terrorism",
    "ge": "Government Effectiveness",
    "rq": "Regulatory Quality",
    "rl": "Rule of Law",
    "cc": "Control of Corruption",
}
COUNTRY_ALIASES = {"Korea": "South Korea", "Turkiye": "Turkey"}
GROUPS = {"emerging": "Emerging markets", "advanced": "Other countries"}
YEARS = range(2000, 2024)


def load_panel_countries(path=PANEL_CSV):
    countries = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            iso = row["iso"].strip()
            name = row["country"].strip()
            group = row["group"].strip().lower()
            if not iso or not name or group not in GROUPS:
                raise ValueError(f"Invalid panel country or group: {iso}, {name}, {group}")
            entry = {"iso": iso, "country": name, "group": group}
            if iso in countries and countries[iso] != entry:
                raise ValueError(f"Inconsistent country metadata for {iso}")
            countries[iso] = entry
    if not countries:
        raise ValueError("No panel countries found")
    return countries


def load_wgi(path=WGI_CSV):
    values = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            aspect = row["dimension"].strip().lower()
            year = int(row["year"])
            if aspect not in ASPECT_LABELS or year not in YEARS:
                continue
            raw = row["estimate"].strip()
            if not raw:
                continue
            value = float(raw)
            if not math.isfinite(value):
                raise ValueError(f"Non-finite WGI score: {row}")
            key = (row["country"].strip(), aspect, year)
            if key in values and values[key] != value:
                raise ValueError(f"Conflicting WGI scores for {key}")
            values[key] = value
    return values


def build_diagnostics(countries, values):
    data = {group: {} for group in GROUPS}
    outliers = []
    missing = defaultdict(list)
    for group in GROUPS:
        group_countries = sorted(
            (c for c in countries.values() if c["group"] == group),
            key=lambda c: c["country"],
        )
        for aspect in ASPECT_LABELS:
            series = []
            means = []
            for country in group_countries:
                name = country["country"]
                wgi_name = COUNTRY_ALIASES.get(name, name)
                scores = [values.get((wgi_name, aspect, year)) for year in YEARS]
                observed = [score for score in scores if score is not None]
                if not observed:
                    missing[(group, aspect)].append(name)
                    continue
                series.append({"iso": country["iso"], "country": name, "scores": scores})
                means.append((name, float(np.mean(observed)), len(observed)))
            data[group][aspect] = series
            if len(means) < 4:
                continue
            q1, q3 = np.percentile([mean for _, mean, _ in means], [25, 75])
            iqr = q3 - q1
            low, high = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            for name, mean, count in means:
                if mean < low or mean > high:
                    outliers.append({
                        "group": group, "aspect": aspect, "country": name,
                        "mean": mean, "years": count, "low": float(low), "high": float(high),
                    })
    return data, outliers, dict(missing)


def render_group_diagnostics():
    countries = load_panel_countries()
    data, outliers, missing = build_diagnostics(countries, load_wgi())
    counts = {group: sum(c["group"] == group for c in countries.values()) for group in GROUPS}
    payload = {
        "data": data,
        "aspects": ASPECT_LABELS,
        "groups": GROUPS,
        "years": list(YEARS),
        "outliers": outliers,
        "missing": [
            {"group": group, "aspect": aspect, "countries": names}
            for (group, aspect), names in missing.items()
        ],
    }
    encoded = json.dumps(payload, ensure_ascii=True, allow_nan=False).replace("</", "<\\/")
    return """
<section id="group-diagnostics">
<h2>WGI trends: emerging and other countries</h2>
<div class="note">
These additional charts include all %d countries in the 2000–2023 replication panel
(%d emerging and %d advanced, labeled “other”), including countries excluded from regressions
because of missing controls. Groups come from the panel's group field. Scores are the
unfilled annual WGI estimates from cleaned/wgi.csv; missing years appear as gaps.
The earlier charts above still use their original regression sample. Select an aspect
independently in each chart; country colors are consistent across aspects.
</div>
<h3>Emerging markets</h3><div id="wgi-emerging" style="height:600px"></div>
<h3>Other countries</h3><div id="wgi-advanced" style="height:600px"></div>
<h3>Potential outliers in country-average scores</h3>
<p>For each group and aspect, calculate each country's mean across its available 2000–2023
annual scores. Flag means outside the group-specific Q1 − 1.5 × IQR or Q3 + 1.5 × IQR.
These are descriptive candidates, not errors or grounds for excluding a country.</p>
<div id="wgi-outliers"></div><div id="wgi-missing"></div>
</section>
<script>
const groupDiagnostics = %s;
const countryPalette = [
  '#0072B2','#D55E00','#009E73','#CC79A7','#E69F00',
  '#56B4E9','#8C564B','#6A3D9A','#2F4F4F','#C51B7D',
  '#1B9E77','#7570B3','#A6761D','#E7298A','#4D4D4D',
  '#B2182B','#01665E','#762A83','#5E3C99','#B35806'
];
function renderGroup(group) {
  const aspects = Object.keys(groupDiagnostics.aspects);
  const allIsos = [...new Set(aspects.flatMap(a => groupDiagnostics.data[group][a].map(s => s.iso)))].sort();
  const colors = Object.fromEntries(allIsos.map((iso, i) => [iso, countryPalette[i %% countryPalette.length]]));
  const traces = [];
  for (const aspect of aspects) {
    for (const country of groupDiagnostics.data[group][aspect]) {
      traces.push({
        type: 'scatter', mode: 'lines+markers', name: country.country,
        x: groupDiagnostics.years, y: country.scores, visible: aspect === 'va',
        connectgaps: false, line: {color: colors[country.iso], width: 2},
        marker: {color: colors[country.iso], size: 5}, meta: aspect,
        hovertemplate: country.country + '<br>Year: %%{x}<br>Score: %%{y:.3f}<extra></extra>'
      });
    }
  }
  const buttons = aspects.map(aspect => ({
    label: groupDiagnostics.aspects[aspect], method: 'update',
    args: [{visible: traces.map(t => t.meta === aspect)},
           {title: groupDiagnostics.groups[group] + ' — ' + groupDiagnostics.aspects[aspect]}]
  }));
  Plotly.newPlot('wgi-' + group, traces, {
    title: groupDiagnostics.groups[group] + ' — ' + groupDiagnostics.aspects.va,
    xaxis: {title: 'Year', dtick: 2}, yaxis: {title: 'WGI estimate'},
    updatemenus: [{buttons: buttons, x: 0, y: 1.18, xanchor: 'left'}],
    margin: {t: 100}, hovermode: 'closest'
  }, {responsive: true});
}
renderGroup('emerging');
renderGroup('advanced');
const outlierDiv = document.getElementById('wgi-outliers');
if (!groupDiagnostics.outliers.length) {
  outlierDiv.textContent = 'No country averages meet this rule.';
} else {
  const table = document.createElement('table');
  const head = table.createTHead().insertRow();
  ['Group','Aspect','Country','Mean','Years','Lower fence','Upper fence'].forEach(label => {
    const th = document.createElement('th'); th.textContent = label; head.appendChild(th);
  });
  const body = table.createTBody();
  groupDiagnostics.outliers.forEach(item => {
    const row = body.insertRow();
    [groupDiagnostics.groups[item.group], groupDiagnostics.aspects[item.aspect], item.country,
     item.mean.toFixed(3), item.years, item.low.toFixed(3), item.high.toFixed(3)].forEach(value => {
      row.insertCell().textContent = value;
    });
  });
  outlierDiv.appendChild(table);
}
const missingDiv = document.getElementById('wgi-missing');
missingDiv.textContent = groupDiagnostics.missing.length
  ? 'No WGI data for: ' + groupDiagnostics.missing.map(item =>
      groupDiagnostics.groups[item.group] + ' / ' + groupDiagnostics.aspects[item.aspect]
      + ': ' + item.countries.join(', ')).join('; ')
  : 'Every panel country has at least one observed WGI score for each aspect.';
</script>
""" % (len(countries), counts["emerging"], counts["advanced"], encoded)
