"""Country correlations of annual GPR and portfolio inflow, and their link to average WGI.

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
OUT_HTML = ROOT / "output" / "correlation_annual_gpr_portfolio_inflow_and_wgi_emerging.html"

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


def portfolio_correlations():
    monthly = pd.read_csv(PANEL)
    monthly["date"] = pd.to_datetime(monthly["date"])
    monthly = monthly[monthly["group"] == "Emerging"].copy()
    monthly["year"] = monthly["date"].dt.year
    monthly = monthly[monthly["year"].between(2002, 2021)]
    grouped = monthly.groupby(["country", "year"], as_index=False).agg(
        gpr_z=("gpr_z", "mean"),
        gpr_n=("gpr_z", "count"),
        portfolio_inflow=("portfolio_inflow", "mean"),
        portfolio_n=("portfolio_inflow", "count"),
    )
    grouped = grouped[(grouped["gpr_n"] == 12) & (grouped["portfolio_n"] == 12)]
    details = {}
    for country in EMERGING14:
        paired = grouped[grouped["country"] == country]
        if len(paired) < 2:
            details[country] = {"r": np.nan, "n": len(paired), "ymin": None, "ymax": None}
        else:
            details[country] = {
                "r": float(paired["gpr_z"].corr(paired["portfolio_inflow"])),
                "n": int(len(paired)),
                "ymin": int(paired["year"].min()),
                "ymax": int(paired["year"].max()),
            }
    return details


def pearson(x_values, y_values):
    return float(pd.Series(x_values).corr(pd.Series(y_values)))


def scatter_png(countries, x_values, y_values, x_label, title):
    figure, axis = plt.subplots(figsize=(9.4, 6.8), dpi=140)
    axis.scatter(x_values, y_values, s=42, color="#1f4e79", zorder=3)
    slope, intercept = np.polyfit(x_values, y_values, 1)
    x_line = np.linspace(min(x_values), max(x_values), 50)
    axis.plot(x_line, intercept + slope * x_line, color="#888888", linewidth=1.2, zorder=2)
    x_span = max(x_values) - min(x_values) or 1
    y_span = max(y_values) - min(y_values) or 1
    placed = []
    lifts = [8, -14, 20, -26]
    for country, x_value, y_value in zip(countries, x_values, y_values):
        close_count = 0
        for earlier_x, earlier_y in placed:
            close_x = abs(x_value - earlier_x) / x_span < 0.12
            close_y = abs(y_value - earlier_y) / y_span < 0.10
            if close_x and close_y:
                close_count += 1
        placed.append((x_value, y_value))
        axis.annotate(
            country,
            (x_value, y_value),
            textcoords="offset points",
            xytext=(0, lifts[close_count % len(lifts)]),
            ha="center",
            va="bottom" if lifts[close_count % len(lifts)] > 0 else "top",
            fontsize=8,
            color="#1a1a1a",
        )
    axis.axhline(0, color="#dddddd", linewidth=0.8, zorder=1)
    axis.margins(x=0.12, y=0.16)
    axis.set_xlabel(x_label)
    axis.set_ylabel("Annual GPR–portfolio-inflow correlation")
    axis.set_title(title)
    axis.grid(True, color="#eeeeee")
    figure.tight_layout()
    buffer = BytesIO()
    figure.savefig(buffer, format="png")
    plt.close(figure)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def main():
    averages = wgi_averages()
    details = portfolio_correlations()
    for country in EMERGING14:
        item = details[country]
        if np.isfinite(item["r"]):
            print(f"{country} {item['r']:.6f} {item['n']} {item['ymin']}-{item['ymax']}")
        else:
            print(f"{country} . {item['n']}")
    used = [country for country in EMERGING14 if np.isfinite(details[country]["r"])]
    y_values = [details[country]["r"] for country in used]
    images = []
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
<title>Annual GPR–portfolio-inflow correlation and average WGI, emerging economies</title>
<style>
body {{ font-family: "Segoe UI", sans-serif; margin: 28px auto 48px; max-width: 980px; color: #1a1a1a; background: #fff; }}
h1 {{ font-size: 22px; font-weight: 600; margin-bottom: 8px; }}
p {{ line-height: 1.45; margin: 0 0 10px; }}
img {{ width: 100%; height: auto; margin-top: 18px; }}
</style>
</head>
<body>
<h1>Annual GPR–portfolio-inflow correlation and average WGI, emerging economies</h1>
<p>Each point is one of the 14 emerging economies. The horizontal axis is that country's average WGI score. The vertical axis is the country's annual correlation between standardized GPR and portfolio inflow. The correlation in the chart title is the Pearson correlation across those 14 economies. The gray line is the fitted line.</p>
<p>The WGI average uses 2000 and 2002 through 2023. WGI is blank in 2001. Source: cleaned/replication_cleaned/country_month.csv.</p>
{image_html}
</body>
</html>
"""
    OUT_HTML.write_text(document, encoding="utf-8")
    print("wrote", OUT_HTML)


if __name__ == "__main__":
    main()
