const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const html = fs.readFileSync(path.join(__dirname, "quarterly_gpr_reer_correlations_dashboard.html"), "utf8");
const dataMatch = html.match(/const rows = (.*);/);
assert.ok(dataMatch, "Embedded quarterly data must be present");
const rows = JSON.parse(dataMatch[1]);
const countries = [...new Set(rows.map(row => row.country))];
const dataset = countries.map(country => {
  const annual = new Map();
  for (const row of rows.filter(r => r.country === country && r.wgi_va !== null)) {
    annual.set(row.year_quarter.slice(0, 4), row.wgi_va);
  }
  assert.equal(annual.size, 23);
  return { country, averages: { wgi_va: [...annual.values()].reduce((a, b) => a + b, 0) / annual.size } };
});
const start = html.indexOf("function inverse(matrix)");
const end = html.indexOf("function renderRegressions(timing)");
assert.ok(start >= 0 && end > start, "Regression implementation must be present");
const context = vm.createContext({ rows, countries, dataset });
vm.runInContext("function quarterNumber(s) { return Number(s.slice(0, 4)) * 4 + Number(s.slice(-1)) - 1; }\n" + html.slice(start, end), context);

function check(timing, expected, n, first, last) {
  const result = vm.runInContext('regression("wgi_va", "' + timing + '")', context);
  assert.equal(result.n, n);
  assert.equal(result.g, 15);
  assert.equal(result.first, first);
  assert.equal(result.last, last);
  for (let i = 0; i < 2; i++) {
    assert.ok(Math.abs(result.coefficients[i] - expected.coefficients[i]) < 0.0000005);
    assert.ok(Math.abs(result.errors[i] - expected.errors[i]) < 0.0000005);
  }
  assert.ok(Math.abs(result.withinR2 - expected.r2) < 0.00005);
}

// Independently estimated with statsmodels OLS and country-clustered covariance.
check("same", { coefficients: [-0.000005, 0.000534], errors: [0.001824, 0.002222], r2: 0 }, 1425, "2000-Q2", "2023-Q4");
check("lead", { coefficients: [-0.000252, 0.003026], errors: [0.001795, 0.001868], r2: 0.0011 }, 1425, "2000-Q1", "2023-Q3");

const removed = rows.findIndex(row => row.country === "Brazil" && row.year_quarter === "2019-Q2");
assert.notEqual(removed, -1);
rows.splice(removed, 1);
assert.equal(vm.runInContext('regression("wgi_va", "same").n', context), 1424);
assert.equal(vm.runInContext('regression("wgi_va", "lead").n', context), 1423);
console.log("Quarterly fixed-effects regression tests passed.");
