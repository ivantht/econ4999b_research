"""Annual emerging Model 1 with the year-t capital flow or portfolio inflow as the outcome.

The right-hand side matches the annual REER regression in model1.md.
The outcome is that year's mean, not the change from the previous year.
Country fixed effects. Standard errors clustered by country, with the
sandwich factor G/(G-1) * (N-1)/(N-k) and t(G-1) p-values.
"""

import csv
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import t as student_t

ROOT = Path(r"c:\Users\ASUS\econ4999b_research")
PANEL = ROOT / "cleaned" / "replication_cleaned" / "country_month.csv"
CAPITAL_FLOW = ROOT / "cleaned" / "capital_flow.csv"
OUT_DIR = ROOT / "output"

ASPECTS = [
    ("va", "Voice and accountability", "wgi_va"),
    ("pv", "Political stability", "wgi_pv"),
    ("ge", "Government effectiveness", "wgi_ge"),
    ("rq", "Regulatory quality", "wgi_rq"),
    ("rl", "Rule of law", "wgi_rl"),
    ("cc", "Control of corruption", "wgi_cc"),
]
WGI_COLUMNS = [column for _, _, column in ASPECTS]
YEAR_MIN = 2002
YEAR_MAX = 2021
CONTROLS = [
    "policy_diff",
    "inflation_diff",
    "oil_diff",
    "ln_vix",
    "gepu_diff",
    "fd_diff",
    "debt_diff",
]
RHS_COUNTS = [
    "public_debt_gdp_n",
    "public_debt_gdp_l1_n",
    "gpr_z_n",
    "policy_rate_n",
    "policy_rate_l1_n",
    "inflation_n",
    "inflation_l1_n",
    "ln_oil_n",
    "ln_oil_l1_n",
    "ln_vix_n",
    "ln_gepu_n",
    "ln_gepu_l1_n",
    "financial_development_n",
    "financial_development_l1_n",
] + [column + "_n" for column in WGI_COLUMNS]

PUBLISHED_REER_VA = {
    "wgi": (0.028816, 0.018889),
    "gpr_z": (-0.014448, 0.006108),
    "inter": (0.004611, 0.005699),
    "policy_diff": (0.003099, 0.002792),
    "inflation_diff": (-0.010637, 0.003671),
    "oil_diff": (0.072929, 0.020902),
    "ln_vix": (-0.021193, 0.008441),
    "gepu_diff": (0.053405, 0.012444),
    "fd_diff": (-0.040139, 0.228658),
    "debt_diff": (-0.003143, 0.000905),
}


def stars(p_value):
    if p_value < 0.01:
        return "***"
    if p_value < 0.05:
        return "**"
    if p_value < 0.10:
        return "*"
    return ""


def fit_country_fe(frame, y_name, x_names):
    countries = sorted(frame["country"].unique())
    y = frame[y_name].to_numpy(dtype=float)
    columns = [np.ones(len(frame), dtype=float)]
    names = ["const"]
    for name in x_names:
        columns.append(frame[name].to_numpy(dtype=float))
        names.append(name)
    for country in countries[1:]:
        columns.append((frame["country"] == country).to_numpy(dtype=float))
        names.append("fe_" + country)
    x_matrix = np.column_stack(columns)
    n_obs, k_params = x_matrix.shape
    xtx_inv = np.linalg.inv(x_matrix.T @ x_matrix)
    beta = xtx_inv @ (x_matrix.T @ y)
    resid = y - x_matrix @ beta
    meat = np.zeros((k_params, k_params))
    country_codes = frame["country"].to_numpy()
    for country in countries:
        in_country = country_codes == country
        score = x_matrix[in_country].T @ resid[in_country]
        meat += np.outer(score, score)
    n_countries = len(countries)
    variance = xtx_inv @ meat @ xtx_inv
    variance *= (n_countries / (n_countries - 1)) * ((n_obs - 1) / (n_obs - k_params))
    se = np.sqrt(np.clip(np.diag(variance), 0, None))
    t_stat = beta / se
    p_value = 2 * (1 - student_t.cdf(np.abs(t_stat), df=n_countries - 1))
    sse = float(resid @ resid)
    sst = float(np.sum((y - y.mean()) ** 2))
    y_within = y.copy()
    for country in countries:
        in_country = country_codes == country
        y_within[in_country] -= y_within[in_country].mean()
    sst_within = float(y_within @ y_within)
    return {
        "names": names,
        "beta": beta,
        "se": se,
        "p": p_value,
        "n_obs": n_obs,
        "n_country": n_countries,
        "r2": 1 - sse / sst,
        "within_r2": 1 - sse / sst_within,
        "year_min": int(frame["year"].min()),
        "year_max": int(frame["year"].max()),
        "countries": countries,
    }


def annual_from_months():
    monthly = pd.read_csv(PANEL)
    monthly["date"] = pd.to_datetime(monthly["date"])
    monthly = monthly[monthly["group"] == "Emerging"].copy()
    monthly["year"] = monthly["date"].dt.year
    monthly["ln_oil"] = np.log(monthly["oil_price"])
    monthly["ln_vix"] = np.log(monthly["vix"])
    monthly["ln_gepu"] = np.log(monthly["gepu"])
    monthly["ln_reer"] = np.log(monthly["reer"])
    level_columns = [
        "public_debt_gdp",
        "financial_development",
        *WGI_COLUMNS,
        "policy_rate",
        "inflation",
        "ln_oil",
        "ln_vix",
        "ln_gepu",
        "ln_reer",
        "gpr_z",
        "portfolio_inflow",
    ]
    grouped = monthly.groupby(["country", "year"], as_index=False)
    annual = grouped[level_columns].mean()
    counts = grouped[level_columns].count().rename(columns={name: name + "_n" for name in level_columns})
    annual = annual.merge(counts, on=["country", "year"])
    annual = annual.sort_values(["country", "year"])
    annual["year_gap"] = annual.groupby("country")["year"].diff()
    for name in (
        "public_debt_gdp",
        "financial_development",
        "policy_rate",
        "inflation",
        "ln_oil",
        "ln_gepu",
        "ln_reer",
        "portfolio_inflow",
    ):
        annual[name + "_l1"] = annual.groupby("country")[name].shift(1)
        annual[name + "_l1_n"] = annual.groupby("country")[name + "_n"].shift(1)
    annual = annual[annual["year_gap"] == 1].copy()
    annual["debt_diff"] = annual["public_debt_gdp"] - annual["public_debt_gdp_l1"]
    annual["fd_diff"] = annual["financial_development"] - annual["financial_development_l1"]
    annual["policy_diff"] = annual["policy_rate"] - annual["policy_rate_l1"]
    annual["inflation_diff"] = annual["inflation"] - annual["inflation_l1"]
    annual["oil_diff"] = annual["ln_oil"] - annual["ln_oil_l1"]
    annual["gepu_diff"] = annual["ln_gepu"] - annual["ln_gepu_l1"]
    annual["reer_diff"] = annual["ln_reer"] - annual["ln_reer_l1"]
    annual["portfolio_diff"] = annual["portfolio_inflow"] - annual["portfolio_inflow_l1"]
    annual["portfolio_pct"] = (
        100 * annual["portfolio_diff"] / annual["portfolio_inflow_l1"].abs()
    )
    return annual


def rhs_sample(annual):
    needed = [
        "gpr_z",
        "policy_diff",
        "inflation_diff",
        "oil_diff",
        "ln_vix",
        "gepu_diff",
        "fd_diff",
        "debt_diff",
        *WGI_COLUMNS,
    ]
    sample = annual[annual["year"].between(YEAR_MIN, YEAR_MAX)].copy()
    sample = sample.dropna(subset=needed)
    for name in RHS_COUNTS:
        sample = sample[sample[name] == 12]
    return sample


def capital_flow_level():
    flows = pd.read_csv(CAPITAL_FLOW)
    flows["country"] = flows["country"].replace({"Turkey": "Turkiye", "Türkiye": "Turkiye"})
    flows["year"] = flows["year_quarter"].str.slice(0, 4).astype(int)
    flows["quarter"] = flows["year_quarter"].str.rsplit("Q", n=1).str[-1]
    flows["usd_millions"] = pd.to_numeric(flows["usd_millions"])
    if flows.duplicated(["country", "year_quarter"]).any():
        raise ValueError("capital_flow.csv has a repeated country-quarter")
    annual = flows.groupby(["country", "year"], as_index=False).agg(
        capital_flow=("usd_millions", "mean"),
        capital_flow_n=("quarter", "nunique"),
        capital_flow_rows=("quarter", "size"),
    )
    if (annual["capital_flow_rows"] < annual["capital_flow_n"]).any():
        raise ValueError("capital_flow.csv has fewer rows than distinct quarters")
    annual = annual[annual["capital_flow_n"] == 4].copy()
    return annual[["country", "year", "capital_flow"]]


def check_published_reer(sample):
    reer = sample.dropna(subset=["reer_diff"]).copy()
    reer = reer[(reer["ln_reer_n"] == 12) & (reer["ln_reer_l1_n"] == 12)]
    reer["wgi"] = reer["wgi_va"]
    reer["inter"] = reer["wgi"] * reer["gpr_z"]
    fitted = fit_country_fe(reer, "reer_diff", ["wgi", "gpr_z", "inter", *CONTROLS])
    if fitted["n_obs"] != 273 or fitted["n_country"] != 14:
        raise RuntimeError(f"REER sample is {fitted['n_obs']} rows and {fitted['n_country']} countries")
    by_name = dict(zip(fitted["names"], zip(fitted["beta"], fitted["se"])))
    for name, (coef_target, se_target) in PUBLISHED_REER_VA.items():
        coef, se = by_name[name]
        if abs(coef - coef_target) > 1.5e-6 or abs(se - se_target) > 1.5e-6:
            raise RuntimeError(f"{name} is {coef:.6f} ({se:.6f}), published {coef_target:.6f} ({se_target:.6f})")
    if abs(fitted["within_r2"] - 0.2660) > 5e-5 or abs(fitted["r2"] - 0.2872) > 5e-5:
        raise RuntimeError(f"REER fit is within {fitted['within_r2']:.4f}, R2 {fitted['r2']:.4f}")


def fit_outcome(sample, y_name):
    fits = []
    rows = []
    for code, label, column in ASPECTS:
        frame = sample.copy()
        frame["wgi"] = frame[column]
        frame["inter"] = frame["wgi"] * frame["gpr_z"]
        fitted = fit_country_fe(frame, y_name, ["wgi", "gpr_z", "inter", *CONTROLS])
        fits.append((code, label, fitted))
        for term, term_label in (
            ("wgi", "WGI"),
            ("gpr_z", "GPR, standardized"),
            ("inter", "WGI x GPR"),
            ("policy_diff", "Policy rate, annual change"),
            ("inflation_diff", "Inflation, annual change"),
            ("oil_diff", "Log oil price, annual change"),
            ("ln_vix", "Log VIX"),
            ("gepu_diff", "Log global EPU, annual change"),
            ("fd_diff", "Financial development, annual change"),
            ("debt_diff", "Debt/GDP, annual change"),
        ):
            index = fitted["names"].index(term)
            rows.append({
                "aspect": code,
                "aspect_label": label,
                "term": term,
                "term_label": term_label,
                "coef": fitted["beta"][index],
                "se": fitted["se"][index],
                "p": fitted["p"][index],
                "stars": stars(fitted["p"][index]),
                "n_obs": fitted["n_obs"],
                "n_country": fitted["n_country"],
                "r2": fitted["r2"],
                "within_r2": fitted["within_r2"],
                "year_min": fitted["year_min"],
                "year_max": fitted["year_max"],
                "countries": "; ".join(fitted["countries"]),
            })
    return fits, rows


def write_rows(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def markdown_table(fits):
    labels = [label for _, label, _ in fits]
    header = "|  | " + " | ".join(labels) + " |"
    rule = "| --- | " + " | ".join(["---:"] * len(labels)) + " |"
    terms = [
        ("wgi", "WGI"),
        ("gpr_z", "GPR, standardized"),
        ("inter", "WGI × GPR"),
        ("policy_diff", "Policy rate, annual change"),
        ("inflation_diff", "Inflation, annual change"),
        ("oil_diff", "Log oil price, annual change"),
        ("ln_vix", "Log VIX"),
        ("gepu_diff", "Log global EPU, annual change"),
        ("fd_diff", "Financial development, annual change"),
        ("debt_diff", "Debt/GDP, annual change"),
    ]
    lines = [header, rule]
    for term, label in terms:
        cells = []
        for _, _, fitted in fits:
            index = fitted["names"].index(term)
            coef = fitted["beta"][index]
            se = fitted["se"][index]
            mark = stars(fitted["p"][index])
            shown = f"{abs(coef):.6f}{mark}"
            if coef < 0:
                shown = "−" + shown
            cells.append(f"{shown} ({se:.6f})")
        lines.append("| " + label + " | " + " | ".join(cells) + " |")
    first = fits[0][2]
    if any(fitted["n_obs"] != first["n_obs"] or fitted["n_country"] != first["n_country"] for _, _, fitted in fits):
        raise RuntimeError("The six WGI regressions do not share a sample")
    lines.append("| Observations | " + " | ".join([f"{fitted['n_obs']:,}" for _, _, fitted in fits]) + " |")
    lines.append("| Countries | " + " | ".join([str(fitted["n_country"]) for _, _, fitted in fits]) + " |")
    year_cell = f"{first['year_min']} to {first['year_max']}"
    lines.append("| Years | " + " | ".join([year_cell] * len(fits)) + " |")
    lines.append("| Within \\(R^2\\) | " + " | ".join([f"{fitted['within_r2']:.4f}" for _, _, fitted in fits]) + " |")
    lines.append("| \\(R^2\\) | " + " | ".join([f"{fitted['r2']:.4f}" for _, _, fitted in fits]) + " |")
    return "\n".join(lines)


def main():
    annual = annual_from_months()
    sample = rhs_sample(annual)
    check_published_reer(sample)
    print("published REER voice-and-accountability column matches")

    portfolio = sample.dropna(subset=["portfolio_inflow"]).copy()
    portfolio = portfolio[portfolio["portfolio_inflow_n"] == 12]
    portfolio_fits, portfolio_rows = fit_outcome(portfolio, "portfolio_inflow")
    portfolio_path = OUT_DIR / "model1_annual_emerging_portfolio_inflow_results.csv"
    write_rows(portfolio_path, portfolio_rows)

    capital = sample.merge(capital_flow_level(), on=["country", "year"], how="inner")
    capital_fits, capital_rows = fit_outcome(capital, "capital_flow")
    capital_path = OUT_DIR / "model1_annual_emerging_capital_flow_results.csv"
    write_rows(capital_path, capital_rows)

    print("\nCAPITAL FLOW")
    print(capital.groupby("country")["year"].agg(["min", "max", "count"]).to_string())
    print(markdown_table(capital_fits))
    print("\nPORTFOLIO INFLOW")
    print(portfolio.groupby("country")["year"].agg(["min", "max", "count"]).to_string())
    print(markdown_table(portfolio_fits))
    print("wrote", capital_path)
    print("wrote", portfolio_path)


if __name__ == "__main__":
    main()
