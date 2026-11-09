"""Find monthly macro series and check capital-flow units."""
import json
from pathlib import Path
import requests
import pandas as pd

ROOT = Path(__file__).resolve().parent / "raw"
UA = {"User-Agent": "Mozilla/5.0"}

panel = pd.read_excel(ROOT / "oecd_capital_flows.xlsx", sheet_name="panel")
print("countries", sorted(panel["country"].dropna().unique()), flush=True)
print(panel["port_inf"].describe().to_string(), flush=True)
us = panel.loc[panel["country"].eq("United States"), ["month", "port_inf"]].dropna()
print("US port_inf head", us.head(3).to_string(), flush=True)
print("US port_inf describe", us["port_inf"].describe().to_string(), flush=True)

readme = pd.read_excel(ROOT / "oecd_capital_flows.xlsx", sheet_name="Readme", header=None)
print("\nREADME", flush=True)
print(readme.dropna(how="all").head(40).to_string(), flush=True)

def get(url, timeout=60):
    print("\nGET", url[:180], flush=True)
    try:
        r = requests.get(url, headers=UA, timeout=timeout)
    except Exception as e:
        print(" ERR", type(e).__name__, e, flush=True)
        return None
    print(" ", r.status_code, len(r.content), flush=True)
    return r

queries = [
    "https://api.db.nomics.world/v22/search?q=share%20prices%20OECD&limit=5",
    "https://api.db.nomics.world/v22/search?q=long-term%20interest%20rates%20provider:OECD&limit=5",
    "https://api.db.nomics.world/v22/search?q=industrial%20production%20OECD.SDD&limit=5",
    "https://api.db.nomics.world/v22/search?q=GGXWDG_NGDP&limit=3",
    "https://api.db.nomics.world/v22/search?q=central%20bank%20independence%20Romelli&limit=3",
]
for url in queries:
    r = get(url)
    if r is None or r.status_code != 200:
        continue
    data = r.json()
    hits = data.get("results", {}).get("docs", data.get("series", {}).get("docs", []))
    if not hits and "results" in data:
        hits = data["results"] if isinstance(data["results"], list) else []
    print(" nhits", data.get("results", {}).get("numFound", len(hits) if isinstance(hits, list) else None), flush=True)
    for h in (hits or [])[:3]:
        if isinstance(h, dict):
            print(" -", h.get("provider_code"), h.get("dataset_code") or h.get("code"), h.get("series_code"), h.get("series_name") or h.get("name"), flush=True)

# OECD SDMX probes
oecd_urls = [
    "https://sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_KEI@DF_KEI,1.0/USA.M.SPASTT01.IX?startPeriod=2020-01&endPeriod=2020-03&format=csv",
    "https://sdmx.oecd.org/public/rest/dataflow/OECD.SDD.STES?format=json",
]
for url in oecd_urls:
    r = get(url, timeout=40)
    if r is not None and r.status_code == 200:
        print(r.text[:500], flush=True)

# CBI page source snippets
r = get("https://cbidata.org/vintages.html")
if r is not None:
    text = r.text
    (ROOT / "cbi_vintages.html").write_text(text, encoding="utf-8")
    for token in ["xlsx", "xls", "dta", "download", ".zip"]:
        idx = text.lower().find(token)
        print("token", token, "idx", idx, flush=True)
    if "xlsx" in text.lower() or ".xls" in text.lower():
        import re
        print(re.findall(r'.{40}xls.{40}', text, flags=re.I)[:10], flush=True)
