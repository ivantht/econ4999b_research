import requests
UA = {"User-Agent": "Mozilla/5.0"}
urls = [
    "https://web.archive.org/cdx/search/cdx?url=www.oecd.org/content/dam/oecd/en/topics/policy-sub-issues/capital-flows/OECD-monthly-capital-flow-dataset.xlsx&output=json&fl=timestamp,statuscode,length&from=202301&to=202511&filter=statuscode:200",
    "https://web.archive.org/cdx/search/cdx?url=oecd.org/*capital-flow-dataset.xlsx&matchType=domain&output=json&fl=timestamp,original,statuscode,length&from=202401&to=202511&filter=statuscode:200&limit=30",
]
for url in urls:
    print("GET", url[:140], flush=True)
    try:
        r = requests.get(url, headers=UA, timeout=60)
        print(r.status_code, r.text[:2000], flush=True)
    except Exception as e:
        print(type(e).__name__, e, flush=True)
