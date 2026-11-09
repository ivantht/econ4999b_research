"""Download the November 2025 GPR file and the last archived OECD workbook."""
from pathlib import Path
import requests

ROOT = Path("replication/raw")
UA = {"User-Agent": "Mozilla/5.0 (research replication)"}

def grab(url, dest, timeout=120):
    print("GET", url[:180], flush=True)
    r = requests.get(url, headers=UA, timeout=timeout)
    print(" ", r.status_code, len(r.content), flush=True)
    if r.status_code == 200 and len(r.content) > 10000:
        dest.write_bytes(r.content)
        print("  saved", dest, flush=True)
        return True
    print("  body", r.text[:150].replace("\n", " "), flush=True)
    return False

grab(
    "https://www.matteoiacoviello.com/gpr_archive_files/data_gpr_export_202511.xls",
    ROOT / "gpr_export_202511.xls",
)
grab(
    "https://web.archive.org/web/20220331223259id_/https://www.oecd.org/daf/inv/investment-policy/oecd-monthly-capital-flow-dataset.xlsx",
    ROOT / "oecd_capital_flows_202203.xlsx",
)
# also try a later crawl in case CDX was incomplete
for stamp in ["20250901000000", "20250601000000", "20241101000000", "20230901000000"]:
    url = (
        "https://web.archive.org/web/" + stamp +
        "/https://www.oecd.org/daf/inv/investment-policy/oecd-monthly-capital-flow-dataset.xlsx"
    )
    print("probe", stamp, flush=True)
    try:
        r = requests.get(url, headers=UA, timeout=30, allow_redirects=True)
        print(" ", r.status_code, len(r.content), r.url[:120], flush=True)
    except Exception as e:
        print(" ", type(e).__name__, e, flush=True)
