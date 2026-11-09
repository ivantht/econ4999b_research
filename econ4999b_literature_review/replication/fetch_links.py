import re
import requests

urls = [
    "https://www.matteoiacoviello.com/gpr_country.htm",
    "https://www.matteoiacoviello.com/gpr.htm",
    "https://cbidata.org/vintages.html",
    "https://www.oecd.org/en/topics/capital-flows-and-investment-standards.html",
    "https://www.policyuncertainty.com/all_country_data.html",
]
headers = {"User-Agent": "Mozilla/5.0 (research replication)"}
for url in urls:
    print("\n====", url)
    try:
        r = requests.get(url, headers=headers, timeout=60)
        print("status", r.status_code, "len", len(r.text))
        hrefs = re.findall(r'href=["\']([^"\']+)["\']', r.text, flags=re.I)
        for h in hrefs:
            low = h.lower()
            if any(k in low for k in ["xls", "xlsx", "csv", "dta", "gpr", "capital", "cbi", "epu", "download"]):
                print(h)
    except Exception as e:
        print(type(e).__name__, e)
