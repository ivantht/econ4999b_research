"""Second pass: vintages and baskets that could reproduce Table 1."""
import json
import numpy as np
import pandas as pd
import requests
from pathlib import Path

UA = {"User-Agent": "Mozilla/5.0"}
ISO2 = ["BE","BR","CA","CL","CN","CO","DE","DK","ES","FI","FR","HU","ID","IN","IT","JP","KR","MX","MY","NL","PH","PL","PT","SE","TH","TR","UA","US","ZA"]
ISO3 = {"BE":"BEL","BR":"BRA","CA":"CAN","CL":"CHL","CN":"CHN","CO":"COL","DE":"DEU","DK":"DNK","ES":"ESP","FI":"FIN","FR":"FRA","HU":"HUN","ID":"IDN","IN":"IND","IT":"ITA","JP":"JPN","KR":"KOR","MX":"MEX","MY":"MYS","NL":"NLD","PH":"PHL","PL":"POL","PT":"PRT","SE":"SWE","TH":"THA","TR":"TUR","UA":"UKR","US":"USA","ZA":"ZAF"}

def show(label, s, target):
    s = pd.to_numeric(pd.Series(s), errors="coerce").dropna()
    tm, ts, tn, tx = target
    if s.empty:
        print(label, "EMPTY")
        return
    print(f"{label:42} n={len(s):5d} mean {s.mean():8.3f}/{tm:<6} sd {s.std():7.3f}/{ts:<5} min {s.min():8.3f}/{tn:<6} max {s.max():8.3f}/{tx}")

panel = pd.read_csv("replication/output/panel.csv", parse_dates=["date"])
panel = panel[panel["date"].between("2000-01-01", "2023-12-01")]

# VIX weighted by how many countries are observed each month
vix = panel.drop_duplicates("date").set_index("date")["vix"]
counts = panel.dropna(subset=["infl"]).groupby("date").size()
# expand vix to the inflation sample
vv = panel.loc[panel["infl"].notna(), "vix"]
show("VIX on inflation sample", vv, (19.59, 7.54, 10.13, 62.67))
vv = panel.dropna(subset=["cf_vol"])["vix"]
show("VIX on capital-flow sample", vv, (19.59, 7.54, 10.13, 62.67))

# oil extremes
oil = panel.drop_duplicates("date")[["date", "oil"]].dropna()
print("oil min", oil.loc[oil["oil"].idxmin()].to_dict())
print("oil max", oil.loc[oil["oil"].idxmax()].to_dict())

# Turkey bond coverage
tr = panel[panel["iso"].eq("TR")]
print("TR bond nonmissing", tr["bond_oecd"].notna().sum(), "max", tr["bond_oecd"].max(), "first", tr.loc[tr["bond_oecd"].notna(), "date"].min())

# real stock min country
sub = panel.dropna(subset=["share_oecd", "PCPI_IX"]).copy()
sub["lnreal"] = np.log(100 * sub["share_oecd"] / sub["PCPI_IX"])
print("real stock min", sub.loc[sub["lnreal"].idxmin(), ["iso", "date", "lnreal"]].to_dict())
print("real stock max", sub.loc[sub["lnreal"].idxmax(), ["iso", "date", "lnreal"]].to_dict())

# policy rate without the euro-area block
euro = ["BE", "DE", "ES", "FI", "FR", "IT", "NL", "PT"]
show("policy rate excluding euro members", panel.loc[~panel["iso"].isin(euro), "rate"], (4.37, 4.87, -0.75, 57))

print("\n--- BIS narrow REER ---")
countries = "+".join(ISO2)
url = f"https://stats.bis.org/api/v1/data/WS_EER/M.R.N.{countries}?startPeriod=2000-01&endPeriod=2023-12&format=csv"
r = requests.get(url, headers=UA, timeout=90)
print("narrow", r.status_code, len(r.content))
if r.status_code == 200:
    reer = pd.read_csv(pd.io.common.BytesIO(r.content))
    reer = reer[reer["REF_AREA"].isin(ISO2)]
    reer["ln"] = np.log(pd.to_numeric(reer["OBS_VALUE"], errors="coerce"))
    show("log BIS narrow", reer["ln"], (4.64, 0.18, 3.61, 5.23))
    i = reer["ln"].idxmin()
    print("narrow min", reer.loc[i, ["REF_AREA", "TIME_PERIOD", "OBS_VALUE", "ln"]].to_dict())

print("\n--- CBI Feb 2024 ---")
p = Path("replication/raw/cbi_2024.xlsx")
if not p.exists():
    rr = requests.get("https://cbidata.org/dataset/CBIData_Romelli_Feb2024.xlsx", headers=UA, timeout=90)
    print("cbi2024", rr.status_code, len(rr.content))
    if rr.status_code == 200:
        p.write_bytes(rr.content)
if p.exists():
    xl = pd.ExcelFile(p)
    print("sheets", xl.sheet_names)
    df = pd.read_excel(p, sheet_name=xl.sheet_names[-1])
    print(list(df.columns)[:8])
    iso_col = "iso_a2" if "iso_a2" in df.columns else "iso_a3"
    cbi_col = "CBIE" if "CBIE" in df.columns else "cbie_index"
    if iso_col == "iso_a3":
        df["iso"] = df[iso_col].map({v: k for k, v in ISO3.items()})
    else:
        df["iso"] = df[iso_col]
    df = df[df["iso"].isin(ISO2) & df["year"].between(2000, 2023)]
    show("CBI 2024 update", df[cbi_col], (0.66, 0.19, 0.14, 0.93))

print("\n--- older WEO debt ---")
for vintage in ["2024-10", "2024-04", "2023-10", "2023-04"]:
    dims = json.dumps({"weo-subject": ["GGXWDG_NGDP"], "weo-country": list(ISO3.values())})
    url = f"https://api.db.nomics.world/v22/series/IMF/WEO:{vintage}?dimensions={requests.utils.quote(dims)}&observations=1&limit=40"
    try:
        rr = requests.get(url, headers=UA, timeout=60)
    except Exception as exc:
        print(vintage, type(exc).__name__)
        continue
    print(vintage, rr.status_code, len(rr.content))
    if rr.status_code != 200:
        continue
    rows = []
    for doc in rr.json().get("series", {}).get("docs", []):
        iso = {v: k for k, v in ISO3.items()}.get(doc["dimensions"].get("weo-country"))
        for period, value in zip(doc.get("period", []), doc.get("value", [])):
            if value in (None, "NA"):
                continue
            year = int(str(period)[:4])
            if 2000 <= year <= 2023 and iso:
                rows.append(float(value))
    show(f"debt {vintage}", rows, (68.77, 36.40, 11.82, 216.33))
