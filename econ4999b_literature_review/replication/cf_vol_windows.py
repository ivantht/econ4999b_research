"""Check whether a longer window or GARCH flips the capital-flow sign."""
import numpy as np
import pandas as pd
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "rep", Path("replication/build_and_replicate.py")
)
rep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rep)

panel = pd.read_csv(rep.OUT / "panel.csv", parse_dates=["date"])
panel = panel.sort_values(["iso", "date"])
x = [
    "gpr_z", "rate_l1", "ln_ip_l1", "infl_l1", "ln_oil_l1", "ln_vix_l1",
    "ln_gepu_l1", "fd_l1", "cbi_l1", "debt_l1",
]

def add_roll(window):
    out = []
    for iso, g in panel.groupby("iso"):
        g = g.set_index("date").sort_index()
        full = g[["port_inf"]].copy()
        full["vol"] = full["port_inf"].rolling(window, min_periods=window).std(ddof=1)
        full["iso"] = iso
        out.append(full.reset_index()[["iso", "date", "vol"]])
    return pd.concat(out, ignore_index=True)

def garch11_sigma(y):
    y = np.asarray(y, dtype=float)
    mask = np.isfinite(y)
    if mask.sum() < 36:
        return np.full(len(y), np.nan)
    z = y[mask]
    z = z - z.mean()
    var = np.empty(len(z))
    v0 = np.var(z)
    var[0] = v0
    # Moments start; then a short grid keeps this dependency-free.
    best = None
    for omega in (0.05, 0.2, 1.0):
        for alpha in (0.05, 0.1, 0.2):
            for beta in (0.7, 0.85, 0.9):
                if alpha + beta >= 0.98:
                    continue
                v = var.copy()
                v[0] = v0
                ll = 0.0
                for t in range(1, len(z)):
                    v[t] = omega + alpha * z[t - 1] ** 2 + beta * v[t - 1]
                    ll += -0.5 * (np.log(v[t]) + z[t] ** 2 / v[t])
                if best is None or ll > best[0]:
                    best = (ll, omega, alpha, beta)
    _, omega, alpha, beta = best
    v = np.empty(len(z))
    v[0] = v0
    for t in range(1, len(z)):
        v[t] = omega + alpha * z[t - 1] ** 2 + beta * v[t - 1]
    sigma = np.full(len(y), np.nan)
    sigma[np.where(mask)[0]] = np.sqrt(np.maximum(v, 1e-8))
    return sigma

print("window | mean | max | GPR coef (se) | N | published 3m is +0.867")
for window, label in [(3, "3-month"), (6, "6-month"), (12, "12-month")]:
    vol = add_roll(window).rename(columns={"vol": "cf_alt"})
    df = panel.drop(columns=["cf_vol"]).merge(vol, on=["iso", "date"], how="left")
    s = df["cf_alt"].dropna()
    fit = rep.within_ols(df, "cf_alt", x)
    print(
        f"{label:8} mean {s.mean():6.2f} max {s.max():7.1f}  "
        f"{rep.stars(fit['coef']['gpr_z'], fit['se']['gpr_z'])}  N={fit['n']}",
        flush=True,
    )

print("GARCH(1,1) conditional SD", flush=True)
parts = []
for iso, g in panel.groupby("iso"):
    sig = garch11_sigma(g["port_inf"].to_numpy())
    parts.append(pd.DataFrame({"iso": iso, "date": g["date"].to_numpy(), "cf_alt": sig}))
garch = pd.concat(parts, ignore_index=True)
df = panel.drop(columns=["cf_vol"]).merge(garch, on=["iso", "date"], how="left")
s = df["cf_alt"].dropna()
fit = rep.within_ols(df, "cf_alt", x)
print(
    f"{'GARCH':8} mean {s.mean():6.2f} max {s.max():7.1f}  "
    f"{rep.stars(fit['coef']['gpr_z'], fit['se']['gpr_z'])}  N={fit['n']}",
    flush=True,
)
