"""WGI regressions with volatility measured as a share of the inflow.

The outcome is cf_vol divided by the absolute 3-month mean of portfolio
inflows. Months with a mean inflow below 0.1 billion dollars are dropped.
The rest of the specification matches run_capital_flow_volatility_wgi.py.
"""

import csv
import os
from collections import defaultdict
from html import escape

import run_capital_flow_volatility_wgi as base
import run_export_reer_2sls as est


OUTPUT = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")), "output")
MINIMUM_INFLOW = 0.1


def load_panel():
    inflows = defaultdict(dict)
    records = []
    with open(base.PANEL, encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            country = base.ISO.get(row["iso"].strip())
            month = row["date"][:7]
            if country is None:
                continue
            inflow = base.num(row["port_inf"])
            if inflow is not None:
                inflows[country][month] = inflow
            if not ("2000-01" <= month <= "2023-12"):
                continue
            record = {
                "country": country,
                "year_month": month,
                "cf_vol": base.num(row["cf_vol"]),
                "gpr": base.num(row["gpr_z"]),
                "lag_year": int(est.add_months(month, -1)[:4]),
            }
            for name, source in base.PANEL_CONTROLS.items():
                record[name] = base.num(row[source])
            records.append(record)
    for record in records:
        window = [
            est.add_months(record["year_month"], -2),
            est.add_months(record["year_month"], -1),
            record["year_month"],
        ]
        values = [inflows[record["country"]].get(month) for month in window]
        if record["cf_vol"] is None or any(value is None for value in values):
            record["volatility"] = None
            continue
        mean_inflow = sum(values) / 3.0
        if abs(mean_inflow) < MINIMUM_INFLOW:
            record["volatility"] = None
            continue
        record["volatility"] = record["cf_vol"] / abs(mean_inflow)
    return records


def write_outputs(path_csv, path_html, results):
    labels = {"gpr": "GPR", "wgi": "WGI", "wgi_x_gpr": "WGI x GPR", **base.CONTROL_LABELS}
    fields = [
        "dimension", "dimension_label", "variable", "label",
        "coef", "se", "p", "stars", "wgi_center",
        "n_obs", "n_country", "r2", "month_min", "month_max", "countries",
    ]
    with open(path_csv, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for code, result in results.items():
            fitted = result["fit"]
            for name in base.INTEREST + base.CONTROLS:
                stat = fitted["stats"][name]
                writer.writerow({
                    "dimension": code,
                    "dimension_label": base.DIMENSIONS[code],
                    "variable": name,
                    "label": labels[name],
                    "coef": f"{stat['coef']:.10g}",
                    "se": f"{stat['se']:.10g}",
                    "p": f"{stat['p']:.10g}",
                    "stars": est.stars(stat["p"]),
                    "wgi_center": f"{result['center']:.10g}",
                    "n_obs": fitted["n_obs"],
                    "n_country": fitted["n_country"],
                    "r2": f"{fitted['r2']:.10g}",
                    "month_min": fitted["month_min"],
                    "month_max": fitted["month_max"],
                    "countries": "; ".join(fitted["countries"]),
                })

    blocks = []
    for code, result in results.items():
        fitted = result["fit"]
        body = []
        for name in base.INTEREST + base.CONTROLS:
            stat = fitted["stats"][name]
            body.append(
                "<tr>"
                f"<td>{escape(labels[name])}</td>"
                f"<td>{est.fmt(stat['coef'])}{est.stars(stat['p'])}</td>"
                f"<td>{est.fmt(stat['se'])}</td>"
                f"<td>{est.fmt(stat['p'])}</td>"
                "</tr>"
            )
        blocks.append(
            f"<h2>{escape(base.DIMENSIONS[code])}</h2>"
            f"<p>N = {fitted['n_obs']}. Countries = {fitted['n_country']}: "
            f"{escape(', '.join(fitted['countries']))}. "
            f"Months = {escape(fitted['month_min'])} to {escape(fitted['month_max'])}. "
            f"R-squared = {est.fmt(fitted['r2'])}. "
            f"WGI is centered at {est.fmt(result['center'])}.</p>"
            "<table><thead><tr><th>Variable</th><th>Coefficient</th><th>SE</th><th>p-value</th></tr></thead>"
            f"<tbody>{''.join(body)}</tbody></table>"
        )
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Scaled capital-flow volatility</title>
<style>
body {{ font: 16px/1.5 Georgia, serif; max-width: 900px; margin: 2em auto; padding: 0 1em; color: #20242a; }}
table {{ border-collapse: collapse; width: 100%; margin: 1em 0; font-size: .92em; }}
th, td {{ border-bottom: 1px solid #ccc; padding: .45em; text-align: right; }}
th:first-child, td:first-child {{ text-align: left; }}
.note {{ background: #fff5da; padding: 1em; border: 1px solid #e6d59d; }}
</style>
</head>
<body>
<h1>Volatility as a share of the inflow</h1>
<div class="note">
<p>The outcome is the 3-month standard deviation of portfolio inflows divided by the absolute value of the 3-month mean inflow. A coefficient is a change in that ratio. A month is dropped when the absolute mean inflow is below 0.1 billion dollars.</p>
<p>GPR is the country index standardized within each country, in the same month. Each regression uses one WGI dimension, taken from the year of the previous month and centered on this sample. The GPR coefficient is the effect at that average. The interaction is the extra GPR effect when WGI is one point higher.</p>
<p>Real industrial production is omitted. The other controls are lagged one month and include central bank independence. Standard errors are clustered by country. *** p&lt;0.01, ** p&lt;0.05, * p&lt;0.10.</p>
</div>
{''.join(blocks)}
</body>
</html>
"""
    with open(path_html, "w", encoding="utf-8") as handle:
        handle.write(html)


def main():
    panel_rows = load_panel()
    usable = sum(row["volatility"] is not None for row in panel_rows)
    print("months with a scaled volatility", usable, "of", len(panel_rows))
    country_order = [country for country in est.read_country_order() if country in set(base.ISO.values())]
    results = {}
    for code in base.DIMENSIONS:
        rows, center = base.build_rows(panel_rows, est.read_wgi(code))
        fitted = base.fit(rows, country_order)
        results[code] = {"fit": fitted, "center": center}
        print(
            code, "N", fitted["n_obs"], "countries", fitted["n_country"],
            "R2", fitted["r2"], "center", center,
        )
        print(",".join(fitted["countries"]))
        for name in base.INTEREST:
            stat = fitted["stats"][name]
            print(" ", name, stat["coef"], stat["se"], stat["p"], est.stars(stat["p"]))
    write_outputs(
        os.path.join(OUTPUT, "capital_flow_volatility_scaled_wgi_results.csv"),
        os.path.join(OUTPUT, "capital_flow_volatility_scaled_wgi_results.html"),
        results,
    )


if __name__ == "__main__":
    main()
