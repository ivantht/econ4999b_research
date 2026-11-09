"""Discover IMF IFS and WEO series codes on DBnomics."""
import requests

UA = {"User-Agent": "Mozilla/5.0"}

def get(url):
    print("\nGET", url[:220], flush=True)
    r = requests.get(url, headers=UA, timeout=90)
    print(" ", r.status_code, len(r.content), flush=True)
    r.raise_for_status()
    return r.json()

queries = [
    "https://api.db.nomics.world/v22/series/IMF/IFS?q=Share%20Prices&limit=8&observations=0",
    "https://api.db.nomics.world/v22/series/IMF/IFS?q=Industrial%20Production%20Index&limit=8&observations=0",
    "https://api.db.nomics.world/v22/series/IMF/IFS?q=Consumer%20Price%20Index&limit=6&observations=0",
    "https://api.db.nomics.world/v22/series/IMF/IFS?q=Government%20Bond&limit=8&observations=0",
    "https://api.db.nomics.world/v22/series/IMF/WEO:2025-04?q=GGXWDG_NGDP&limit=4&observations=0",
]
for url in queries:
    try:
        data = get(url)
    except Exception as e:
        print(" ERR", e, flush=True)
        continue
    docs = data.get("series", {}).get("docs", [])
    print(" ndocs", data.get("series", {}).get("num_found"), "returned", len(docs), flush=True)
    for d in docs:
        print(" ", d.get("series_code"), "|", d.get("series_name"), flush=True)
