"""Model 1 (Channel 1: IQ on REER) monthly regression, full sample and emerging only.

Reproduces the estimator described in `1. Source of Truth/model1.md`: OLS with a full
set of country indicators, country-clustered standard errors, small-sample factor
G/(G-1) * (N-1)/(N-k), and two-sided t p-values with G-1 degrees of freedom.

Writes output/model1_monthly_emerging_results.csv.
"""

import math

import numpy as np
import pandas as pd

CM_PATH = "cleaned/replication_cleaned/country_month.csv"
WGI_PATH = "cleaned/wgi.csv"
OUT_PATH = "output/model1_monthly_emerging_results.csv"

DIMS = ["va", "pv", "ge", "rq", "rl", "cc"]
DIM_LABEL = {
    "va": "Voice and accountability",
    "pv": "Political stability",
    "ge": "Government effectiveness",
    "rq": "Regulatory quality",
    "rl": "Rule of law",
    "cc": "Control of corruption",
}


# ---------------------------------------------------------------- p-values
def _betacf(a, b, x):
    MAXIT, EPS, FPMIN = 300, 3e-16, 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > FPMIN else FPMIN)
    h = d
    for m in range(1, MAXIT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > FPMIN else FPMIN)
        c = 1.0 + aa / c
        c = c if abs(c) > FPMIN else FPMIN
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > FPMIN else FPMIN)
        c = 1.0 + aa / c
        c = c if abs(c) > FPMIN else FPMIN
        de = d * c
        h *= de
        if abs(de - 1.0) < EPS:
            break
    return h


def _betai(a, b, x):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lb = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    bt = math.exp(lb + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def t_pvalue(t, df):
    return _betai(df / 2.0, 0.5, df / (df + t * t))


def stars(p):
    if p < 0.01:
        return "***"
    if p < 0.05:
        return "**"
    if p < 0.10:
        return "*"
    return ""


# ---------------------------------------------------------------- panel
def build_panel():
    cm = pd.read_csv(CM_PATH, parse_dates=["date"]).sort_values(["country", "date"])
    cm = cm.reset_index(drop=True)
    wgi = pd.read_csv(WGI_PATH)

    # WGI spells some countries differently from the panel.
    cm["wgi_name"] = cm["country"].replace({"Korea": "South Korea", "Turkiye": "Turkey"})

    # gpr_z: within-country mean and sample sd over Jan 2000 - Dec 2023.
    base = cm[(cm["date"] >= "2000-01-01") & (cm["date"] <= "2023-12-01")]
    stats = base.groupby("country")["gpr"].agg(["mean", "std"])
    cm["gpr_z"] = (cm["gpr"] - cm["country"].map(stats["mean"])) / cm["country"].map(stats["std"])

    # annual WGI repeated on every month of the calendar year
    wide = (
        wgi.pivot_table(index=["country", "year"], columns="dimension", values="estimate")
        .reset_index()
        .rename(columns={d: f"wgi_{d}" for d in DIMS})
    )
    cm["year"] = cm["date"].dt.year
    cm = cm.merge(
        wide,
        left_on=["wgi_name", "year"],
        right_on=["country", "year"],
        how="left",
        suffixes=("", "_wgi"),
        validate="many_to_one",
    )

    # outcome and treated changes
    cm["d_log_reer"] = np.log(cm["reer"]).groupby(cm["country"]).diff()
    # Financial development and debt/GDP are annual levels repeated on every month of
    # the calendar year. Their treated change is the year-over-year difference in that
    # annual level, repeated on every month of the year (not a monthly difference).
    for col in ["financial_development", "public_debt_gdp"]:
        cm[f"{col}_annual"] = cm.groupby(["country", "year"])[col].transform("first")
        cm[f"d_{col}"] = cm.groupby("country")[f"{col}_annual"].diff()
        cm[f"d_{col}"] = cm.groupby(["country", "year"])[f"d_{col}"].transform("first")
    cm["d_policy_rate"] = cm.groupby("country")["policy_rate"].diff()
    cm["d_inflation"] = cm.groupby("country")["inflation"].diff()
    cm["d_log_oil"] = np.log(cm["oil_price"]).groupby(cm["country"]).diff()
    cm["d_log_gepu"] = np.log(cm["gepu"]).groupby(cm["country"]).diff()
    cm["ln_vix"] = np.log(cm["vix"])

    lagged = [
        *[f"wgi_{d}" for d in DIMS],
        "d_financial_development",
        "d_public_debt_gdp",
        "d_policy_rate",
        "d_inflation",
        "d_log_oil",
        "d_log_gepu",
        "ln_vix",
    ]
    for col in lagged:
        cm[f"{col}_lag1"] = cm.groupby("country")[col].shift(1)
    return cm, lagged


# ---------------------------------------------------------------- estimator
def fit(df, ycol, xcols):
    d = df.dropna(subset=[ycol, *xcols]).reset_index(drop=True)
    dum = pd.get_dummies(d["country"], prefix="c", drop_first=True, dtype=float)
    X = np.column_stack(
        [
            np.ones(len(d)),
            d[xcols].to_numpy(float),
            dum.to_numpy(float),
        ]
    )
    y = d[ycol].to_numpy(float)
    n, k = X.shape

    XtX_inv = np.linalg.pinv(X.T @ X)
    b = XtX_inv @ (X.T @ y)
    e = y - X @ b

    meat = np.zeros((k, k))
    groups = d["country"].to_numpy()
    for g in np.unique(groups):
        idx = np.where(groups == g)[0]
        s = X[idx].T @ e[idx]
        meat += np.outer(s, s)
    G = len(np.unique(groups))
    factor = (G / (G - 1)) * ((n - 1) / (n - k))
    V = factor * XtX_inv @ meat @ XtX_inv
    se = np.sqrt(np.diag(V))

    resid_within = d[ycol] - d.groupby("country")[ycol].transform("mean")
    fitted_within = pd.Series(X @ b, index=d.index)
    fitted_within = fitted_within - fitted_within.groupby(groups).transform("mean")
    r2_within = 1 - ((resid_within - fitted_within) ** 2).sum() / (resid_within ** 2).sum()
    r2 = 1 - (e**2).sum() / ((y - y.mean()) ** 2).sum()

    out = pd.DataFrame({"term": ["const", *xcols, *dum.columns], "coef": b, "se": se})
    out["t"] = out["coef"] / out["se"]
    out["p"] = out["t"].apply(lambda v: t_pvalue(v, G - 1))
    out["stars"] = out["p"].apply(stars)
    out.attrs.update(n=n, G=G, k=k, r2_within=r2_within, r2=r2)
    return out


def main():
    cm, lagged = build_panel()
    # The reference sample is February 2002 through January 2022.
    cm = cm[(cm["date"] >= "2002-02-01") & (cm["date"] <= "2022-01-01")].copy()
    results = []

    for sample, frame in [
        ("full", cm),
        ("emerging", cm[cm["group"] == "Emerging"]),
    ]:
        for dim in DIMS:
            w = f"wgi_{dim}"
            xcols = [
                "gpr_z",
                f"{w}_lag1",
                "interaction",
                "d_policy_rate_lag1",
                "d_inflation_lag1",
                "d_log_oil_lag1",
                "ln_vix_lag1",
                "d_log_gepu_lag1",
                "d_financial_development_lag1",
                "d_public_debt_gdp_lag1",
            ]
            f = frame.copy()
            f["interaction"] = f[f"{w}_lag1"] * f["gpr_z"]
            res = fit(f, "d_log_reer", xcols)
            key = {
                "gpr_z": "gpr_z",
                f"{w}_lag1": "wgi_lag1",
                "interaction": "wgi_x_gpr",
            }
            focused = res[res["term"].isin(xcols)].copy()
            focused["term"] = focused["term"].map(lambda t: key.get(t, t))
            focused["sample"] = sample
            focused["dimension"] = DIM_LABEL[dim]
            focused["n"] = res.attrs["n"]
            focused["countries"] = res.attrs["G"]
            focused["r2_within"] = res.attrs["r2_within"]
            focused["r2"] = res.attrs["r2"]
            results.append(focused)

    out = pd.concat(results, ignore_index=True)
    out = out[["sample", "dimension", "term", "coef", "se", "p", "stars", "n", "countries",
               "r2_within", "r2"]]
    out.to_csv(OUT_PATH, index=False)

    pd.set_option("display.width", 200)
    for sample in ["full", "emerging"]:
        block = out[out["sample"] == sample]
        print(f"\n=== {sample}: N={block['n'].iloc[0]}, G={block['countries'].iloc[0]} ===")
        piv = block.pivot(index="term", columns="dimension", values="coef")
        se = block.pivot(index="term", columns="dimension", values="se")
        pv = block.pivot(index="term", columns="dimension", values="p")
        st = block.pivot(index="term", columns="dimension", values="stars")
        for term in ["wgi_lag1", "gpr_z", "wgi_x_gpr"]:
            cells = []
            for dim in [DIM_LABEL[d] for d in DIMS]:
                cells.append(f"{piv.loc[term, dim]:+.6f}{st.loc[term, dim]:3s}"
                             f" ({se.loc[term, dim]:.6f}, p={pv.loc[term, dim]:.3f})")
            print(f"  {term:10s} " + " | ".join(cells))
        print(f"  within R2 {block['r2_within'].iloc[0]:.4f}  R2 {block['r2'].iloc[0]:.4f}")
    print(f"\nwrote {OUT_PATH}")


if __name__ == "__main__":
    main()
