"""Annual emerging debt/GDP percentage change on same-year GPR, WGI, and their interaction.

Country fixed effects. Standard errors clustered by country, with the same
finite-sample factor as model1.md: G/(G-1) * (N-1)/(N-k).
"""

import csv
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import t as student_t

ROOT = Path(r"c:\Users\ASUS\econ4999b_research")
PANEL = ROOT / "cleaned" / "replication_cleaned" / "country_month.csv"
OUT_CSV = ROOT / "output" / "model1_annual_emerging_debt_pct_results.csv"

ASPECTS = [
    ("va", "Voice and accountability", "wgi_va"),
    ("pv", "Political stability", "wgi_pv"),
    ("ge", "Government effectiveness", "wgi_ge"),
    ("rq", "Regulatory quality", "wgi_rq"),
    ("rl", "Rule of law", "wgi_rl"),
    ("cc", "Control of corruption", "wgi_cc"),
]
YEAR_MIN = 2002
YEAR_MAX = 2021


def stars(p):
    if p < 0.01:
        return "***"
    if p < 0.05:
        return "**"
    if p < 0.10:
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


def annual_panel():
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
        "wgi_va",
        "wgi_pv",
        "wgi_ge",
        "wgi_rq",
        "wgi_rl",
        "wgi_cc",
        "policy_rate",
        "inflation",
        "ln_oil",
        "ln_vix",
        "ln_gepu",
        "ln_reer",
        "gpr_z",
    ]
    grouped = monthly.groupby(["country", "year"], as_index=False)
    annual = grouped[level_columns].mean()
    counts = grouped[level_columns].count()
    counts = counts.rename(columns={name: name + "_n" for name in level_columns})
    annual = annual.merge(counts, on=["country", "year"])
    annual = annual.sort_values(["country", "year"])
    annual["year_gap"] = annual.groupby("country")["year"].diff()
    for name in ("public_debt_gdp", "financial_development", "policy_rate", "inflation", "ln_oil", "ln_gepu", "ln_reer"):
        annual[name + "_l1"] = annual.groupby("country")[name].shift(1)
        annual[name + "_l1_n"] = annual.groupby("country")[name + "_n"].shift(1)
    annual = annual[annual["year_gap"] == 1].copy()
    annual["debt_diff"] = annual["public_debt_gdp"] - annual["public_debt_gdp_l1"]
    annual["debt_pct"] = 100 * annual["debt_diff"] / annual["public_debt_gdp_l1"]
    annual["fd_diff"] = annual["financial_development"] - annual["financial_development_l1"]
    annual["policy_diff"] = annual["policy_rate"] - annual["policy_rate_l1"]
    annual["inflation_diff"] = annual["inflation"] - annual["inflation_l1"]
    annual["oil_diff"] = annual["ln_oil"] - annual["ln_oil_l1"]
    annual["gepu_diff"] = annual["ln_gepu"] - annual["ln_gepu_l1"]
    annual["reer_diff"] = annual["ln_reer"] - annual["ln_reer_l1"]
    return annual


def complete_level_change_sample(annual):
    """Emerging country-years used by the published debt level-change table."""
    needed = [
        "debt_diff",
        "gpr_z",
        "wgi_va",
        "policy_diff",
        "inflation_diff",
        "oil_diff",
        "ln_vix",
        "gepu_diff",
        "fd_diff",
        "reer_diff",
    ]
    counts = [
        "public_debt_gdp_n",
        "public_debt_gdp_l1_n",
        "gpr_z_n",
        "wgi_va_n",
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
        "ln_reer_n",
        "ln_reer_l1_n",
    ]
    sample = annual[annual["year"].between(YEAR_MIN, YEAR_MAX)].copy()
    sample = sample.dropna(subset=needed)
    for name in counts:
        sample = sample[sample[name] == 12]
    return sample


def percentage_change_sample(annual):
    sample = annual[annual["year"].between(YEAR_MIN, YEAR_MAX)].copy()
    sample = sample.dropna(subset=["debt_pct", "public_debt_gdp", "public_debt_gdp_l1", "gpr_z", "wgi_va"])
    sample = sample[sample["public_debt_gdp_l1"] != 0]
    sample = sample[(sample["gpr_z_n"] == 12) & (sample["wgi_va_n"] == 12) & (sample["public_debt_gdp_n"] == 12)]
    return sample


def check_published_level_change(sample):
    published = {
        "wgi_va": -2.910935,
        "gpr_z": -0.624035,
        "inter": -2.058312,
    }
    frame = sample.copy()
    frame["inter"] = frame["wgi_va"] * frame["gpr_z"]
    fitted = fit_country_fe(
        frame,
        "debt_diff",
        ["wgi_va", "gpr_z", "inter", "policy_diff", "inflation_diff", "oil_diff", "ln_vix", "gepu_diff", "fd_diff"],
    )
    by_name = dict(zip(fitted["names"], zip(fitted["beta"], fitted["se"])))
    print("level-change check", fitted["n_obs"], fitted["n_country"], round(fitted["within_r2"], 4), round(fitted["r2"], 4))
    for name, target in published.items():
        coef, se = by_name[name]
        print(f"  {name}: {coef:.6f} ({se:.6f}) vs {target:.6f} gap {coef - target:.6f}")


def main():
    annual = annual_panel()
    level_sample = complete_level_change_sample(annual)
    check_published_level_change(level_sample)

    sample = percentage_change_sample(annual)
    print("percentage-change sample", len(sample), sample["country"].nunique(), sample["year"].min(), sample["year"].max())
    print(sample.groupby("country")["year"].agg(["min", "max", "count"]).to_string())
    print("negative lagged debt", int((sample["public_debt_gdp_l1"] < 0).sum()))

    rows = []
    fits = []
    for code, label, column in ASPECTS:
        frame = sample.dropna(subset=[column]).copy()
        frame["wgi"] = frame[column]
        frame["inter"] = frame["wgi"] * frame["gpr_z"]
        fitted = fit_country_fe(frame, "debt_pct", ["wgi", "gpr_z", "inter"])
        fits.append((code, label, fitted))
        for term, term_label in (("wgi", "WGI"), ("gpr_z", "GPR, standardized"), ("inter", "WGI x GPR")):
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
    with OUT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print("wrote", OUT_CSV)
    for code, label, fitted in fits:
        print(label, fitted["n_obs"], f"within {fitted['within_r2']:.4f}", f"r2 {fitted['r2']:.4f}")
        for term in ("wgi", "gpr_z", "inter"):
            index = fitted["names"].index(term)
            print(f"  {term}: {fitted['beta'][index]:.6f}{stars(fitted['p'][index])} ({fitted['se'][index]:.6f})")


if __name__ == "__main__":
    main()
