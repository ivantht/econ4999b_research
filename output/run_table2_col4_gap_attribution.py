import csv
import os
from collections import defaultdict
from html import escape

import numpy as np
from scipy.stats import t as student_t

import run_replication_cleaned_controls_baseline as base


OUT_CSV = os.path.join(base.eq1.OUT_DIR, "replication_cleaned_table2_col4_gap_attribution.csv")
OUT_HTML = os.path.join(base.eq1.OUT_DIR, "replication_cleaned_table2_col4_gap_attribution.html")
TARGET = "y_ln_reer"


def carry_forward_fd(rows):
    by_iso = defaultdict(list)
    for r in rows:
        by_iso[r["iso"]].append(r)
    for seq in by_iso.values():
        seq.sort(key=lambda x: x["date"])
        last = None
        for r in seq:
            if base.present(r.get("fd")):
                last = r["fd"]
            elif last is not None:
                r["fd"] = last


def collect_sample(rows, rhs):
    out = []
    for r in rows:
        if not base.present(r.get(TARGET)):
            continue
        ok = True
        for v in rhs:
            if not base.present(r.get(v)):
                ok = False
                break
        if ok:
            out.append(r)
    return out


def fit_model(rows, rhs, se_type="cluster", include_fe=True):
    if len(rows) < 3:
        return None, "Too few observations."
    countries = sorted({r["iso"] for r in rows})
    if include_fe and len(countries) < 2:
        return None, "Need >=2 countries for FE."

    y = np.array([r[TARGET] for r in rows], dtype=float)
    X_cols = [np.ones(len(rows), dtype=float)]
    names = ["const"]
    for v in rhs:
        X_cols.append(np.array([r[v] for r in rows], dtype=float))
        names.append(v)
    if include_fe:
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
        return None, "Design matrix singular."

    beta = xtx_inv @ (X.T @ y)
    resid = y - (X @ beta)

    if se_type == "cluster":
        clusters = defaultdict(list)
        for i, r in enumerate(rows):
            clusters[r["iso"]].append(i)
        g = len(clusters)
        if g < 2:
            return None, "Need >=2 clusters."
        meat = np.zeros((k, k), dtype=float)
        for idxs in clusters.values():
            xg = X[idxs, :]
            ug = resid[idxs]
            s = xg.T @ ug
            meat += np.outer(s, s)
        vcv = xtx_inv @ meat @ xtx_inv
        if g > 1 and n > k:
            vcv *= (g / (g - 1)) * ((n - 1) / (n - k))
        df = g - 1
    elif se_type == "hc1":
        u2 = resid**2
        meat = X.T @ (X * u2[:, None])
        vcv = xtx_inv @ meat @ xtx_inv
        if n > k:
            vcv *= n / (n - k)
        df = n - k
    elif se_type == "ols":
        sigma2 = float((resid @ resid) / (n - k))
        vcv = sigma2 * xtx_inv
        df = n - k
    else:
        return None, f"Unknown se_type: {se_type}"

    se = np.sqrt(np.clip(np.diag(vcv), a_min=0.0, a_max=None))
    with np.errstate(divide="ignore", invalid="ignore"):
        tvals = beta / se
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
        "p": dict(zip(names, pvals)),
        "ci_lo": dict(zip(names, ci_lo)),
        "ci_hi": dict(zip(names, ci_hi)),
        "n_obs": n,
        "n_country": len(countries),
        "r2": r2,
        "k_params": k,
        "df": df,
    }, None


def run_scenario(label, change_axis, rows, rhs, se_type, group_filter=None, fd_fill=False):
    work = [dict(r) for r in rows]
    if fd_fill:
        carry_forward_fd(work)
    base.standardize_gpr_within_country(work)
    base.add_lagged_controls(work)
    sample = collect_sample(work, rhs)
    if group_filter == "emerging":
        sample = [r for r in sample if (r.get("group") or "").lower() == "emerging"]
    elif group_filter == "non_emerging":
        sample = [r for r in sample if (r.get("group") or "").lower() != "emerging"]

    fit, err = fit_model(sample, rhs, se_type=se_type, include_fe=True)
    months = sorted({r["month"] for r in sample})
    countries = sorted({r["country"] for r in sample})
    row = {
        "scenario": label,
        "change_axis": change_axis,
        "rhs": ", ".join(rhs),
        "se_type": se_type,
        "group_filter": group_filter or "full",
        "fd_fill": fd_fill,
        "n_obs": len(sample) if fit is None else fit["n_obs"],
        "n_country": len({r["iso"] for r in sample}) if fit is None else fit["n_country"],
        "month_min": months[0] if months else "",
        "month_max": months[-1] if months else "",
        "countries": ", ".join(countries),
        "r2": "" if fit is None else fit["r2"],
        "gpr_coef": "" if fit is None else fit["coef"]["gpr_z"],
        "gpr_se": "" if fit is None else fit["se"]["gpr_z"],
        "gpr_p": "" if fit is None else fit["p"]["gpr_z"],
        "gpr_ci_lo": "" if fit is None else fit["ci_lo"]["gpr_z"],
        "gpr_ci_hi": "" if fit is None else fit["ci_hi"]["gpr_z"],
        "gpr_sig_10pct": "" if fit is None else (fit["p"]["gpr_z"] < 0.10),
        "error": err or "",
    }
    return row


def write_outputs(rows):
    fields = [
        "scenario",
        "change_axis",
        "rhs",
        "se_type",
        "group_filter",
        "fd_fill",
        "n_obs",
        "n_country",
        "month_min",
        "month_max",
        "r2",
        "gpr_coef",
        "gpr_se",
        "gpr_p",
        "gpr_ci_lo",
        "gpr_ci_hi",
        "gpr_sig_10pct",
        "countries",
        "error",
    ]
    with open(OUT_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    def f4(v):
        if v == "" or v is None:
            return ""
        return f"{float(v):.4f}"

    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write("<!doctype html><html lang='en'><head><meta charset='utf-8'>")
        f.write("<title>Table 2(4) gap attribution</title>")
        f.write(
            "<style>"
            "body{font:16px/1.5 Georgia,serif;max-width:1300px;margin:2em auto;padding:0 1em;color:#20242a}"
            "table{border-collapse:collapse;width:100%;margin:1em 0;font-size:.9em}"
            "th,td{border-bottom:1px solid #ccc;padding:.45em;text-align:right;vertical-align:top}"
            "th:first-child,td:first-child{text-align:left}"
            ".note{background:#fff5da;padding:1em;border:1px solid #e6d59d}"
            "</style></head><body>"
        )
        f.write("<h1>Gap attribution exercise for Table 2 (4)</h1>")
        f.write(
            "<div class='note'>"
            "<strong>Purpose</strong>: one-change-at-a-time decomposition of why GPR significance may differ.<br>"
            "<strong>Data</strong>: cleaned/replication_cleaned/country_month.csv only.<br>"
            "<strong>Dependent variable</strong>: ln(REER).<br>"
            "<strong>FE</strong>: country fixed effects in every scenario."
            "</div>"
        )
        f.write(
            "<table><thead><tr>"
            "<th>Scenario</th><th>Axis changed</th><th>SE</th><th>Group</th><th>FD fill</th>"
            "<th>N</th><th>Countries</th><th>Window</th><th>GPR coef</th><th>SE</th><th>p</th><th>95% CI</th><th>Sig. (10%)</th>"
            "</tr></thead><tbody>"
        )
        for r in rows:
            win = f"{escape(r['month_min'])} to {escape(r['month_max'])}" if r["month_min"] else ""
            ci = "" if r["gpr_ci_lo"] == "" else f"[{f4(r['gpr_ci_lo'])}, {f4(r['gpr_ci_hi'])}]"
            f.write(
                "<tr>"
                f"<td>{escape(r['scenario'])}</td>"
                f"<td>{escape(r['change_axis'])}</td>"
                f"<td>{escape(str(r['se_type']))}</td>"
                f"<td>{escape(str(r['group_filter']))}</td>"
                f"<td>{'yes' if r['fd_fill'] else 'no'}</td>"
                f"<td>{r['n_obs']}</td>"
                f"<td>{r['n_country']}</td>"
                f"<td>{win}</td>"
                f"<td>{f4(r['gpr_coef'])}</td>"
                f"<td>{f4(r['gpr_se'])}</td>"
                f"<td>{f4(r['gpr_p'])}</td>"
                f"<td>{ci}</td>"
                f"<td>{r['gpr_sig_10pct']}</td>"
                "</tr>"
            )
        f.write("</tbody></table>")
        f.write("</body></html>")


def main():
    rows = base.load_rows()
    rhs_full = list(base.RHS)

    scenarios = [
        ("S0 baseline matched", "reference", rhs_full, "cluster", None, True),
        ("S1 no FD carry-forward", "fd handling + effective period", rhs_full, "cluster", None, False),
        ("S2 drop ln(IP) control", "country coverage via control availability", [v for v in rhs_full if v != "ln_ip_l1"], "cluster", None, True),
        ("S3 emerging only", "subgroup filter", rhs_full, "cluster", "emerging", True),
        ("S4 non-emerging only", "subgroup filter", rhs_full, "cluster", "non_emerging", True),
        ("S5 HC1 robust SE", "SE choice", rhs_full, "hc1", None, True),
        ("S6 OLS conventional SE", "SE choice", rhs_full, "ols", None, True),
    ]

    out = []
    for label, axis, rhs, se, grp, fd_fill in scenarios:
        out.append(run_scenario(label, axis, rows, rhs, se, group_filter=grp, fd_fill=fd_fill))

    write_outputs(out)
    print("Generated:")
    print(OUT_CSV)
    print(OUT_HTML)


if __name__ == "__main__":
    main()
