"""Small mathematical regression fixtures, not claimed game simulations."""
import unittest
from fractions import Fraction as F

from games.graveyard_shift.audit import (
    UINT64_MAX, audit, contract, distribution_metrics, maxzero_feasibility,
    mode_spec, suite_report, upper_tail_mean, validate_rows,
)


class AuditTests(unittest.TestCase):
    def test_exact_maxzero_probability_and_rtp(self):
        report = maxzero_feasibility()
        self.assertEqual(report["exact_hit_probability"], "481/12500")
        self.assertEqual(report["metrics"]["rtp"], F(481, 500))
        self.assertEqual(report["metrics"]["expected_payout_base_bet"], 962)
        self.assertFalse(report["publish_ready"])

    def test_current_maxzero_risks_are_not_critical_failures(self):
        c = maxzero_feasibility()["checks"]
        self.assertEqual(c["critical_distribution_failures"], [])
        self.assertEqual(set(c["three_star_risk_classes"]), {"tail_probability", "tail_liability"})

    def test_current_cost_normalization_and_raw_probabilities(self):
        m = maxzero_feasibility()["metrics"]
        self.assertEqual(m["etl10k_cost_normalized"], F("0.962"))
        self.assertEqual(m["etl40_cost_normalized"], 0)
        self.assertEqual(m["cvar_absolute"], 25000)
        self.assertEqual(m["cvar_per_mode_cost"], 25)
        self.assertEqual(m["prob10k_raw"], F("0.03848"))

    def test_tail_boundary_atom_is_split(self):
        self.assertEqual(upper_tail_mean({F(0): F(9999, 10000), F(1000): F(1, 10000)}), 100)

    def test_pay_unit_scaling(self):
        self.assertEqual(distribution_metrics([(0, 1, 100)], "base")["rtp"], 1)

    def test_cost_division(self):
        self.assertEqual(distribution_metrics([(0, 1, 300)], "ante")["rtp"], 1)

    def test_zero_weight_does_not_create_supported_maxwin(self):
        m = distribution_metrics([(0, 1, 100), (1, 0, 2500000)], "base")
        self.assertEqual(m["max_win_probability"], 0)
        self.assertEqual(m["max_supported_payout_base_bet"], 1)

    def test_duplicate_id_rejected(self):
        with self.assertRaises(ValueError):
            validate_rows([(0, 1, 0), (0, 1, 100)])

    def test_invalid_integer_inputs_rejected(self):
        for value in [True, -1, 1.5, "1.0", "1e3", "-1", UINT64_MAX + 1]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_rows([(0, value, 100)])

    def test_total_weight_overflow_rejected(self):
        with self.assertRaises(ValueError):
            validate_rows([(0, UINT64_MAX, 0), (1, 1, 100)])

    def test_zero_mass_rejected(self):
        for rows in [[], [(0, 0, 100)]]:
            with self.assertRaises(ValueError):
                validate_rows(rows)

    def test_illegal_payout_rejected(self):
        for payout in [1, 101, 2500010]:
            with self.assertRaises(ValueError):
                validate_rows([(0, 1, payout)])

    def test_nonzero_floor_and_base_std_enforced(self):
        result = audit([(0, 1, 0)], "base")
        self.assertIn("nonzero_probability", result["checks"]["critical_distribution_failures"])
        self.assertIn("base_standard_deviation_minimum", result["checks"]["critical_distribution_failures"])

    def test_all_seven_costs_preserved(self):
        self.assertEqual([m["cost"] for m in contract()["modes"]], [1, 3, 10, 100, 300, 500, 1000])
        self.assertEqual(mode_spec("hidden")["config_id"], "secretShift")

    def test_unknown_mode_rejected(self):
        with self.assertRaises(ValueError):
            mode_spec("old_bonus")

    def test_suite_requires_all_modes(self):
        with self.assertRaises(ValueError):
            suite_report({"base": [(0, 1, 100)]})

    def test_cross_mode_threshold_is_half_percentage_point(self):
        rows = {m["id"]: [(0, 44, 0), (1, 956, m["cost"] * 100)] for m in contract()["modes"]}
        rows["maxzero"] = [(0, 6011, 0), (1, 239, 2500000)]
        rows["base"] = [(0, 38, 0), (1, 962, 100)]
        report = suite_report(rows)
        self.assertEqual(report["cross_mode_spread"], F("0.006"))
        self.assertFalse(report["cross_mode_pass"])

    def test_maxzero_cannot_be_tuned_with_intermediate_wins(self):
        with self.assertRaises(ValueError):
            distribution_metrics([(0, 1, 100000)], "maxzero")

    def test_thresholds_are_strict_for_etl_and_inclusive_for_probability(self):
        m = distribution_metrics([(0, 1, 1000000)], "bonus")
        self.assertEqual(m["prob10k_raw"], 1)
        self.assertEqual(m["etl10k_cost_normalized"], 0)


if __name__ == "__main__":
    unittest.main()
