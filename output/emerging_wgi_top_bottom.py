"""Top-five and bottom-five WGI regressions for the 15 emerging economies.

Follows the agreed plan: monthly panel, equation with centered WGI and its
interaction with country-standardized GPR, country fixed effects, and
paper-style tables.
"""

import numpy as np
import pandas as pd
from scipy import stats

ROOT = r"c:\Users\ASUS\econ4999b_research"
CM_PATH = ROOT + r"\cleaned\replication_cleaned\country_month.csv"
WGI_PATH = ROOT + r"\cleaned\wgi.csv"
HTML_PATH = ROOT + r"\output\emerging_wgi_top_bottom_results.html"
CSV_PATH = ROOT + r"\output\emerging_wgi_top_bottom_results.csv"

EMERGING = [
    "Brazil",
    "Chile",
    "China",
    "Colombia",
    "Hungary",
    "India",
    "Indonesia",
    "Malaysia",
    "Mexico",
    "Philippines",
    "Poland",
    "South Africa",
    "Thailand",
    "Turkiye",
    "Ukraine",
]
DISPLAY = {"Turkiye": "Türkiye", "Philippines": "Philippines"}
ASPECTS = [
    ("va", "Voice and accountability"),
    ("pv", "Political stability and absence of violence"),
    ("ge", "Government effectiveness"),
    ("rq", "Regulatory quality"),
    ("rl", "Rule of law"),
    ("cc", "Control of corruption"),
]
CONTROLS = [
    "policy_rate_l1",
    "ln_ip_l1",
    "inflation_l1",
    "ln_oil_l1",
    "ln_vix_l1",
    "ln_gepu_l1",
    "financial_development_l1",
    "central_bank_independence_l1",
    "public_debt_gdp_l1",
]
OUTCOMES = [
    ("capital_flow_volatility", "Capital-flow volatility"),
    ("ln_reer", "Exchange rate"),
]
TERMS = [
    ("gpr_z", "GPR"),
    ("wgi_c", "WGI"),
    ("inter", "WGI × GPR"),
]


def stars(p):
    if p < 0.01:
        return "***"
    if p < 0.05:
        return "**"
    if p < 0.10:
        return "*"
    return ""


def fmt_num(x):
    text = f"{x:.3f}"
    if text in {"0.000", "-0.000"} and abs(x) >= 5e-5:
        return f"{x:.4f}"
    return text


def load_panel():
    cm = pd.read_csv(CM_PATH, parse_dates=["date"])
    cm = cm[cm["country"].isin(EMERGING)].copy()
    cm = cm[(cm["date"] >= "2000-01-01") & (cm["date"] <= "2023-12-01")]
    cm = cm.sort_values(["country", "date"])
    grouped = cm.groupby("country", group_keys=False)
    lag_src = [
        "policy_rate",
        "industrial_production",
        "inflation",
        "oil_price",
        "vix",
        "gepu",
        "financial_development",
        "central_bank_independence",
        "public_debt_gdp",
    ]
    for col in lag_src:
        cm[col + "_l1"] = grouped[col].shift(1)
    cm["lag_date"] = grouped["date"].shift(1)
    cm["wgi_year"] = cm["lag_date"].dt.year
    cm["ln_ip_l1"] = np.log(cm["industrial_production_l1"])
    cm["ln_oil_l1"] = np.log(cm["oil_price_l1"])
    cm["ln_vix_l1"] = np.log(cm["vix_l1"])
    cm["ln_gepu_l1"] = np.log(cm["gepu_l1"])
    cm["ln_reer"] = np.log(cm["reer"])

    wgi = pd.read_csv(WGI_PATH)
    wgi["country"] = wgi["country"].replace({"Turkey": "Turkiye"})
    wgi = wgi[wgi["dimension"].isin([code for code, _ in ASPECTS])]
    missing = sorted(set(EMERGING) - set(wgi["country"]))
    if missing:
        raise RuntimeError(f"WGI file has no rows for: {missing}")
    annual = (
        wgi.pivot_table(
            index=["country", "year"],
            columns="dimension",
            values="estimate",
            aggfunc="first",
        )
        .reset_index()
    )
    rank_years = annual[
        annual["country"].isin(EMERGING) & annual["year"].between(2000, 2021)
    ]
    means = rank_years.groupby("country")[[code for code, _ in ASPECTS]].mean()
    if set(means.index) != set(EMERGING):
        raise RuntimeError("Every emerging economy needs a 2000–2021 WGI average.")
    cm = cm.merge(annual, left_on=["country", "wgi_year"], right_on=["country", "year"], how="left")
    return cm, means


def tail(means, code, high):
    ordered = means[code].sort_values(ascending=not high)
    cutoff = float(ordered.iloc[4])
    if high:
        chosen = ordered[ordered >= cutoff]
    else:
        chosen = ordered[ordered <= cutoff]
    return list(chosen.index)


def prepare_sample(frame, outcome, countries, aspect):
    need = [outcome, "gpr", aspect] + CONTROLS
    sample = frame[frame["country"].isin(countries)].dropna(subset=need).copy()
    sample = sample.rename(columns={aspect: "wgi"})
    # A within-country sample standard deviation needs at least two months.
    counts = sample.groupby("country")["gpr"].transform("size")
    sample = sample[counts >= 2].copy()
    if sample["country"].nunique() < 2 or sample.empty:
        return None
    sample["gpr_z"] = sample.groupby("country")["gpr"].transform(
        lambda s: (s - s.mean()) / s.std(ddof=1)
    )
    sample["wgi_c"] = sample["wgi"] - sample["wgi"].mean()
    sample["inter"] = sample["wgi_c"] * sample["gpr_z"]
    return sample


def fit_within(sample):
    x_cols = [name for name, _ in TERMS] + CONTROLS
    y_name = "y"
    work = sample.copy()
    cols = [y_name] + x_cols
    demeaned = work[cols] - work.groupby("country")[cols].transform("mean")
    y = demeaned[y_name].to_numpy(dtype=float)
    x = demeaned[x_cols].to_numpy(dtype=float)
    beta, _, rank, _ = np.linalg.lstsq(x, y, rcond=None)
    if rank < x.shape[1]:
        return None
    resid = y - x @ beta
    n = len(work)
    k = x.shape[1]
    g = int(work["country"].nunique())
    dof = n - k - g
    if dof <= 0:
        return None
    sse = float(resid @ resid)
    sst = float(y @ y)
    xtx_inv = np.linalg.inv(x.T @ x)
    se = np.sqrt(np.diag(xtx_inv) * (sse / dof))
    pvals = 2 * stats.t.sf(np.abs(beta / se), dof)
    return {
        "coef": dict(zip(x_cols, beta)),
        "se": dict(zip(x_cols, se)),
        "p": dict(zip(x_cols, pvals)),
        "n": n,
        "g": g,
        "dof": dof,
        "r2": 1 - sse / sst if sst > 0 else np.nan,
        "countries": sorted(work["country"].unique()),
        "date_min": work["date"].min(),
        "date_max": work["date"].max(),
        "wgi_mean": float(work["wgi"].mean()),
    }


def cell(fit, term):
    if fit is None:
        return "not estimated"
    coef = fit["coef"][term]
    se = fit["se"][term]
    mark = stars(fit["p"][term])
    return f"{fmt_num(coef)}{mark}<br>({fmt_num(se)})"


def stat_cell(fit, key, digits=None):
    if fit is None:
        return ""
    if key == "n":
        return f"{fit['n']:,}"
    if key == "r2":
        return f"{fit['r2']:.3f}"
    return "YES"


def country_line(label, countries, means, code, missing_by_outcome):
    ordered = means.loc[countries, code].sort_values(ascending=(label == "Bottom"))
    names = []
    for country, value in ordered.items():
        names.append(f"{DISPLAY.get(country, country)} ({value:.3f})")
    text = f"<p><strong>{label}:</strong> " + "; ".join(names) + "."
    notes = []
    for outcome, outcome_label in OUTCOMES:
        missing = missing_by_outcome[outcome]
        if missing:
            shown = ", ".join(DISPLAY.get(c, c) for c in missing)
            notes.append(f"No complete month for {outcome_label.lower()}: {shown}")
    if notes:
        text += " " + ". ".join(notes) + "."
    return text + "</p>"


def build():
    panel, means = load_panel()
    rows = []
    sections = []
    for code, aspect_name in ASPECTS:
        top = tail(means, code, high=True)
        bottom = tail(means, code, high=False)
        fits = {}
        missing = {}
        for group_name, members in (("Top", top), ("Bottom", bottom)):
            missing[group_name] = {}
            for outcome, _ in OUTCOMES:
                sample = prepare_sample(panel, outcome, members, code)
                if sample is None:
                    fit = None
                    used = []
                else:
                    sample = sample.copy()
                    sample["y"] = sample[outcome]
                    fit = fit_within(sample)
                    used = [] if fit is None else fit["countries"]
                fits[(group_name, outcome)] = fit
                missing[group_name][outcome] = [c for c in members if c not in used]
                if fit is None:
                    rows.append(
                        {
                            "aspect": code,
                            "aspect_name": aspect_name,
                            "group": group_name,
                            "outcome": outcome,
                            "term": "",
                            "coef": np.nan,
                            "se": np.nan,
                            "p": np.nan,
                            "stars": "",
                            "n": 0,
                            "countries_used": 0,
                            "r2": np.nan,
                            "selected": "; ".join(members),
                            "no_complete_month": "; ".join(missing[group_name][outcome]),
                        }
                    )
                    continue
                for term, term_label in TERMS:
                    rows.append(
                        {
                            "aspect": code,
                            "aspect_name": aspect_name,
                            "group": group_name,
                            "outcome": outcome,
                            "term": term_label,
                            "coef": fit["coef"][term],
                            "se": fit["se"][term],
                            "p": fit["p"][term],
                            "stars": stars(fit["p"][term]),
                            "n": fit["n"],
                            "countries_used": fit["g"],
                            "r2": fit["r2"],
                            "dof": fit["dof"],
                            "date_min": fit["date_min"].strftime("%Y-%m"),
                            "date_max": fit["date_max"].strftime("%Y-%m"),
                            "wgi_mean": fit["wgi_mean"],
                            "selected": "; ".join(members),
                            "used": "; ".join(used),
                            "no_complete_month": "; ".join(missing[group_name][outcome]),
                        }
                    )
        header = (
            "<tr><th></th>"
            "<th colspan='2'>Top five</th><th colspan='2'>Bottom five</th></tr>"
            "<tr><th></th>"
            "<th>(1)<br>Capital-flow volatility</th><th>(2)<br>Exchange rate</th>"
            "<th>(3)<br>Capital-flow volatility</th><th>(4)<br>Exchange rate</th></tr>"
        )
        body = []
        for term, label in TERMS:
            body.append(
                "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                    label,
                    cell(fits[("Top", "capital_flow_volatility")], term),
                    cell(fits[("Top", "ln_reer")], term),
                    cell(fits[("Bottom", "capital_flow_volatility")], term),
                    cell(fits[("Bottom", "ln_reer")], term),
                )
            )
        for key, label in (
            ("n", "Observations"),
            ("r2", "R-squared"),
            ("controls", "Controls"),
            ("fe", "Country fixed effects"),
        ):
            vals = []
            for group_name, outcome in (
                ("Top", "capital_flow_volatility"),
                ("Top", "ln_reer"),
                ("Bottom", "capital_flow_volatility"),
                ("Bottom", "ln_reer"),
            ):
                if key in {"controls", "fe"}:
                    vals.append("YES" if fits[(group_name, outcome)] is not None else "")
                else:
                    vals.append(stat_cell(fits[(group_name, outcome)], key))
            body.append("<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(label, *vals))
        sections.append(
            f"<h2>{aspect_name}</h2>"
            + country_line("Top", top, means, code, missing["Top"])
            + country_line("Bottom", bottom, means, code, missing["Bottom"])
            + "<table><thead>"
            + header
            + "</thead><tbody>"
            + "".join(body)
            + "</tbody></table>"
            + "<p class='note'>Standard errors in parentheses. *** p&lt;0.01, ** p&lt;0.05, * p&lt;0.10. "
            "The R-squared is the within R-squared. Controls are lagged one month: the policy rate, "
            "log real industrial production, inflation, log oil, log VIX, log global EPU, "
            "financial development, central-bank independence, and debt to GDP.</p>"
        )
    pd.DataFrame(rows).to_csv(CSV_PATH, index=False)
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Emerging economies, WGI top and bottom five</title>
<style>
body {{ font: 16px/1.5 Georgia, serif; max-width: 980px; margin: 2em auto; padding: 0 1em; color: #20242a; }}
table {{ border-collapse: collapse; width: 100%; margin: 1em 0 0.4em; font-size: .92em; }}
th, td {{ border-bottom: 1px solid #ccc; padding: .45em; text-align: right; vertical-align: top; }}
th:first-child, td:first-child {{ text-align: left; }}
.note {{ color: #333; font-size: .92em; }}
h2 {{ margin-top: 1.8em; }}
</style>
</head>
<body>
<h1>Emerging economies: GPR and WGI, top five and bottom five</h1>
<p>Each table is one WGI aspect. Countries are the 15 emerging economies, ranked by their average score over 2000–2021. Averages in parentheses are those country scores. The top five and the bottom five are estimated separately. Each observation is a country-month from January 2000 through December 2023, kept only when the outcome and every regressor are observed.</p>
{''.join(sections)}
</body>
</html>
"""
    with open(HTML_PATH, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(html)
    print(f"Wrote {HTML_PATH}")
    print(f"Wrote {CSV_PATH}")
    print(pd.DataFrame(rows).groupby(["aspect_name", "group", "outcome"])["n"].max().to_string())


if __name__ == "__main__":
    build()
