import unittest

from institution_group_diagnostics import YEARS, build_diagnostics


class GroupDiagnosticsTests(unittest.TestCase):
    def test_group_coverage_missing_and_outlier(self):
        countries = {
            str(i): {"iso": str(i), "country": f"Country {i}", "group": "emerging"}
            for i in range(5)
        }
        countries["A"] = {"iso": "A", "country": "Other", "group": "advanced"}
        values = {
            (f"Country {i}", "va", 2000): value
            for i, value in enumerate([0, 0, 0, 0, 10])
        }
        values[("Other", "va", 2000)] = 2
        data, outliers, missing = build_diagnostics(countries, values)

        self.assertEqual(len(data["emerging"]["va"]), 5)
        self.assertEqual(len(data["advanced"]["va"]), 1)
        self.assertEqual(data["emerging"]["va"][0]["scores"][0], 0)
        self.assertIsNone(data["emerging"]["va"][0]["scores"][1])
        self.assertEqual(len(data["emerging"]["va"][0]["scores"]), len(YEARS))
        self.assertEqual([o["country"] for o in outliers], ["Country 4"])
        self.assertIn("Other", missing[("advanced", "pv")])

    def test_aliases_match_panel_to_wgi(self):
        countries = {
            "KR": {"iso": "KR", "country": "Korea", "group": "advanced"},
            "TR": {"iso": "TR", "country": "Turkiye", "group": "emerging"},
        }
        values = {("South Korea", "va", 2000): 0.5, ("Turkey", "va", 2000): -0.5}
        data, _, _ = build_diagnostics(countries, values)
        self.assertEqual(data["advanced"]["va"][0]["scores"][0], 0.5)
        self.assertEqual(data["emerging"]["va"][0]["scores"][0], -0.5)


if __name__ == "__main__":
    unittest.main()
