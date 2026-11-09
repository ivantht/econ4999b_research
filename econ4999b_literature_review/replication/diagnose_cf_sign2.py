"""Partial out crises and inspect the months that dominate volatility."""
from __future__ import annotations

import numpy as np
import pandas as pd
from pathlib import Path

OUT = Path(__file__).resolve().parent / "output"
ADV = {"BE", "CA", "DK", "FI", "FR", "DE", "IT", "JP", "KR", "NL", "PT", "ES", "SE", "US"}


def within_beta(df, y, x="gpr_z"):
    d = df[[y, x, "iso"]].dropna().copy()
    d["y"] = d[y] - d.groupby("iso")[y].transform("mean")
    d["x"] = d[x] - d.groupby("iso")[x].transform("mean")
    xv, yv = d["x"].to_numpy(), d["y"].to_numpy()
    return float(np.dot(xv, yv) / np.dot(xv, xv)), len(d)


def main() -> None:
    p = pd.read_csv(OUT / "panel.csv", parse_dates=["date"])
    p = p[p["date"].between("2000-01-01", "2023-12-01")].copy()
    p["ae"] = p["iso"].isin(ADV)
    d = p.dropna(subset=["cf_vol", "gpr_z"]).copy()

    crisis = (
        d["date"].between("2008-09-01", "2009-06-01")
        | d["date"].between("2020-02-01", "2020-06-01")
    )
    print("bivariate all", within_beta(d, "cf_vol"))
    print("drop GFC+COVID windows", within_beta(d.loc[~crisis], "cf_vol"))
    print("AE bivariate", within_beta(d.loc[d.ae], "cf_vol"))
    print("AE drop crises", within_beta(d.loc[d.ae & ~crisis], "cf_vol"))
    print("EM bivariate", within_beta(d.loc[~d.ae], "cf_vol"))
    print("EM drop crises", within_beta(d.loc[~d.ae & ~crisis], "cf_vol"))

    # residualize volatility on lagged VIX, then slope on GPR
    r = d.dropna(subset=["ln_vix_l1"]).copy()
    r["v"] = r["ln_vix_l1"] - r.groupby("iso")["ln_vix_l1"].transform("mean")
    r["y"] = r["cf_vol"] - r.groupby("iso")["cf_vol"].transform("mean")
    r["g"] = r["gpr_z"] - r.groupby("iso")["gpr_z"].transform("mean")
    b_v = float(np.dot(r.v, r.y) / np.dot(r.v, r.v))
    y_res = r.y - b_v * r.v
    b = float(np.dot(r.g, y_res) / np.dot(r.g, r.g))
    print("after residualizing vol on lagged log VIX", round(b, 3), "N", len(r))
    print("VIX coefficient in that bivariate", round(b_v, 3))
    print("corr within gpr and vix", round(float(np.dot(r.g, r.v) / np.sqrt(np.dot(r.g, r.g) * np.dot(r.v, r.v))), 3))

    print("\nLargest US portfolio-inflow months")
    us = d.loc[d.iso.eq("US"), ["date", "port_inf", "cf_vol", "gpr", "gpr_z"]].dropna()
    print(us.reindex(us.port_inf.abs().nlargest(12).index).sort_values("date").to_string(index=False))

    print("\nLargest DE vol months")
    de = d.loc[d.iso.eq("DE"), ["date", "port_inf", "cf_vol", "gpr_z"]].dropna()
    print(de.nlargest(8, "cf_vol").sort_values("date").to_string(index=False))

    print("\nShare of sum of squared within-vol coming from US, DE, JP, CN, FR")
    z = d.copy()
    z["y"] = z.cf_vol - z.groupby("iso").cf_vol.transform("mean")
    ss = z.groupby("iso").y.apply(lambda s: float(np.dot(s, s))).sort_values(ascending=False)
    print((ss / ss.sum()).head(8).round(3).to_string())
    print("top 4 share", round(float(ss.head(4).sum() / ss.sum()), 3))


if __name__ == "__main__":
    main()
