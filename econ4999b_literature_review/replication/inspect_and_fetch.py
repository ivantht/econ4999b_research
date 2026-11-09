"""Inspect the OECD workbook and fetch the remaining public series."""
import json
from pathlib import Path
import requests
import pandas as pd

ROOT = Path(__file__).resolve().parent / "raw"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0.0.0 Safari/537.36"}

def get(url, timeout=90):
    print("GET", url, flush=True)
    r = requests.get(url, headers=UA, timeout=timeout)
    print(" ", r.status_code, len(r.content), r.headers.get("content-type", "")[:70], flush=True)
    r.raise_for_status()
    return r

# OECD capital flows
path = ROOT / "oecd_capital_flows.xlsx"
xl = pd.ExcelFile(path)
print("OECD sheets", xl.sheet_names, flush=True)
for sheet in xl.sheet_names[:8]:
    df = pd.read_excel(path, sheet_name=sheet, nrows=5)
    print("\nSHEET", sheet, "ncols", len(df.columns), flush=True)
    print(list(df.columns)[:25], flush=True)
    print(df.head(2).iloc[:, :8].to_string(), flush=True)

# GEPU scale in the sample window
epu = pd.read_excel(ROOT / "epu_all_country.xlsx")
epu = epu.dropna(subset=["Year", "Month"])
epu["date"] = pd.to_datetime(dict(year=epu["Year"].astype(int), month=epu["Month"].astype(int), day=1))
g = epu.loc[epu["date"].between("2000-01-01", "2023-12-01"), "GEPU_current"]
print("\nGEPU 2000-2023", g.describe().to_string(), flush=True)

# VIX and WTI
r = get("https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv")
(ROOT / "vix_history.csv").write_bytes(r.content)
r = get("https://www.eia.gov/dnav/pet/hist_xls/RWTCm.xls")
(ROOT / "wti_monthly.xls").write_bytes(r.content)

# BIS full panels
countries = "US+CN+JP+DE+FR+GB+KR+BR+MX+IN+ZA+CA+AU+TR+ID+TH+MY+PH+CL+CO+PL+HU+BE+NL+ES+IT+SE+DK+FI+PT+UA"
for name, url in {
    "bis_reer.csv": f"https://stats.bis.org/api/v1/data/WS_EER/M.R.B.{countries}?startPeriod=1999-01&endPeriod=2023-12&format=csv",
    "bis_policy.csv": f"https://stats.bis.org/api/v1/data/WS_CBPOL/M.{countries}?startPeriod=1999-01&endPeriod=2023-12&format=csv",
}.items():
    try:
        r = get(url, timeout=120)
        (ROOT / name).write_bytes(r.content)
        text = r.content[:400].decode("utf-8", "replace")
        print(text[:400], flush=True)
    except Exception as e:
        print("BIS FAIL", name, type(e).__name__, e, flush=True)

# db.nomics FDI catalog sample
r = get("https://api.db.nomics.world/v22/series/IMF/FDI?limit=3&observations=0&q=Financial%20Development%20Index")
(ROOT / "fdi_search.json").write_bytes(r.content)
data = r.json()
print("FDI keys", data.keys(), flush=True)
series = data.get("series", {}).get("docs", data.get("results", data))
print(json.dumps(series if isinstance(series, list) else list(data)[:20], default=str)[:1500], flush=True)
