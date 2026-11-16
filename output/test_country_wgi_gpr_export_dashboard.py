import math
import tempfile
import unittest
from pathlib import Path

import openpyxl

from build_country_wgi_gpr_export_dashboard import (
    annual_changes,
    annual_log_changes,
    base_100_index,
    control_points,
    correlation_rows,
    read_annual_country_values,
    read_financial_development_index,
    read_global_annual_log_means,
    read_workbook_annual_means,
)


class DashboardSeriesTests(unittest.TestCase):
    def test_annual_changes_use_means_and_do_not_bridge_missing_years(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "levels.xlsx"
            workbook = openpyxl.Workbook()
            sheet = workbook.active
            sheet.append(["month", "A", "B"])
            sheet.append([None, "units", "units"])
            sheet.append(["2000-01", 100, None])
            sheet.append(["2000-02", 300, None])
            sheet.append(["2001-01", 400, 50])
            sheet.append(["2003-01", 800, 100])
            workbook.save(path)
            workbook.close()
            changes = annual_log_changes(read_workbook_annual_means(path))

        self.assertAlmostEqual(changes[("A", 2001)], math.log(2))
        self.assertNotIn(("A", 2003), changes)
        self.assertNotIn(("B", 2003), changes)
        indexed = base_100_index([changes[("A", 2001)], 0])
        self.assertEqual(indexed[0], 100)
        self.assertAlmostEqual(indexed[1], 0)

    def test_nonpositive_levels_raise(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "levels.xlsx"
            workbook = openpyxl.Workbook()
            workbook.active.append(["month", "A"])
            workbook.active.append(["2000-01", 0])
            workbook.save(path)
            workbook.close()
            with self.assertRaisesRegex(ValueError, "Non-positive"):
                read_workbook_annual_means(path)

    def test_reer_correlations_use_pairwise_complete_annual_changes(self):
        wgi = {("A", 2001, "va"): 1, ("A", 2002, "va"): 2}
        gpr = {("A", 2001): 3, ("A", 2002): 5}
        exports = {("A", 2001): 0.1, ("A", 2002): 0.2}
        reer = {("A", 2001): -0.1, ("A", 2002): 0.1}
        _, _, observations, correlations, pooled = correlation_rows(
            wgi, gpr, exports, {}, {}, reer
        )
        self.assertEqual(observations["A|va"][0]["reer_log_change"], -0.1)
        pair = correlations[0]["pairs"]["export_log_change|reer_log_change"]
        self.assertEqual(pair["n"], 2)
        self.assertAlmostEqual(pair["r"], 1)
        self.assertEqual(len(pooled), 60)

    def test_global_controls_average_monthly_logs(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "global.csv"
            path.write_text("year_month,value\n2001-01,1\n2001-02,9\n2003-01,4\n", encoding="utf-8")
            values = read_global_annual_log_means(path, "value")
        self.assertAlmostEqual(values[2001], math.log(9) / 2)
        points = control_points({"oil": values})
        self.assertEqual(points[0]["index_oil"], 100)
        self.assertIsNone(points[1]["oil"])
        self.assertIsNone(points[1]["index_oil"])
        self.assertAlmostEqual(points[2]["oil"], math.log(4))

    def test_global_log_changes_use_prior_year_and_do_not_bridge_gaps(self):
        values = {2000: math.log(2), 2001: math.log(4), 2003: math.log(8)}
        changes = annual_changes(values)
        self.assertAlmostEqual(changes[2001], math.log(2))
        self.assertNotIn(2003, changes)
        points = control_points({"oil_change": changes})
        self.assertAlmostEqual(points[0]["oil_change"], math.log(2))
        self.assertIsNone(points[2]["oil_change"])

    def test_country_controls_keep_annual_data_and_missing_index(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "debt.csv"
            path.write_text(
                "country,period,frequency,debt_gdp_pct\nA,2001,Annual,42\nA,2001,Quarterly,50\n",
                encoding="utf-8",
            )
            debt = read_annual_country_values(path, "period", "debt_gdp_pct", annual_only=True)
            path = Path(directory) / "index.csv"
            path.write_text(
                "country,date,financial_development\nKorea,2001-01-01,0.5\nKorea,2001-02-01,0.5\n",
                encoding="utf-8",
            )
            index = read_financial_development_index(path)
        self.assertEqual(debt[("A", 2001)], 42)
        self.assertEqual(index[("South Korea", 2001)], 0.5)
        points = control_points({"debt": debt, "index": index}, "A")
        self.assertEqual(points[0]["debt"], 42)
        self.assertEqual(points[0]["index_debt"], 100)
        self.assertIsNone(points[0]["index"])


if __name__ == "__main__":
    unittest.main()
