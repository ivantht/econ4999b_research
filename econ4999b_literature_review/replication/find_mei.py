import requests

UA = {"User-Agent": "Mozilla/5.0"}

def show(url):
    print("\n", url[:180], flush=True)
    r = requests.get(url, headers=UA, timeout=90)
    print(" ", r.status_code, len(r.content), flush=True)
    if r.status_code != 200:
        print(r.text[:300].replace("\n", " "), flush=True)
        return
    data = r.json()
    docs = data.get("series", {}).get("docs", [])
    print(" num_found", data.get("series", {}).get("num_found"), "returned", len(docs), flush=True)
    for d in docs[:8]:
        print(" -", d.get("series_code"), "|", d.get("series_name"), flush=True)
        print("   dims", d.get("dimensions"), flush=True)

queries = [
    "https://api.db.nomics.world/v22/series/OECD/MEI?q=Share%20prices&limit=6&observations=0",
    "https://api.db.nomics.world/v22/series/OECD/MEI?q=Long-term%20interest&limit=6&observations=0",
    "https://api.db.nomics.world/v22/series/OECD/MEI?q=Industrial%20production&limit=4&observations=0",
    "https://api.db.nomics.world/v22/series/OECD/MEI?q=SPASTT01&limit=4&observations=0",
    "https://api.db.nomics.world/v22/series/OECD/MEI?q=IRLTLT01&limit=4&observations=0",
]
for url in queries:
    show(url)
