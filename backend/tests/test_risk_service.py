import unittest

from app.models.risk import RiskAssessmentRequest, RiskLevel
from app.services.risk_service import (
    RECOMMENDED_ACTIONS,
    SignalSeverity,
    calculate_risk_score,
    evaluate_risk,
)


class RiskServiceTests(unittest.TestCase):
    def evaluate(
        self,
        rainfall: float,
        river_level: float,
        river_change: float,
    ):
        return evaluate_risk(
            RiskAssessmentRequest(
                rainfall_intensity_mm_per_hour=rainfall,
                river_level_m=river_level,
                river_change_m_per_hour=river_change,
                station_id="demo-station",
            )
        )

    def test_all_green(self):
        result = self.evaluate(5.0, 1.2, 0.02)
        self.assertEqual(result.risk_level, RiskLevel.GREEN)
        self.assertEqual(result.risk_score, 0)

    def test_exact_yellow_boundaries(self):
        cases = [
            (15.0, 0.0, 0.0),
            (0.0, 2.0, 0.0),
            (0.0, 0.0, 0.10),
        ]

        for case in cases:
            with self.subTest(case=case):
                result = self.evaluate(*case)
                self.assertEqual(result.risk_level, RiskLevel.YELLOW)
                self.assertEqual(result.risk_score, 25)

    def test_exact_orange_boundaries(self):
        cases = [
            (30.0, 0.0, 0.0),
            (0.0, 3.0, 0.0),
            (0.0, 0.0, 0.30),
        ]

        for case in cases:
            with self.subTest(case=case):
                result = self.evaluate(*case)
                self.assertEqual(result.risk_level, RiskLevel.ORANGE)
                self.assertEqual(result.risk_score, 50)

    def test_exact_red_boundaries(self):
        cases = [
            (50.0, 0.0, 0.0),
            (0.0, 4.0, 0.0),
            (0.0, 0.0, 0.60),
        ]

        for case in cases:
            with self.subTest(case=case):
                result = self.evaluate(*case)
                self.assertEqual(result.risk_level, RiskLevel.RED)
                self.assertEqual(result.risk_score, 75)

    def test_values_just_below_thresholds(self):
        cases = [
            ((14.99, 0.0, 0.0), RiskLevel.GREEN, 0),
            ((29.99, 0.0, 0.0), RiskLevel.YELLOW, 25),
            ((49.99, 0.0, 0.0), RiskLevel.ORANGE, 50),
            ((0.0, 1.99, 0.0), RiskLevel.GREEN, 0),
            ((0.0, 2.99, 0.0), RiskLevel.YELLOW, 25),
            ((0.0, 3.99, 0.0), RiskLevel.ORANGE, 50),
            ((0.0, 0.0, 0.09), RiskLevel.GREEN, 0),
            ((0.0, 0.0, 0.29), RiskLevel.YELLOW, 25),
            ((0.0, 0.0, 0.59), RiskLevel.ORANGE, 50),
        ]

        for values, expected_level, expected_score in cases:
            with self.subTest(values=values):
                result = self.evaluate(*values)
                self.assertEqual(result.risk_level, expected_level)
                self.assertEqual(result.risk_score, expected_score)

    def test_values_just_above_thresholds(self):
        cases = [
            ((15.01, 0.0, 0.0), RiskLevel.YELLOW, 25),
            ((30.01, 0.0, 0.0), RiskLevel.ORANGE, 50),
            ((50.01, 0.0, 0.0), RiskLevel.RED, 75),
            ((0.0, 2.01, 0.0), RiskLevel.YELLOW, 25),
            ((0.0, 3.01, 0.0), RiskLevel.ORANGE, 50),
            ((0.0, 4.01, 0.0), RiskLevel.RED, 75),
            ((0.0, 0.0, 0.11), RiskLevel.YELLOW, 25),
            ((0.0, 0.0, 0.31), RiskLevel.ORANGE, 50),
            ((0.0, 0.0, 0.61), RiskLevel.RED, 75),
        ]

        for values, expected_level, expected_score in cases:
            with self.subTest(values=values):
                result = self.evaluate(*values)
                self.assertEqual(result.risk_level, expected_level)
                self.assertEqual(result.risk_score, expected_score)

    def test_mixed_severities_follow_exact_formula(self):
        result = self.evaluate(35.0, 3.2, 0.20)

        self.assertEqual(result.risk_level, RiskLevel.ORANGE)
        self.assertEqual(result.risk_score, 62)

    def test_all_red(self):
        result = self.evaluate(70.0, 4.5, 0.80)

        self.assertEqual(result.risk_level, RiskLevel.RED)
        self.assertEqual(result.risk_score, 99)

    def test_negative_river_change_is_green_signal(self):
        result = self.evaluate(0.0, 0.0, -0.20)

        self.assertEqual(result.risk_level, RiskLevel.GREEN)
        self.assertEqual(result.risk_score, 0)
        self.assertIn("falling", result.reasons[0].lower())

    def test_repeated_calculations_are_deterministic(self):
        request = RiskAssessmentRequest(
            rainfall_intensity_mm_per_hour=35.0,
            river_level_m=3.2,
            river_change_m_per_hour=0.20,
        )

        first = evaluate_risk(request)

        for _ in range(10):
            self.assertEqual(evaluate_risk(request), first)

    def test_score_stays_in_range(self):
        for severity_1 in SignalSeverity:
            for severity_2 in SignalSeverity:
                for severity_3 in SignalSeverity:
                    score = calculate_risk_score(
                        [severity_1, severity_2, severity_3]
                    )

                    self.assertGreaterEqual(score, 0)
                    self.assertLessEqual(score, 100)

    def test_reasons_match_actual_signals(self):
        result = self.evaluate(35.0, 1.0, 0.35)
        joined = " ".join(result.reasons)

        self.assertIn("Rainfall intensity", joined)
        self.assertIn("River level rise rate", joined)
        self.assertNotIn("River level is", joined)

    def test_action_matches_risk_level(self):
        cases = [
            ((5.0, 1.0, 0.0), RiskLevel.GREEN),
            ((15.0, 1.0, 0.0), RiskLevel.YELLOW),
            ((30.0, 1.0, 0.0), RiskLevel.ORANGE),
            ((50.0, 1.0, 0.0), RiskLevel.RED),
        ]

        for values, expected_level in cases:
            with self.subTest(values=values):
                result = self.evaluate(*values)

                self.assertEqual(
                    result.recommended_action,
                    RECOMMENDED_ACTIONS[expected_level],
                )


if __name__ == "__main__":
    unittest.main()
