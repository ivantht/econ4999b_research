"""Build a quarterly Model 1 panel and source-comparison report."""

import csv
import math
import statistics
from collections import defaultdict
from pathlib import Path

import openpyxl


ROOT = Path(__file__).resolve().parents[1]
CLEANED = ROOT / "cleaned"
PANEL = CLEANED / "replication_cleaned" / "country_month.csv"
PANEL_CODEBOOK = CLEANED / "replication_cleaned" / "codebook.csv"
DATASET = CLEANED / "data_for_quarter_model.csv"
CODEBOOK = CLEANED / "data_for_quarter_model_codebook.csv"
REPORT = CLEANED / "data_for_quarter_model_validation.csv"
YEARS = range(2000, 2024)
ASPECTS = ("va", "pv", "ge", "rq", "rl", "cc")
ALIASES = {"Korea": "South Korea", "Turkiye": "Turkey"}
TEXT_COLUMNS = {"share_source", "bond_source", "reer_source", "ip_source"}
ANNUAL_COLUMNS = {
    "financial_development", "central_bank_independence", "public_debt_gdp",
    "d_financial_development", "d_public_debt_gdp",
    *(f"wgi_{a}" for a in ASPECTS), *(f"d_wgi_{a}" for a in ASPECTS),
}
SUM_COLUMNS = {
    "portfolio_inflow", "d_policy_rate", "d_inflation", "d_log_gepu",
    "d_log_oil", "d_log_reer",
}
MODEL_LAGS = (
    *(f"wgi_{a}" for a in ASPECTS), "d_financial_development",
    "d_public_debt_gdp", "d_policy_rate", "d_inflation", "d_log_oil",
    "d_log_gepu", "ln_vix",
)
CLEANED_SOURCES = {
    "gpr": ("cleaned\\gpr_country.csv", "article share"),
    "reer": ("cleaned\\real effective exchange rate.xlsx", "index"),
    "policy_rate": ("cleaned\\policy_rate.csv", "percent"),
    "inflation": ("cleaned\\inflation.csv", "percent"),
    "oil_price": ("cleaned\\oil_price.csv", "US dollars per barrel"),
    "vix": ("cleaned\\vix.csv", "index"),
    "gepu": ("cleaned\\gepu_current.csv", "index"),
    "public_debt_gdp": ("cleaned\\debt_gdp.csv", "percent of GDP"),
    "fd_fdi_ovrl": ("cleaned\\financial_development.csv", "fd_fdi_ovrl source units"),
    **{f"wgi_{a}": ("cleaned\\wgi.csv", "WGI estimate") for a in ASPECTS},
}


def number(raw, context):
    if raw is None or str(raw).strip() == "":
        return None
    try:
        value = float(raw)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid numeric value for {context}: {raw!r}") from exc
    if not math.isfinite(value):
        raise ValueError(f"Non-finite value for {context}: {raw!r}")
    return value


def quarter_months(year, quarter):
    return [f"{year}-{month:02d}" for month in range(3 * quarter - 2, 3 * quarter + 1)]


def previous_month(month):
    year, m = map(int, month.split("-"))
    return f"{year - 1}-12" if m == 1 else f"{year}-{m - 1:02d}"


def aggregate(values, method):
    if len(values) != 3 or any(value is None for value in values):
        return None
    if method == "sum":
        return sum(values)
    if method == "annual":
        if not all(value == values[0] for value in values):
            raise ValueError(f"Inconsistent annual values within quarter: {values}")
        return values[0]
    return sum(values) / 3


def log_value(value):
    return math.log(value) if value is not None and value > 0 else None


def delta(current, previous, logarithm=False):
    if logarithm:
        current, previous = log_value(current), log_value(previous)
    return current - previous if current is not None and previous is not None else None


def load_panel(path):
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        columns = reader.fieldnames or []
        if len(columns) != len(set(columns)) or not {"iso", "country", "group", "date"}.issubset(columns):
            raise ValueError(f"Invalid columns in {path}")
        rows = {}
        metadata = {}
        for line, row in enumerate(reader, 2):
            country, date = row["country"].strip(), row["date"].strip()
            if not country or len(date) != 10 or date[7:] != "-01":
                raise ValueError(f"Invalid country or month at {path}:{line}")
            month = date[:7]
            if int(month[:4]) not in YEARS or not 1 <= int(month[5:]) <= 12:
                raise ValueError(f"Outside panel window or invalid month at {path}:{line}")
            key = (country, month)
            if key in rows:
                raise ValueError(f"Duplicate panel month {key}")
            meta = (row["iso"], row["group"])
            if country in metadata and metadata[country] != meta:
                raise ValueError(f"Inconsistent country metadata for {country}")
            metadata[country] = meta
            rows[key] = row
    expected = {(c, f"{y}-{m:02d}") for c in metadata for y in YEARS for m in range(1, 13)}
    if set(rows) != expected or len(metadata) != 29:
        raise ValueError("Panel is not the expected complete 29-country monthly grid")
    return columns, rows, metadata


def read_series(path, value_column, key_columns, filter_row=None):
    result = {}
    seen = set()
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if not set((*key_columns, value_column)).issubset(reader.fieldnames or []):
            raise ValueError(f"Missing columns in {path}")
        for line, row in enumerate(reader, 2):
            if filter_row and not filter_row(row):
                continue
            key = tuple(row[column].strip() for column in key_columns)
            if not all(key) or key in seen:
                raise ValueError(f"Missing or duplicate key at {path}:{line}: {key}")
            seen.add(key)
            value = number(row[value_column], f"{path}:{line}")
            if value is not None:
                result[key] = value
    return result


def read_reer(path):
    values = {}
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        rows = workbook.active.iter_rows(values_only=True)
        header = next(rows)
        if header[0] != "month" or len(set(header[1:])) != len(header[1:]):
            raise ValueError(f"Invalid REER workbook header in {path}")
        seen = set()
        for line, row in enumerate(rows, 2):
            month = str(row[0]).strip()
            if len(month) != 7 or month[4] != "-" or month in seen:
                raise ValueError(f"Invalid or duplicate REER month in {path}:{line}")
            seen.add(month)
            for country, raw in zip(header[1:], row[1:]):
                value = number(raw, f"{path}:{line}, {country}")
                if value is not None:
                    values[(str(country), month)] = value
    finally:
        workbook.close()
    return values


def load_cleaned():
    monthly = {
        "gpr": read_series(CLEANED / "gpr_country.csv", "value", ("country", "year_month")),
        "reer": read_reer(CLEANED / "real effective exchange rate.xlsx"),
        "policy_rate": read_series(CLEANED / "policy_rate.csv", "value", ("country", "year_month")),
        "inflation": read_series(CLEANED / "inflation.csv", "value", ("country", "year_month")),
    }
    global_series = {
        "oil_price": read_series(CLEANED / "oil_price.csv", "wti_spot", ("year_month",)),
        "vix": read_series(CLEANED / "vix.csv", "value", ("year_month",)),
        "gepu": read_series(CLEANED / "gepu_current.csv", "value", ("year_month",)),
    }
    annual = {
        "public_debt_gdp": read_series(
            CLEANED / "debt_gdp.csv", "debt_gdp_pct", ("country", "period"),
            lambda row: row["frequency"].strip().lower() == "annual",
        ),
        "fd_fdi_ovrl": read_series(CLEANED / "financial_development.csv", "fd_fdi_ovrl", ("country", "year")),
    }
    wgi = read_series(CLEANED / "wgi.csv", "estimate", ("country", "year", "dimension"))
    for aspect in ASPECTS:
        annual[f"wgi_{aspect}"] = {(c, y): v for (c, y, a), v in wgi.items() if a == aspect}
    return monthly, global_series, annual


def panel_number(rows, country, month, column):
    row = rows.get((country, month))
    return number(row[column], f"panel {country} {month} {column}") if row else None


def cleaned_quarter(country, year, quarter, monthly, global_series, annual):
    country = ALIASES.get(country, country)
    months = quarter_months(year, quarter)
    result = {}
    for name, series in monthly.items():
        result[f"cleaned_{name}"] = aggregate([series.get((country, m)) for m in months], "mean")
    for name, series in global_series.items():
        result[f"cleaned_{name}"] = aggregate([series.get((m,)) for m in months], "mean")
    result["cleaned_ln_vix"] = aggregate([log_value(global_series["vix"].get((m,))) for m in months], "mean")
    for name, series in annual.items():
        result[f"cleaned_{name}"] = series.get((country, str(year)))
    for name in ("policy_rate", "inflation", "reer"):
        series = monthly[name]
        result[f"cleaned_d_{'log_' if name == 'reer' else ''}{name}"] = aggregate(
            [delta(series.get((country, m)), series.get((country, previous_month(m))), name == "reer") for m in months],
            "sum",
        )
    for name, series in (("oil", global_series["oil_price"]), ("gepu", global_series["gepu"])):
        result[f"cleaned_d_log_{name}"] = aggregate(
            [delta(series.get((m,)), series.get((previous_month(m),)), True) for m in months], "sum"
        )
    for name in ("public_debt_gdp", "fd_fdi_ovrl", *(f"wgi_{a}" for a in ASPECTS)):
        series = annual[name]
        result[f"cleaned_d_{name}"] = delta(series.get((country, str(year))), series.get((country, str(year - 1))))
    return result


def build_quarters(columns, rows, metadata, sources):
    result = []
    for country in sorted(metadata):
        previous = None
        for year in YEARS:
            for quarter in range(1, 5):
                months = quarter_months(year, quarter)
                out = {
                    "iso": metadata[country][0], "country": country, "group": metadata[country][1],
                    "date": f"{months[0]}-01", "year_quarter": f"{year}-Q{quarter}",
                }
                for column in columns:
                    if column in {"iso", "country", "group", "date"}:
                        continue
                    if column in TEXT_COLUMNS:
                        values = [rows[(country, month)][column].strip() for month in months]
                        out[column] = "|".join(sorted(set(values))) if all(values) else None
                    else:
                        values = [panel_number(rows, country, month, column) for month in months]
                        method = "sum" if column in SUM_COLUMNS else "annual" if column in ANNUAL_COLUMNS else "mean"
                        out[column] = aggregate(values, method)
                out["ln_vix"] = aggregate([log_value(panel_number(rows, country, m, "vix")) for m in months], "mean")
                out.update(cleaned_quarter(country, year, quarter, *sources))
                for name in MODEL_LAGS:
                    out[f"{name}_lag1q"] = previous[name] if previous is not None else None
                for aspect in ASPECTS:
                    wgi, gpr = out[f"wgi_{aspect}_lag1q"], out["gpr_z"]
                    out[f"wgi_{aspect}_lag1q_x_gpr_z"] = wgi * gpr if wgi is not None and gpr is not None else None
                result.append(out)
                previous = out
    return result


def comparison(name, pairs, notes):
    both = [(a, b) for a, b in pairs if a is not None and b is not None]
    matches = sum(math.isclose(a, b, rel_tol=1e-8, abs_tol=1e-6) for a, b in both)
    return {
        "check": name, "compared": len(both), "matches": matches, "mismatches": len(both) - matches,
        "left_only": sum(a is not None and b is None for a, b in pairs),
        "right_only": sum(a is None and b is not None for a, b in pairs),
        "max_abs_difference": max((abs(a - b) for a, b in both), default=None), "notes": notes,
    }


def validation(rows, panel_rows, metadata, sources):
    checks = []
    same = [
        "gpr", "reer", "policy_rate", "inflation", "oil_price", "vix", "gepu",
        "public_debt_gdp", *(f"wgi_{a}" for a in ASPECTS),
        "d_log_reer", "d_policy_rate", "d_inflation", "d_log_oil", "d_log_gepu",
        "d_public_debt_gdp", *(f"d_wgi_{a}" for a in ASPECTS), "ln_vix",
    ]
    for name in same:
        pairs = [(r[name], r[f"cleaned_{name}"]) for r in rows]
        checks.append(comparison(f"quarterly_panel_vs_cleaned_{name}", pairs,
            "Left: panel; right: separately sourced cleaned data. Match tolerance: abs 1e-6 or relative 1e-8; different sources may legitimately differ."))
    checks.append({
        "check": "financial_development_not_comparable", "compared": None, "matches": None,
        "mismatches": None, "left_only": None, "right_only": None, "max_abs_difference": None,
        "notes": "Panel IMF financial-development index and cleaned fd_fdi_ovrl are different indicators; not substituted or compared.",
    })
    for name, base, log in (
        ("d_log_reer", "reer", True), ("d_policy_rate", "policy_rate", False),
        ("d_inflation", "inflation", False), ("d_log_oil", "oil_price", True),
        ("d_log_gepu", "gepu", True),
    ):
        pairs = []
        for country, month in panel_rows:
            actual = panel_number(panel_rows, country, month, name)
            expected = delta(panel_number(panel_rows, country, month, base),
                             panel_number(panel_rows, country, previous_month(month), base), log)
            pairs.append((actual, expected))
        checks.append(comparison(f"monthly_panel_recomputed_{name}", pairs,
            "Left: stored monthly change; right: recomputed from consecutive panel months; includes missingness counts."))
    pairs = []
    for country in metadata:
        months = [f"{year}-{month:02d}" for year in YEARS for month in range(1, 13)]
        raw = [panel_number(panel_rows, country, month, "gpr") for month in months]
        valid = [value for value in raw if value is not None]
        mean = statistics.mean(valid) if valid else None
        sd = statistics.stdev(valid) if len(valid) > 1 else None
        for month, value in zip(months, raw):
            expected = (value - mean) / sd if value is not None and sd else None
            pairs.append((panel_number(panel_rows, country, month, "gpr_z"), expected))
    checks.append(comparison("monthly_panel_recomputed_gpr_z", pairs,
        "Stored z-score versus country mean and sample SD over available 2000–2023 monthly GPR."))
    for base in ("financial_development", "public_debt_gdp", *(f"wgi_{a}" for a in ASPECTS)):
        pairs = []
        for country in metadata:
            for year in YEARS:
                month = f"{year}-01"
                actual = panel_number(panel_rows, country, month, f"d_{base}")
                expected = delta(panel_number(panel_rows, country, month, base),
                                 panel_number(panel_rows, country, f"{year - 1}-01", base))
                pairs.append((actual, expected))
        checks.append(comparison(f"annual_panel_recomputed_d_{base}", pairs,
            "Left: stored annual change in January; right: panel annual value minus previous calendar year."))
    return checks


def write_csv(path, columns, rows):
    with path.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=columns, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def write_codebook(columns, rows):
    with PANEL_CODEBOOK.open(encoding="utf-8-sig", newline="") as source:
        definitions = {r["variable"]: r for r in csv.DictReader(source)}
    codebook = []
    for name in rows[0]:
        source, unit, convention = "", "", ""
        if name in {"iso", "country", "group"}:
            source, convention = "country_month.csv", "Unchanged country metadata."
        elif name == "date":
            source, convention = "country_month.csv", "First day of the calendar quarter; monthly date replaced by quarter start."
        elif name == "year_quarter":
            source, convention = "Calculated", "Calendar quarter YYYY-Q1 through YYYY-Q4."
        elif name in columns:
            source = "cleaned\\replication_cleaned\\country_month.csv"
            original = definitions[name]["description"]
            unit = definitions[name]["unit"]
            if name in TEXT_COLUMNS:
                convention = "Distinct monthly source labels joined by |; blank if any month is missing."
            elif name in ANNUAL_COLUMNS:
                convention = "Annual value repeated in quarter; all three months required and must agree."
            elif name in SUM_COLUMNS:
                convention = "Sum of three monthly values; blank unless all three exist."
            else:
                convention = "Arithmetic mean of three monthly values; blank unless all three exist."
            convention = f"{original}. {convention} Panel definition: {definitions[name]['source']}"
        elif name == "ln_vix":
            source, convention = "country_month.csv", "Mean of three monthly natural logs of positive VIX; all three required."
        elif name.startswith("cleaned_"):
            variable = name[len("cleaned_"):]
            changes = {
                "d_policy_rate": ("policy_rate", False), "d_inflation": ("inflation", False),
                "d_log_reer": ("reer", True), "d_log_oil": ("oil_price", True),
                "d_log_gepu": ("gepu", True),
            }
            if variable == "ln_vix":
                source, unit = CLEANED_SOURCES["vix"]
                convention = "Mean of three monthly natural logs of positive VIX; all three months required."
            elif variable in changes:
                base, logarithm = changes[variable]
                source, unit = CLEANED_SOURCES[base]
                unit = "log change" if logarithm else f"change in {unit}"
                convention = ("Sum of three consecutive monthly changes in "
                              + ("natural log " if logarithm else "") + base
                              + "; all three changes and the preceding month required.")
            elif variable.startswith("d_"):
                base = variable[2:]
                source, unit = CLEANED_SOURCES[base]
                unit = f"change in {unit}"
                convention = "Annual value minus previous calendar year; repeated each quarter without summing."
            else:
                source, unit = CLEANED_SOURCES[variable]
                convention = ("Annual value repeated each quarter."
                              if variable in {"public_debt_gdp", "fd_fdi_ovrl", *(f"wgi_{a}" for a in ASPECTS)}
                              else "Arithmetic mean of three monthly values; all three months required.")
            convention += " Separate cleaned-source series; not substituted for panel values."
            if "fd_fdi_ovrl" in variable:
                convention += " This indicator is not the IMF financial-development index in the panel."
        elif name.endswith("_lag1q"):
            source, convention = "Calculated from panel quarterly values", "Value in previous calendar quarter for same country; no gap bridging."
        elif name.endswith("_lag1q_x_gpr_z"):
            source, convention = "Calculated from panel quarterly values", "Previous-quarter WGI times current-quarter mean stored monthly gpr_z; no centering."
        else:
            raise ValueError(f"No codebook convention for {name}")
        codebook.append({"variable": name, "source": source, "unit": unit, "convention": convention})
    write_csv(CODEBOOK, ["variable", "source", "unit", "convention"], codebook)


def main():
    columns, panel_rows, metadata = load_panel(PANEL)
    sources = load_cleaned()
    rows = build_quarters(columns, panel_rows, metadata, sources)
    checks = validation(rows, panel_rows, metadata, sources)
    write_csv(DATASET, list(rows[0]), rows)
    write_codebook(columns, rows)
    write_csv(REPORT, ["check", "compared", "matches", "mismatches", "left_only", "right_only", "max_abs_difference", "notes"], checks)
    print(f"Wrote {len(rows)} quarters for {len(metadata)} countries to {DATASET}")
    print(f"Wrote conventions to {CODEBOOK} and comparison results to {REPORT}")


if __name__ == "__main__":
    main()
