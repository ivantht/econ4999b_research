import math
import unittest
from unittest.mock import patch

import build_data_for_quarter_model as model


class QuarterlyModelTests(unittest.TestCase):
    def test_strict_quarterly_aggregation(self):
        self.assertEqual(model.aggregate([1, 2, 6], "mean"), 3)
        self.assertEqual(model.aggregate([1, 2, 6], "sum"), 9)
        self.assertIsNone(model.aggregate([1, None, 6], "sum"))
        self.assertEqual(model.aggregate([7, 7, 7], "annual"), 7)
        with self.assertRaisesRegex(ValueError, "Inconsistent annual"):
            model.aggregate([7, 8, 7], "annual")

    def test_cleaned_changes_use_previous_month_and_missing_values(self):
        monthly = {name: {} for name in ("gpr", "reer", "policy_rate", "inflation")}
        monthly["reer"] = {
            ("A", "1999-12"): 100, ("A", "2000-01"): 110,
            ("A", "2000-02"): 120, ("A", "2000-03"): 140,
        }
        globals_ = {name: {} for name in ("oil_price", "vix", "gepu")}
        annual = {name: {} for name in ("public_debt_gdp", "fd_fdi_ovrl", *(f"wgi_{a}" for a in model.ASPECTS))}
        annual["wgi_va"] = {("A", "1999"): 0.1, ("A", "2000"): 0.4}
        result = model.cleaned_quarter("A", 2000, 1, monthly, globals_, annual)
        self.assertAlmostEqual(result["cleaned_d_log_reer"], math.log(1.4))
        self.assertAlmostEqual(result["cleaned_d_wgi_va"], 0.3)
        del monthly["reer"][("A", "2000-02")]
        result = model.cleaned_quarter("A", 2000, 1, monthly, globals_, annual)
        self.assertIsNone(result["cleaned_reer"])
        self.assertIsNone(result["cleaned_d_log_reer"])

    def test_quarter_lag_interaction_and_annual_boundaries(self):
        names = {
            "gpr_z", "vix", "portfolio_inflow", "d_financial_development", "d_public_debt_gdp",
            "d_policy_rate", "d_inflation", "d_log_oil", "d_log_gepu", "d_log_reer",
            *(f"wgi_{a}" for a in model.ASPECTS),
        }
        columns = ["iso", "country", "group", "date", *sorted(names)]
        panel = {}
        for year in (2000, 2001):
            for month in range(1, 13):
                ym = f"{year}-{month:02d}"
                row = {name: "1" for name in names}
                row.update(iso="AA", country="A", group="Emerging", date=f"{ym}-01")
                for aspect in model.ASPECTS:
                    row[f"wgi_{aspect}"] = "2" if year == 2000 else "4"
                if year == 2000 and month in (1, 2, 3):
                    row["vix"] = str(math.exp(month - 1))
                if ym == "2000-11":
                    row["d_policy_rate"] = ""
                panel[("A", ym)] = row
        monthly = {name: {} for name in ("gpr", "reer", "policy_rate", "inflation")}
        globals_ = {name: {} for name in ("oil_price", "vix", "gepu")}
        annual = {name: {} for name in ("public_debt_gdp", "fd_fdi_ovrl", *(f"wgi_{a}" for a in model.ASPECTS))}
        with patch.object(model, "YEARS", range(2000, 2002)):
            rows = model.build_quarters(columns, panel, {"A": ("AA", "Emerging")}, (monthly, globals_, annual))
        first, next_year = rows[0], rows[4]
        self.assertEqual(first["portfolio_inflow"], 3)
        self.assertAlmostEqual(first["ln_vix"], 1)
        self.assertIsNone(first["wgi_va_lag1q"])
        self.assertEqual(next_year["wgi_va"], 4)
        self.assertEqual(next_year["wgi_va_lag1q"], 2)
        self.assertEqual(next_year["wgi_va_lag1q_x_gpr_z"], 2)
        self.assertIsNone(next_year["d_policy_rate_lag1q"])


if __name__ == "__main__":
    unittest.main()
