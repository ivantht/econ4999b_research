import requests

UA = {"User-Agent": "Mozilla/5.0"}

def show(url, n=6):
    print("\n", url[:160], flush=True)
    r = requests.get(url, headers=UA, timeout=60)
    print(" ", r.status_code, len(r.content), flush=True)
    if r.status_code != 200:
        print(r.text[:200].replace("\n", " "), flush=True)
        return
    if "json" in r.headers.get("content-type", "") or r.text.startswith("{") or r.text.startswith("["):
        data = r.json()
        docs = data.get("results", {}).get("docs") or data.get("series", {}).get("docs") or []
        print(" hits", data.get("results", {}).get("numFound"), "docs", len(docs), flush=True)
        for d in docs[:n]:
            print(" -", d.get("provider_code"), d.get("dataset_code") or d.get("code"), "|", (d.get("series_name") or d.get("name") or "")[:140], flush=True)
            if d.get("series_code"):
                print("   ", d.get("series_code"), flush=True)
    else:
        print(r.text[:250].replace("\n", " | "), flush=True)

show("https://api.db.nomics.world/v22/search?q=%22Main%20Economic%20Indicators%22&limit=6")
show("https://api.db.nomics.world/v22/search?q=long-term%20government%20bond%20yield%20monthly&limit=8")
show("https://api.db.nomics.world/v22/series/IMF/IFS?q=Equities%2C%20Index&limit=3&observations=0")
show("https://data-api.ecb.europa.eu/service/data/IRS/M.DE.L.L40.CI.0000.EUR.N.Z?startPeriod=2020-01&endPeriod=2020-03&format=csvdata")
