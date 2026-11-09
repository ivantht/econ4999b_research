"""Download public source files used by Beirne and Renzhi (2025)."""
import re
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent / "raw"
ROOT.mkdir(parents=True, exist_ok=True)
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    )
}

FILES = {
    "gpr_export.xls": "https://www.matteoiacoviello.com/gpr_files/data_gpr_export.xls",
    "epu_all_country.xlsx": "https://www.policyuncertainty.com/media/All_Country_Data.xlsx",
    "fred_gepu.csv": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=GEPUCURRENT",
    "fred_vix.csv": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=VIXCLS",
    "fred_wti.csv": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=MCOILWTICO",
    "oecd_capital_flows.xlsx": "https://www.oecd.org/daf/inv/investment-policy/OECD-monthly-capital-flow-dataset.xlsx",
    "oecd_capital_flows_alt.xlsx": "https://www.oecd.org/investment/OECD-monthly-capital-flow-dataset.xlsx",
}

def grab(name, url):
    dest = ROOT / name
    print(f"GET {url}")
    try:
        r = requests.get(url, headers=UA, timeout=120, allow_redirects=True)
    except Exception as e:
        print("  FAIL", type(e).__name__, e)
        return
    print("  status", r.status_code, "bytes", len(r.content), "ctype", r.headers.get("content-type"))
    if r.status_code == 200 and len(r.content) > 500:
        dest.write_bytes(r.content)
        print("  saved", dest)
    else:
        snippet = r.text[:300].replace("\n", " ")
        print("  body", snippet)

def cbi_links():
    r = requests.get("https://cbidata.org/vintages.html", headers=UA, timeout=60)
    print("\nCBI status", r.status_code)
    (ROOT / "cbi_vintages.html").write_text(r.text, encoding="utf-8")
    for m in re.findall(r'(?:href|src)=["\']([^"\']+)["\']', r.text):
        print(" ", m)

if __name__ == "__main__":
    for name, url in FILES.items():
        grab(name, url)
    cbi_links()
