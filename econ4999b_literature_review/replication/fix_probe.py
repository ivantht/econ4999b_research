import json
import requests

UA = {"User-Agent": "Mozilla/5.0"}
url = "https://api.db.nomics.world/v22/series/IMF/WEO:2025-04/USA.GGXWDG_NGDP.pcent_gdp?observations=1"
r = requests.get(url, headers=UA, timeout=60)
doc = r.json()["series"]["docs"][0]
print("keys", sorted(doc.keys()))
print("dims", doc.get("dimensions"))
print("code", doc.get("series_code"))
print("period", doc.get("period")[:3], "value", doc.get("value")[:3])

# more bond / share indicators present for a missing country, e.g. Brazil and Korea
for code in ["FPE_IX", "FIGB_PA", "FIGB_LT_PA", "FITB_PA", "FID_PA", "FILR_PA", "FPOLM_PA", "FIMM_PA"]:
    u = f"https://api.db.nomics.world/v22/series/IMF/IFS/M.BR.{code}?observations=0"
    rr = requests.get(u, headers=UA, timeout=40)
    print(code, rr.status_code, end=" ")
    if rr.status_code == 200:
        d = rr.json()["series"]["docs"][0]
        print(d.get("series_name"))
    else:
        print()

print("--- FRED ---")
try:
    fr = requests.get(
        "https://fred.stlouisfed.org/graph/fredgraph.csv?id=IRLTLT01USM156N",
        headers=UA,
        timeout=20,
    )
    print("fred", fr.status_code, len(fr.content), fr.text[:120].replace("\n", " | "))
except Exception as e:
    print(type(e).__name__, e)
