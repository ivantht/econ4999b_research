"""Probe public endpoints and save small successful downloads."""
import io
from pathlib import Path
import requests
import pandas as pd

ROOT = Path(__file__).resolve().parent / "raw"
ROOT.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0.0.0 Safari/537.36"}

def get(url, timeout=45):
    print("GET", url, flush=True)
    try:
        r = requests.get(url, headers=UA, timeout=timeout, allow_redirects=True)
    except Exception as e:
        print("  ERR", type(e).__name__, e, flush=True)
        return None
    print("  status", r.status_code, "bytes", len(r.content), "ctype", r.headers.get("content-type", "")[:80], flush=True)
    if r.status_code != 200:
        print("  body", r.text[:180].replace("\n", " "), flush=True)
    return r

# GPR scale check
gpr = pd.read_excel(ROOT / "gpr_export.xls")
gpr["month"] = pd.to_datetime(gpr["month"])
sub = gpr.loc[gpr["month"].between("2000-01-01", "2023-12-01"), [c for c in gpr.columns if c.startswith("GPRC_")]]
print("GPRC 2000-2023 describe", flush=True)
vals = sub.stack()
print(vals.describe().to_string(), flush=True)
print("max country", vals.idxmax(), vals.max(), flush=True)

# globals
for name, url in {
    "fred_gepu.csv": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=GEPUCURRENT",
    "fred_vix.csv": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=VIXCLS",
    "fred_wti.csv": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=MCOILWTICO",
}.items():
    r = get(url)
    if r is not None and r.status_code == 200 and len(r.content) > 200:
        (ROOT / name).write_bytes(r.content)

# sample FRED country series
sample = [
    "SPASTT01USM661N", "SPASTT01DEM661N", "SPASTT01CNM661N", "SPASTT01UAM661N",
    "IRLTLT01USM156N", "IRLTLT01TRM156N", "IRLTLT01UAM156N",
    "CPALTT01USM659N", "PRINTO01USM661S", "PRMNTO01USM661N",
    "RBUSBIS", "RBCNBIS", "RBTRBIS", "RBTUBIS", "RBDEBIS",
    "IRSTCI01USM156N", "IRSTCB01USM156N", "FEDFUNDS",
]
r = get("https://fred.stlouisfed.org/graph/fredgraph.csv?id=" + ",".join(sample))
if r is not None and r.status_code == 200:
    (ROOT / "fred_sample.csv").write_bytes(r.content)
    df = pd.read_csv(io.BytesIO(r.content))
    print(df.head(2).to_string(), flush=True)
    print("ncols", df.shape, "nonnull", df.notna().sum().to_dict(), flush=True)

oecd_urls = [
    "https://www.oecd.org/daf/inv/investment-policy/oecd-monthly-capital-flow-dataset.xlsx",
    "https://www.oecd.org/daf/inv/investment-policy/OECD-monthly-capital-flow-dataset.xlsx",
    "https://www.oecd.org/investment/investment-policy/oecd-monthly-capital-flow-dataset.xlsx",
]
for url in oecd_urls:
    r = get(url, timeout=40)
    if r is not None and r.status_code == 200 and len(r.content) > 5000:
        (ROOT / "oecd_capital_flows.xlsx").write_bytes(r.content)
        break

for url in [
    "https://stats.bis.org/api/v1/data/WS_CBPOL/M.US?startPeriod=2000-01&format=csv",
    "https://stats.bis.org/api/v2/data/dataflow/BIS/WS_EER/1.0/M.R.B.US?startPeriod=2000-01&format=csv",
    "https://dataservices.imf.org/REST/SDMX_JSON.svc/CompactData/IFS/M.US.PCPI_IX?startPeriod=2000&endPeriod=2002",
    "https://api.db.nomics.world/v22/series/IMF/FDI?limit=2&observations=0",
]:
    get(url, timeout=40)
