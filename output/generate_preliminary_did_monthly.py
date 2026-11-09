import csv
import math
import os
from collections import defaultdict
from datetime import date
from html import escape

import numpy as np
from openpyxl import load_workbook
from scipy.stats import t as student_t

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt


ROOT = r"C:\0 UST CourseWork\ECON4999B\econ4999b_research"
CLEANED_DIR = os.path.join(ROOT, "cleaned")
OUTPUT_DIR = os.path.join(ROOT, "output")
FIG_DIR = os.path.join(OUTPUT_DIR, "figures")

os.makedirs(FIG_DIR, exist_ok=True)


SHOCK_MONTHS = {
    "E03": "2003-03",
    "E09": "2011-03",
    "E13": "2020-01",
    "E14": "2022-02",
    "E16": "2023-10",
    "E17": "2024-04",
    "E19": "2025-06",
    "E20": "2026-02",
}

COUNTRY_MAP = {
    "Türkiye": "Turkey",
}

DIMENSIONS = [("rl", "Rule of law"), ("ge", "Government effectiveness")]
TREND_PRE_MONTHS = 6
TREND_POST_MONTHS = 6

CONTROL_NAMES = [
    "inflation_l1",
    "policy_rate_l1",
    "debt_gdp_l1",
    "financial_development_l1",
    "oil_price_l1",
    "vix_l1",
    "gepu_l1",
]


def parse_month(s):
    y, m = s.split("-")
    return date(int(y), int(m), 1)


def month_str(d):
    return f"{d.year:04d}-{d.month:02d}"


def add_months(d, n):
    ym = d.year * 12 + d.month - 1 + n
    y = ym // 12
    m = ym % 12 + 1
    return date(y, m, 1)


def month_range(start, end):
    cur = start
    out = []
    while cur <= end:
        out.append(cur)
        cur = add_months(cur, 1)
    return out


def cell(row, idx, default=None):
    if row is None:
        return default
    if idx < len(row):
        return row[idx]
    return default


def read_fx():
    path = os.path.join(CLEANED_DIR, "fx_rate.csv")
    fx = defaultdict(dict)
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            c = row["country"].strip()
            m = row["year_month"].strip()
            v = row["local_per_usd"].strip()
            if not v:
                continue
            fx[c][m] = float(v)
    return fx


def read_wgi():
    path = os.path.join(CLEANED_DIR, "wgi.csv")
    wgi = defaultdict(lambda: defaultdict(dict))
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            c = row["country"].strip()
            d = row["dimension"].strip().lower()
            y = int(row["year"])
            v = row["estimate"].strip()
            if not v:
                continue
            wgi[c][d][y] = float(v)
    return wgi


def read_monthly_country_series(file_name, value_col):
    path = os.path.join(CLEANED_DIR, file_name)
    out = defaultdict(dict)
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            c = row["country"].strip()
            m = row["year_month"].strip()
            v = row[value_col].strip()
            if not v:
                continue
            out[c][m] = float(v)
    return out


def read_monthly_global_series(file_name, value_col):
    path = os.path.join(CLEANED_DIR, file_name)
    out = {}
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            m = row["year_month"].strip()
            v = row[value_col].strip()
            if not v:
                continue
            out[m] = float(v)
    return out


def read_annual_country_series(file_name, year_col, value_col):
    path = os.path.join(CLEANED_DIR, file_name)
    out = defaultdict(dict)
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            c = row["country"].strip()
            y = row[year_col].strip()
            v = row[value_col].strip()
            if not y or not v:
                continue
            out[c][int(y)] = float(v)
    return out


def get_wgi_value(wgi, country, dim, year):
    series = wgi.get(country, {}).get(dim, {})
    if year in series:
        return series[year]
    if year == 2026 and 2025 in series:
        return series[2025]
    return None


def read_shock_workbook():
    wb = load_workbook(
        os.path.join(CLEANED_DIR, "oil_related_geopolitical_shocks_imf.xlsx"),
        read_only=True,
        data_only=True,
    )

    episodes = {}
    ws_ep = wb["Episode lists"]
    for row in ws_ep.iter_rows(min_row=7, max_row=80, values_only=True):
        if not row or len(row) == 0:
            continue
        ep = cell(row, 0)
        if not ep or not isinstance(ep, str) or ep not in SHOCK_MONTHS:
            continue
        if cell(row, 1) in (None, ""):
            continue
        if not isinstance(cell(row, 3), (int, float)):
            continue
        episodes[ep] = {
            "episode": ep,
            "event": cell(row, 1),
            "shock_type": cell(row, 2),
            "selected_count_workbook": cell(row, 3),
            "eligible_count_workbook": cell(row, 4),
        }

    selected = defaultdict(list)
    ws_sel = wb["Selected countries"]
    for row in ws_sel.iter_rows(min_row=7, max_row=300, values_only=True):
        if not row or len(row) < 9:
            continue
        ep = cell(row, 0)
        if not ep or not isinstance(ep, str) or not ep.startswith("E"):
            continue
        status = cell(row, 7)
        if status != "Selected":
            continue
        raw_country = cell(row, 2)
        if not raw_country:
            continue
        mapped = COUNTRY_MAP.get(raw_country, raw_country)
        selected[ep].append(
            {
                "episode": ep,
                "country_raw": raw_country,
                "country": mapped,
                "rank": cell(row, 1),
                "increase_pct": cell(row, 3),
                "shock_type": cell(row, 8),
            }
        )
    return episodes, selected


def fit_did_clustered(obs, control_names):
    y = np.array([x["y"] for x in obs], dtype=float)
    treat = np.array([x["treat"] for x in obs], dtype=float)
    post = np.array([x["post"] for x in obs], dtype=float)
    inter = treat * post
    control_cols = []
    for c in control_names:
        control_cols.append(np.array([x["controls"][c] for x in obs], dtype=float))
    X_parts = [np.ones(len(y)), treat, post, inter] + control_cols
    X = np.column_stack(X_parts)
    n, k = X.shape
    if n <= k:
        return None, "Insufficient observations after filtering (N <= number of parameters)."

    counts = {
        (0, 0): 0,
        (0, 1): 0,
        (1, 0): 0,
        (1, 1): 0,
    }
    for t, p in zip(treat, post):
        counts[(int(t), int(p))] += 1
    zero_cells = [cell for cell, c in counts.items() if c == 0]
    if zero_cells:
        return None, f"DiD not identified: empty group-period cells {zero_cells}."

    try:
        xtx_inv = np.linalg.inv(X.T @ X)
    except np.linalg.LinAlgError:
        return None, "Regression design matrix is singular."

    beta = xtx_inv @ (X.T @ y)
    resid = y - (X @ beta)

    clusters = defaultdict(list)
    for i, row in enumerate(obs):
        clusters[row["country"]].append(i)
    g = len(clusters)

    if g > 1:
        meat = np.zeros((k, k), dtype=float)
        for idxs in clusters.values():
            xg = X[idxs, :]
            ug = resid[idxs]
            s = xg.T @ ug
            meat += np.outer(s, s)
        v = xtx_inv @ meat @ xtx_inv
        if g > 1 and n > k:
            v *= (g / (g - 1)) * ((n - 1) / (n - k))
        df = g - 1
        se_type = "cluster(country)"
    else:
        xu = X * resid[:, None]
        meat = xu.T @ xu
        v = xtx_inv @ meat @ xtx_inv
        if n > k:
            v *= n / (n - k)
        df = n - k
        se_type = "HC1"

    se = np.sqrt(np.clip(np.diag(v), a_min=0.0, a_max=None))
    with np.errstate(divide="ignore", invalid="ignore"):
        tvals = beta / se
    pvals = 2 * (1 - student_t.cdf(np.abs(tvals), df=df))
    ci_lo = beta - student_t.ppf(0.975, df=df) * se
    ci_hi = beta + student_t.ppf(0.975, df=df) * se

    result = {
        "beta": beta,
        "se": se,
        "t": tvals,
        "p": pvals,
        "ci_lo": ci_lo,
        "ci_hi": ci_hi,
        "n_obs": n,
        "n_country": g,
        "df": df,
        "se_type": se_type,
        "cell_counts": counts,
        "k_params": k,
    }
    return result, None


def stars(p):
    if p < 0.01:
        return "***"
    if p < 0.05:
        return "**"
    if p < 0.10:
        return "*"
    return ""


def make_plot(obs, episode, dim_code, dim_label, shock_dt):
    grouped = {0: defaultdict(list), 1: defaultdict(list)}
    for row in obs:
        grouped[row["treat"]][row["month"]].append(row["y"])

    fig, ax = plt.subplots(figsize=(10, 5.2))
    colors = {0: "#b42318", 1: "#1f4e8c"}
    labels = {0: "Bad institutions (0)", 1: "Good institutions (1)"}

    any_drawn = False
    for g in [0, 1]:
        if not grouped[g]:
            continue
        months = sorted(grouped[g].keys())
        means = []
        lo = []
        hi = []
        for m in months:
            vals = np.array(grouped[g][m], dtype=float)
            mu = float(np.mean(vals))
            means.append(mu)
            if len(vals) >= 2:
                se = float(np.std(vals, ddof=1) / math.sqrt(len(vals)))
                c = 1.96 * se
                if m > shock_dt:
                    lo.append(mu - c)
                    hi.append(mu + c)
                else:
                    lo.append(np.nan)
                    hi.append(np.nan)
            else:
                lo.append(np.nan)
                hi.append(np.nan)
        ax.plot(months, means, color=colors[g], linewidth=2, label=labels[g])
        ax.fill_between(months, lo, hi, color=colors[g], alpha=0.16)
        any_drawn = True

    window_start = add_months(shock_dt, -TREND_PRE_MONTHS)
    window_end = add_months(shock_dt, TREND_POST_MONTHS)
    ax.axvspan(window_start, shock_dt, color="#f3f4f6", alpha=0.45, label="Pre-shock window")
    ax.axvspan(add_months(shock_dt, 1), window_end, color="#eef6ff", alpha=0.35, label="Post-shock window")
    ax.axvline(shock_dt, color="#404040", linestyle="--", linewidth=1.4, label="Shock month")
    ax.set_title(f"{episode} — {dim_label}: Monthly exchange-rate change around shock")
    ax.set_ylabel("100 × ln(local_per_usd / pre-shock monthly mean)")
    ax.set_xlabel("Month")
    ax.grid(True, alpha=0.25)
    ax.set_xlim(window_start, window_end)
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    ax.legend(loc="best")
    fig.tight_layout()

    out_name = f"{episode}_{dim_code}.png"
    out_path = os.path.join(FIG_DIR, out_name)
    if any_drawn:
        fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_name if any_drawn else None


def get_controls_for_month(country, month_dt, controls):
    lag_month_dt = add_months(month_dt, -1)
    lag_month = month_str(lag_month_dt)
    lag_year = lag_month_dt.year
    out = {}
    missing = []

    country_monthly = controls["country_monthly"]
    country_annual = controls["country_annual"]
    global_monthly = controls["global_monthly"]

    country_mapping = [
        ("inflation_l1", country_monthly["inflation"], lag_month),
        ("policy_rate_l1", country_monthly["policy_rate"], lag_month),
        ("debt_gdp_l1", country_annual["debt_gdp"], lag_year),
        ("financial_development_l1", country_annual["financial_development"], lag_year),
    ]

    for name, series, key in country_mapping:
        val = series.get(country, {}).get(key)
        if val is None:
            missing.append(name)
        else:
            out[name] = val

    global_mapping = [
        ("oil_price_l1", global_monthly["oil_price"], lag_month),
        ("vix_l1", global_monthly["vix"], lag_month),
        ("gepu_l1", global_monthly["gepu"], lag_month),
    ]
    for name, series, key in global_mapping:
        if name in out:
            continue
        val = series.get(key)
        if val is None:
            if name not in missing:
                missing.append(name)
        else:
            out[name] = val
            if name in missing:
                missing.remove(name)

    return out, missing


def build_trend_obs(fx, used_countries, treat_map, shock_dt):
    trend_window = month_range(add_months(shock_dt, -TREND_PRE_MONTHS), add_months(shock_dt, TREND_POST_MONTHS))
    trend = []
    base_month = month_str(add_months(shock_dt, -1))
    for c in used_countries:
        if c not in treat_map:
            continue
        pre_raw = fx[c].get(base_month)
        if pre_raw is None or pre_raw <= 0:
            continue
        for m in trend_window:
            ms = month_str(m)
            raw = fx[c].get(ms)
            if raw is None or raw <= 0:
                continue
            dep = 100.0 * math.log(raw / pre_raw)
            trend.append(
                {
                    "country": c,
                    "month": m,
                    "y": dep,
                    "treat": treat_map[c],
                    "post": 1 if m > add_months(shock_dt, -1) else 0,
                }
            )
    return trend


def run():
    fx = read_fx()
    wgi = read_wgi()
    episodes_meta, selected = read_shock_workbook()
    controls = {
        "country_monthly": {
            "inflation": read_monthly_country_series("inflation.csv", "value"),
            "policy_rate": read_monthly_country_series("policy_rate.csv", "value"),
        },
        "country_annual": {
            "debt_gdp": read_annual_country_series("debt_gdp.csv", "period", "debt_gdp_pct"),
            "financial_development": read_annual_country_series(
                "financial_development.csv", "year", "fd_fdi_ovrl"
            ),
        },
        "global_monthly": {
            "oil_price": read_monthly_global_series("oil_price.csv", "wti_spot"),
            "vix": read_monthly_global_series("vix.csv", "value"),
            "gepu": read_monthly_global_series("gepu_current.csv", "value"),
        },
    }

    available_fx_countries = set(fx.keys())
    all_results = []
    all_limits = []
    episode_sections = []

    for ep in sorted(selected.keys()):
        meta = episodes_meta.get(ep, {"event": None, "shock_type": None})
        shock_month = SHOCK_MONTHS.get(ep)
        if not shock_month:
            all_limits.append(
                {
                    "episode": ep,
                    "dimension": "all",
                    "reason": "Shock month not specified; model not estimated for this episode.",
                }
            )
            continue
        shock_dt = parse_month(shock_month)
        pre_month_dt = add_months(shock_dt, -1)
        post_month_dt = add_months(shock_dt, 1)
        window = [pre_month_dt, post_month_dt]
        pre_month = month_str(pre_month_dt)
        post_month = month_str(post_month_dt)

        sel_rows = selected[ep]
        selected_countries = sorted({r["country"] for r in sel_rows})
        missing_from_fx = sorted([c for c in selected_countries if c not in available_fx_countries])
        used_countries = [c for c in selected_countries if c in available_fx_countries]

        section = {
            "episode": ep,
            "event": meta.get("event") or "",
            "shock_type": meta.get("shock_type") or "",
            "shock_month": shock_month,
            "pre_month": pre_month,
            "post_month": post_month,
            "selected_countries": selected_countries,
            "missing_from_fx": missing_from_fx,
            "dimension_blocks": [],
        }

        for dim_code, dim_label in DIMENSIONS:
            if not used_countries:
                reason = "No selected countries are present in cleaned/fx_rate.csv."
                all_limits.append({"episode": ep, "dimension": dim_code, "reason": reason})
                section["dimension_blocks"].append(
                    {"dimension": dim_label, "status": "not_estimated", "reason": reason}
                )
                continue

            pre_year = pre_month_dt.year
            vals = []
            for c in selected_countries:
                v = get_wgi_value(wgi, c, dim_code, pre_year)
                if v is not None:
                    vals.append(v)
            if not vals:
                reason = f"No available WGI values for pre-shock year {pre_year}."
                all_limits.append({"episode": ep, "dimension": dim_code, "reason": reason})
                section["dimension_blocks"].append(
                    {"dimension": dim_label, "status": "not_estimated", "reason": reason}
                )
                continue
            pre_year_mean = float(np.mean(vals))

            treat_map = {}
            missing_wgi = []
            for c in used_countries:
                wv = get_wgi_value(wgi, c, dim_code, pre_year)
                if wv is None:
                    missing_wgi.append(c)
                    continue
                treat_map[c] = 1 if wv > pre_year_mean else 0

            obs = []
            missing_fx_pairs = []
            missing_controls = defaultdict(set)
            for c in used_countries:
                if c not in treat_map:
                    continue
                pre_raw = fx[c].get(pre_month)
                post_raw = fx[c].get(post_month)
                if pre_raw is None or post_raw is None:
                    missing_fx_pairs.append(c)
                    continue
                if pre_raw <= 0 or post_raw <= 0:
                    continue
                treat = treat_map[c]
                pre_controls, pre_missing = get_controls_for_month(c, pre_month_dt, controls)
                post_controls, post_missing = get_controls_for_month(c, post_month_dt, controls)
                if pre_missing:
                    for item in pre_missing:
                        missing_controls[c].add(item)
                if post_missing:
                    for item in post_missing:
                        missing_controls[c].add(item)
                if pre_missing or post_missing:
                    continue
                obs.append(
                    {
                        "country": c,
                        "month": pre_month_dt,
                        "y": 0.0,
                        "treat": treat,
                        "post": 0,
                        "controls": pre_controls,
                    }
                )
                obs.append(
                    {
                        "country": c,
                        "month": post_month_dt,
                        "y": 100.0 * math.log(post_raw / pre_raw),
                        "treat": treat,
                        "post": 1,
                        "controls": post_controls,
                    }
                )

            fit, err = (
                fit_did_clustered(obs, CONTROL_NAMES) if obs else (None, "No usable monthly observations.")
            )
            if err:
                reason = err
                if missing_wgi:
                    reason += f" Missing pre-year WGI for: {', '.join(sorted(missing_wgi))}."
                if missing_fx_pairs:
                    reason += f" Missing pre/post FX pair for: {', '.join(sorted(set(missing_fx_pairs)))}."
                if missing_controls:
                    parts = []
                    for country_name in sorted(missing_controls.keys()):
                        parts.append(f"{country_name} ({', '.join(sorted(missing_controls[country_name]))})")
                    reason += " Missing lagged controls for: " + "; ".join(parts) + "."
                all_limits.append({"episode": ep, "dimension": dim_code, "reason": reason})
                section["dimension_blocks"].append(
                    {"dimension": dim_label, "status": "not_estimated", "reason": reason}
                )
                continue

            trend_obs = build_trend_obs(fx, used_countries, treat_map, shock_dt)
            fig_name = make_plot(trend_obs if trend_obs else obs, ep, dim_code, dim_label, shock_dt)
            theta_idx = 3
            res = {
                "episode": ep,
                "event": meta.get("event") or "",
                "shock_type": meta.get("shock_type") or "",
                "shock_month": shock_month,
                "dimension": dim_code,
                "dimension_label": dim_label,
                "n_obs": fit["n_obs"],
                "n_country": fit["n_country"],
                "se_type": fit["se_type"],
                "theta": float(fit["beta"][theta_idx]),
                "theta_se": float(fit["se"][theta_idx]),
                "theta_t": float(fit["t"][theta_idx]),
                "theta_p": float(fit["p"][theta_idx]),
                "theta_ci_lo": float(fit["ci_lo"][theta_idx]),
                "theta_ci_hi": float(fit["ci_hi"][theta_idx]),
                "cell_counts": fit["cell_counts"],
                "pre_year": pre_year,
                "pre_year_mean": pre_year_mean,
                "missing_wgi_countries": sorted(missing_wgi),
                "missing_fx_pair_countries": sorted(set(missing_fx_pairs)),
                "missing_controls": {
                    c: sorted(list(v)) for c, v in sorted(missing_controls.items(), key=lambda x: x[0])
                },
                "k_params": fit["k_params"],
                "figure": fig_name,
                "chart_window_start": month_str(add_months(shock_dt, -TREND_PRE_MONTHS)),
                "chart_window_end": month_str(add_months(shock_dt, TREND_POST_MONTHS)),
                "inferential_ok": fit["n_country"] >= 5,
            }
            if not res["inferential_ok"]:
                all_limits.append(
                    {
                        "episode": ep,
                        "dimension": dim_code,
                        "reason": (
                            "Significance test not reliable with fewer than 5 country clusters; "
                            "coefficients shown as descriptive only."
                        ),
                    }
                )
            all_results.append(res)
            section["dimension_blocks"].append(
                {
                    "dimension": dim_label,
                    "status": "estimated",
                    "result": res,
                }
            )

        episode_sections.append(section)

    csv_path = os.path.join(OUTPUT_DIR, "preliminary_did_monthly_results.csv")
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "episode",
                "event",
                "shock_type",
                "shock_month",
                "dimension",
                "n_obs",
                "n_country",
                "theta_did",
                "theta_se",
                "t_value",
                "p_value",
                "ci95_lo",
                "ci95_hi",
                "se_type",
                "k_params",
                "controls",
                "cell_00_control_pre",
                "cell_01_control_post",
                "cell_10_treated_pre",
                "cell_11_treated_post",
            ]
        )
        for r in all_results:
            cc = r["cell_counts"]
            w.writerow(
                [
                    r["episode"],
                    r["event"],
                    r["shock_type"],
                    r["shock_month"],
                    r["dimension"],
                    r["n_obs"],
                    r["n_country"],
                    r["theta"],
                    r["theta_se"],
                    r["theta_t"],
                    r["theta_p"] if r["inferential_ok"] else "",
                    r["theta_ci_lo"],
                    r["theta_ci_hi"],
                    r["se_type"],
                    r["k_params"],
                    ";".join(CONTROL_NAMES),
                    cc[(0, 0)],
                    cc[(0, 1)],
                    cc[(1, 0)],
                    cc[(1, 1)],
                ]
            )

    html_path = os.path.join(OUTPUT_DIR, "preliminary_did_monthly_results.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write("<!doctype html><html lang='en'><head><meta charset='utf-8'>")
        f.write("<title>Preliminary monthly DiD results</title>")
        f.write(
            "<style>"
            "body{font:16px/1.5 Georgia,serif;max-width:1200px;margin:2em auto;padding:0 1em;color:#20242a}"
            "table{border-collapse:collapse;width:100%;margin:1em 0;font-size:.9em}"
            "th,td{border-bottom:1px solid #ccc;padding:.45em;text-align:right}"
            "th:first-child,td:first-child{text-align:left}"
            ".note{background:#fff5da;padding:1em;border:1px solid #e6d59d}"
            ".warn{background:#ffe6e6;padding:.8em;border:1px solid #e0a7a7}"
            ".ok{background:#eef7ee;padding:.8em;border:1px solid #b6d5b6}"
            "img{max-width:980px;width:100%;height:auto;border:1px solid #ddd}"
            "code{font-size:.92em}"
            "</style></head><body>"
        )
        f.write("<h1>Preliminary monthly difference-in-differences (augmented): exchange-rate response to geopolitical shocks</h1>")
        f.write(
            "<p>This report replicates a preliminary DiD design at monthly frequency using cleaned data, "
            "with new shock-country episodes from <code>cleaned/oil_related_geopolitical_shocks_imf.xlsx</code>.</p>"
        )
        f.write("<h2>Model and construction choices</h2>")
        f.write("<ul>")
        f.write("<li>Reference framework from the PDF (<code>doc/how GRP affect FX and capital flow.pdf</code>): monthly GPR context, exchange-rate channel, and macro/global controls.</li>")
        f.write("<li>Outcome (<em>Y</em>): immediate exchange-rate change from just two values: <code>100 × ln(FX[t+1] / FX[t-1])</code>. The pre-shock row is 0 and the post-shock row is this change.</li>")
        f.write("<li>No averaging is used for exchange-rate levels: only month <code>t-1</code> (before shock) and month <code>t+1</code> (right after shock) are used.</li>")
        f.write("<li>Charts are for trend visualization only and use a 13-month window around the shock (<code>t-6</code> to <code>t+6</code>), normalized by <code>t-1</code> for each country.</li>")
        f.write("<li>Treatment/control: good institution (=1) if country WGI score in the pre-shock year is strictly above the selected-country mean in that pre-shock year; otherwise 0.</li>")
        f.write("<li>Dimensions: Rule of Law (<code>rl</code>) and Government Effectiveness (<code>ge</code>).</li>")
        f.write("<li>Augmented DiD model: <code>Y = α + δ·Treat + γ·Post + θ·(Treat×Post) + β'Controls + ε</code>; θ is the DiD effect.</li>")
        f.write("<li>Lagged controls (t−1): country inflation, policy rate, debt-to-GDP, financial development; global WTI oil price, VIX, and GEPU.</li>")
        f.write("<li>Shock months were set from episode chronology: E03=2003-03, E09=2011-03, E13=2020-01, E14=2022-02, E16=2023-10, E17=2024-04, E19=2025-06, E20=2026-02.</li>")
        f.write("</ul>")
        f.write(
            "<div class='note'><strong>Important:</strong> WGI has no 2026 publication in cleaned data. "
            "Following the prior report logic, 2026 uses 2025 WGI values only for classification.</div>"
        )

        f.write("<h2>Main regression table (interaction term θ)</h2>")
        f.write(
            "<table><thead><tr>"
            "<th>Episode</th><th>Shock month</th><th>Dimension</th><th>N obs</th><th>N countries</th>"
            "<th>θ (Treat×Post)</th><th>SE</th><th>t</th><th>p</th><th>95% CI</th><th>SE type</th><th>k params</th>"
            "</tr></thead><tbody>"
        )
        if all_results:
            for r in sorted(all_results, key=lambda x: (x["episode"], x["dimension"])):
                p_text = f"{r['theta_p']:.4f}" if r["inferential_ok"] else "N/A (&lt;5 clusters)"
                ci_text = (
                    f"[{r['theta_ci_lo']:.4f}, {r['theta_ci_hi']:.4f}]"
                    if r["inferential_ok"]
                    else "N/A (&lt;5 clusters)"
                )
                f.write(
                    "<tr>"
                    f"<td>{escape(r['episode'])}</td>"
                    f"<td>{escape(r['shock_month'])}</td>"
                    f"<td>{escape(r['dimension_label'])}</td>"
                    f"<td>{r['n_obs']}</td>"
                    f"<td>{r['n_country']}</td>"
                    f"<td>{r['theta']:.4f}{stars(r['theta_p']) if r['inferential_ok'] else ''}</td>"
                    f"<td>{r['theta_se']:.4f}</td>"
                    f"<td>{r['theta_t']:.3f}</td>"
                    f"<td>{p_text}</td>"
                    f"<td>{ci_text}</td>"
                    f"<td>{escape(r['se_type'])}</td>"
                    f"<td>{r['k_params']}</td>"
                    "</tr>"
                )
        else:
            f.write("<tr><td colspan='12'>No estimable episode-dimension models.</td></tr>")
        f.write("</tbody></table>")
        f.write("<p><em>Significance stars:</em> *** p&lt;0.01, ** p&lt;0.05, * p&lt;0.10.</p>")

        f.write("<h2>Limitations and non-estimable cases</h2>")
        if all_limits:
            f.write("<table><thead><tr><th>Episode</th><th>Dimension</th><th>Problem / limitation</th></tr></thead><tbody>")
            for lim in all_limits:
                dlab = lim["dimension"]
                if dlab == "rl":
                    dlab = "Rule of law"
                elif dlab == "ge":
                    dlab = "Government effectiveness"
                f.write(
                    "<tr>"
                    f"<td>{escape(lim['episode'])}</td>"
                    f"<td>{escape(dlab)}</td>"
                    f"<td style='text-align:left'>{escape(lim['reason'])}</td>"
                    "</tr>"
                )
            f.write("</tbody></table>")
        else:
            f.write("<div class='ok'>All planned episode-dimension models were estimated.</div>")

        f.write("<h2>Episode-by-episode details and DiD trend charts</h2>")
        for sec in episode_sections:
            f.write(f"<h3>{escape(sec['episode'])}: {escape(sec['event'])}</h3>")
            f.write(
                f"<p><strong>Shock month:</strong> {escape(sec['shock_month'])} | "
                f"<strong>Shock type:</strong> {escape(sec['shock_type'])}</p>"
            )
            f.write(
                f"<p><strong>FX months used:</strong> before = {escape(sec['pre_month'])}, "
                f"after = {escape(sec['post_month'])}</p>"
            )
            f.write(
                "<p><strong>Selected countries (workbook):</strong> "
                + escape(", ".join(sec["selected_countries"]))
                + "</p>"
            )
            if sec["missing_from_fx"]:
                f.write(
                    "<div class='warn'><strong>Coverage warning:</strong> The following selected countries "
                    "were not found in cleaned FX data and were excluded: "
                    + escape(", ".join(sec["missing_from_fx"]))
                    + ".</div>"
                )
            for block in sec["dimension_blocks"]:
                f.write(f"<h4>{escape(block['dimension'])}</h4>")
                if block["status"] != "estimated":
                    f.write("<div class='warn'>" + escape(block["reason"]) + "</div>")
                    continue
                r = block["result"]
                p_text = f"{r['theta_p']:.4f}" if r["inferential_ok"] else "N/A; <5 clusters"
                f.write(
                    "<p>"
                    f"N={r['n_obs']} monthly observations across {r['n_country']} countries. "
                    f"θ={r['theta']:.4f} (SE={r['theta_se']:.4f}, "
                    f"p={p_text})."
                    "</p>"
                )
                cc = r["cell_counts"]
                f.write(
                    "<p>Group-period counts "
                    f"(control/pre, control/post, treated/pre, treated/post): "
                    f"{cc[(0,0)]}, {cc[(0,1)]}, {cc[(1,0)]}, {cc[(1,1)]}.</p>"
                )
                f.write(
                    f"<p>Pre-shock WGI year for grouping: {r['pre_year']} "
                    f"(selected-country mean = {r['pre_year_mean']:.4f}).</p>"
                )
                if r["missing_wgi_countries"]:
                    f.write(
                        "<div class='warn'>Dropped due to missing pre-year WGI: "
                        + escape(", ".join(r["missing_wgi_countries"]))
                        + ".</div>"
                    )
                if r["missing_fx_pair_countries"]:
                    f.write(
                        "<div class='warn'>Dropped due to missing immediate pre/post FX values: "
                        + escape(", ".join(r["missing_fx_pair_countries"]))
                        + ".</div>"
                    )
                if r["missing_controls"]:
                    msg = []
                    for cname, vars_missing in r["missing_controls"].items():
                        msg.append(f"{cname} ({', '.join(vars_missing)})")
                    f.write(
                        "<div class='warn'>Dropped due to missing lagged controls: "
                        + escape("; ".join(msg))
                        + ".</div>"
                    )
                if r["figure"]:
                    fig_rel = f"figures/{r['figure']}"
                    f.write(f"<img src='{escape(fig_rel)}' alt='{escape(r['episode'])} {escape(r['dimension'])} chart'>")
                    f.write(
                        f"<p><em>Trend chart window: {r['chart_window_start']} to {r['chart_window_end']}. "
                        "Shaded area shows 95% confidence bands only for months after the shock (normal approximation).</em></p>"
                    )
        f.write("</body></html>")

    print("Generated:")
    print(html_path)
    print(csv_path)
    print(FIG_DIR)
    print(f"Estimated models: {len(all_results)} | Non-estimable cases: {len(all_limits)}")


if __name__ == "__main__":
    run()
