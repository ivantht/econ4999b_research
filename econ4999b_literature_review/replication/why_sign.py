"""Locate which observations make the GPR coefficient on capital-flow volatility negative."""
import numpy as np
import pandas as pd
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("rep", Path("replication/build_and_replicate.py"))
rep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rep)

panel = pd.read_csv(rep.OUT / "panel.csv", parse_dates=["date"])
panel = panel.sort_values(["iso", "date"])
x = ["gpr_z", "rate_l1", "ln_ip_l1", "infl_l1", "ln_oil_l1", "ln_vix_l1", "ln_gepu_l1", "fd_l1", "cbi_l1", "debt_l1"]

base = rep.within_ols(panel, "cf_vol", x)
print(f"baseline {rep.stars(base['coef']['gpr_z'], base['se']['gpr_z'])} N={base['n']} countries={base['countries']}")

# Same regression, but do not require the policy rate (brings Ukraine back if other controls exist).
x_nopol = [c for c in x if c != "rate_l1"]
fit = rep.within_ols(panel, "cf_vol", x_nopol)
print(f"without policy rate {rep.stars(fit['coef']['gpr_z'], fit['se']['gpr_z'])} N={fit['n']} countries={fit['countries']}")
x_noip = [c for c in x if c != "ln_ip_l1"]
fit = rep.within_ols(panel, "cf_vol", x_noip)
print(f"without industrial production {rep.stars(fit['coef']['gpr_z'], fit['se']['gpr_z'])} N={fit['n']} countries={fit['countries']}")
x_min = [c for c in x if c not in ("ln_ip_l1", "rate_l1")]
fit = rep.within_ols(panel, "cf_vol", x_min)
print(f"without IP and policy rate {rep.stars(fit['coef']['gpr_z'], fit['se']['gpr_z'])} N={fit['n']} countries={fit['countries']}")

use = panel.loc[:, ["iso", "date", "cf_vol", "gpr", "group", *x]].dropna()
print("countries in baseline", sorted(use["iso"].unique()))
print("missing from baseline", sorted(set(panel["iso"].unique()) - set(use["iso"].unique())))
need = ["cf_vol", "gpr_z", *x]
for iso in ["CO", "ID", "PH", "TH", "UA", "ZA"]:
    g = panel[panel["iso"].eq(iso)]
    empty = [c for c in need if g[c].notna().sum() == 0]
    print(f"  {iso} completely missing {empty}")

# Within-country covariance contribution of GPR and volatility.
rows = []
for iso, g in use.groupby("iso"):
    gz = np.ravel(g["gpr_z"].to_numpy(dtype=float))
    yy = np.ravel(g["cf_vol"].to_numpy(dtype=float))
    gz = gz - gz.mean()
    y = yy - yy.mean()
    rows.append({
        "iso": iso,
        "group": g["group"].iloc[0],
        "n": len(g),
        "cov": float(np.mean(gz * y)),
        "corr": float(np.corrcoef(np.ravel(g["gpr_z"].to_numpy(dtype=float)), np.ravel(g["cf_vol"].to_numpy(dtype=float)))[0, 1]),
        "gpr_max": g["gpr"].max(),
        "gpr_max_date": g.loc[g["gpr"].idxmax(), "date"].date(),
        "vol_at_gpr_max": g.loc[g["gpr"].idxmax(), "cf_vol"],
    })
contrib = pd.DataFrame(rows).sort_values("cov")
print("\nMost negative within covariance")
print(contrib.head(8).to_string(index=False))
print("\nMost positive within covariance")
print(contrib.tail(8).to_string(index=False))
print("sum of cov", contrib["cov"].sum(), "share negative countries", (contrib["corr"] < 0).mean())

# Leave-one-country-out on the controlled regression.
print("\nLeave-one-out GPR coefficient")
loos = []
for iso in sorted(use["iso"].unique()):
    fit = rep.within_ols(use[use["iso"] != iso], "cf_vol", x)
    loos.append((iso, fit["coef"]["gpr_z"], fit["n"]))
loos = sorted(loos, key=lambda t: t[1])
for iso, b, n in loos[:5]:
    print(f"  drop {iso:3}  {b:+.3f}  N={n}")
print("  ...")
for iso, b, n in loos[-5:]:
    print(f"  drop {iso:3}  {b:+.3f}  N={n}")

# High-GPR months: is volatility actually high?
hi = use[use["gpr_z"] > 2]
print(f"\nMonths with GPR more than 2 within-country SD: {len(hi)}")
print(f"  mean volatility in those months {hi['cf_vol'].mean():.2f}")
print(f"  mean volatility in other months {use.loc[~use.index.isin(hi.index), 'cf_vol'].mean():.2f}")
top = use.nlargest(15, "gpr")[["iso", "date", "gpr", "cf_vol"]]
print("\nLargest raw GPR readings in the estimation sample")
print(top.assign(date=top["date"].dt.date).to_string(index=False))
