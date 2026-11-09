"""Close the remaining Table 1 gaps: VIX sample, older WEO, GPR vintage."""
import json
import numpy as np
import pandas as pd
import requests

UA = {"User-Agent": "Mozilla/5.0"}
ISO3 = {"BE":"BEL","BR":"BRA","CA":"CAN","CL":"CHL","CN":"CHN","CO":"COL","DE":"DEU","DK":"DNK","ES":"ESP","FI":"FIN","FR":"FRA","HU":"HUN","ID":"IDN","IN":"IND","IT":"ITA","JP":"JPN","KR":"KOR","MX":"MEX","MY":"MYS","NL":"NLD","PH":"PHL","PL":"POL","PT":"PRT","SE":"SWE","TH":"THA","TR":"TUR","UA":"UKR","US":"USA","ZA":"ZAF"}
inv = {v: k for k, v in ISO3.items()}

def show(label, s, target):
    s = pd.to_numeric(pd.Series(s), errors="coerce").dropna()
    tm, ts, tn, tx = target
    print(f"{label:36} n={len(s):5d} mean {s.mean():8.3f}/{tm:<6} sd {s.std():7.3f}/{ts:<5} min {s.min():8.3f}/{tn:<6} max {s.max():8.3f}/{tx}")

panel = pd.read_csv("replication/output/panel.csv", parse_dates=["date"])
x = ["gpr_z","rate_l1","ln_ip_l1","infl_l1","ln_oil_l1","ln_vix_l1","ln_gepu_l1","fd_l1","cbi_l1","debt_l1"]
reg = panel.dropna(subset=["cf_vol", *x])
show("VIX on Table 2 sample", reg["vix"], (19.59, 7.54, 10.13, 62.67))
show("GEPU on Table 2 sample", reg["gepu"], (140.26, 74.91, 49.23, 431.73))

# debt shape in the current file
d = panel.dropna(subset=["debt"])[["iso","year","debt"]].drop_duplicates()
print("debt below 12:\n", d[d["debt"] < 12].sort_values("debt").head(8).to_string(index=False))
print("debt above 200:\n", d[d["debt"] > 200].groupby("iso")["debt"].max())

print("--- WEO vintages ---")
for vintage in ["2022-10", "2022-04", "2021-10", "2020-10"]:
    dims = json.dumps({"weo-subject": ["GGXWDG_NGDP"], "weo-country": list(ISO3.values())})
    url = f"https://api.db.nomics.world/v22/series/IMF/WEO:{vintage}?dimensions={requests.utils.quote(dims)}&observations=1&limit=40"
    rr = requests.get(url, headers=UA, timeout=60)
    print(vintage, rr.status_code)
    if rr.status_code != 200:
        continue
    rows = []
    for doc in rr.json().get("series", {}).get("docs", []):
        iso = inv.get(doc["dimensions"].get("weo-country"))
        for period, value in zip(doc.get("period", []), doc.get("value", [])):
            if value in (None, "NA") or iso is None:
                continue
            year = int(str(period)[:4])
            if 2000 <= year <= 2023:
                rows.append((iso, year, float(value)))
    df = pd.DataFrame(rows, columns=["iso","year","debt"])
    show(f"debt {vintage}", df["debt"], (68.77, 36.40, 11.82, 216.33))
    if len(df):
        print("  min", df.loc[df["debt"].idxmin()].to_dict(), "max", df.loc[df["debt"].idxmax()].to_dict())

print("--- GPR archive ---")
for stamp in ["202511", "202510", "202506", "202501"]:
    url = f"https://www.matteoiacoviello.com/gpr_archive_files/data_gpr_export_{stamp}.xls"
    try:
        rr = requests.get(url, headers=UA, timeout=40)
    except Exception as exc:
        print(stamp, type(exc).__name__)
        continue
    print(stamp, rr.status_code, len(rr.content))
    if rr.status_code == 200 and len(rr.content) > 100000:
        path = f"replication/raw/gpr_{stamp}.xls"
        open(path, "wb").write(rr.content)
        gpr = pd.read_excel(path)
        gpr["month"] = pd.to_datetime(gpr["month"])
        cols = [f"GPRC_{v}" for v in ISO3.values() if f"GPRC_{v}" in gpr.columns]
        sub = gpr.loc[gpr["month"].between("2000-01-01", "2023-12-01"), cols]
        show(f"GPR {stamp}", sub.stack(), (0.22, 0.52, 0, 13.23))
        break
