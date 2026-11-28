"""Monthly Model 1 on emerging economies.

Same equation, window, and country-clustered standard errors as the monthly
regression in model1.md. The sample is the Emerging group in
cleaned/replication_cleaned/country_month.csv. Ukraine drops out because the
lagged policy-rate change is blank.
"""

import csv
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import t as student_t

ROOT = Path(r"c:\Users\ASUS\econ4999b_research")
PANEL = ROOT / "cleaned" / "replication_cleaned" / "country_month.csv"
FULL_CSV = ROOT / "output" / "model1_results.csv"
OUT_CSV = ROOT / "output" / "model1_monthly_emerging_results.csv"

ASPECTS = [
    ("va", "Voice and accountability", "wgi_va"),
    ("pv", "Political stability", "wgi_pv"),
    ("ge", "Government effectiveness", "wgi_ge"),
    ("rq", "Regulatory quality", "wgi_rq"),
    ("rl", "Rule of law", "wgi_rl"),
    ("cc", "Control of corruption", "wgi_cc"),
]
LAG_SOURCES = [
    "wgi_va",
    "wgi_pv",
    "wgi_ge",
    "wgi_rq",
    "wgi_rl",
    "wgi_cc",
    "d_policy_rate",
    "d_inflation",
    "d_log_oil",
    "vix",
    "d_log_gepu",
    "d_financial_development",
    "d_public_debt_gdp",
]
CONTROLS = [
    ("d_policy_rate_l1", "Policy rate, lagged change"),
    ("d_inflation_l1", "Inflation, lagged change"),
    ("d_log_oil_l1", "Log oil price, lagged change"),
    ("ln_vix_l1", "Log VIX, lagged"),
    ("d_log_gepu_l1", "Log global EPU, lagged change"),
    ("d_financial_development_l1", "Financial development, lagged change"),
    ("d_public_debt_gdp_l1", "Debt/GDP, lagged change"),
]
WINDOW_START = pd.Timestamp("2002-02-01")
WINDOW_END = pd.Timestamp("2022-01-01")


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
        "month_min": frame["date"].min().strftime("%Y-%m"),
        "month_max": frame["date"].max().strftime("%Y-%m"),
        "countries": countries,
    }


def monthly_frame():
    frame = pd.read_csv(PANEL)
    frame["date"] = pd.to_datetime(frame["date"])
    lagged = frame[["country", "date", *LAG_SOURCES]].copy()
    lagged["date"] = lagged["date"] + pd.DateOffset(months=1)
    lagged = lagged.rename(columns={name: name + "_l1" for name in LAG_SOURCES})
    frame = frame.merge(lagged, on=["country", "date"], how="left")
    frame["ln_vix_l1"] = np.where(frame["vix_l1"] > 0, np.log(frame["vix_l1"]), np.nan)
    frame = frame[(frame["date"] >= WINDOW_START) & (frame["date"] <= WINDOW_END)].copy()
    return frame


def complete_sample(frame, wgi_column):
    needed = [
        "d_log_reer",
        "gpr_z",
        wgi_column + "_l1",
        *[name for name, _label in CONTROLS],
    ]
    sample = frame.dropna(subset=needed).copy()
    sample["wgi_l1"] = sample[wgi_column + "_l1"]
    sample["gpr_x_wgi"] = sample["wgi_l1"] * sample["gpr_z"]
    return sample


def regressors():
    return ["wgi_l1", "gpr_z", "gpr_x_wgi", *[name for name, _label in CONTROLS]]


def check_full_sample(frame):
    published = pd.read_csv(FULL_CSV)
    worst = 0.0
    for code, _label, column in ASPECTS:
        sample = complete_sample(frame, column)
        fitted = fit_country_fe(sample, "d_log_reer", regressors())
        lookup = dict(zip(fitted["names"], zip(fitted["beta"], fitted["se"])))
        rows = published[published["aspect"] == code]
        if len(sample) != int(rows["n_obs"].iloc[0]):
            raise SystemExit(f"{code} observations {len(sample)} != {int(rows['n_obs'].iloc[0])}")
        published_names = {
            "wgi_l1": "wgi_l1",
            "gpr_z": "gpr_z",
            "gpr_x_wgi": "gpr_x_wgi",
            "d_rate_l1": "d_policy_rate_l1",
            "d_infl_l1": "d_inflation_l1",
            "d_log_oil_l1": "d_log_oil_l1",
            "ln_vix_l1": "ln_vix_l1",
            "d_log_gepu_l1": "d_log_gepu_l1",
            "d_fd_l1": "d_financial_development_l1",
            "d_debt_l1": "d_public_debt_gdp_l1",
        }
        for _index, row in rows.iterrows():
            coef, se = lookup[published_names[row["term"]]]
            worst = max(worst, abs(coef - row["coef"]), abs(se - row["se"]))
    if worst > 5e-7:
        raise SystemExit(f"full-sample check failed, largest gap {worst:.3e}")
    print(f"full sample matches published coefficients, largest gap {worst:.3e}")


def term_rows():
    return [
        ("wgi_l1", "WGI, lagged"),
        ("gpr_z", "GPR, standardized"),
        ("gpr_x_wgi", "WGI x GPR"),
        *CONTROLS,
    ]


def write_results(frame):
    rows = []
    fitted_by_aspect = []
    sample_keys = None
    for code, label, column in ASPECTS:
        sample = complete_sample(frame, column)
        keys = set(zip(sample["country"], sample["date"]))
        if sample_keys is None:
            sample_keys = keys
        elif keys != sample_keys:
            raise SystemExit(f"{code} uses a different set of country-months")
        fitted = fit_country_fe(sample, "d_log_reer", regressors())
        fitted_by_aspect.append((code, label, fitted, sample))
        lookup = dict(zip(fitted["names"], range(len(fitted["names"]))))
        for term, term_label in term_rows():
            index = lookup[term]
            rows.append(
                {
                    "aspect": code,
                    "aspect_label": label,
                    "term": term,
                    "term_label": term_label,
                    "coef": f"{fitted['beta'][index]:.8f}",
                    "se": f"{fitted['se'][index]:.8f}",
                    "p": f"{fitted['p'][index]:.6f}",
                    "stars": stars(fitted["p"][index]),
                    "n_obs": fitted["n_obs"],
                    "n_country": fitted["n_country"],
                    "r2": f"{fitted['r2']:.4f}",
                    "within_r2": f"{fitted['within_r2']:.4f}",
                    "month_min": fitted["month_min"],
                    "month_max": fitted["month_max"],
                    "countries": "; ".join(fitted["countries"]),
                }
            )
    with OUT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return fitted_by_aspect


def main():
    frame = monthly_frame()
    check_full_sample(frame)
    emerging = frame[frame["group"] == "Emerging"].copy()
    fitted_by_aspect = write_results(emerging)
    _code, _label, fitted, sample = fitted_by_aspect[0]
    counts = sample.groupby("country")["date"].agg(["min", "max", "count"])
    print(counts.to_string())
    print(f"wrote {OUT_CSV}")
    print(f"{fitted['n_obs']} country-months, {fitted['n_country']} countries")


if __name__ == "__main__":
    main()
