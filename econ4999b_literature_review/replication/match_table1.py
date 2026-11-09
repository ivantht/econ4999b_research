"""Match published Table 1 by trying alternate definitions of each series."""
import numpy as np
import pandas as pd
from pathlib import Path

RAW = Path("replication/raw")
OUT = Path("replication/output")
ISO3 = {
    "BE": "BEL", "BR": "BRA", "CA": "CAN", "CL": "CHL", "CN": "CHN", "CO": "COL",
    "DE": "DEU", "DK": "DNK", "ES": "ESP", "FI": "FIN", "FR": "FRA", "HU": "HUN",
    "ID": "IDN", "IN": "IND", "IT": "ITA", "JP": "JPN", "KR": "KOR", "MX": "MEX",
    "MY": "MYS", "NL": "NLD", "PH": "PHL", "PL": "POL", "PT": "PRT", "SE": "SWE",
    "TH": "THA", "TR": "TUR", "UA": "UKR", "US": "USA", "ZA": "ZAF",
}
NAMES = {
    "Austria": None, "Belgium": "BE", "Brazil": "BR", "Canada": "CA", "Chile": "CL",
    "China": "CN", "Colombia": "CO", "Germany": "DE", "Denmark": "DK", "Spain": "ES",
    "Finland": "FI", "France": "FR", "Hungary": "HU", "Indonesia": "ID", "India": "IN",
    "Italy": "IT", "Japan": "JP", "Korea": "KR", "Mexico": "MX", "Malaysia": "MY",
    "Netherlands": "NL", "Philippines": "PH", "Poland": "PL", "Portugal": "PT",
    "Sweden": "SE", "Thailand": "TH", "Türkiye": "TR", "Turkey": "TR", "Ukraine": "UA",
    "United States": "US", "South Africa": "ZA",
}

def show(label, s, target):
    s = pd.to_numeric(s, errors="coerce").dropna()
    if s.empty:
        print(f"{label:48} EMPTY")
        return
    tm, ts, tn, tx = target
    print(
        f"{label:48} n={len(s):5d}  mean {s.mean():8.3f} (pub {tm:7.2f})  "
        f"sd {s.std():7.3f} ({ts:6.2f})  min {s.min():8.3f} ({tn:7.2f})  "
        f"max {s.max():8.3f} ({tx:7.2f})"
    )

panel = pd.read_csv(OUT / "panel.csv", parse_dates=["date"])
panel = panel[(panel["date"] >= "2000-01-01") & (panel["date"] <= "2023-12-01")]

print("=== CAPITAL FLOWS: 3-month SD of each OECD column, 29 countries ===")
flows = pd.read_excel(RAW / "oecd_capital_flows.xlsx", sheet_name="panel")
flows["iso"] = flows["country"].map(NAMES)
flows = flows.dropna(subset=["iso"])
flows["date"] = pd.to_datetime(flows["month"])
flows = flows[(flows["date"] >= "2000-01-01") & (flows["date"] <= "2023-12-01")]
cols = ["debt_inf", "debt_out", "eq_inf", "eq_out", "fdi_inf", "fdi_out", "other_inf", "other_out", "port_inf", "port_out"]
pieces = []
for iso, g in flows.groupby("iso"):
    g = g.sort_values("date").set_index("date")
    g = g.reindex(pd.date_range(g.index.min(), g.index.max(), freq="MS"))
    rec = {"iso": iso, "date": g.index}
    for c in cols:
        rec[c] = g[c].rolling(3, min_periods=3).std(ddof=1)
    rec["gross_in"] = (g["port_inf"].fillna(0) + g["fdi_inf"].fillna(0) + g["other_inf"].fillna(0)).rolling(3, min_periods=3).std(ddof=1)
    rec["net_port"] = (g["port_inf"] - g["port_out"]).rolling(3, min_periods=3).std(ddof=1)
    rec["abs_port"] = g["port_inf"].abs().rolling(3, min_periods=3).std(ddof=1)
    pieces.append(pd.DataFrame(rec))
vol = pd.concat(pieces, ignore_index=True)
target_cf = (7.22, 19.62, 0, 528.40)
for c in cols + ["gross_in", "net_port", "abs_port"]:
    show(c, vol[c], target_cf)
# where is the current maximum
i = vol["port_inf"].idxmax()
print("current port_inf vol max at", vol.loc[i, ["iso", "date", "port_inf"]].to_dict())

print("\n=== STOCKS ===")
share = panel["share_oecd"]
cpi = panel["PCPI_IX"]
show("log OECD share index", np.log(share), (4.32, 0.47, 2.37, 5.46))
show("log(share/cpi)", np.log(share / cpi), (4.32, 0.47, 2.37, 5.46))
show("log(100*share/cpi)", np.log(100 * share / cpi), (4.32, 0.47, 2.37, 5.46))
show("log IFS equity FPE", np.log(panel["FPE_IX"]), (4.32, 0.47, 2.37, 5.46))
# extreme of log share
sub = panel.dropna(subset=["share_oecd"]).copy()
sub["ln"] = np.log(sub["share_oecd"])
print("log share min", sub.loc[sub["ln"].idxmin(), ["iso", "date", "share_oecd", "ln"]].to_dict())
print("log share max", sub.loc[sub["ln"].idxmax(), ["iso", "date", "share_oecd", "ln"]].to_dict())

print("\n=== BONDS ===")
show("OECD 10y", panel["bond_oecd"], (4.74, 3.63, -0.65, 42.18))
show("IFS FIGB", panel["FIGB_PA"], (4.74, 3.63, -0.65, 42.18))
show("filled bond", panel["bond"], (4.74, 3.63, -0.65, 42.18))
for col in ["bond_oecd", "FIGB_PA"]:
    s = panel.dropna(subset=[col])
    top = s.groupby("iso")[col].max().sort_values(ascending=False).head(8)
    print(col, "max by country\n", top.to_string())
print("bond min", panel.loc[panel["bond"].idxmin(), ["iso", "date", "bond"]].to_dict())

print("\n=== REER ===")
show("log BIS broad", panel["ln_reer"], (4.64, 0.18, 3.61, 5.23))
print("REER min", panel.loc[panel["ln_reer"].idxmin(), ["iso", "date", "reer", "ln_reer"]].to_dict())
print("REER max", panel.loc[panel["ln_reer"].idxmax(), ["iso", "date", "reer", "ln_reer"]].to_dict())
print("countries with REER", sorted(panel.loc[panel["reer"].notna(), "iso"].unique()))

print("\n=== POLICY, IP, INFLATION, GPR ===")
show("policy rate", panel["rate"], (4.37, 4.87, -0.75, 57))
show("log IP", panel["ln_ip"], (4.58, 0.31, 2.29, 5.81))
print("IP countries", sorted(panel.loc[panel["ln_ip"].notna(), "iso"].unique()))
print("IP min", panel.loc[panel["ln_ip"].idxmin(), ["iso", "date", "ln_ip"]].to_dict())
print("IP max", panel.loc[panel["ln_ip"].idxmax(), ["iso", "date", "ln_ip"]].to_dict())
show("inflation", panel["infl"], (4.06, 6.18, -4.43, 85.51))
show("GPR raw", panel["gpr"], (0.22, 0.52, 0, 13.23))

print("\n=== OIL with US CPI deflators ===")
us = panel[panel["iso"].eq("US")][["date", "PCPI_IX", "oil"]].drop_duplicates("date")
us = us.dropna()
print("US CPI 2015-01", us.loc[us["date"].eq("2015-01-01"), "PCPI_IX"].tolist()[:1], "2010-01", us.loc[us["date"].eq("2010-01-01"), "PCPI_IX"].tolist()[:1])
for base in ["2000-01-01", "2010-01-01", "2015-01-01"]:
    b = us.loc[us["date"].eq(base), "PCPI_IX"]
    if b.empty:
        continue
    cpi0 = float(b.iloc[0])
    real = us["oil"] / (us["PCPI_IX"] / cpi0)
    show(f"log real WTI CPI base {base[:7]}", np.log(real), (3.73, 0.63, 2.42, 4.90))
show("log nominal WTI", np.log(us["oil"]), (3.73, 0.63, 2.42, 4.90))

print("\n=== VIX and GEPU, unique months vs panel ===")
vix = pd.read_csv(RAW / "vix_history.csv")
vix["date"] = pd.to_datetime(vix["DATE"])
vix = vix[(vix["date"] >= "2000-01-01") & (vix["date"] <= "2023-12-31")]
monthly_mean = vix.set_index("date")["CLOSE"].resample("MS").mean()
monthly_eom = vix.set_index("date")["CLOSE"].resample("MS").last()
show("VIX monthly mean", monthly_mean, (19.59, 7.54, 10.13, 62.67))
show("VIX month-end", monthly_eom, (19.59, 7.54, 10.13, 62.67))
epu = pd.read_excel(RAW / "epu_all_country.xlsx")
epu = epu.dropna(subset=["Year", "Month"])
epu["date"] = pd.to_datetime({"year": epu["Year"].astype(int), "month": epu["Month"].astype(int), "day": 1})
epu = epu[(epu["date"] >= "2000-01-01") & (epu["date"] <= "2023-12-01")]
show("GEPU current", epu["GEPU_current"], (140.26, 74.91, 49.23, 431.73))
show("GEPU ppp", epu["GEPU_ppp"], (140.26, 74.91, 49.23, 431.73))
print("GEPU current max month", epu.loc[epu["GEPU_current"].idxmax(), ["date", "GEPU_current"]].to_dict())

print("\n=== CBI 2022 file ===")
cbi = pd.read_excel(RAW / "cbi_2022.xlsx", sheet_name="CBI Indices")
cbi = cbi[cbi["iso_a2"].isin(ISO3)]
cbi = cbi[(cbi["year"] >= 2000) & (cbi["year"] <= 2017)]
# repeat annual to monthly so the weight matches a monthly panel
show("CBI 2022 annual 2000-2017", cbi["CBIE"], (0.66, 0.19, 0.14, 0.93))
monthly = cbi.loc[cbi.index.repeat(12)]
show("CBI 2022 monthly-weighted", monthly["CBIE"], (0.66, 0.19, 0.14, 0.93))
print("CBI 2022 min", cbi.loc[cbi["CBIE"].idxmin(), ["iso_a2", "year", "CBIE"]].to_dict())
print("CBI 2022 max", cbi.loc[cbi["CBIE"].idxmax(), ["iso_a2", "year", "CBIE"]].to_dict())

print("\n=== FD and debt on 2000-2023 ===")
show("FD", panel["fd"], (0.60, 0.19, 0.11, 0.93))
show("debt", panel["debt"], (68.77, 36.40, 11.82, 216.33))
print("debt min", panel.loc[panel["debt"].idxmin(), ["iso", "year", "debt"]].to_dict())
print("debt max", panel.loc[panel["debt"].idxmax(), ["iso", "year", "debt"]].to_dict())
