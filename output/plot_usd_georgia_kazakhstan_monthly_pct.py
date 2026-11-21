"""Monthly USD exchange rate change for Georgia and Kazakhstan: USD per local unit.

Input is a daily quote file. The series used here is USD per unit of local
currency (USD_per_GEL, USD_per_KZT), so a rise means the local currency
appreciated against the dollar. Daily quotes are collapsed to a monthly period
average, matching the convention of cleaned/fx_rate.csv.

Two charts are produced, each with two stacked panels (one per country):

1. Cumulative percent change from the first month.
2. Month-on-month percent change.

Both panels within a chart share the same y-axis limits and the same y tick
spacing (5 percentage points), so the two countries can be compared directly
across charts. Feb-Mar 2022 is shaded and labelled.
"""

import csv
import os
import sys
from datetime import date

# matplotlib is not installed in the system interpreter; fall back to a local
# target install if it is present there.
try:
    import matplotlib  # noqa: F401
except ModuleNotFoundError:
    sys.path.insert(0, "/tmp/pylibs")

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
import matplotlib.pyplot as plt


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(
    "/Users/liontsui/.cursor/projects",
    "Users-liontsui-Documents-ECON-4999B-Research-econ4999b-research",
    "attachments",
    "8d0bf2d4-0cb5-47d4-bea9-dfb4fe1d64b1",
    "Georgia_Kazakhstan_USD_2020-02_to_2024-02.csv",
)
OUT_DIR = os.path.join(ROOT, "output")
FIG_DIR = os.path.join(OUT_DIR, "figures")
CSV_OUT = os.path.join(OUT_DIR, "usd_gel_kzt_monthly_pct_change.csv")
PNG_CUM = os.path.join(FIG_DIR, "usd_gel_kzt_monthly_cumulative_pct_change.png")
PNG_MOM = os.path.join(FIG_DIR, "usd_gel_kzt_monthly_pct_change.png")

# (source column, series key, country, axis label)
COUNTRIES = [
    ("USD_per_GEL", "GEL", "Georgia", "Georgian lari (GEL)"),
    ("USD_per_KZT", "KZT", "Kazakhstan", "Kazakhstani tenge (KZT)"),
]

NAVY = "#003049"
ORANGE = "#dd7547"
ORANGE_PALE = "#f6d9c9"
GREY = "#5b6b78"

TICK_STEP = 5  # percentage points between y ticks, identical on every panel

SHOCK_START = date(2022, 2, 1)
SHOCK_END = date(2022, 4, 1)  # exclusive edge, covers all of March


def load_daily():
    with open(SRC, newline="", encoding="utf-8") as fh:
        raw = list(csv.DictReader(fh))
    rows = [{"date": date.fromisoformat(r["date"])} for r in raw]
    for col, key, _name, _label in COUNTRIES:
        for r, raw_row in zip(rows, raw):
            r[key] = float(raw_row[col])
    rows.sort(key=lambda r: r["date"])
    return rows


def to_monthly(rows):
    """Collapse daily quotes to a monthly period average."""
    buckets = {}
    for r in rows:
        key = date(r["date"].year, r["date"].month, 1)
        b = buckets.setdefault(key, {k: [] for _c, k, _n, _l in COUNTRIES})
        for _col, k, _n, _l in COUNTRIES:
            b[k].append(r[k])

    monthly = []
    for key in sorted(buckets):
        b = buckets[key]
        monthly.append(
            {k: sum(b[k]) / len(b[k]) for _c, k, _n, _l in COUNTRIES}
            | {"date": key, "n_days": len(b[COUNTRIES[0][1]])}
        )
    return monthly


def cumulative_pct(levels):
    base = levels[0][1]
    return [(d, (v / base - 1.0) * 100.0) for d, v in levels]


def month_on_month(levels):
    return [
        (levels[i][0], (levels[i][1] / levels[i - 1][1] - 1.0) * 100.0)
        for i in range(1, len(levels))
    ]


def stdev(vals):
    m = sum(vals) / len(vals)
    return (sum((v - m) ** 2 for v in vals) / len(vals)) ** 0.5


def shared_limits(series_list, step=TICK_STEP):
    """Limits on a common step grid, wide enough for every panel."""
    vals = [v for series in series_list for _d, v in series]
    lo = min(0, int(min(vals) // step) * step)
    hi = max(0, int(-(-max(vals) // step)) * step)
    if lo == hi:
        hi = lo + step
    return lo, hi


def style_axis(ax, lo, hi):
    ax.set_ylim(lo, hi)
    ax.yaxis.set_major_locator(mticker.MultipleLocator(TICK_STEP))
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%+.0f%%"))
    ax.grid(axis="y", color="#cad7df", lw=0.6, alpha=0.9)
    for side, spine in ax.spines.items():
        spine.set_visible(side in ("left", "bottom"))
        spine.set_color("#cad7df")
    ax.tick_params(labelsize=8, colors=NAVY)
    ax.margins(x=0.015)


def date_axis(ax):
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=(1, 7)))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))


def shade_shock(ax):
    ax.axvspan(SHOCK_START, SHOCK_END, color=ORANGE_PALE, alpha=0.75, zorder=0)
    ax.annotate(
        "Feb-Mar 2022",
        xy=(SHOCK_START, 0.97),
        xycoords=("data", "axes fraction"),
        xytext=(3, 0),
        textcoords="offset points",
        va="top",
        ha="left",
        fontsize=7.5,
        color=ORANGE,
        fontweight="bold",
    )


def plot_cumulative(panel_data):
    lo, hi = shared_limits([cum for _n, _l, _lv, cum, _m in panel_data])
    fig, axes = plt.subplots(
        len(panel_data), 1, figsize=(11.5, 7.2), sharex=True, dpi=160
    )
    fig.patch.set_facecolor("white")

    for ax, (name, label, levels, cum, _mom) in zip(axes, panel_data):
        dates = [d for d, _ in cum]
        vals = [v for _, v in cum]

        shade_shock(ax)
        ax.axhline(0, color=NAVY, lw=0.9, zorder=2)
        ax.plot(dates, vals, color=NAVY, lw=1.3, marker="o", ms=2.6,
                mfc=NAVY, mec="white", mew=0.5, zorder=3)
        ax.fill_between(dates, 0, vals, color=NAVY, alpha=0.07, zorder=1)

        shock_pts = [(d, v) for d, v in cum if SHOCK_START <= d < SHOCK_END]
        if shock_pts:
            ax.scatter([d for d, _ in shock_pts], [v for _, v in shock_pts],
                       s=28, color=ORANGE, zorder=5, linewidths=0)

        last_d, last_v = cum[-1]
        ax.annotate(
            f"{last_v:+.1f}%",
            xy=(last_d, last_v),
            xytext=(-6, 9 if last_v > 0 else -15),
            textcoords="offset points",
            ha="right",
            fontsize=9,
            color=NAVY,
            fontweight="bold",
        )

        ax.set_title(
            f"USD per {label}   |   cumulative % change since "
            f"{levels[0][0]:%b %Y}   |   "
            f"{levels[0][1]:.5g} -> {levels[-1][1]:.5g} USD per unit",
            loc="left",
            fontsize=9.5,
            color=NAVY,
            fontweight="bold",
            pad=8,
        )
        ax.set_ylabel("% vs. base", fontsize=8.5, color=NAVY)
        style_axis(ax, lo, hi)

    date_axis(axes[-1])
    fig.text(
        0.008,
        0.006,
        "Monthly period averages of daily quotes, quoted as USD per unit of local currency. "
        f"Positive = local currency appreciated. Both panels share the same y scale "
        f"({lo:+.0f}% to {hi:+.0f}%, {TICK_STEP}-point ticks). Shaded window = Feb-Mar 2022.",
        fontsize=7.2,
        color=GREY,
    )
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(PNG_CUM, facecolor="white")
    return PNG_CUM


def plot_month_on_month(panel_data):
    lo, hi = shared_limits([mom for _n, _l, _lv, _c, mom in panel_data])
    fig, axes = plt.subplots(
        len(panel_data), 1, figsize=(11.5, 7.4), sharex=True, dpi=160
    )
    fig.patch.set_facecolor("white")

    for ax, (name, label, levels, _cum, mom) in zip(axes, panel_data):
        dates = [d for d, _ in mom]
        vals = [v for _, v in mom]
        sd = stdev(vals)

        shade_shock(ax)
        ax.axhline(0, color=NAVY, lw=0.9, zorder=2)
        ax.plot(dates, vals, color=NAVY, lw=1.4, marker="o", ms=3.2,
                mfc=NAVY, mec="white", mew=0.6, zorder=3)

        shock_pts = [(d, v) for d, v in mom if SHOCK_START <= d < SHOCK_END]
        if shock_pts:
            ax.scatter([d for d, _ in shock_pts], [v for _, v in shock_pts],
                       s=34, color=ORANGE, zorder=5, linewidths=0)
            for d, v in shock_pts:
                ax.annotate(
                    f"{v:+.1f}%",
                    xy=(d, v),
                    xytext=(0, 8 if v > 0 else -16),
                    textcoords="offset points",
                    ha="center",
                    fontsize=8,
                    color=ORANGE,
                    fontweight="bold",
                )

        ax.set_title(
            f"USD per {label}   |   monthly % change   |   "
            f"mean {sum(vals)/len(vals):+.2f}%, sd {sd:.2f}%   |   "
            f"{len(vals)} months",
            loc="left",
            fontsize=9.5,
            color=NAVY,
            fontweight="bold",
            pad=8,
        )
        ax.set_ylabel("% change", fontsize=8.5, color=NAVY)
        style_axis(ax, lo, hi)

    date_axis(axes[-1])
    fig.text(
        0.008,
        0.006,
        "Monthly period averages of daily quotes, quoted as USD per unit of local currency. "
        f"Positive = local currency appreciated. Both panels share the same y scale "
        f"({lo:+.0f}% to {hi:+.0f}%, {TICK_STEP}-point ticks). Shaded window = Feb-Mar 2022.",
        fontsize=7.2,
        color=GREY,
    )
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(PNG_MOM, facecolor="white")
    return PNG_MOM


def plot_single_country(panel_data, lo, hi):
    """One standalone figure per country, all on the same y scale.

    These are placed side by side on a slide, so the figure is sized and the
    type scaled for projection rather than for a report page.
    """
    paths = {}
    for (name, label, levels, _cum, mom) in panel_data:
        fig, ax = plt.subplots(figsize=(6.0, 3.2), dpi=220)
        fig.patch.set_facecolor("white")

        dates = [d for d, _ in mom]
        vals = [v for _, v in mom]
        sd = stdev(vals)

        shade_shock(ax)
        ax.axhline(0, color=NAVY, lw=1.3, zorder=2)
        ax.plot(dates, vals, color=NAVY, lw=2.6, marker="o", ms=5.4,
                mfc=NAVY, mec="white", mew=0.9, zorder=3)

        shock_pts = [(d, v) for d, v in mom if SHOCK_START <= d < SHOCK_END]
        if shock_pts:
            ax.scatter([d for d, _ in shock_pts], [v for _, v in shock_pts],
                       s=70, color=ORANGE, zorder=5, linewidths=0)
            for d, v in shock_pts:
                ax.annotate(
                    f"{v:+.1f}%",
                    xy=(d, v),
                    xytext=(0, 10 if v > 0 else -20),
                    textcoords="offset points",
                    ha="center",
                    fontsize=13.5,
                    color=ORANGE,
                    fontweight="bold",
                )

        ax.set_title(
            f"USD per {label}",
            loc="left",
            fontsize=17,
            color=NAVY,
            fontweight="bold",
            pad=26,
        )
        ax.text(
            0.0,
            1.015,
            f"monthly % change, mean {sum(vals)/len(vals):+.2f}%, sd {sd:.2f}%",
            transform=ax.transAxes,
            fontsize=12,
            color=GREY,
            va="bottom",
            ha="left",
        )
        ax.set_ylabel("% change", fontsize=12.5, color=NAVY)
        style_axis(ax, lo, hi)
        ax.tick_params(axis="both", labelsize=12)
        ax.yaxis.set_major_locator(mticker.MultipleLocator(10))
        date_axis(ax)
        ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=(1,), bymonthday=1))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        fig.tight_layout()
        path = os.path.join(
            FIG_DIR, f"usd_per_{label.split('(')[1].rstrip(')')}_monthly_pct_change.png"
        )
        fig.savefig(path, facecolor="white")
        plt.close(fig)
        paths[name] = path
    return paths


def main():
    os.makedirs(FIG_DIR, exist_ok=True)
    monthly = to_monthly(load_daily())

    panel_data = []
    for _col, key, name, label in COUNTRIES:
        levels = [(r["date"], r[key]) for r in monthly]
        panel_data.append(
            (name, label, levels, cumulative_pct(levels), month_on_month(levels))
        )

    with open(CSV_OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "year_month",
                "country",
                "usd_per_local_month_avg",
                "cum_pct_change",
                "monthly_pct_change",
            ]
        )
        for name, _label, levels, cum, mom in panel_data:
            cum_map = dict(cum)
            mom_map = dict(mom)
            for d, v in levels:
                mv = mom_map.get(d, "")
                w.writerow(
                    [
                        f"{d:%Y-%m}",
                        name,
                        f"{v:.8f}",
                        f"{cum_map[d]:.6f}",
                        f"{mv:.6f}" if mv != "" else "",
                    ]
                )

    print("wrote", CSV_OUT)
    print("wrote", plot_cumulative(panel_data))
    print("wrote", plot_month_on_month(panel_data))

    mom_lo, mom_hi = shared_limits([mom for _n, _l, _lv, _c, mom in panel_data])
    for name, path in plot_single_country(panel_data, mom_lo, mom_hi).items():
        print("wrote", path, f"({name})")

    for name, _label, levels, cum, mom in panel_data:
        vals = [v for _, v in mom]
        shock = [(d, v) for d, v in mom if SHOCK_START <= d < SHOCK_END]
        print(
            f"{name}: months={len(levels)} | {levels[0][0]:%Y-%m} "
            f"{levels[0][1]:.6f} -> {levels[-1][0]:%Y-%m} {levels[-1][1]:.6f} USD/unit | "
            f"cumulative {cum[-1][1]:+.1f}% | monthly mean {sum(vals)/len(vals):+.2f}% "
            f"sd {stdev(vals):.2f}% | shock: "
            + ", ".join(f"{d:%Y-%m} {v:+.2f}%" for d, v in shock)
        )


if __name__ == "__main__":
    main()
