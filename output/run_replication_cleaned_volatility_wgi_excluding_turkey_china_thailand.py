"""Run the cleaned volatility/WGI models without Turkey, China, or Thailand."""

import os

import run_replication_cleaned_volatility_wgi as model


EXCLUDED_COUNTRIES = {"turkey", "turkiye", "china", "thailand"}
OUTPUT_STEM = (
    "replication_cleaned_volatility_wgi_excluding_turkey_china_thailand_results"
)


def main():
    panel = [
        row
        for row in model.load_panel()
        if row["country"].strip().casefold() not in EXCLUDED_COUNTRIES
    ]
    panel = model.attach_lags(panel)
    all_countries = list(dict.fromkeys(row["country"] for row in panel))
    results = {}

    for code in model.DIMENSIONS:
        rows, center = model.complete_cases(panel, model.est.read_wgi(code))
        fitted = model.fit(rows)
        results[code] = {"fit": fitted, "center": center}
        print(
            code, "N", fitted["n_obs"], "countries", fitted["n_country"],
            "R2", round(fitted["r2"], 4), "center", round(center, 4),
            fitted["month_min"], fitted["month_max"],
        )
        print(" ", ", ".join(fitted["countries"]))
        lookup = {name: i for i, name in enumerate(fitted["names"])}
        for name in ("gpr_z", "wgi", "wgi_x_gpr"):
            i = lookup[name]
            print(
                " ", name,
                round(float(fitted["beta"][i]), 4),
                "within", round(fitted["p_within"][i], 4),
                model.est.stars(fitted["p_within"][i]),
                "cluster", round(fitted["p_cluster"][i], 4),
                model.est.stars(fitted["p_cluster"][i]),
            )

    model.write_outputs(
        os.path.join(model.OUTPUT, f"{OUTPUT_STEM}.csv"),
        os.path.join(model.OUTPUT, f"{OUTPUT_STEM}.html"),
        results,
        all_countries,
        sample_note="Restricted sample excludes Turkey/Turkiye, China, and Thailand.",
    )


if __name__ == "__main__":
    main()
