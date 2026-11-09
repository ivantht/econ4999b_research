"""Why the capital-flow volatility coefficient has the opposite sign from the paper."""
from __future__ import annotations

import numpy as np
import pandas as pd
from pathlib import Path

RAW = Path(__file__).resolve().parent / "raw"
OUT = Path(__file__).resolve().parent / "output"

ISO2 = {
    "Belgium": "BE", "Brazil": "BR", "Canada": "CA", "Chile": "CL", "China": "CN",
    "Colombia": "CO", "Germany": "DE", "Denmark": "DK", "Spain": "ES", "Finland": "FI",
    "France": "FR", "Hungary": "HU", "Indonesia": "ID", "India": "IN", "Italy": "IT",
    "Japan": "JP", "Korea": "KR", "Mexico": "MX", "Malaysia": "MY", "Netherlands": "NL",
    "Philippines": "PH", "Poland": "PL", "Portugal": "PT", "Sweden": "SE", "Thailand": "TH",
    "Türkiye": "TR", "Turkey": "TR", "Ukraine": "UA", "United States": "US", "South Africa": "ZA",
}
ADV = {"BE", "CA", "DK", "FI", "FR", "DE", "IT", "JP", "KR", "NL", "PT", "ES", "SE", "US"}


def within_beta(df: pd.DataFrame, y: str, x: str = "gpr_z"):
    d = df[[y, x, "iso"]].dropna().copy()
    if d["iso"].nunique() < 3 or len(d) < 50:
        return np.nan, len(d), d["iso"].nunique()
    d["y"] = d[y] - d.groupby("iso")[y].transform("mean")
    d["x"] = d[x] - d.groupby("iso")[x].transform("mean")
    xv, yv = d["x"].to_numpy(), d["y"].to_numpy()
    den = float(np.dot(xv, xv))
    if den == 0:
        return np.nan, len(d), d["iso"].nunique()
    return float(np.dot(xv, yv) / den), len(d), int(d["iso"].nunique())


def main() -> None:
    panel = pd.read_csv(OUT / "panel.csv", parse_dates=["date"])
    flows = pd.read_excel(RAW / "oecd_capital_flows.xlsx", sheet_name="panel")
    flows["iso"] = flows["country"].map(ISO2)
    flows["date"] = pd.to_datetime(flows["month"])
    flows = flows[flows["iso"].notna()].sort_values(["iso", "date"])
    print("duplicate iso-date", int(flows.duplicated(["iso", "date"]).sum()))

    pieces = []
    for iso, g in flows.groupby("iso"):
        g = g.drop_duplicates("date").set_index("date").sort_index()
        start = max(g.index.min(), pd.Timestamp("1999-01-01"))
        end = min(g.index.max(), pd.Timestamp("2023-12-01"))
        idx = pd.date_range(start, end, freq="MS")
        g = g.reindex(idx)
        s = g["port_inf"]
        out = pd.DataFrame({"iso": iso, "date": idx, "port": s.to_numpy()})
        out["vol3"] = s.rolling(3, min_periods=3).std(ddof=1).to_numpy()
        out["vol6"] = s.rolling(6, min_periods=6).std(ddof=1).to_numpy()
        out["vol12"] = s.rolling(12, min_periods=12).std(ddof=1).to_numpy()
        out["vol_out"] = g["port_out"].rolling(3, min_periods=3).std(ddof=1).to_numpy()
        net = g["port_inf"] - g["port_out"]
        out["vol_net"] = net.rolling(3, min_periods=3).std(ddof=1).to_numpy()
        out["vol_turn"] = (g["port_inf"] + g["port_out"]).rolling(3, min_periods=3).std(ddof=1).to_numpy()
        out["vol_abs"] = s.abs().rolling(3, min_periods=3).std(ddof=1).to_numpy()
        out["vol_d"] = s.diff().rolling(3, min_periods=3).std(ddof=1).to_numpy()
        out["vol_debt"] = g["debt_inf"].rolling(3, min_periods=3).std(ddof=1).to_numpy()
        out["vol_eq"] = g["eq_inf"].rolling(3, min_periods=3).std(ddof=1).to_numpy()
        out["abs_flow"] = s.abs().to_numpy()
        out["sq"] = s.to_numpy() ** 2
        # all gross capital-flow legs the file actually has
        legs = ["debt_inf", "debt_out", "eq_inf", "eq_out", "fdi_inf", "fdi_out", "other_inf", "other_out"]
        gross_all = g[legs].abs().sum(axis=1, min_count=1)
        out["vol_all"] = gross_all.rolling(3, min_periods=3).std(ddof=1).to_numpy()
        pieces.append(out)
    alt = pd.concat(pieces, ignore_index=True)
    base = panel[["iso", "date", "gpr", "gpr_z"]].drop_duplicates()
    m = alt.merge(base, on=["iso", "date"], how="inner")
    m = m[m["date"].between("2000-01-01", "2023-12-01")].copy()
    m["group"] = np.where(m["iso"].isin(ADV), "Advanced", "Emerging")

    ys = [
        "vol3", "vol6", "vol12", "vol_out", "vol_net", "vol_turn", "vol_abs",
        "vol_d", "vol_debt", "vol_eq", "abs_flow", "sq", "vol_all",
    ]
    print(f"{'measure':12} {'all':>10} {'N':>6} {'AE':>10} {'EM':>10}")
    for y in ys:
        b, n, _ = within_beta(m, y)
        ba, _, _ = within_beta(m[m["group"].eq("Advanced")], y)
        be, _, _ = within_beta(m[m["group"].eq("Emerging")], y)
        print(f"{y:12} {b:10.3f} {n:6d} {ba:10.3f} {be:10.3f}")

    print("\nTiming: k>0 means GPR is lagged k months (GPR leads volatility)")
    d0 = m[["iso", "date", "vol3", "gpr_z", "group"]].dropna().copy()
    for k in range(-6, 7):
        d = d0.copy()
        d["gpr_k"] = d.groupby("iso")["gpr_z"].shift(k)
        b, n, _ = within_beta(d, "vol3", "gpr_k")
        ba, _, _ = within_beta(d[d["group"].eq("Advanced")], "vol3", "gpr_k")
        be, _, _ = within_beta(d[d["group"].eq("Emerging")], "vol3", "gpr_k")
        print(f"k={k:2d} all {b:8.3f} AE {ba:8.3f} EM {be:8.3f} N {n}")

    print("\nDrop one large country at a time, bivariate vol3")
    base_b, _, _ = within_beta(m, "vol3")
    print("baseline", round(base_b, 3))
    for iso in ["US", "DE", "JP", "CN", "FR", "CA", "NL", "SE"]:
        b, n, g = within_beta(m[m["iso"].ne(iso)], "vol3")
        print(f"drop {iso}: {b:8.3f} N {n} countries {g}")

    print("\nHigh-GPR months")
    for iso in ["US", "DE", "JP", "CN", "FR", "UA"]:
        g = m[m["iso"].eq(iso)].dropna(subset=["vol3", "gpr"])
        hi = g.nlargest(6, "gpr")[["date", "gpr", "port", "vol3"]]
        print("\n", iso, "corr(gpr, vol3)", round(g["gpr"].corr(g["vol3"]), 3),
              "corr(gpr, |port|)", round(g["gpr"].corr(g["port"].abs()), 3))
        print(hi.to_string(index=False))

    # Where does the 3-month std peak, and is that month a high-GPR month?
    print("\nMax vol3 by country and GPR z that month")
    rows = []
    for iso, g in m.dropna(subset=["vol3"]).groupby("iso"):
        i = g["vol3"].idxmax()
        rows.append((iso, str(g.loc[i, "date"].date()), float(g.loc[i, "vol3"]), float(g.loc[i, "gpr_z"])))
    peak = pd.DataFrame(rows, columns=["iso", "date", "vol3", "gpr_z"]).sort_values("vol3", ascending=False)
    print(peak.head(12).to_string(index=False))


if __name__ == "__main__":
    main()
