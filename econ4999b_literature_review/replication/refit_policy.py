"""Refit with BIS policy rates and a raw-GPR check. Avoids re-downloading IMF."""
import numpy as np
import pandas as pd
import requests
from pathlib import Path
import importlib.util

spec = importlib.util.spec_from_file_location("rep", Path("replication/build_and_replicate.py"))
rep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rep)

panel = pd.read_csv(rep.OUT / "panel.csv", parse_dates=["date"])
bis = rep.load_policy()
panel = panel.drop(columns=["rate"], errors="ignore").merge(bis, on=["iso", "date"], how="left")

# BIS codes the euro area as XM. National series for euro members are not in the country file.
euro = ["BE", "DE", "ES", "FI", "FR", "IT", "NL", "PT"]
xm = rep.load_policy()
xm = xm[xm["iso"].eq("XM")][["date", "rate"]].rename(columns={"rate": "ecb_rate"})
# load_policy maps only sample countries, so pull XM directly if the mapper dropped it.
if xm.empty:
    raw = pd.read_csv(rep.RAW / "bis_policy_xm.csv")
    raw["date"] = pd.to_datetime(raw["TIME_PERIOD"].astype(str) + "-01")
    raw["ecb_rate"] = pd.to_numeric(raw["OBS_VALUE"], errors="coerce")
    xm = raw.groupby("date", as_index=False)["ecb_rate"].mean()
panel = panel.merge(xm, on="date", how="left")
miss = panel["iso"].isin(euro) & panel["rate"].isna()
panel.loc[miss, "rate"] = panel.loc[miss, "ecb_rate"]

panel = panel.sort_values(["iso", "date"])
panel["rate_l1"] = panel.groupby("iso")["rate"].shift(1)
print("policy rate", panel["rate"].describe().to_string(), flush=True)
print("missing", sorted(set(rep.SAMPLE_COUNTRIES) - set(panel.loc[panel["rate"].notna(), "iso"])), flush=True)

x = ["gpr_z", "rate_l1", "ln_ip_l1", "infl_l1", "ln_oil_l1", "ln_vix_l1", "ln_gepu_l1", "fd_l1", "cbi_l1", "debt_l1"]
for label, cols in [("raw GPR bivariate", ["gpr"]), ("z GPR bivariate", ["gpr_z"])]:
    fit = rep.within_ols(panel, "cf_vol", cols)
    key = cols[0]
    print(label, rep.stars(fit["coef"][key], fit["se"][key]), "N", fit["n"], flush=True)

print("\nREFIT TABLE 3", flush=True)
published_t3 = {
    ("Emerging", "cf_vol"): (3.144, 1.840),
    ("Emerging", "ln_stock_real"): (-0.017, 0.005),
    ("Emerging", "bond"): (0.088, 0.043),
    ("Emerging", "ln_reer"): (-0.010, 0.002),
    ("Advanced", "cf_vol"): (4.465, 1.343),
    ("Advanced", "ln_stock_real"): (-0.032, 0.005),
    ("Advanced", "bond"): (0.037, 0.020),
    ("Advanced", "ln_reer"): (-0.003, 0.002),
}
labels = {"cf_vol": "Capital flow volatility", "ln_stock_real": "Stock prices", "bond": "Bond yield", "ln_reer": "Exchange rate"}
for group in ["Emerging", "Advanced"]:
    sub = panel[panel["group"].eq(group)]
    for col, pub in ((k, v) for (g, k), v in published_t3.items() if g == group):
        fit = rep.within_ols(sub, col, x)
        print(group, labels[col], rep.stars(fit["coef"]["gpr_z"], fit["se"]["gpr_z"]), "paper", pub, "N", fit["n"], flush=True)

print("\nREFIT TABLE 2", flush=True)
for col, label, pub in [
    ("cf_vol", "Capital flow volatility", (0.867, 0.382)),
    ("ln_stock_real", "Stock prices", (-0.039, 0.006)),
    ("bond", "Bond yield", (0.134, 0.030)),
    ("ln_reer", "Exchange rate", (0.001, 0.002)),
]:
    fit = rep.within_ols(panel, col, x)
    print(label, rep.stars(fit["coef"]["gpr_z"], fit["se"]["gpr_z"]), "paper", pub, "N", fit["n"], "R2", round(fit["r2_within"], 3), flush=True)
