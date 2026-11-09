"""Download CBI, IMF FD/WEO, and try OECD/IMF monthly macro series."""
import json
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent / "raw"
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/csv,application/json,application/octet-stream,*/*",
}

def get(url, timeout=90):
    print("GET", url[:200], flush=True)
    try:
        r = requests.get(url, headers=UA, timeout=timeout)
    except Exception as e:
        print(" ERR", type(e).__name__, e, flush=True)
        return None
    print(" ", r.status_code, len(r.content), r.headers.get("content-type", "")[:60], flush=True)
    if r.status_code != 200:
        print(" ", r.text[:250].replace("\n", " "), flush=True)
    return r

r = get("https://cbidata.org/dataset/CBIData_Romelli_2022.xlsx")
if r and r.status_code == 200 and len(r.content) > 10000:
    (ROOT / "cbi_2022.xlsx").write_bytes(r.content)

r = get("https://api.db.nomics.world/v22/datasets/IMF")
if r and r.status_code == 200:
    docs = r.json().get("datasets", {}).get("docs", [])
    print("IMF datasets", len(docs), flush=True)
    for d in docs:
        code = d.get("code", "")
        name = d.get("name", "")
        if any(k in (code + name).upper() for k in ["IFS", "WEO", "FDI", "CPI", "FINANCIAL"]):
            print(" ", code, "|", name, flush=True)

# country FD index, one country to learn the code, then a filtered pull
for url in [
    "https://api.db.nomics.world/v22/series/IMF/FDI/A.US.FD_FD_IX?observations=1",
    "https://api.db.nomics.world/v22/series/IMF/FDI/A.USA.FD_FD_IX?observations=1",
    "https://api.db.nomics.world/v22/series/IMF/FDI?dimensions=%7B%22INDICATOR%22%3A%5B%22FD_FD_IX%22%5D%7D&observations=1&limit=5",
]:
    r = get(url)
    if r and r.status_code == 200:
        data = r.json()
        docs = data.get("series", {}).get("docs", [])
        print(" ndocs", len(docs), flush=True)
        if docs:
            d0 = docs[0]
            print(" code", d0.get("series_code"), "dims", d0.get("dimensions"), flush=True)
            obs = d0.get("observations") or d0.get("series_observations")
            print(" obs keys", list(d0.keys()), flush=True)
            if obs:
                print(str(obs)[:300], flush=True)

# WEO debt
for url in [
    "https://api.db.nomics.world/v22/datasets/IMF/WEO:2025-04",
    "https://api.db.nomics.world/v22/datasets/IMF/WEO:2024-10",
    "https://api.db.nomics.world/v22/datasets/IMF/WEO:2024-04",
]:
    r = get(url, timeout=40)
    if r and r.status_code == 200:
        print(" found", url, flush=True)
        break

oecd_tries = [
    "https://sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_STES@DF_FINMARK,1.0/M.USA.SPASTT01?startPeriod=2020-01&endPeriod=2020-02&format=csv",
    "https://stats.oecd.org/SDMX-JSON/data/MEI/SPASTT01.USA.IXOB.M/all?startTime=2020-01&endTime=2020-03",
    "https://sdmx.oecd.org/public/rest/availableconstraint/OECD.SDD.STES,DSD_KEI@DF_KEI,1.0?format=json",
]
for url in oecd_tries:
    get(url, timeout=40)
