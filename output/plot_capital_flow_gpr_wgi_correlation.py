"""Cross-country correlation of the annual GPR–capital-flow correlation and average WGI.

The WGI average matches Correlation_GPR_REER.md: the mean of the annual
scores in 2000 and 2002–2023. WGI is blank in 2001.
"""

import base64
from io import BytesIO
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(r"c:\Users\ASUS\econ4999b_research")
PANEL = ROOT / "cleaned" / "replication_cleaned" / "country_month.csv"
CAPITAL_FLOW = ROOT / "cleaned" / "capital_flow.csv"
OUT_HTML = ROOT / "output" / "correlation_annual_gpr_capital_flow_and_wgi_emerging.html"

ASPECTS = [
    ("wgi_va", "Voice and accountability"),
    ("wgi_pv", "Political stability"),
    ("wgi_ge", "Government effectiveness"),
    ("wgi_rq", "Regulatory quality"),
    ("wgi_rl", "Rule of law"),
    ("wgi_cc", "Control of corruption"),
]
EMERGING14 = [
    "Brazil",
    "Chile",
    "China",
    "Colombia",
    "Hungary",
    "India",
    "Indonesia",
    "Malaysia",
    "Mexico",
    "Philippines",
    "Poland",
    "South Africa",
    "Thailand",
    "Turkiye",
]
REER_ANNUAL = {
    "Brazil": 0.206,
    "Chile": 0.049,
    "China": -0.390,
    "Colombia": -0.099,
    "Hungary": 0.144,
    "India": -0.144,
    "Indonesia": 0.400,
    "Malaysia": -0.029,
    "Mexico": 0.028,
    "Philippines": -0.508,
    "Poland": 0.226,
    "South Africa": -0.050,
    "Thailand": 0.001,
    "Turkiye": 0.076,
    "Ukraine": -0.252,
}
PUBLISHED_VA = 0.484


def wgi_averages():
    monthly = pd.read_csv(PANEL)
    monthly["date"] = pd.to_datetime(monthly["date"])
    monthly["year"] = monthly["date"].dt.year
    columns = [name for name, _ in ASPECTS]
    years = [2000, *range(2002, 2024)]
    sample = monthly[monthly["year"].isin(years)].copy()
    annual = sample.groupby(["country", "year"], as_index=False)[columns].mean()
    counts = annual.groupby("country")[columns[0]].count()
    if (counts.reindex(EMERGING14) != 23).any():
        raise RuntimeError("An emerging economy does not have 23 WGI years")
    return annual.groupby("country")[columns].mean()


def capital_flow_correlations():
    monthly = pd.read_csv(PANEL)
    monthly["date"] = pd.to_datetime(monthly["date"])
    monthly = monthly[monthly["group"] == "Emerging"].copy()
    monthly["year"] = monthly["date"].dt.year
    monthly = monthly[monthly["year"].between(2002, 2021)]
    gpr = monthly.groupby(["country", "year"])["gpr_z"].agg(gpr_z="mean", gpr_n="count").reset_index()
    gpr = gpr[gpr["gpr_n"] == 12]
    flows = pd.read_csv(CAPITAL_FLOW)
    flows["country"] = flows["country"].replace({"Turkey": "Turkiye", "Türkiye": "Turkiye"})
    flows["year"] = flows["year_quarter"].str.slice(0, 4).astype(int)
    flows["quarter"] = flows["year_quarter"].str.rsplit("Q", n=1).str[-1]
    flows = flows[flows["year"].between(2002, 2021)]
    annual = flows.groupby(["country", "year"], as_index=False).agg(
        capital_flow=("usd_millions", "mean"),
        n_quarters=("quarter", "nunique"),
    )
    annual = annual[annual["n_quarters"] == 4]
    correlations = {}
    for country in EMERGING14:
        paired = gpr.loc[gpr["country"] == country, ["year", "gpr_z"]].merge(
            annual.loc[annual["country"] == country, ["year", "capital_flow"]],
            on="year",
        )
        if len(paired) < 2:
            correlations[country] = np.nan
        else:
            correlations[country] = float(paired["gpr_z"].corr(paired["capital_flow"]))
    return correlations


def pearson(x_values, y_values):
    return float(pd.Series(x_values).corr(pd.Series(y_values)))


def scatter_png(countries, x_values, y_values, x_label, title):
    figure, axis = plt.subplots(figsize=(8.2, 6.2), dpi=140)
    axis.scatter(x_values, y_values, s=42, color="#1f4e79", zorder=3)
    slope, intercept = np.polyfit(x_values, y_values, 1)
    x_line = np.linspace(min(x_values), max(x_values), 50)
    axis.plot(x_line, intercept + slope * x_line, color="#888888", linewidth=1.2, zorder=2)
    x_cut = min(x_values) + 0.72 * (max(x_values) - min(x_values))
    for country, x_value, y_value in zip(countries, x_values, y_values):
        if x_value >= x_cut:
            offset = (-6, 4)
            alignment = "right"
        else:
            offset = (6, 4)
            alignment = "left"
        axis.annotate(
            country,
            (x_value, y_value),
            textcoords="offset points",
            xytext=offset,
            ha=alignment,
            fontsize=8,
            color="#1a1a1a",
        )
    axis.axhline(0, color="#dddddd", linewidth=0.8, zorder=1)
    axis.margins(x=0.14, y=0.12)
    axis.set_xlabel(x_label)
    axis.set_ylabel("Annual GPR–capital-flow correlation")
    axis.set_title(title)
    axis.grid(True, color="#eeeeee")
    figure.tight_layout()
    buffer = BytesIO()
    figure.savefig(buffer, format="png")
    plt.close(figure)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def main():
    averages = wgi_averages()
    reer_countries = list(REER_ANNUAL)
    reer_y = [REER_ANNUAL[country] for country in reer_countries]
    reer_x = averages.loc[reer_countries, "wgi_va"].to_numpy()
    reer_r = pearson(reer_x, reer_y)
    if abs(reer_r - PUBLISHED_VA) > 0.0015:
        raise RuntimeError(f"Voice-and-accountability check is {reer_r:.3f}, published {PUBLISHED_VA:.3f}")
    print(f"published emerging REER check {reer_r:.3f}")

    flow_r = capital_flow_correlations()
    used = [country for country in EMERGING14 if np.isfinite(flow_r[country])]
    missing = [country for country in EMERGING14 if country not in used]
    y_values = [flow_r[country] for country in used]
    images = []
    print("countries", ", ".join(used))
    print("missing", ", ".join(missing))
    for column, label in ASPECTS:
        x_values = averages.loc[used, column].to_numpy()
        correlation = pearson(x_values, y_values)
        print(f"{label}: {correlation:.6f}")
        title = f"{label}, r = {correlation:.3f}"
        images.append((label, correlation, scatter_png(used, x_values, y_values, f"Average {label.lower()}", title)))

    image_html = "\n".join(
        f'<img alt="{label}, r = {correlation:.3f}" src="data:image/png;base64,{encoded}">'
        for label, correlation, encoded in images
    )
    document = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Annual GPR–capital-flow correlation and average WGI, emerging economies</title>
<style>
body {{ font-family: "Segoe UI", sans-serif; margin: 28px auto 48px; max-width: 980px; color: #1a1a1a; background: #fff; }}
h1 {{ font-size: 22px; font-weight: 600; margin-bottom: 8px; }}
p {{ line-height: 1.45; margin: 0 0 10px; }}
img {{ width: 100%; height: auto; margin-top: 18px; }}
</style>
</head>
<body>
<h1>Annual GPR–capital-flow correlation and average WGI, emerging economies</h1>
<p>Each point is one emerging economy with a capital-flow series. The horizontal axis is that country's average WGI score. The vertical axis is the country's annual correlation between standardized GPR and capital flow. The correlation in the chart title is the Pearson correlation across those nine economies. The gray line is the fitted line.</p>
<p>The WGI average uses 2000 and 2002 through 2023. WGI is blank in 2001. Brazil, China, Colombia, Malaysia, and Poland have no capital-flow row. Source: cleaned/replication_cleaned/country_month.csv and cleaned/capital_flow.csv.</p>
{image_html}
</body>
</html>
"""
    OUT_HTML.write_text(document, encoding="utf-8")
    print("wrote", OUT_HTML)


if __name__ == "__main__":
    main()
