import csv
import json
import math
import os
from collections import defaultdict
from datetime import date
from html import escape

import numpy as np
from scipy.stats import t as student_t
from openpyxl import load_workbook


ROOT = r"C:\0 UST CourseWork\ECON4999B\econ4999b_research"
PANEL_CSV = os.path.join(
    ROOT,
    "econ4999b_literature_review",
    "replication",
    "output",
    "panel.csv",
)
INST_CSV = os.path.join(ROOT, "output", "wgi_merged_3nf.csv")
SCREENED_COUNTRY_CSV = os.path.join(ROOT, "cleaned", "country.csv")
REER_XLSX = os.path.join(ROOT, "cleaned", "real effective exchange rate.xlsx")
POLICY_CSV = os.path.join(ROOT, "cleaned", "policy_rate.csv")
INFL_CSV = os.path.join(ROOT, "cleaned", "inflation.csv")
FD_CSV = os.path.join(ROOT, "cleaned", "financial_development.csv")
DEBT_CSV = os.path.join(ROOT, "cleaned", "debt_gdp.csv")
OIL_CSV = os.path.join(ROOT, "cleaned", "oil_price.csv")
VIX_CSV = os.path.join(ROOT, "cleaned", "vix.csv")
GEPU_CSV = os.path.join(ROOT, "cleaned", "gepu_current.csv")
GPR_CSV = os.path.join(ROOT, "cleaned", "gpr_index.csv")
CBI_XLSX = os.path.join(ROOT, "econ4999b_literature_review", "replication", "raw", "cbi_2025.xlsx")
OUT_DIR = os.path.join(ROOT, "output")
RESULTS_CSV = os.path.join(OUT_DIR, "equation1_six_aspects_results.csv")
RESULTS_HTML = os.path.join(OUT_DIR, "equation1_six_aspects_results.html")
PLOTS_HTML = os.path.join(OUT_DIR, "equation1_six_aspects_plots.html")
EXPANDED17_RESULTS_CSV = os.path.join(OUT_DIR, "equation1_six_aspects_results_expanded17.csv")
EXPANDED17_RESULTS_HTML = os.path.join(OUT_DIR, "equation1_six_aspects_results_expanded17.html")
TWO_TABLES_HTML = os.path.join(OUT_DIR, "equation1_six_aspects_results_two_tables.html")

START_YEAR = 2000
END_YEAR = 2023
ASPECTS = ["va", "pv", "ge", "rq", "rl", "cc"]

ARTICLE_COUNTRIES = {
    "Belgium": "BE",
    "Brazil": "BR",
    "Canada": "CA",
    "Chile": "CL",
    "China": "CN",
    "Colombia": "CO",
    "Germany": "DE",
    "Denmark": "DK",
    "Spain": "ES",
    "Finland": "FI",
    "France": "FR",
    "Hungary": "HU",
    "Indonesia": "ID",
    "India": "IN",
    "Italy": "IT",
    "Japan": "JP",
    "Korea": "KR",
    "Mexico": "MX",
    "Malaysia": "MY",
    "Netherlands": "NL",
    "Philippines": "PH",
    "Poland": "PL",
    "Portugal": "PT",
    "Sweden": "SE",
    "Thailand": "TH",
    "Türkiye": "TR",
    "Ukraine": "UA",
    "United States": "US",
    "South Africa": "ZA",
}
ISO_TO_ARTICLE_COUNTRY = {v: k for k, v in ARTICLE_COUNTRIES.items()}
INST_COUNTRY_ALIASES = {"Korea": "South Korea", "Türkiye": "Turkey"}
SCREENED_COUNTRY_TO_ISO = {
    "Mexico": "MX",
    "Argentina": "AR",
    "Chile": "CL",
    "Peru": "PE",
    "Hungary": "HU",
    "Ukraine": "UA",
    "Turkey": "TR",
    "Egypt": "EG",
    "Tunisia": "TN",
    "South Africa": "ZA",
    "India": "IN",
    "Indonesia": "ID",
    "Philippines": "PH",
    "Thailand": "TH",
    "Vietnam": "VN",
    "Taiwan": "TW",
    "South Korea": "KR",
}
ISO_TO_SCREENED_COUNTRY = {v: k for k, v in SCREENED_COUNTRY_TO_ISO.items()}
ISO_TO_COUNTRY = dict(ISO_TO_SCREENED_COUNTRY)
ISO_TO_COUNTRY.update(ISO_TO_ARTICLE_COUNTRY)

ASPECT_LABELS = {
    "va": "Voice and Accountability",
    "pv": "Political Stability and Absence of Violence/Terrorism",
    "ge": "Government Effectiveness",
    "rq": "Regulatory Quality",
    "rl": "Rule of Law",
    "cc": "Control of Corruption",
}


def parse_month(s):
    y, m, _ = s.split("-")
    return date(int(y), int(m), 1)


def month_key(d):
    return f"{d.year:04d}-{d.month:02d}"


def to_float(x):
    if x is None:
        return None
    s = str(x).strip()
    if s == "" or s.lower() == "nan":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def safe_log(v):
    if v is None:
        return None
    if v <= 0:
        return None
    return math.log(v)


def previous_month(d):
    y = d.year
    m = d.month - 1
    if m == 0:
        y -= 1
        m = 12
    return date(y, m, 1)


def iter_months(start_year, end_year):
    out = []
    y = start_year
    m = 1
    while y < end_year or (y == end_year and m <= 12):
        out.append(date(y, m, 1))
        m += 1
        if m == 13:
            m = 1
            y += 1
    return out


def stars(p):
    if p < 0.01:
        return "***"
    if p < 0.05:
        return "**"
    if p < 0.10:
        return "*"
    return ""


def load_screened_country_set():
    screened_names = []
    with open(SCREENED_COUNTRY_CSV, "r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            name = (row.get("country") or "").strip()
            if name:
                screened_names.append(name)
    screened_names = sorted(set(screened_names))
    mapped_iso = sorted({SCREENED_COUNTRY_TO_ISO.get(n) for n in screened_names if SCREENED_COUNTRY_TO_ISO.get(n)})
    unmapped_names = sorted([n for n in screened_names if SCREENED_COUNTRY_TO_ISO.get(n) is None])
    return screened_names, mapped_iso, unmapped_names


def load_panel_iso_universe():
    out = set()
    with open(PANEL_CSV, "r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            iso = (row.get("iso") or "").strip()
            if iso:
                out.add(iso)
    return sorted(out)


def load_country_month_csv(path):
    out = defaultdict(dict)
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            c = (row.get("country") or "").strip()
            ym = (row.get("year_month") or "").strip()
            if not c or not ym:
                continue
            v = to_float(row.get("value"))
            out[c][ym] = v
    return out


def load_global_month_csv(path, value_col):
    out = {}
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            ym = (row.get("year_month") or "").strip()
            if not ym:
                continue
            out[ym] = to_float(row.get(value_col))
    return out


def load_gpr_global_z():
    vals = {}
    with open(GPR_CSV, "r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            if (row.get("series") or "").strip().upper() != "GPRH":
                continue
            ym = (row.get("year_month") or "").strip()
            if not ym:
                continue
            d = parse_month(ym + "-01")
            if d.year < START_YEAR or d.year > END_YEAR:
                continue
            v = to_float(row.get("value"))
            if v is not None:
                vals[ym] = v
    arr = np.array(list(vals.values()), dtype=float)
    if len(arr) == 0:
        return {}, {}
    mean = float(np.mean(arr))
    std = float(np.std(arr))
    if std == 0:
        std = 1.0
    z = {k: (v - mean) / std for k, v in vals.items()}
    return vals, z


def load_reer_monthly_by_country():
    wb = load_workbook(REER_XLSX, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    header = [str(x).strip() if x is not None else "" for x in next(ws.iter_rows(min_row=1, max_row=1, values_only=True))]
    countries = header[1:]
    out = {c: {} for c in countries if c}
    for row in ws.iter_rows(min_row=2, values_only=True):
        ym = str(row[0]).strip() if row[0] is not None else ""
        if not ym:
            continue
        try:
            d = parse_month(ym + "-01")
        except Exception:
            continue
        if d.year < START_YEAR or d.year > END_YEAR:
            continue
        for j, c in enumerate(countries, start=1):
            if not c:
                continue
            v = to_float(row[j] if j < len(row) else None)
            if v is not None:
                out[c][ym] = v
    return out


def load_annual_by_country(path, year_col, value_col):
    out = defaultdict(dict)
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            c = (row.get("country") or "").strip()
            y = (row.get(year_col) or "").strip()
            if not c or not y:
                continue
            try:
                year = int(y[:4])
            except ValueError:
                continue
            v = to_float(row.get(value_col))
            out[c][year] = v
    return out


def load_cbi_annual():
    wb = load_workbook(CBI_XLSX, read_only=True, data_only=True)
    ws = wb["CBI data"]
    hdr = [x for x in next(ws.iter_rows(min_row=1, max_row=1, values_only=True))]
    idx = {k: i for i, k in enumerate(hdr)}
    ci = idx["country"]
    yi = idx["year"]
    vi = idx["cbie_index"]
    out = defaultdict(dict)
    for row in ws.iter_rows(min_row=2, values_only=True):
        c = row[ci]
        y = row[yi]
        v = row[vi]
        if c is None or y is None or v is None:
            continue
        out[str(c).strip()][int(y)] = float(v)
    return out


def fit_ols_cluster(rows, rhs_vars, target_var):
    countries = sorted({r["iso"] for r in rows})
    if len(countries) < 2:
        return None, "Need at least two countries for FE model."

    y = np.array([r[target_var] for r in rows], dtype=float)
    X_cols = [np.ones(len(rows), dtype=float)]
    names = ["const"]
    for v in rhs_vars:
        X_cols.append(np.array([r[v] for r in rows], dtype=float))
        names.append(v)
    for c in countries[1:]:
        X_cols.append(np.array([1.0 if r["iso"] == c else 0.0 for r in rows], dtype=float))
        names.append(f"fe_{c}")

    X = np.column_stack(X_cols)
    n, k = X.shape
    if n <= k:
        return None, f"Insufficient observations (N={n}, k={k})."

    try:
        xtx_inv = np.linalg.inv(X.T @ X)
    except np.linalg.LinAlgError:
        return None, "Design matrix is singular."

    beta = xtx_inv @ (X.T @ y)
    resid = y - (X @ beta)

    clusters = defaultdict(list)
    for i, r in enumerate(rows):
        clusters[r["iso"]].append(i)
    g = len(clusters)
    if g < 2:
        return None, "Need at least two clusters."

    meat = np.zeros((k, k), dtype=float)
    for idxs in clusters.values():
        xg = X[idxs, :]
        ug = resid[idxs]
        s = xg.T @ ug
        meat += np.outer(s, s)
    v = xtx_inv @ meat @ xtx_inv
    if g > 1 and n > k:
        v *= (g / (g - 1)) * ((n - 1) / (n - k))

    se = np.sqrt(np.clip(np.diag(v), a_min=0.0, a_max=None))
    with np.errstate(divide="ignore", invalid="ignore"):
        tvals = beta / se
    df = g - 1
    pvals = 2 * (1 - student_t.cdf(np.abs(tvals), df=df))
    tcrit = student_t.ppf(0.975, df=df)
    ci_lo = beta - tcrit * se
    ci_hi = beta + tcrit * se

    sst = float(np.sum((y - np.mean(y)) ** 2))
    sse = float(np.sum(resid**2))
    r2 = float(1 - sse / sst) if sst > 0 else float("nan")

    return {
        "coef": dict(zip(names, beta)),
        "se": dict(zip(names, se)),
        "t": dict(zip(names, tvals)),
        "p": dict(zip(names, pvals)),
        "ci_lo": dict(zip(names, ci_lo)),
        "ci_hi": dict(zip(names, ci_hi)),
        "n_obs": n,
        "n_country": g,
        "k_params": k,
        "r2": r2,
    }, None


def load_panel(allowed_isos):
    by_iso = defaultdict(list)
    panel_isos_present = set()
    with open(PANEL_CSV, "r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            iso = (row.get("iso") or "").strip()
            if iso not in allowed_isos:
                continue
            country_name = ISO_TO_COUNTRY.get(iso, iso)
            panel_isos_present.add(iso)
            d = parse_month(row["date"])
            if d.year < START_YEAR or d.year > END_YEAR:
                continue
            by_iso[iso].append(
                {
                    "iso": iso,
                    "country": country_name,
                    "date": d,
                    "month": month_key(d),
                    "year": d.year,
                    "gpr": to_float(row.get("gpr")),
                    "gpr_z": to_float(row.get("gpr_z")),
                    "ln_reer": to_float(row.get("ln_reer")),
                    "rate_l1": to_float(row.get("rate_l1")),
                    "ln_ip_l1": to_float(row.get("ln_ip_l1")),
                    "infl_l1": to_float(row.get("infl_l1")),
                    "ln_oil_l1": to_float(row.get("ln_oil_l1")),
                    "ln_vix_l1": to_float(row.get("ln_vix_l1")),
                    "ln_gepu_l1": to_float(row.get("ln_gepu_l1")),
                    "fd_l1": to_float(row.get("fd_l1")),
                    "cbi_l1": to_float(row.get("cbi_l1")),
                    "debt_l1": to_float(row.get("debt_l1")),
                }
            )

    missing_isos = sorted(set(allowed_isos) - panel_isos_present)
    if missing_isos:
        reer = load_reer_monthly_by_country()
        policy = load_country_month_csv(POLICY_CSV)
        inflation = load_country_month_csv(INFL_CSV)
        fd = load_annual_by_country(FD_CSV, "year", "fd_fdi_ovrl")
        debt = load_annual_by_country(DEBT_CSV, "period", "debt_gdp_pct")
        cbi = load_cbi_annual()
        oil = load_global_month_csv(OIL_CSV, "wti_spot")
        vix = load_global_month_csv(VIX_CSV, "value")
        gepu = load_global_month_csv(GEPU_CSV, "value")
        gpr_raw, gpr_z = load_gpr_global_z()

        cbi_alias = {
            "South Korea": "Korea, Rep.",
            "Turkey": "Turkey",
            "Vietnam": "Vietnam",
            "Egypt": "Egypt, Arab Rep.",
        }
        months = iter_months(START_YEAR, END_YEAR)
        for iso in missing_isos:
            country = ISO_TO_COUNTRY.get(iso, iso)
            reer_map = reer.get(country, {})
            if not reer_map:
                continue
            cbi_country = cbi_alias.get(country, country)
            for d in months:
                ym = month_key(d)
                prev_ym = month_key(previous_month(d))
                ln_reer = safe_log(to_float(reer_map.get(ym)))
                row = {
                    "iso": iso,
                    "country": country,
                    "date": d,
                    "month": ym,
                    "year": d.year,
                    "gpr": to_float(gpr_raw.get(ym)),
                    "gpr_z": to_float(gpr_z.get(ym)),
                    "ln_reer": ln_reer,
                    "rate_l1": to_float(policy.get(country, {}).get(prev_ym)),
                    "ln_ip_l1": None,
                    "infl_l1": to_float(inflation.get(country, {}).get(prev_ym)),
                    "ln_oil_l1": safe_log(to_float(oil.get(prev_ym))),
                    "ln_vix_l1": safe_log(to_float(vix.get(prev_ym))),
                    "ln_gepu_l1": safe_log(to_float(gepu.get(prev_ym))),
                    "fd_l1": to_float(fd.get(country, {}).get(previous_month(d).year)),
                    "cbi_l1": to_float(cbi.get(cbi_country, {}).get(previous_month(d).year)),
                    "debt_l1": to_float(debt.get(country, {}).get(previous_month(d).year)),
                }
                by_iso[iso].append(row)

    # keep log-level REER for article-aligned LHS (Eq. 2 style)
    panel = []
    for iso, rows in by_iso.items():
        rows.sort(key=lambda x: x["date"])
        for row in rows:
            row["y_ln_reer"] = row["ln_reer"]
            panel.append(row)
    panel.sort(key=lambda x: (x["iso"], x["date"]))
    return panel


def load_institution_aspect_yearly():
    # (country, year, aspect) -> score
    m = {}
    with open(INST_CSV, "r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            country = (row.get("country") or "").strip()
            year = int(row.get("time"))
            aspect = (row.get("aspect") or "").strip().lower()
            score = to_float(row.get("score"))
            if not country or score is None or aspect not in ASPECTS:
                continue
            m[(country, year, aspect)] = score
    return m


def aspect_values_for_row(inst_map, row_country, year, aspect):
    inst_country = INST_COUNTRY_ALIASES.get(row_country, row_country)
    return inst_map.get((inst_country, year, aspect))


def build_model_data(panel, inst_map, aspect):
    # fill yearly institution within country (ffill+bfill), then lag monthly
    by_iso = defaultdict(list)
    for r in panel:
        by_iso[r["iso"]].append(dict(r))

    model_rows = []
    inst_fill_meta = {}
    for iso, rows in by_iso.items():
        rows.sort(key=lambda x: x["date"])
        country = rows[0]["country"]
        yvals = {y: aspect_values_for_row(inst_map, country, y, aspect) for y in range(START_YEAR, END_YEAR + 1)}
        fill_type = {}
        last = None
        for y in range(START_YEAR, END_YEAR + 1):
            if yvals[y] is not None:
                last = yvals[y]
                fill_type[y] = "raw"
            elif last is not None:
                yvals[y] = last
                fill_type[y] = "ffill"
        nxt = None
        for y in range(END_YEAR, START_YEAR - 1, -1):
            if yvals[y] is not None:
                nxt = yvals[y]
                if y not in fill_type:
                    fill_type[y] = "raw"
            elif nxt is not None:
                yvals[y] = nxt
                fill_type[y] = "bfill"
        for y in range(START_YEAR, END_YEAR + 1):
            if y not in fill_type:
                fill_type[y] = "missing"
        inst_fill_meta[iso] = fill_type

        prev_inst = None
        for row in rows:
            row["inst_raw_year"] = aspect_values_for_row(inst_map, country, row["year"], aspect)
            row["inst_filled_year"] = yvals[row["year"]]
            row["inst_l1"] = prev_inst
            if row["inst_filled_year"] is not None:
                prev_inst = row["inst_filled_year"]
            model_rows.append(row)

    # standardize inst_l1
    inst_vals = [r["inst_l1"] for r in model_rows if r["inst_l1"] is not None]
    if inst_vals:
        mean = float(np.mean(np.array(inst_vals, dtype=float)))
        std = float(np.std(np.array(inst_vals, dtype=float)))
        if std == 0:
            std = 1.0
    else:
        mean = None
        std = None
    for r in model_rows:
        if r["inst_l1"] is None or mean is None:
            r["inst_z_l1"] = None
        else:
            r["inst_z_l1"] = (r["inst_l1"] - mean) / std
        if r["gpr_z"] is None or r["inst_z_l1"] is None:
            r["gpr_x_inst"] = None
        else:
            r["gpr_x_inst"] = r["gpr_z"] * r["inst_z_l1"]

    return model_rows, mean, std, inst_fill_meta


def run_models(expanded_target=False):
    screened_names, screened_isos, unmapped_screened = load_screened_country_set()
    panel_iso_universe = load_panel_iso_universe()
    panel_iso_set = set(panel_iso_universe)
    target_isos = list(screened_isos)
    if expanded_target:
        allowed_isos = sorted(target_isos)
    else:
        allowed_isos = sorted([iso for iso in target_isos if iso in panel_iso_set])

    panel = load_panel(set(allowed_isos))
    panel_loaded_isos = sorted({r["iso"] for r in panel if r.get("y_ln_reer") is not None})
    unavailable_in_panel = sorted([iso for iso in target_isos if iso not in panel_loaded_isos])
    inst_map = load_institution_aspect_yearly()

    controls = [
        "rate_l1",
        "infl_l1",
        "ln_oil_l1",
        "ln_vix_l1",
        "ln_gepu_l1",
        "fd_l1",
        "cbi_l1",
        "debt_l1",
    ]
    rhs = ["inst_z_l1", "gpr_z", "gpr_x_inst"] + controls

    results = []
    model_data_for_plot = {}
    for aspect in ASPECTS:
        rows, inst_mean, inst_std, inst_fill_meta = build_model_data(panel, inst_map, aspect)
        sample = []
        missing_rhs_counts = defaultdict(int)
        for r in rows:
            if r["y_ln_reer"] is None:
                continue
            ok = True
            for v in rhs:
                val = r.get(v)
                if val is None or (isinstance(val, float) and math.isnan(val)):
                    missing_rhs_counts[v] += 1
                    ok = False
            if ok:
                sample.append(r)

        fit, err = fit_ols_cluster(sample, rhs, "y_ln_reer")
        if err:
            results.append(
                {
                    "aspect": aspect,
                    "aspect_label": ASPECT_LABELS[aspect],
                    "error": err,
                    "n_obs": len(sample),
                }
            )
            continue

        results.append(
            {
                "aspect": aspect,
                "aspect_label": ASPECT_LABELS[aspect],
                "coef_inst": float(fit["coef"]["inst_z_l1"]),
                "se_inst": float(fit["se"]["inst_z_l1"]),
                "p_inst": float(fit["p"]["inst_z_l1"]),
                "ci_lo_inst": float(fit["ci_lo"]["inst_z_l1"]),
                "ci_hi_inst": float(fit["ci_hi"]["inst_z_l1"]),
                "coef_gpr": float(fit["coef"]["gpr_z"]),
                "se_gpr": float(fit["se"]["gpr_z"]),
                "p_gpr": float(fit["p"]["gpr_z"]),
                "ci_lo_gpr": float(fit["ci_lo"]["gpr_z"]),
                "ci_hi_gpr": float(fit["ci_hi"]["gpr_z"]),
                "coef_int": float(fit["coef"]["gpr_x_inst"]),
                "se_int": float(fit["se"]["gpr_x_inst"]),
                "p_int": float(fit["p"]["gpr_x_inst"]),
                "ci_lo_int": float(fit["ci_lo"]["gpr_x_inst"]),
                "ci_hi_int": float(fit["ci_hi"]["gpr_x_inst"]),
                "n_obs": fit["n_obs"],
                "n_country": fit["n_country"],
                "k_params": fit["k_params"],
                "r2": float(fit["r2"]),
                "inst_mean_before_z": inst_mean,
                "inst_std_before_z": inst_std,
                "missing_rhs_counts": dict(missing_rhs_counts),
            }
        )

        # keep plot data for included sample countries (complete-case)
        included_countries = sorted({r["iso"] for r in sample})
        country_lookup = {r["iso"]: r["country"] for r in sample}
        by_country_year = defaultdict(dict)
        for r in rows:
            if r["iso"] in included_countries and r["inst_raw_year"] is not None:
                by_country_year[(r["iso"], r["country"])][r["year"]] = r["inst_raw_year"]
        plot_points = []
        for (iso, country), ymap in by_country_year.items():
            for y, v in sorted(ymap.items()):
                plot_points.append({"iso": iso, "country": country, "year": y, "score": float(v)})

        model_data_for_plot[aspect] = {
            "included_isos": included_countries,
            "included_countries": [country_lookup[i] for i in included_countries if i in country_lookup],
            "points": plot_points,
        }

    meta = {
        "is_expanded_run": expanded_target,
        "screened_names": screened_names,
        "screened_isos": screened_isos,
        "target_isos": target_isos,
        "unmapped_screened_names": unmapped_screened,
        "panel_iso_universe_count": len(panel_iso_universe),
        "allowed_isos": panel_loaded_isos,
        "allowed_countries": [ISO_TO_COUNTRY.get(i, i) for i in panel_loaded_isos],
        "unavailable_in_panel": unavailable_in_panel,
    }
    return results, model_data_for_plot, meta


def write_results_csv(results, out_csv):
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "aspect",
                "aspect_label",
                "coef_inst_z_l1",
                "se_inst_z_l1",
                "p_inst_z_l1",
                "ci95_lo_inst",
                "ci95_hi_inst",
                "coef_gpr_z",
                "se_gpr_z",
                "p_gpr_z",
                "ci95_lo_gpr",
                "ci95_hi_gpr",
                "coef_interaction",
                "se_interaction",
                "p_interaction",
                "ci95_lo_interaction",
                "ci95_hi_interaction",
                "n_obs",
                "n_country",
                "k_params",
                "r2",
                "inst_mean_before_z",
                "inst_std_before_z",
                "error",
            ]
        )
        for r in results:
            w.writerow(
                [
                    r.get("aspect"),
                    r.get("aspect_label"),
                    r.get("coef_inst"),
                    r.get("se_inst"),
                    r.get("p_inst"),
                    r.get("ci_lo_inst"),
                    r.get("ci_hi_inst"),
                    r.get("coef_gpr"),
                    r.get("se_gpr"),
                    r.get("p_gpr"),
                    r.get("ci_lo_gpr"),
                    r.get("ci_hi_gpr"),
                    r.get("coef_int"),
                    r.get("se_int"),
                    r.get("p_int"),
                    r.get("ci_lo_int"),
                    r.get("ci_hi_int"),
                    r.get("n_obs"),
                    r.get("n_country"),
                    r.get("k_params"),
                    r.get("r2"),
                    r.get("inst_mean_before_z"),
                    r.get("inst_std_before_z"),
                    r.get("error", ""),
                ]
            )


def write_results_html(results, meta, out_html):
    ok = [r for r in results if "error" not in r]
    failed = [r for r in results if "error" in r]
    with open(out_html, "w", encoding="utf-8") as f:
        f.write("<!doctype html><html lang='en'><head><meta charset='utf-8'>")
        if meta.get("is_expanded_run"):
            f.write("<title>Expanded sampled-country regressions: six institution aspects</title>")
        else:
            f.write("<title>Article-aligned regressions: six institution aspects</title>")
        f.write(
            "<style>"
            "body{font:16px/1.5 Georgia,serif;max-width:1280px;margin:2em auto;padding:0 1em;color:#20242a}"
            "table{border-collapse:collapse;width:100%;margin:1em 0;font-size:.9em}"
            "th,td{border-bottom:1px solid #ccc;padding:.45em;text-align:right;vertical-align:top}"
            "th:first-child,td:first-child{text-align:left}"
            ".note{background:#fff5da;padding:1em;border:1px solid #e6d59d}"
            ".warn{background:#ffe6e6;padding:.8em;border:1px solid #e0a7a7}"
            "code{font-size:.92em}"
            "</style></head><body>"
        )
        f.write("<h1>Article-aligned exchange-rate regressions with six institution aspects</h1>")
        f.write("<p>Dependent variable: <code>ln(REER_it)</code> (log level of REER, aligned with article Eq. (2) exchange-rate specification).</p>")
        gpr_def = "country-standardized monthly GPR (<code>gpr_z</code>) from article replication panel"
        if meta.get("is_expanded_run"):
            gpr_def = (
                "country-standardized monthly GPR (<code>gpr_z</code>) from article replication panel for panel countries; "
                "for added screened countries outside panel, global GPRH monthly z-score proxy from <code>cleaned/gpr_index.csv</code>"
            )
        f.write(
            "<div class='note'><strong>Article-aligned specification used</strong>: "
            "<code>ln(REER_it) = α + β1·Institution_i,t-1 + β2·GPR_it + β3·(GPR_it×Institution_i,t-1) + ν'Controls_i,t-1 + δ_i + ε_it</code><br>"
            "<strong>Controls (reworked set)</strong>: policy rate, inflation, log oil price, log VIX, log GEPU, financial development, central bank independence, debt/GDP (all lagged 1 month). "
            "Real industrial production control is dropped in this run to retain more countries.<br>"
            f"<strong>GPR definition</strong>: {gpr_def}.<br>"
            "<strong>Institution definition</strong>: for each aspect (va/pv/ge/rq/rl/cc), annual score from merged cleaned institution file, "
            "filled within-country (forward/backward), lagged one month, z-standardized.<br>"
            "<strong>Estimator</strong>: OLS with country fixed effects and clustered SE by country; 95% confidence intervals reported."
            "</div>"
        )
        f.write("<h2>Screened-country alignment check</h2>")
        f.write("<ul>")
        f.write(f"<li>Screened country names from <code>cleaned/country.csv</code>: {len(meta['screened_names'])}</li>")
        f.write(f"<li>Mapped screened ISO codes: {len(meta['target_isos'])} ({', '.join(meta['target_isos'])})</li>")
        if meta["unavailable_in_panel"]:
            f.write(
                f"<li>Screened ISO codes unavailable after combining replication panel + cleaned REER sources: "
                f"{', '.join(meta['unavailable_in_panel'])}</li>"
            )
        else:
            f.write("<li>All screened ISO codes are available after combining replication panel + cleaned REER sources.</li>")
        f.write(
            f"<li>Country set available for this run: {len(meta['allowed_isos'])} "
            f"({', '.join(meta['allowed_isos'])})</li>"
        )
        f.write("</ul>")

        f.write("<h2>Results across 6 institution aspects</h2>")
        f.write(
            "<table><thead><tr>"
            "<th>Aspect</th>"
            "<th>β1 Institution</th><th>SE</th><th>p</th><th>95% CI</th>"
            "<th>β2 GPR</th><th>SE</th><th>p</th><th>95% CI</th>"
            "<th>β3 Interaction</th><th>SE</th><th>p</th><th>95% CI</th>"
            "<th>N</th><th>Countries</th><th>R²</th>"
            "</tr></thead><tbody>"
        )
        for r in ok:
            f.write(
                "<tr>"
                f"<td>{escape(r['aspect'])} — {escape(r['aspect_label'])}</td>"
                f"<td>{r['coef_inst']:.4f}{stars(r['p_inst'])}</td><td>{r['se_inst']:.4f}</td><td>{r['p_inst']:.4f}</td><td>[{r['ci_lo_inst']:.4f}, {r['ci_hi_inst']:.4f}]</td>"
                f"<td>{r['coef_gpr']:.4f}{stars(r['p_gpr'])}</td><td>{r['se_gpr']:.4f}</td><td>{r['p_gpr']:.4f}</td><td>[{r['ci_lo_gpr']:.4f}, {r['ci_hi_gpr']:.4f}]</td>"
                f"<td>{r['coef_int']:.4f}{stars(r['p_int'])}</td><td>{r['se_int']:.4f}</td><td>{r['p_int']:.4f}</td><td>[{r['ci_lo_int']:.4f}, {r['ci_hi_int']:.4f}]</td>"
                f"<td>{r['n_obs']}</td><td>{r['n_country']}</td><td>{r['r2']:.4f}</td>"
                "</tr>"
            )
        f.write("</tbody></table>")
        f.write("<p><em>Significance stars:</em> *** p&lt;0.01, ** p&lt;0.05, * p&lt;0.10.</p>")
        if ok:
            min_countries = min(r["n_country"] for r in ok)
            f.write(
                "<div class='warn'>"
                f"Limitation: although {len(meta['allowed_isos'])} screened countries have usable exchange-rate source rows, "
                f"complete-case estimation under the reworked control set uses {min_countries} countries in the final regression sample."
                "</div>"
            )

        if failed:
            f.write("<h3>Non-estimable aspect models</h3><div class='warn'>")
            for r in failed:
                f.write(f"<p>{escape(r['aspect'])} — {escape(r['aspect_label'])}: {escape(r['error'])}</p>")
            f.write("</div>")

        f.write("<h2>Variable alignment table: original article vs selected data in this run</h2>")
        f.write(
            "<table><thead><tr>"
            "<th>Article variable</th><th>Article definition/source</th><th>Selected data in this run</th>"
            "</tr></thead><tbody>"
        )
        y_selected = "ln_reer from article replication panel (BIS real broad REER path)"
        gpr_selected = "gpr_z from article replication panel"
        if meta.get("is_expanded_run"):
            y_selected = (
                "ln_reer from article replication panel where available; supplemented with cleaned REER workbook "
                "for screened countries outside panel"
            )
            gpr_selected = (
                "gpr_z from article replication panel where available; global GPRH z-score proxy for added screened countries"
            )
        rows_map = [
            ("Exchange rate (Y)", "Log real effective exchange rate (REER), monthly", y_selected),
            ("GPR", "Country-specific monthly GPR, standardized by country", gpr_selected),
            ("Policy rate", "Policy rate, lagged", "rate_l1"),
            ("Real industrial production", "Log real industrial production, lagged", "Excluded in this run by request (to increase country coverage)"),
            ("Inflation", "YoY CPI inflation, lagged", "infl_l1"),
            ("Oil price", "Log WTI oil price, lagged", "ln_oil_l1"),
            ("VIX", "Log VIX, lagged", "ln_vix_l1"),
            ("Global EPU", "Log GEPU, lagged", "ln_gepu_l1"),
            ("Financial development", "FD index", "fd_l1"),
            ("Central bank independence", "CBI index", "cbi_l1"),
            ("Debt-to-GDP", "Public debt ratio", "debt_l1"),
            ("Institution robustness term", "Not in baseline Eq. (2); used for robustness tests", "aspect-specific institution_z_l1 and interaction gpr_x_inst"),
        ]
        for a, b, c in rows_map:
            f.write(
                "<tr>"
                f"<td>{escape(a)}</td>"
                f"<td style='text-align:left'>{escape(b)}</td>"
                f"<td style='text-align:left'>{escape(c)}</td>"
                "</tr>"
            )
        f.write("</tbody></table>")
        if meta.get("is_expanded_run"):
            f.write("<h2>Expanded sampled-country note</h2>")
            f.write(
                "<div class='note'>"
                f"We expanded the sampled countries to all 17 screened ISO codes: {', '.join(meta['target_isos'])}. "
                f"Among these, {len(meta['allowed_isos'])} have usable exchange-rate source rows (replication panel and/or cleaned REER) and enter this expanded-country test."
                "</div>"
            )
        f.write("</body></html>")


def write_two_tables_html(base_results, base_meta, exp_results, exp_meta, out_html):
    def render_table_rows(f, rows):
        for r in rows:
            f.write(
                "<tr>"
                f"<td>{escape(r['aspect'])} — {escape(r['aspect_label'])}</td>"
                f"<td>{r['coef_inst']:.4f}{stars(r['p_inst'])}</td><td>{r['se_inst']:.4f}</td><td>{r['p_inst']:.4f}</td><td>[{r['ci_lo_inst']:.4f}, {r['ci_hi_inst']:.4f}]</td>"
                f"<td>{r['coef_gpr']:.4f}{stars(r['p_gpr'])}</td><td>{r['se_gpr']:.4f}</td><td>{r['p_gpr']:.4f}</td><td>[{r['ci_lo_gpr']:.4f}, {r['ci_hi_gpr']:.4f}]</td>"
                f"<td>{r['coef_int']:.4f}{stars(r['p_int'])}</td><td>{r['se_int']:.4f}</td><td>{r['p_int']:.4f}</td><td>[{r['ci_lo_int']:.4f}, {r['ci_hi_int']:.4f}]</td>"
                f"<td>{r['n_obs']}</td><td>{r['n_country']}</td><td>{r['r2']:.4f}</td>"
                "</tr>"
            )

    base_ok = [r for r in base_results if "error" not in r]
    exp_ok = [r for r in exp_results if "error" not in r]
    with open(out_html, "w", encoding="utf-8") as f:
        f.write("<!doctype html><html lang='en'><head><meta charset='utf-8'>")
        f.write("<title>Two-table REER regressions (10-country vs expanded sample)</title>")
        f.write(
            "<style>"
            "body{font:16px/1.5 Georgia,serif;max-width:1380px;margin:2em auto;padding:0 1em;color:#20242a}"
            "table{border-collapse:collapse;width:100%;margin:1em 0;font-size:.88em}"
            "th,td{border-bottom:1px solid #ccc;padding:.4em;text-align:right;vertical-align:top}"
            "th:first-child,td:first-child{text-align:left}"
            ".note{background:#fff5da;padding:1em;border:1px solid #e6d59d}"
            ".warn{background:#ffe6e6;padding:.8em;border:1px solid #e0a7a7}"
            "</style></head><body>"
        )
        f.write("<h1>REER regressions with six institution aspects (two tables)</h1>")
        f.write(
            "<div class='note'>"
            "<strong>Exchange-rate variable check:</strong> both tables use only real effective exchange rate (REER) as Y "
            "(<code>ln(REER_it)</code>). No nominal bilateral FX series are used in these two tables."
            "</div>"
        )
        f.write(
            "<p><strong>Common model:</strong> "
            "<code>ln(REER_it) = α + β1·Institution_i,t-1 + β2·GPR_it + β3·(GPR_it×Institution_i,t-1) + ν'Controls_i,t-1 + δ_i + ε_it</code>. "
            "Controls: policy rate, inflation, log oil price, log VIX, log GEPU, financial development, central bank independence, debt/GDP (lagged 1 month)."
            "</p>"
        )

        f.write("<h2>Table 1 — 10-country baseline result set</h2>")
        f.write(
            f"<p>Screened target ISO list: {', '.join(base_meta['target_isos'])}. "
            f"Available countries in this baseline run: {len(base_meta['allowed_isos'])} ({', '.join(base_meta['allowed_isos'])}). "
            f"Complete-case countries in regressions: {min(r['n_country'] for r in base_ok) if base_ok else 0}.</p>"
        )
        f.write(
            "<table><thead><tr>"
            "<th>Aspect</th>"
            "<th>β1 Institution</th><th>SE</th><th>p</th><th>95% CI</th>"
            "<th>β2 GPR</th><th>SE</th><th>p</th><th>95% CI</th>"
            "<th>β3 Interaction</th><th>SE</th><th>p</th><th>95% CI</th>"
            "<th>N</th><th>Countries</th><th>R²</th>"
            "</tr></thead><tbody>"
        )
        render_table_rows(f, base_ok)
        f.write("</tbody></table>")

        f.write("<h2>Table 2 — Expanded sampled-country result set</h2>")
        f.write(
            f"<p>Expanded target to all 17 screened ISO codes: {', '.join(exp_meta['target_isos'])}. "
            f"Usable exchange-rate-source countries in this expanded run: {len(exp_meta['allowed_isos'])} ({', '.join(exp_meta['allowed_isos'])}). "
            f"Unavailable after combining replication panel + cleaned REER: {', '.join(exp_meta['unavailable_in_panel']) if exp_meta['unavailable_in_panel'] else 'none'}."
            "</p>"
        )
        f.write(
            "<table><thead><tr>"
            "<th>Aspect</th>"
            "<th>β1 Institution</th><th>SE</th><th>p</th><th>95% CI</th>"
            "<th>β2 GPR</th><th>SE</th><th>p</th><th>95% CI</th>"
            "<th>β3 Interaction</th><th>SE</th><th>p</th><th>95% CI</th>"
            "<th>N</th><th>Countries</th><th>R²</th>"
            "</tr></thead><tbody>"
        )
        render_table_rows(f, exp_ok)
        f.write("</tbody></table>")
        f.write("<p><em>Significance stars:</em> *** p&lt;0.01, ** p&lt;0.05, * p&lt;0.10.</p>")
        f.write("</body></html>")


def write_plots_html(model_data_for_plot):
    # Pack data for JS
    packed = {}
    for aspect, payload in model_data_for_plot.items():
        packed[aspect] = payload

    with open(PLOTS_HTML, "w", encoding="utf-8") as f:
        f.write("<!doctype html><html lang='en'><head><meta charset='utf-8'>")
        f.write("<title>Institution diagnostics plots (six aspects)</title>")
        f.write("<script src='https://cdn.plot.ly/plotly-2.35.2.min.js'></script>")
        f.write(
            "<style>"
            "body{font:16px/1.45 Georgia,serif;max-width:1300px;margin:1.6em auto;padding:0 1em;color:#20242a}"
            "h1,h2{margin:.4em 0}"
            ".note{background:#fff5da;padding:1em;border:1px solid #e6d59d;margin:.8em 0}"
            "#dist,#trend{height:560px;margin:1em 0}"
            "</style></head><body>"
        )
        f.write("<h1>Institution score diagnostics for included countries</h1>")
        f.write(
            "<div class='note'>"
            "Interactive charts use the countries included in each aspect's complete-case Equation (1) sample. "
            "Hover points to view country names and scores."
            "</div>"
        )
        f.write("<h2>Distribution of institution scores per year (hover shows country)</h2>")
        f.write("<div id='dist'></div>")
        f.write("<h2>Time-series trend by aspect for included countries</h2>")
        f.write("<div id='trend'></div>")
        f.write("<script>")
        f.write("const dataByAspect = " + json.dumps(packed) + ";\n")
        f.write("const aspects = ['va','pv','ge','rq','rl','cc'];\n")
        f.write("const aspectLabel = " + json.dumps(ASPECT_LABELS) + ";\n")

        f.write(
            """
function tracesForAspect(aspect){
  const pts = (dataByAspect[aspect] || {}).points || [];
  const byCountry = {};
  for(const p of pts){
    const key = p.iso + '|' + p.country;
    if(!byCountry[key]) byCountry[key] = [];
    byCountry[key].push(p);
  }
  const keys = Object.keys(byCountry).sort();
  const traces = [];
  for(const k of keys){
    const arr = byCountry[k].sort((a,b)=>a.year-b.year);
    const country = arr[0].country;
    traces.push({
      type:'scatter',
      mode:'lines+markers',
      name: country,
      x: arr.map(d=>d.year),
      y: arr.map(d=>d.score),
      hovertemplate: 'Country: %{text}<br>Year: %{x}<br>Score: %{y:.3f}<extra></extra>',
      text: arr.map(d=>d.country),
      marker:{size:5},
      line:{width:1.5}
    });
  }
  return traces;
}

function distTracesForAspect(aspect){
  const pts = (dataByAspect[aspect] || {}).points || [];
  return [{
    type:'box',
    name: aspectLabel[aspect],
    x: pts.map(d=>d.year),
    y: pts.map(d=>d.score),
    boxpoints:'all',
    jitter:0.35,
    pointpos:0,
    marker:{size:6,opacity:0.75},
    text: pts.map(d=>d.country),
    hovertemplate:'Country: %{text}<br>Year: %{x}<br>Score: %{y:.3f}<extra></extra>'
  }];
}

function makeButtons(target){
  return aspects.map(a=>({
    method:'update',
    label: a + ' - ' + aspectLabel[a],
    args: target==='dist'
      ? [ {x:[distTracesForAspect(a)[0].x], y:[distTracesForAspect(a)[0].y], text:[distTracesForAspect(a)[0].text], name:[aspectLabel[a]]},
          {title:'Distribution by year — ' + a + ' (' + aspectLabel[a] + ')'} ]
      : [ {visible: tracesForAspect(a).map(()=>true)},
          {title:'Country trends — ' + a + ' (' + aspectLabel[a] + ')'} ]
  }));
}

// Initial aspect
const init = 'va';
const distInit = distTracesForAspect(init);
Plotly.newPlot('dist', distInit, {
  title: 'Distribution by year — va (' + aspectLabel['va'] + ')',
  xaxis:{title:'Year'},
  yaxis:{title:'Institution score'},
  updatemenus:[{buttons:makeButtons('dist'), direction:'down', x:1.02, y:1.15, xanchor:'left', yanchor:'top'}],
  margin:{t:80}
});

// Trend chart: prebuild all traces and toggle by aspect
const allTrendTraces = [];
const aspectTraceRanges = {};
let cursor = 0;
for(const a of aspects){
  const t = tracesForAspect(a);
  aspectTraceRanges[a] = [cursor, cursor + t.length - 1];
  for(const tr of t){
    tr.visible = (a === init);
    allTrendTraces.push(tr);
  }
  cursor += t.length;
}
const trendButtons = aspects.map(a=>{
  const vis = allTrendTraces.map(()=>false);
  const rg = aspectTraceRanges[a];
  if(rg && rg[1] >= rg[0]){
    for(let i=rg[0]; i<=rg[1]; i++){ vis[i] = true; }
  }
  return {
    method:'update',
    label: a + ' - ' + aspectLabel[a],
    args:[{visible:vis},{title:'Country trends — ' + a + ' (' + aspectLabel[a] + ')'}]
  };
});
Plotly.newPlot('trend', allTrendTraces, {
  title:'Country trends — va (' + aspectLabel['va'] + ')',
  xaxis:{title:'Year'},
  yaxis:{title:'Institution score'},
  updatemenus:[{buttons:trendButtons, direction:'down', x:1.02, y:1.15, xanchor:'left', yanchor:'top'}],
  legend:{orientation:'v'},
  margin:{t:80}
});
"""
        )
        f.write("</script></body></html>")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    results, model_data_for_plot, meta = run_models(expanded_target=False)
    write_results_csv(results, RESULTS_CSV)
    write_results_html(results, meta, RESULTS_HTML)
    write_plots_html(model_data_for_plot)
    exp_results, _, exp_meta = run_models(expanded_target=True)
    write_results_csv(exp_results, EXPANDED17_RESULTS_CSV)
    write_results_html(exp_results, exp_meta, EXPANDED17_RESULTS_HTML)
    write_two_tables_html(results, meta, exp_results, exp_meta, TWO_TABLES_HTML)
    print("Generated:")
    print(RESULTS_CSV)
    print(RESULTS_HTML)
    print(PLOTS_HTML)
    print(EXPANDED17_RESULTS_CSV)
    print(EXPANDED17_RESULTS_HTML)
    print(TWO_TABLES_HTML)


if __name__ == "__main__":
    main()
