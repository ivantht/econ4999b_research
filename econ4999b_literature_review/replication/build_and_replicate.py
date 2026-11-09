"""
Approximate replication of Beirne and Renzhi (ADB WP 820, 2025), Table 2 and Table 3.

The paper does not release code or a vintage file. Series below are the public
sources named in Section II, or the closest public substitute when a portal blocks
bulk download. Coefficients will not match exactly.
"""
from __future__ import annotations

import io
import json
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import statsmodels.api as sm

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "raw"
OUT = ROOT / "output"
OUT.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (research replication)"}

ISO2 = {
    "Belgium": "BE", "Brazil": "BR", "Canada": "CA", "Chile": "CL", "China": "CN",
    "Colombia": "CO", "Germany": "DE", "Denmark": "DK", "Spain": "ES", "Finland": "FI",
    "France": "FR", "Hungary": "HU", "Indonesia": "ID", "India": "IN", "Italy": "IT",
    "Japan": "JP", "Korea": "KR", "Mexico": "MX", "Malaysia": "MY", "Netherlands": "NL",
    "Philippines": "PH", "Poland": "PL", "Portugal": "PT", "Sweden": "SE", "Thailand": "TH",
    "Türkiye": "TR", "Turkey": "TR", "Ukraine": "UA", "United States": "US", "South Africa": "ZA",
}
# IMF WEO uses ISO3. BIS REER uses ISO2, with a few exceptions checked below.
ISO3 = {
    "BE": "BEL", "BR": "BRA", "CA": "CAN", "CL": "CHL", "CN": "CHN", "CO": "COL",
    "DE": "DEU", "DK": "DNK", "ES": "ESP", "FI": "FIN", "FR": "FRA", "HU": "HUN",
    "ID": "IDN", "IN": "IND", "IT": "ITA", "JP": "JPN", "KR": "KOR", "MX": "MEX",
    "MY": "MYS", "NL": "NLD", "PH": "PHL", "PL": "POL", "PT": "PRT", "SE": "SWE",
    "TH": "THA", "TR": "TUR", "UA": "UKR", "US": "USA", "ZA": "ZAF",
}
ADVANCED = {"BE", "CA", "DK", "FI", "FR", "DE", "IT", "JP", "KR", "NL", "PT", "ES", "SE", "US"}
START, END = "2000-01-01", "2023-12-01"
SAMPLE_COUNTRIES = set(ISO3)


def get_json(url: str) -> dict:
    print("GET", url[:180], flush=True)
    r = requests.get(url, headers=UA, timeout=180)
    print(" ", r.status_code, len(r.content), flush=True)
    r.raise_for_status()
    return r.json()


def series_frame(data: dict, iso_key: str, value_name: str) -> pd.DataFrame:
    docs = data.get("series", {}).get("docs", [])
    rows = []
    for doc in docs:
        dims = doc.get("dimensions") or {}
        iso = dims.get(iso_key) or dims.get("REF_AREA") or dims.get("COUNTRY")
        periods = doc.get("period") or []
        values = doc.get("value") or []
        for period, value in zip(periods, values):
            if value is None or value == "NA":
                continue
            rows.append((iso, period, float(value)))
    df = pd.DataFrame(rows, columns=["iso_raw", "period", value_name])
    print(f"  {value_name}: {df['iso_raw'].nunique() if len(df) else 0} areas, {len(df)} obs", flush=True)
    return df


def monthly_index(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["date"] = pd.to_datetime(df["period"].astype(str).str.slice(0, 7) + "-01")
    return df.drop(columns=["period"])


def fetch_ifs(indicator: str) -> pd.DataFrame:
    areas = "+".join(sorted(SAMPLE_COUNTRIES))
    # REF_AREA in IFS is ISO2. Pass dimensions as JSON.
    dims = json.dumps({"FREQ": ["M"], "INDICATOR": [indicator], "REF_AREA": sorted(SAMPLE_COUNTRIES)})
    url = (
        "https://api.db.nomics.world/v22/series/IMF/IFS"
        f"?dimensions={requests.utils.quote(dims)}&observations=1&limit=100"
    )
    data = get_json(url)
    df = series_frame(data, "REF_AREA", indicator)
    if df.empty:
        return df
    df = monthly_index(df)
    df = df.rename(columns={"iso_raw": "iso"})
    return df[["iso", "date", indicator]]


def fetch_fd() -> pd.DataFrame:
    dims = json.dumps({"FREQ": ["A"], "INDICATOR": ["FD_FD_IX"], "REF_AREA": sorted(SAMPLE_COUNTRIES)})
    url = (
        "https://api.db.nomics.world/v22/series/IMF/FDI"
        f"?dimensions={requests.utils.quote(dims)}&observations=1&limit=50"
    )
    df = series_frame(get_json(url), "REF_AREA", "fd")
    df["year"] = df["period"].astype(str).str.slice(0, 4).astype(int)
    df = df.rename(columns={"iso_raw": "iso"})
    return df[["iso", "year", "fd"]]


def fetch_debt() -> pd.DataFrame:
    dims = json.dumps({"weo-subject": ["GGXWDG_NGDP"], "weo-country": sorted(ISO3.values())})
    url = (
        "https://api.db.nomics.world/v22/series/IMF/WEO:2025-04"
        f"?dimensions={requests.utils.quote(dims)}&observations=1&limit=40"
    )
    df = series_frame(get_json(url), "weo-country", "debt")
    if df.empty:
        return df
    inv3 = {v: k for k, v in ISO3.items()}
    df["iso"] = df["iso_raw"].map(inv3)
    df = df.dropna(subset=["iso"])
    df["year"] = df["period"].astype(str).str.slice(0, 4).astype(int)
    return df[["iso", "year", "debt"]]


def fetch_mei(subject: str, measure: str, value_name: str) -> pd.DataFrame:
    dims = json.dumps({
        "FREQUENCY": ["M"],
        "SUBJECT": [subject],
        "MEASURE": [measure],
        "LOCATION": sorted(ISO3.values()),
    })
    url = (
        "https://api.db.nomics.world/v22/series/OECD/MEI"
        f"?dimensions={requests.utils.quote(dims)}&observations=1&limit=40"
    )
    df = series_frame(get_json(url), "LOCATION", value_name)
    if df.empty:
        return df
    inv3 = {v: k for k, v in ISO3.items()}
    df["iso"] = df["iso_raw"].map(inv3)
    df = monthly_index(df.dropna(subset=["iso"]))
    return df[["iso", "date", value_name]]


def load_gpr() -> pd.DataFrame:
    gpr = pd.read_excel(RAW / "gpr_export.xls")
    gpr["date"] = pd.to_datetime(gpr["month"])
    cols = [f"GPRC_{iso3}" for iso3 in ISO3.values()]
    long = gpr.melt(id_vars=["date"], value_vars=cols, var_name="col", value_name="gpr")
    long["iso"] = long["col"].str.replace("GPRC_", "", regex=False).map({v: k for k, v in ISO3.items()})
    long = long.dropna(subset=["iso"])
    return long[["iso", "date", "gpr"]]


def load_flows() -> pd.DataFrame:
    panel = pd.read_excel(RAW / "oecd_capital_flows.xlsx", sheet_name="panel")
    panel["iso"] = panel["country"].map(ISO2)
    panel = panel.dropna(subset=["iso"]).copy()
    panel["date"] = pd.to_datetime(panel["month"])
    panel = panel.sort_values(["iso", "date"])
    pieces = []
    for iso, g in panel.groupby("iso"):
        g = g.set_index("date").sort_index()
        full = g.reindex(pd.date_range(g.index.min(), g.index.max(), freq="MS"))
        full["iso"] = iso
        full["port_inf"] = full["port_inf"]
        full["cf_vol"] = full["port_inf"].rolling(3, min_periods=3).std(ddof=1)
        pieces.append(full.reset_index().rename(columns={"index": "date"}))
    out = pd.concat(pieces, ignore_index=True)
    return out[["iso", "date", "port_inf", "cf_vol"]]


def load_gepu() -> pd.DataFrame:
    epu = pd.read_excel(RAW / "epu_all_country.xlsx")
    epu = epu.dropna(subset=["Year", "Month"])
    epu["date"] = pd.to_datetime({"year": epu["Year"].astype(int), "month": epu["Month"].astype(int), "day": 1})
    return epu[["date", "GEPU_current", "GEPU_ppp"]].rename(columns={"GEPU_current": "gepu"})


def load_vix() -> pd.DataFrame:
    vix = pd.read_csv(RAW / "vix_history.csv")
    vix["date"] = pd.to_datetime(vix["DATE"])
    vix = vix.rename(columns={"CLOSE": "vix_daily"})
    monthly = vix.set_index("date")["vix_daily"].resample("MS").mean().rename("vix").reset_index()
    return monthly


def load_oil() -> pd.DataFrame:
    oil = pd.read_excel(RAW / "wti_monthly.xls", sheet_name="Data 1", header=2)
    oil = oil.iloc[:, :2]
    oil.columns = ["date", "oil"]
    oil["date"] = pd.to_datetime(oil["date"], errors="coerce")
    oil["oil"] = pd.to_numeric(oil["oil"], errors="coerce")
    oil = oil.dropna()
    oil["date"] = oil["date"].dt.to_period("M").dt.to_timestamp()
    return oil[["date", "oil"]]


def load_reer() -> pd.DataFrame:
    reer = pd.read_csv(RAW / "bis_reer.csv")
    reer = reer[reer["EER_TYPE"].eq("R") & reer["EER_BASKET"].eq("B")].copy()
    reer["date"] = pd.to_datetime(reer["TIME_PERIOD"].astype(str) + "-01")
    reer["iso"] = reer["REF_AREA"]
    reer["reer"] = pd.to_numeric(reer["OBS_VALUE"], errors="coerce")
    reer = reer[reer["iso"].isin(SAMPLE_COUNTRIES)]
    return reer[["iso", "date", "reer"]]


def load_policy() -> pd.DataFrame:
    pol = pd.read_csv(RAW / "bis_policy.csv")
    xm_path = RAW / "bis_policy_xm.csv"
    if not xm_path.exists():
        r = requests.get(
            "https://stats.bis.org/api/v1/data/WS_CBPOL/M.XM?startPeriod=1999-01&endPeriod=2023-12&format=csv",
            headers=UA,
            timeout=90,
        )
        r.raise_for_status()
        xm_path.write_bytes(r.content)
    pol = pd.concat([pol, pd.read_csv(xm_path)], ignore_index=True)
    pol["date"] = pd.to_datetime(pol["TIME_PERIOD"].astype(str) + "-01")
    pol["rate"] = pd.to_numeric(pol["OBS_VALUE"], errors="coerce")
    # Some countries have more than one compiled rate. Keep the last vintage per month
    # by preferring rows whose title mentions policy rate, then averaging duplicates.
    pol["iso"] = pol["REF_AREA"]
    euro = {"BE", "DE", "ES", "FI", "FR", "IT", "NL", "PT"}
    xm = pol[pol["iso"].isin(["XM", "U2", "EU"])][["date", "rate"]].dropna()
    if len(xm):
        xm = xm.groupby("date", as_index=False)["rate"].mean()
    own = pol[pol["iso"].isin(SAMPLE_COUNTRIES)][["iso", "date", "rate"]].dropna()
    own = own.groupby(["iso", "date"], as_index=False)["rate"].mean()
    if len(xm):
        missing = []
        have = set(own["iso"].unique())
        for iso in euro - have:
            tmp = xm.copy()
            tmp["iso"] = iso
            missing.append(tmp)
        if missing:
            own = pd.concat([own, *missing], ignore_index=True)
        # Fill gaps inside euro-area countries with the euro-area policy rate.
        own = own.set_index(["iso", "date"])
        for iso in euro:
            if iso not in own.index.get_level_values(0):
                continue
            block = own.loc[iso, "rate"]
            filled = block.copy()
            xm_s = xm.set_index("date")["rate"]
            filled = filled.reindex(filled.index.union(xm_s.index))
            filled = filled.fillna(xm_s.reindex(filled.index))
            # keep only original-or-filled dates already in xm or own; trim later
            replacement = filled.dropna().rename("rate").reset_index()
            replacement["iso"] = iso
            own = own.drop(index=iso, errors="ignore")
            own = pd.concat([own.reset_index(), replacement], ignore_index=True).set_index(["iso", "date"])
        own = own.reset_index()
    return own[["iso", "date", "rate"]]


def load_cbi() -> pd.DataFrame:
    path = RAW / "cbi_2025.xlsx"
    if not path.exists():
        print("Downloading Romelli 2025 CBI update", flush=True)
        r = requests.get(
            "https://cbidata.org/dataset/CBIData_Romelli_2025.xlsx",
            headers=UA,
            timeout=120,
        )
        r.raise_for_status()
        path.write_bytes(r.content)
    xl = pd.ExcelFile(path)
    sheet = "CBI data" if "CBI data" in xl.sheet_names else "CBI Indices"
    cbi = pd.read_excel(path, sheet_name=sheet)
    print("CBI sheet", sheet, "years", int(cbi["year"].min()), int(cbi["year"].max()), flush=True)
    iso_col = "iso_a3" if "iso_a3" in cbi.columns else "iso_a2"
    cbi_col = "cbie_index" if "cbie_index" in cbi.columns else "CBIE"
    out = cbi.rename(columns={iso_col: "iso_raw", cbi_col: "cbi"})
    return out[["iso_raw", "year", "cbi"]]


def normalize_cbi(cbi: pd.DataFrame) -> pd.DataFrame:
    if {"iso", "year", "cbi"}.issubset(cbi.columns):
        out = cbi.copy()
    elif {"iso_raw", "year", "cbi"}.issubset(cbi.columns):
        out = cbi.rename(columns={"iso_raw": "iso"}).copy()
    else:
        # Try long format after detecting a year column.
        year_col = next((c for c in cbi.columns if str(c).lower() in {"year", "yr"}), None)
        if year_col is None:
            raise RuntimeError(f"Unrecognized CBI layout: {list(cbi.columns)[:12]}")
        id_cols = [c for c in cbi.columns if c != year_col and cbi[c].dtype == object][:1]
        if not id_cols:
            # wide years in columns
            raise RuntimeError(f"Unrecognized CBI layout: {list(cbi.columns)[:12]}")
        value_cols = [c for c in cbi.columns if c not in id_cols + [year_col]]
        # If many numeric country columns, melt.
        numeric_cols = [c for c in value_cols if pd.api.types.is_numeric_dtype(cbi[c])]
        if len(numeric_cols) > 5 and not any("cbie" in str(c).lower() for c in cbi.columns):
            out = cbi.melt(id_vars=[id_cols[0], year_col], value_vars=numeric_cols, var_name="iso", value_name="cbi")
            out = out.rename(columns={year_col: "year"})
        else:
            cbi_col = next(c for c in cbi.columns if "cbie" in str(c).lower())
            iso_col = id_cols[0]
            out = cbi.rename(columns={iso_col: "iso", year_col: "year", cbi_col: "cbi"})
    out["year"] = pd.to_numeric(out["year"], errors="coerce")
    out["cbi"] = pd.to_numeric(out["cbi"], errors="coerce")
    out = out.dropna(subset=["year", "cbi"])
    out["year"] = out["year"].astype(int)
    # Map country names or ISO3 to ISO2.
    name_map = {**ISO2, **{v: k for k, v in ISO3.items()}, **{k: k for k in SAMPLE_COUNTRIES}}
    # ISO3 values map to ISO2 already via the dict comprehension above? 
    # {v: k for k, v in ISO3.items()} maps BEL -> BE. Good.
    extra = {
        "Belgium": "BE", "Brazil": "BR", "Canada": "CA", "Chile": "CL", "China": "CN",
        "Colombia": "CO", "Germany": "DE", "Denmark": "DK", "Spain": "ES", "Finland": "FI",
        "France": "FR", "Hungary": "HU", "Indonesia": "ID", "India": "IN", "Italy": "IT",
        "Japan": "JP", "Korea": "KR", "South Korea": "KR", "Mexico": "MX", "Malaysia": "MY",
        "Netherlands": "NL", "Philippines": "PH", "Poland": "PL", "Portugal": "PT",
        "Sweden": "SE", "Thailand": "TH", "Turkey": "TR", "Türkiye": "TR", "Ukraine": "UA",
        "United States": "US", "South Africa": "ZA", "USA": "US", "CHN": "CN",
    }
    name_map.update(extra)
    out["iso"] = out["iso"].map(lambda x: name_map.get(x, name_map.get(str(x).strip(), None)))
    out = out.dropna(subset=["iso"])
    out = out[out["iso"].isin(SAMPLE_COUNTRIES)]
    return out.groupby(["iso", "year"], as_index=False)["cbi"].mean()


def within_ols(df: pd.DataFrame, y: str, x_cols: list[str]) -> dict:
    use = df[[y, "iso", *x_cols]].dropna().copy()
    if use.empty or use["iso"].nunique() < 2:
        raise RuntimeError(f"No usable observations for {y}")
    demeaned = use.copy()
    for col in [y, *x_cols]:
        demeaned[col] = use[col] - use.groupby("iso")[col].transform("mean")
    keep = [col for col in x_cols if float(demeaned[col].std()) > 1e-8]
    dropped = [col for col in x_cols if col not in keep]
    if dropped:
        print(f"  dropped flat controls for {y}: {dropped}", flush=True)
    x_cols = keep
    demeaned = demeaned[[y, "iso", *x_cols]]
    # Drop one country degree of freedom in the variance, matching xtreg approximately
    # by using the within residual df = N - K - N_groups.
    yv = demeaned[y].to_numpy()
    X = demeaned[x_cols].to_numpy()
    nobs = len(use)
    n_groups = use["iso"].nunique()
    k = X.shape[1]
    beta = np.linalg.lstsq(X, yv, rcond=None)[0]
    resid = yv - X @ beta
    dof = nobs - k - n_groups
    if dof <= 0:
        dof = max(nobs - k, 1)
    sigma2 = float(resid @ resid) / dof
    xtx_inv = np.linalg.inv(X.T @ X)
    se = np.sqrt(np.diag(xtx_inv) * sigma2)
    sst = float(yv @ yv)
    r2 = 1 - float(resid @ resid) / sst
    # Country-clustered SE
    scores = X * resid[:, None]
    clusters = use["iso"].to_numpy()
    meat = np.zeros((k, k))
    for iso in pd.unique(clusters):
        g = scores[clusters == iso].sum(axis=0)
        meat += np.outer(g, g)
    g_count = use["iso"].nunique()
    scale = (g_count / (g_count - 1)) * ((nobs - 1) / dof) if g_count > 1 else 1
    vcov = scale * xtx_inv @ meat @ xtx_inv
    se_cl = np.sqrt(np.diag(vcov))
    out = {"n": nobs, "countries": int(n_groups), "r2_within": r2, "coef": {}, "se": {}, "se_cl": {}}
    for name, b, s, sc in zip(x_cols, beta, se, se_cl):
        out["coef"][name] = float(b)
        out["se"][name] = float(s)
        out["se_cl"][name] = float(sc)
    return out


def stars(coef: float, se: float) -> str:
    if se == 0 or np.isnan(se):
        return f"{coef:.3f}"
    t = abs(coef / se)
    mark = "***" if t > 2.576 else "**" if t > 1.96 else "*" if t > 1.645 else ""
    return f"{coef:.3f}{mark} ({se:.3f})"


def main() -> None:
    print("Loading local files", flush=True)
    gpr = load_gpr()
    flows = load_flows()
    gepu = load_gepu()
    vix = load_vix()
    oil = load_oil()
    reer = load_reer()
    policy = load_policy()
    cbi_raw = load_cbi()
    cbi = normalize_cbi(cbi_raw)
    print("CBI sample", cbi["iso"].nunique(), "years", cbi["year"].min(), cbi["year"].max(), flush=True)

    print("Downloading IMF series", flush=True)
    ip = fetch_ifs("AIP_IX")
    cpi = fetch_ifs("PCPI_IX")
    cpi_yoy = fetch_ifs("PCPI_PC_CP_A_PT")
    shares = fetch_ifs("FPE_IX")
    bonds = fetch_ifs("FIGB_PA")
    fd = fetch_fd()
    debt = fetch_debt()
    shares_oecd = fetch_mei("SPASTT01", "IXOB", "share_oecd")
    bonds_oecd = fetch_mei("IRLTLT01", "ST", "bond_oecd")
    print("policy countries", sorted(policy["iso"].unique()), flush=True)
    print("missing policy", sorted(SAMPLE_COUNTRIES - set(policy["iso"].unique())), flush=True)

    # If the long-term yield code is empty, try the short-to-medium government yield.
    if bonds.empty:
        print("FIGB_PA empty, trying FIGBY_SM_PA", flush=True)
        bonds = fetch_ifs("FIGBY_SM_PA")
    if shares.empty:
        print("FPE_IX empty", flush=True)

    panel = gpr.merge(flows, on=["iso", "date"], how="outer")
    panel = panel.merge(reer, on=["iso", "date"], how="left")
    panel = panel.merge(policy, on=["iso", "date"], how="left")
    panel = panel.merge(ip, on=["iso", "date"], how="left")
    panel = panel.merge(cpi, on=["iso", "date"], how="left")
    panel = panel.merge(cpi_yoy, on=["iso", "date"], how="left")
    if not shares.empty:
        panel = panel.merge(shares, on=["iso", "date"], how="left")
    if not bonds.empty:
        panel = panel.merge(bonds, on=["iso", "date"], how="left")
    if not shares_oecd.empty:
        panel = panel.merge(shares_oecd, on=["iso", "date"], how="left")
    if not bonds_oecd.empty:
        panel = panel.merge(bonds_oecd, on=["iso", "date"], how="left")
    # IMF FPOLM_PA is not used. For several countries it is not the policy rate
    # (values up to 400), and it does not cover the euro area. The BIS policy rate
    # matches the paper's minimum of -0.75 and maximum of 57.
    panel = panel.merge(gepu, on="date", how="left")
    panel = panel.merge(vix, on="date", how="left")
    panel = panel.merge(oil, on="date", how="left")

    panel = panel[panel["iso"].isin(SAMPLE_COUNTRIES)].copy()
    panel = panel[panel["date"].between(START, END)].copy()
    panel["year"] = panel["date"].dt.year
    panel = panel.merge(fd, on=["iso", "year"], how="left")
    panel = panel.merge(debt, on=["iso", "year"], how="left")
    panel = panel.merge(cbi, on=["iso", "year"], how="left")

    panel = panel.sort_values(["iso", "date"])
    panel["gpr_z"] = panel.groupby("iso")["gpr"].transform(lambda s: (s - s.mean()) / s.std(ddof=1))
    panel["ln_reer"] = np.log(panel["reer"])
    panel["ln_ip"] = np.log(panel["AIP_IX"])
    share = panel["share_oecd"] if "share_oecd" in panel.columns else pd.Series(np.nan, index=panel.index)
    if "FPE_IX" in panel.columns:
        share = share.fillna(panel["FPE_IX"])
    panel["ln_stock_real"] = np.log(share / panel["PCPI_IX"])
    panel["bond"] = panel["bond_oecd"] if "bond_oecd" in panel.columns else np.nan
    if "FIGB_PA" in panel.columns:
        panel["bond"] = panel["bond"].fillna(panel["FIGB_PA"])
    panel["infl"] = panel["PCPI_PC_CP_A_PT"]
    panel["ln_oil"] = np.log(panel["oil"])
    panel["ln_vix"] = np.log(panel["vix"])
    panel["ln_gepu"] = np.log(panel["gepu"])
    panel["group"] = np.where(panel["iso"].isin(ADVANCED), "Advanced", "Emerging")

    lag_cols = ["rate", "ln_ip", "infl", "ln_oil", "ln_vix", "ln_gepu", "fd", "cbi", "debt"]
    lagged = panel.groupby("iso")[lag_cols].shift(1)
    lagged.columns = [f"{c}_l1" for c in lag_cols]
    panel = pd.concat([panel, lagged], axis=1)
    panel.to_csv(OUT / "panel.csv", index=False)
    print("Saved", OUT / "panel.csv", "rows", len(panel), flush=True)

    # Summary statistics versus Table 1
    summary_map = {
        "cf_vol": "Capital flow volatility",
        "ln_stock_real": "Real stock prices (log)",
        "bond": "Long-term bond yield",
        "ln_reer": "REER (log)",
        "gpr": "Geopolitical risk",
        "rate": "Policy rate",
        "ln_ip": "Real industrial production (log)",
        "infl": "Inflation",
        "ln_oil": "Oil price (log)",
        "vix": "VIX level",
        "gepu": "Global EPU",
        "fd": "Financial development",
        "cbi": "Central bank independence",
        "debt": "Public debt/GDP",
    }
    rows = []
    for col, label in summary_map.items():
        if col not in panel.columns:
            continue
        s = panel[col].dropna()
        rows.append({"variable": label, "N": int(s.shape[0]), "mean": s.mean(), "sd": s.std(), "min": s.min(), "max": s.max()})
    summary = pd.DataFrame(rows)
    summary.to_csv(OUT / "summary_vs_table1.csv", index=False)
    print("\nSUMMARY VS TABLE 1", flush=True)
    print(summary.to_string(index=False, float_format=lambda v: f"{v:8.3f}"), flush=True)

    x_cols = [
        "gpr_z", "rate_l1", "ln_ip_l1", "infl_l1", "ln_oil_l1", "ln_vix_l1",
        "ln_gepu_l1", "fd_l1", "cbi_l1", "debt_l1",
    ]
    outcomes = {
        "cf_vol": "Capital flow volatility",
        "ln_stock_real": "Stock prices",
        "bond": "Bond yield",
        "ln_reer": "Exchange rate",
    }
    published = {
        "cf_vol": (0.867, 0.382),
        "ln_stock_real": (-0.039, 0.006),
        "bond": (0.134, 0.030),
        "ln_reer": (0.001, 0.002),
    }
    results = []
    bare = within_ols(panel, "cf_vol", ["gpr_z"])
    print(
        f"\nBivariate capital-flow volatility on GPR: {stars(bare['coef']['gpr_z'], bare['se']['gpr_z'])} N={bare['n']}",
        flush=True,
    )
    print("\nTABLE 2 REPLICATION (within estimator)", flush=True)
    for col, label in outcomes.items():
        if col not in panel.columns:
            print("missing", col, flush=True)
            continue
        fit = within_ols(panel, col, x_cols)
        pub_b, pub_se = published[col]
        line = {
            "outcome": label,
            "gpr_coef": fit["coef"]["gpr_z"],
            "gpr_se": fit["se"]["gpr_z"],
            "gpr_se_cluster": fit["se_cl"]["gpr_z"],
            "published_coef": pub_b,
            "published_se": pub_se,
            "N": fit["n"],
            "countries": fit["countries"],
            "r2_within": fit["r2_within"],
        }
        results.append(line)
        print(
            f"{label:24}  ours {stars(fit['coef']['gpr_z'], fit['se']['gpr_z'])}  "
            f"cluster {stars(fit['coef']['gpr_z'], fit['se_cl']['gpr_z'])}  "
            f"paper {pub_b:.3f} ({pub_se:.3f})  N={fit['n']}  R2={fit['r2_within']:.3f}",
            flush=True,
        )
    pd.DataFrame(results).to_csv(OUT / "table2_replication.csv", index=False)

    print("\nTABLE 3 REPLICATION", flush=True)
    published_t3 = {
        ("Emerging", "cf_vol"): (3.144, 1.840),
        ("Emerging", "ln_stock_real"): (-0.017, 0.005),
        ("Emerging", "bond"): (0.088, 0.043),
        ("Emerging", "ln_reer"): (-0.010, 0.002),
        ("Advanced", "cf_vol"): (4.465, 1.343),
        ("Advanced", "ln_stock_real"): (-0.032, 0.005),
        ("Advanced", "bond"): (0.037, 0.020),
        ("Advanced", "ln_reer"): (-0.003, 0.002),
    }
    t3_rows = []
    for group in ["Emerging", "Advanced"]:
        sub = panel[panel["group"].eq(group)]
        for col, label in outcomes.items():
            if col not in sub.columns:
                continue
            fit = within_ols(sub, col, x_cols)
            pub_b, pub_se = published_t3[(group, col)]
            t3_rows.append({
                "group": group, "outcome": label,
                "gpr_coef": fit["coef"]["gpr_z"], "gpr_se": fit["se"]["gpr_z"],
                "published_coef": pub_b, "published_se": pub_se,
                "N": fit["n"], "r2_within": fit["r2_within"],
            })
            print(
                f"{group:10} {label:24} ours {stars(fit['coef']['gpr_z'], fit['se']['gpr_z'])}  "
                f"paper {pub_b:.3f} ({pub_se:.3f})  N={fit['n']}",
                flush=True,
            )
    pd.DataFrame(t3_rows).to_csv(OUT / "table3_replication.csv", index=False)
    print("\nDone", flush=True)


if __name__ == "__main__":
    main()
