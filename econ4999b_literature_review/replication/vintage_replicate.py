"""Compare a November 2025 GPR vintage, and the March 2022 OECD file, with the published Table 2."""
from pathlib import Path
import importlib.util
import numpy as np
import pandas as pd

spec = importlib.util.spec_from_file_location("rep", Path("replication/build_and_replicate.py"))
rep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rep)

ISO3_TO_ISO2 = {v: k for k, v in rep.ISO3.items()}
NAME_TO_ISO2 = rep.ISO2


def volatility(flows: pd.DataFrame) -> pd.DataFrame:
    flows = flows.dropna(subset=["iso"]).sort_values(["iso", "date"])
    pieces = []
    for iso, g in flows.groupby("iso"):
        g = g.set_index("date").sort_index()
        full = g.reindex(pd.date_range(g.index.min(), g.index.max(), freq="MS"))
        full["iso"] = iso
        full["cf_vol"] = full["port_inf"].rolling(3, min_periods=3).std(ddof=1)
        pieces.append(full.reset_index().rename(columns={"index": "date"}))
    return pd.concat(pieces, ignore_index=True)


def load_flows(path: Path) -> pd.DataFrame:
    xl = pd.ExcelFile(path)
    sheet = "panel" if "panel" in xl.sheet_names else xl.sheet_names[-1]
    df = pd.read_excel(path, sheet_name=sheet)
    print(path.name, "sheet", sheet, "cols", list(df.columns)[:12], flush=True)
    if "country" not in df.columns:
        print(df.head(3).to_string(), flush=True)
        raise RuntimeError("unexpected layout")
    df["iso"] = df["country"].map(NAME_TO_ISO2)
    df["date"] = pd.to_datetime(df["month"])
    df["port_inf"] = pd.to_numeric(df["port_inf"], errors="coerce")
    return df.loc[df["iso"].notna(), ["iso", "date", "port_inf"]]


def describe_vol(label, vol):
    s = vol.loc[vol["date"].between("2000-01-01", "2023-12-01"), "cf_vol"].dropna()
    print(
        f"{label:22} N={s.shape[0]:5d} mean={s.mean():7.3f} sd={s.std():7.3f} max={s.max():8.3f}",
        flush=True,
    )


print("Loading flow vintages", flush=True)
new_flows = load_flows(rep.RAW / "oecd_capital_flows.xlsx")
old_flows = load_flows(rep.RAW / "oecd_capital_flows_202203.xlsx")
print("old file last month", old_flows["date"].max(), "countries", old_flows["iso"].nunique(), flush=True)
new_vol = volatility(new_flows)
old_vol = volatility(old_flows)
describe_vol("current file, 2000-23", new_vol)
describe_vol("Mar 2022 file, to its end", old_vol)
# Common history: through the last month present in the 2022 file, and only 2000 onward.
end_old = old_flows["date"].max()
common_end = min(end_old, pd.Timestamp("2023-12-01"))
describe_vol("current file, through old end", new_vol[new_vol["date"] <= common_end])
describe_vol("Mar 2022 file, 2000-old end", old_vol[old_vol["date"].between("2000-01-01", common_end)])

# How different are the overlapping portfolio-inflow observations?
m = new_flows.merge(old_flows, on=["iso", "date"], suffixes=("_new", "_old"))
m = m[m["date"].between("2000-01-01", common_end)]
both = m.dropna()
print(
    f"overlapping port_inf months {len(both)} corr {both['port_inf_new'].corr(both['port_inf_old']):.4f} "
    f"mean abs diff { (both['port_inf_new']-both['port_inf_old']).abs().mean():.4f}",
    flush=True,
)

print("\nGPR November 2025 versus the November 2026 file", flush=True)
gpr = pd.read_excel(rep.RAW / "gpr_export_202511.xls")
gpr["date"] = pd.to_datetime(gpr["month"])
cols = [f"GPRC_{iso3}" for iso3 in rep.ISO3.values() if f"GPRC_{iso3}" in gpr.columns]
long = gpr.melt(id_vars=["date"], value_vars=cols, var_name="col", value_name="gpr_202511")
long["iso"] = long["col"].str.replace("GPRC_", "", regex=False).map(ISO3_TO_ISO2)
long = long[(long["date"].between("2000-01-01", "2023-12-01")) & long["iso"].notna()]
cur = pd.read_excel(rep.RAW / "gpr_export.xls")
cur["date"] = pd.to_datetime(cur["month"])
cur_long = cur.melt(id_vars=["date"], value_vars=cols, var_name="col", value_name="gpr_now")
cur_long["iso"] = cur_long["col"].str.replace("GPRC_", "", regex=False).map(ISO3_TO_ISO2)
cur_long = cur_long[(cur_long["date"].between("2000-01-01", "2023-12-01")) & cur_long["iso"].notna()]
g = long.merge(cur_long, on=["iso", "date"])
bothg = g.dropna()
print(
    f"GPR months {len(bothg)} corr {bothg['gpr_202511'].corr(bothg['gpr_now']):.6f} "
    f"max abs diff {(bothg['gpr_202511']-bothg['gpr_now']).abs().max():.6f} "
    f"mean 202511 {bothg['gpr_202511'].mean():.4f} mean now {bothg['gpr_now'].mean():.4f}",
    flush=True,
)

panel = pd.read_csv(rep.OUT / "panel.csv", parse_dates=["date"])
panel = panel.drop(columns=[c for c in panel.columns if c.startswith("gpr")], errors="ignore")
panel = panel.merge(long[["iso", "date", "gpr_202511"]], on=["iso", "date"], how="left")
panel["gpr"] = panel["gpr_202511"]
panel["gpr_z"] = panel.groupby("iso")["gpr"].transform(lambda s: (s - s.mean()) / s.std(ddof=1))

x = ["gpr_z", "rate_l1", "ln_ip_l1", "infl_l1", "ln_oil_l1", "ln_vix_l1", "ln_gepu_l1", "fd_l1", "cbi_l1", "debt_l1"]
published = {
    "cf_vol": (0.867, 0.382),
    "ln_stock_real": (-0.039, 0.006),
    "bond": (0.134, 0.030),
    "ln_reer": (0.001, 0.002),
}
print("\nTABLE 2 with GPR as of November 2025", flush=True)
rows = []
for col, pub in published.items():
    fit = rep.within_ols(panel, col, x)
    print(
        f"{col:16} {rep.stars(fit['coef']['gpr_z'], fit['se']['gpr_z'])}  paper {pub[0]:.3f} ({pub[1]:.3f})  N={fit['n']}",
        flush=True,
    )
    rows.append({"outcome": col, "gpr_coef": fit["coef"]["gpr_z"], "gpr_se": fit["se"]["gpr_z"], "N": fit["n"], "published": pub[0]})

# Capital-flow coefficient on the common pre-March-2022 sample, old versus current flows.
print("\nCapital-flow coefficient on the common sample through", common_end.date(), flush=True)
base = panel.drop(columns=["cf_vol"], errors="ignore")
for label, vol in [("current flows", new_vol), ("March 2022 flows", old_vol)]:
    use = base.merge(vol[["iso", "date", "cf_vol"]], on=["iso", "date"], how="left")
    use = use[use["date"] <= common_end]
    fit = rep.within_ols(use, "cf_vol", x)
    bare = rep.within_ols(use, "cf_vol", ["gpr_z"])
    print(
        f"{label:18} controlled {rep.stars(fit['coef']['gpr_z'], fit['se']['gpr_z'])} N={fit['n']}  "
        f"bivariate {rep.stars(bare['coef']['gpr_z'], bare['se']['gpr_z'])}",
        flush=True,
    )

pd.DataFrame(rows).to_csv(rep.OUT / "table2_gpr_202511.csv", index=False)
print("saved", rep.OUT / "table2_gpr_202511.csv", flush=True)
