// Generate a standalone dashboard from the quarterly model data.
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const source = path.join(root, "cleaned", "data_for_quarter_model.csv");
const destination = path.join(__dirname, "quarterly_gpr_reer_correlations_dashboard.html");

function parseCsv(text) {
  const rows = [];
  let row = [], field = "", quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c === '"' && text[i + 1] === '"') { field += '"'; i++; }
      else if (c === '"') quoted = false;
      else field += c;
    } else if (c === '"') {
      if (field) throw new Error("Unexpected quote in CSV");
      quoted = true;
    } else if (c === ",") {
      row.push(field); field = "";
    } else if (c === "\n") {
      row.push(field.replace(/\r$/, "")); rows.push(row); row = []; field = "";
    } else field += c;
  }
  if (quoted) throw new Error("Unterminated quoted CSV field");
  if (field || row.length) { row.push(field.replace(/\r$/, "")); rows.push(row); }
  return rows;
}

const csv = parseCsv(fs.readFileSync(source, "utf8").replace(/^\uFEFF/, ""));
const header = csv.shift();
const columns = ["country", "group", "year_quarter", "gpr_z", "d_log_reer",
  "wgi_va", "wgi_pv", "wgi_ge", "wgi_rq", "wgi_rl", "wgi_cc"];
const indices = columns.map(name => {
  const index = header.indexOf(name);
  if (index < 0) throw new Error("Missing CSV column: " + name);
  return index;
});
const data = csv.map((row, i) => {
  if (row.length !== header.length) throw new Error("Incorrect CSV field count at row " + (i + 2));
  return Object.fromEntries(columns.map((name, j) => [name, row[indices[j]]]));
}).filter(row => row.group === "Emerging" && /^20(?:0\d|1\d|2[0-3])-Q[1-4]$/.test(row.year_quarter));
if (!data.length) throw new Error("No emerging-economy quarters found in 2000–2023");
const seen = new Set();
for (const row of data) {
  const key = row.country + ":" + row.year_quarter;
  if (seen.has(key)) throw new Error("Duplicate country-quarter: " + key);
  seen.add(key);
  for (const name of columns.slice(3)) {
    if (row[name] !== "" && !Number.isFinite(Number(row[name]))) {
      throw new Error("Invalid " + name + " in " + key);
    }
    row[name] = row[name] === "" ? null : Number(row[name]);
  }
}

const html = String.raw`<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Quarterly GPR and REER correlations</title>
<style>
:root { color-scheme: light; font-family: "Segoe UI", Arial, sans-serif; color: #17283e; background: #f3f6fa; }
body { margin: 0; }
main { max-width: 1280px; margin: auto; padding: 32px 24px 60px; }
h1 { margin: 0 0 8px; font-size: clamp(1.7rem, 3vw, 2.4rem); }
h2 { margin: 0 0 10px; font-size: 1.3rem; }
h3 { margin: 0 0 8px; font-size: 1rem; }
p { line-height: 1.55; margin: 8px 0; }
.intro { max-width: 1000px; color: #45566d; }
.panel { background: white; border: 1px solid #dce5ef; border-radius: 12px; padding: 22px; margin-top: 20px; box-shadow: 0 3px 14px #2539570a; }
.controls { display: flex; flex-wrap: wrap; gap: 18px; align-items: end; }
label { display: grid; gap: 6px; font-size: .88rem; font-weight: 600; }
select { font: inherit; color: inherit; background: white; border: 1px solid #aebdd0; border-radius: 6px; padding: 8px 30px 8px 10px; }
.caption, .note { color: #52637a; font-size: .9rem; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 365px), 1fr)); gap: 14px; }
.chart-card { border: 1px solid #e0e7f0; border-radius: 8px; padding: 14px; min-width: 0; }
svg { display: block; width: 100%; height: auto; overflow: visible; }
svg text { font-family: "Segoe UI", Arial, sans-serif; fill: #51637a; font-size: 11px; }
.legend { display: flex; flex-wrap: wrap; gap: 16px; font-size: .88rem; margin: 10px 0; }
.swatch { display: inline-block; width: 15px; height: 3px; vertical-align: middle; margin-right: 5px; }
.table-wrap { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: .92rem; }
th, td { padding: 8px 10px; border-bottom: 1px solid #e7edf4; text-align: left; }
th { background: #f6f9fc; color: #435670; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
.error { color: #a00000; font-weight: 600; }
@media (max-width: 600px) { main { padding: 22px 12px 40px; } .panel { padding: 16px; } }
</style>
</head>
<body>
<main>
<h1>Quarterly GPR and REER correlations</h1>
<p class="intro">Emerging economies, 2000–2023. Country-level Pearson correlations and their relationship with average World Governance Indicators (WGI).</p>
<p class="intro">Descriptive correlations are not Model 1 regression estimates: they do not include fixed effects, controls, interactions, or clustered standard errors.</p>
<p id="error" class="error" role="alert"></p>
<section class="panel">
  <div class="controls">
    <label>Outcome timing
      <select id="timing">
        <option value="same">Same quarter: GPR(t), REER change(t)</option>
        <option value="lead">Next quarter: GPR(t), REER change(t+1)</option>
      </select>
    </label>
    <label>Country time series <select id="country"></select></label>
  </div>
  <p id="timing-note" class="note"></p>
</section>
<section class="panel">
  <h2>Country time series</h2>
  <p class="caption">Both lines are plotted against the GPR quarter t. The REER line uses the right axis; in next-quarter mode its values are from t+1. Hover over points for exact quarters and values.</p>
  <div class="legend"><span><span class="swatch" style="background:#1267a8"></span>GPR z-score (left axis)</span><span><span class="swatch" style="background:#d16a2a"></span>Log REER change (right axis)</span></div>
  <div id="series"></div>
</section>
<section class="panel">
  <h2>Country correlations</h2>
  <p class="caption">Both timing definitions are shown for comparison. N counts complete, calendar-aligned pairs.</p>
  <div class="table-wrap"><table><thead><tr><th>Country</th><th>Group</th><th class="num">Same quarter r</th><th class="num">N</th><th class="num">Next quarter r</th><th class="num">N</th></tr></thead><tbody id="country-table"></tbody></table></div>
</section>
<section class="panel">
  <h2>Average WGI and country correlation</h2>
  <p class="caption">Each point is a country; horizontal values are average annual WGI scores, and vertical values are that country's correlation for the selected timing. The line is a descriptive least-squares fit. Hover for country values.</p>
  <div class="table-wrap"><table><thead><tr><th>WGI measure</th><th class="num">Across-country Pearson r</th><th class="num">Countries</th></tr></thead><tbody id="wgi-table"></tbody></table></div>
  <div id="scatters" class="grid"></div>
</section>
<section class="panel">
  <h2>Quarterly log REER change regression without controls</h2>
  <p>For each WGI measure, estimate a separate country-fixed-effects regression:
    <strong>Δln(REER)<sub>i,t or t+1</sub> = α<sub>i</sub> + β₁ GPR<sub>i,t</sub> + β₂ (GPR<sub>i,t</sub> × average WGI<sub>i</sub>) + ε<sub>i,t</sub>.</strong>
    Use the outcome-timing selector above to switch between the two outcome quarters.</p>
  <p class="caption">The outcome is the stored quarterly <code>d_log_reer</code>, the sum of three monthly log changes. GPR is the stored quarterly <code>gpr_z</code>. Average WGI is the same country-specific 2000–2023 annual average used in the scatterplots, in original units; its interaction with GPR is not centered or standardized. Only complete pairs with an available country average enter. The WGI main effect is omitted because it is constant within country and absorbed by the fixed effects. No additional controls are included.</p>
  <p class="caption">The WGI average uses the full period, including years after some observations, so the results are descriptive rather than a real-time or causal analysis. Each coefficient is followed by its country-clustered standard error in parentheses. The cluster correction is G/(G−1) × (N−1)/(N−k), where k includes the country fixed effects and two slopes. Within R² measures fit after removing country means. The GPR coefficient is the association at average WGI = 0.</p>
  <p id="regression-timing" class="note"></p>
  <div class="table-wrap"><table><thead><tr><th>WGI measure</th><th class="num">GPR (SE)</th><th class="num">GPR × average WGI (SE)</th><th class="num">N</th><th class="num">Countries</th><th>GPR quarters</th><th class="num">Within R²</th></tr></thead><tbody id="regression-table"></tbody></table></div>
</section>
<section class="panel">
  <h2>Definitions and sample</h2>
  <p>Source: <code>cleaned/data_for_quarter_model.csv</code>. Quarterly <code>gpr_z</code> is the mean of three monthly within-country standardized GPR values; <code>d_log_reer</code> is the sum of three monthly log REER changes. A positive correlation means higher GPR aligns with a larger rise in log REER, not necessarily a causal effect.</p>
  <p>Same-quarter pairs use 2000Q2–2023Q4; next-quarter pairs use GPR in 2000Q1–2023Q3 and REER changes in 2000Q2–2023Q4. The first quarter's REER change is missing and 2023Q4 has no following quarter. Only non-missing, consecutive-quarter pairs are included.</p>
  <p>Each country's WGI average gives equal weight to available annual scores in 2000–2023, in original units. The 2001 scores are missing. Both the scatterplots and the regression use this full-period average, unlike the lagged WGI in Model 1.</p>
</section>
</main>
<script>
"use strict";
const rows = __DATA__;
const measures = [
  ["wgi_va", "Voice and accountability"], ["wgi_pv", "Political stability"],
  ["wgi_ge", "Government effectiveness"], ["wgi_rq", "Regulatory quality"],
  ["wgi_rl", "Rule of law"], ["wgi_cc", "Control of corruption"]
];
const ns = "http://www.w3.org/2000/svg";
const byId = id => document.getElementById(id);
function element(tag, attrs, text) {
  const node = document.createElementNS(ns, tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  if (text !== undefined) node.textContent = text;
  return node;
}
function quarterNumber(s) { return Number(s.slice(0, 4)) * 4 + Number(s.slice(-1)) - 1; }
function pearson(pairs) {
  if (pairs.length < 2) return null;
  const mx = pairs.reduce((s, p) => s + p.x, 0) / pairs.length;
  const my = pairs.reduce((s, p) => s + p.y, 0) / pairs.length;
  let xy = 0, xx = 0, yy = 0;
  for (const p of pairs) { const x = p.x - mx, y = p.y - my; xy += x * y; xx += x * x; yy += y * y; }
  return xx && yy ? xy / Math.sqrt(xx * yy) : null;
}
function fmt(n) { return n === null ? "—" : (Math.abs(n) < 0.0005 ? 0 : n).toFixed(3); }
const countries = [...new Set(rows.map(r => r.country))].sort((a, b) => a.localeCompare(b));
const dataset = countries.map(country => {
  const series = rows.filter(r => r.country === country).sort((a, b) => quarterNumber(a.year_quarter) - quarterNumber(b.year_quarter));
  const lookup = new Map(series.map(r => [quarterNumber(r.year_quarter), r]));
  const pairs = timing => series.flatMap(r => {
    const target = timing === "same" ? r : lookup.get(quarterNumber(r.year_quarter) + 1);
    return r.gpr_z !== null && target && target.d_log_reer !== null
      ? [{ x: r.gpr_z, y: target.d_log_reer, quarter: r.year_quarter, outcomeQuarter: target.year_quarter }]
      : [];
  });
  const averages = {};
  for (const [key] of measures) {
    const annual = new Map();
    for (const r of series) if (r[key] !== null) {
      const year = r.year_quarter.slice(0, 4);
      if (annual.has(year) && annual.get(year) !== r[key]) throw new Error("WGI values differ within " + country + " " + year + ": " + key);
      annual.set(year, r[key]);
    }
    const values = [...annual.values()];
    averages[key] = values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
  }
  const same = pairs("same"), lead = pairs("lead");
  return { country, same, lead, averages };
});
function cell(row, text, numeric) {
  const td = document.createElement("td");
  td.textContent = text;
  if (numeric) td.className = "num";
  row.appendChild(td);
}
for (const c of dataset) {
  const tr = document.createElement("tr");
  cell(tr, c.country); cell(tr, "Emerging"); cell(tr, fmt(pearson(c.same)), true); cell(tr, c.same.length, true);
  cell(tr, fmt(pearson(c.lead)), true); cell(tr, c.lead.length, true);
  byId("country-table").appendChild(tr);
  const option = document.createElement("option"); option.value = c.country; option.textContent = c.country; byId("country").appendChild(option);
}
function range(values) {
  let min = Math.min(...values), max = Math.max(...values);
  const padding = (max - min) * .1 || Math.abs(max) * .1 || 1;
  return [min - padding, max + padding];
}
function svgBase(width, height, label) {
  const svg = element("svg", { viewBox: "0 0 " + width + " " + height, role: "img", "aria-label": label });
  return svg;
}
function line(svg, x1, y1, x2, y2, color, width) {
  svg.appendChild(element("line", { x1, y1, x2, y2, stroke: color, "stroke-width": width || 1 }));
}
function text(svg, x, y, value, anchor) {
  svg.appendChild(element("text", { x, y, "text-anchor": anchor || "middle" }, value));
}
function point(svg, x, y, color, title) {
  const circle = element("circle", { cx: x, cy: y, r: 4, fill: color, opacity: .85 });
  circle.appendChild(element("title", {}, title)); svg.appendChild(circle);
}
function seriesChart(c, timing) {
  const pairs = c[timing], host = byId("series"); host.replaceChildren();
  if (!pairs.length) { host.textContent = "No complete pairs available."; return; }
  const svg = svgBase(1000, 300, c.country + " quarterly GPR and REER change"), left = 60, right = 930, top = 18, bottom = 250;
  const xr = range(pairs.map(p => p.x)), yr = range(pairs.map(p => p.y));
  const start = quarterNumber(pairs[0].quarter), end = quarterNumber(pairs[pairs.length - 1].quarter);
  const xp = q => left + (quarterNumber(q) - start) / (end - start || 1) * (right - left);
  const yp = (v, r) => bottom - (v - r[0]) / (r[1] - r[0]) * (bottom - top);
  for (let i = 0; i <= 4; i++) {
    const y = bottom - i * (bottom - top) / 4;
    line(svg, left, y, right, y, "#e5ebf2");
    text(svg, left - 8, y + 4, (xr[0] + i * (xr[1] - xr[0]) / 4).toFixed(2), "end");
    text(svg, right + 8, y + 4, (yr[0] + i * (yr[1] - yr[0]) / 4).toFixed(3), "start");
  }
  line(svg, left, bottom, right, bottom, "#8797aa");
  const years = [...new Set(pairs.map(p => p.quarter.slice(0, 4)))].filter(y => Number(y) % 4 === 0);
  for (const year of years) {
    const p = pairs.find(p => p.quarter.startsWith(year));
    text(svg, xp(p.quarter), bottom + 20, year);
  }
  for (const [field, r, color] of [["x", xr, "#1267a8"], ["y", yr, "#d16a2a"]]) {
    for (let i = 0; i < pairs.length; i++) {
      const p = pairs[i], x = xp(p.quarter), y = yp(p[field], r);
      if (i && quarterNumber(p.quarter) === quarterNumber(pairs[i - 1].quarter) + 1) {
        line(svg, xp(pairs[i - 1].quarter), yp(pairs[i - 1][field], r), x, y, color, 1.5);
      }
      point(svg, x, y, color, field === "x" ? p.quarter + " GPR: " + p.x.toFixed(4) : p.outcomeQuarter + " REER change: " + p.y.toFixed(4));
    }
  }
  text(svg, (left + right) / 2, 293, "GPR quarter (t)");
  host.appendChild(svg);
}
function scatterChart(points, name, correlation) {
  const card = document.createElement("div"); card.className = "chart-card";
  const h = document.createElement("h3"); h.textContent = name + " · r = " + fmt(correlation); card.appendChild(h);
  if (points.length < 2) { card.appendChild(document.createTextNode("Insufficient data.")); return card; }
  const svg = svgBase(420, 270, name + ", average WGI versus country correlation"), left = 55, right = 402, top = 16, bottom = 220;
  const xr = range(points.map(p => p.x)), yr = range(points.map(p => p.y));
  const xp = x => left + (x - xr[0]) / (xr[1] - xr[0]) * (right - left);
  const yp = y => bottom - (y - yr[0]) / (yr[1] - yr[0]) * (bottom - top);
  for (let i = 0; i <= 4; i++) {
    const x = left + i * (right - left) / 4, y = bottom - i * (bottom - top) / 4;
    line(svg, left, y, right, y, "#e5ebf2");
    text(svg, left - 7, y + 4, (yr[0] + i * (yr[1] - yr[0]) / 4).toFixed(2), "end");
    text(svg, x, bottom + 17, (xr[0] + i * (xr[1] - xr[0]) / 4).toFixed(2));
  }
  const mx = points.reduce((s, p) => s + p.x, 0) / points.length;
  const my = points.reduce((s, p) => s + p.y, 0) / points.length;
  const denominator = points.reduce((s, p) => s + (p.x - mx) ** 2, 0);
  if (denominator) {
    const slope = points.reduce((s, p) => s + (p.x - mx) * (p.y - my), 0) / denominator;
    const min = Math.min(...points.map(p => p.x)), max = Math.max(...points.map(p => p.x));
    line(svg, xp(min), yp(my + slope * (min - mx)), xp(max), yp(my + slope * (max - mx)), "#93a0b0", 1.5);
  }
  for (const p of points) point(svg, xp(p.x), yp(p.y), "#1267a8", p.country + ": WGI " + p.x.toFixed(3) + ", correlation " + p.y.toFixed(3));
  text(svg, (left + right) / 2, 263, "Average WGI");
  const axis = element("text", { x: 14, y: (top + bottom) / 2, "text-anchor": "middle", transform: "rotate(-90 14 " + ((top + bottom) / 2) + ")" }, "Country correlation");
  svg.appendChild(axis); card.appendChild(svg); return card;
}
function inverse(matrix) {
  const n = matrix.length;
  const augmented = matrix.map((row, i) => row.concat(row.map((_, j) => i === j ? 1 : 0)));
  const scale = Math.max(...matrix.flat().map(Math.abs));
  for (let j = 0; j < n; j++) {
    let pivot = j;
    for (let i = j + 1; i < n; i++) if (Math.abs(augmented[i][j]) > Math.abs(augmented[pivot][j])) pivot = i;
    if (Math.abs(augmented[pivot][j]) <= scale * 1e-12) throw new Error("Regression design matrix is singular.");
    [augmented[j], augmented[pivot]] = [augmented[pivot], augmented[j]];
    const divisor = augmented[j][j];
    for (let k = 0; k < n * 2; k++) augmented[j][k] /= divisor;
    for (let i = 0; i < n; i++) if (i !== j) {
      const factor = augmented[i][j];
      for (let k = 0; k < n * 2; k++) augmented[i][k] -= factor * augmented[j][k];
    }
  }
  return augmented.map(row => row.slice(n));
}
function regression(key, timing) {
  const groups = new Map();
  for (const country of countries) {
    const series = rows.filter(r => r.country === country);
    const lookup = new Map(series.map(r => [quarterNumber(r.year_quarter), r]));
    const wgi = dataset.find(c => c.country === country).averages[key];
    if (wgi === null) continue;
    const observations = [];
    for (const row of series) {
      const outcome = timing === "same" ? row : lookup.get(quarterNumber(row.year_quarter) + 1);
      if (!outcome || outcome.d_log_reer === null || row.gpr_z === null) continue;
      observations.push({ quarter: row.year_quarter, y: outcome.d_log_reer, x: [row.gpr_z, row.gpr_z * wgi] });
    }
    if (observations.length) groups.set(country, observations);
  }
  const n = [...groups.values()].reduce((sum, group) => sum + group.length, 0), g = groups.size;
  if (g < 2 || n <= g + 2) throw new Error("Insufficient observations for clustered fixed-effects regression.");
  const xx = Array.from({ length: 2 }, () => [0, 0]), xy = [0, 0];
  const demeaned = [];
  for (const [country, group] of groups) {
    const meanY = group.reduce((s, row) => s + row.y, 0) / group.length;
    const meanX = [0, 1].map(j => group.reduce((s, row) => s + row.x[j], 0) / group.length);
    for (const row of group) {
      const y = row.y - meanY, x = row.x.map((value, j) => value - meanX[j]);
      for (let j = 0; j < 2; j++) {
        xy[j] += x[j] * y;
        for (let k = 0; k < 2; k++) xx[j][k] += x[j] * x[k];
      }
      demeaned.push({ country, x, y });
    }
  }
  const bread = inverse(xx);
  const coefficients = bread.map(row => row.reduce((sum, value, j) => sum + value * xy[j], 0));
  const scores = new Map([...groups.keys()].map(country => [country, [0, 0]]));
  let sse = 0, sst = 0;
  for (const row of demeaned) {
    const residual = row.y - row.x.reduce((sum, value, j) => sum + value * coefficients[j], 0);
    sse += residual * residual; sst += row.y * row.y;
    const score = scores.get(row.country);
    for (let j = 0; j < 2; j++) score[j] += row.x[j] * residual;
  }
  if (!sst) throw new Error("No within-country variation in the outcome.");
  const correction = g / (g - 1) * (n - 1) / (n - g - 2);
  const errors = bread.map(b => Math.sqrt(correction * [...scores.values()].reduce((sum, score) => {
    const projected = b.reduce((total, value, j) => total + value * score[j], 0);
    return sum + projected * projected;
  }, 0)));
  const quarters = [...groups.values()].flat().map(row => row.quarter).sort();
  return { coefficients, errors, n, g, first: quarters[0], last: quarters[quarters.length - 1], withinR2: 1 - sse / sst };
}
function renderRegressions(timing) {
  byId("regression-timing").textContent = timing === "same"
    ? "Outcome: change in ln(REER) in quarter t; GPR in t; WGI is the country average."
    : "Outcome: change in ln(REER) in quarter t+1; GPR in t; WGI is the country average. The final GPR quarter has no following outcome.";
  const table = byId("regression-table"); table.replaceChildren();
  for (const [key, name] of measures) {
    const result = regression(key, timing), tr = document.createElement("tr");
    cell(tr, name);
    for (let i = 0; i < 2; i++) cell(tr, result.coefficients[i].toFixed(6) + " (" + result.errors[i].toFixed(6) + ")", true);
    cell(tr, result.n, true); cell(tr, result.g, true); cell(tr, result.first + " to " + result.last);
    cell(tr, result.withinR2.toFixed(4), true); table.appendChild(tr);
  }
}
function render() {
  const timing = byId("timing").value;
  byId("timing-note").textContent = timing === "same"
    ? "Same-quarter: GPR(t) and the REER change in quarter t."
    : "Next-quarter: GPR(t) and the REER change in the following calendar quarter, t+1.";
  seriesChart(dataset.find(c => c.country === byId("country").value), timing);
  byId("wgi-table").replaceChildren(); byId("scatters").replaceChildren();
  for (const [key, name] of measures) {
    const points = dataset.map(c => ({ country: c.country, x: c.averages[key], y: pearson(c[timing]) }))
      .filter(p => p.x !== null && p.y !== null);
    const correlation = pearson(points), tr = document.createElement("tr");
    cell(tr, name); cell(tr, fmt(correlation), true); cell(tr, points.length, true); byId("wgi-table").appendChild(tr);
    byId("scatters").appendChild(scatterChart(points, name, correlation));
  }
  renderRegressions(timing);
}
function renderSafely() {
  try { byId("error").textContent = ""; render(); }
  catch (error) { byId("error").textContent = "Dashboard error: " + error.message; throw error; }
}
byId("timing").addEventListener("change", renderSafely);
byId("country").addEventListener("change", renderSafely);
renderSafely();
</script>
</body>
</html>
`;
fs.writeFileSync(destination, html.replace("__DATA__", JSON.stringify(data).replace(/</g, "\\u003c")), "utf8");
console.log("Wrote " + destination + " with " + data.length + " country-quarters.");
