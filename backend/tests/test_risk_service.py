import unittest

from app.models.risk import RiskAssessmentRequest, RiskLevel
from app.services.risk_service import (
    RECOMMENDED_ACTIONS,
    SignalSeverity,
    calculate_risk_score,
    classify_forecast_rainfall,
    classify_live_rainfall,
    evaluate_risk,
)


class RiskServiceTests(unittest.TestCase):
    def evaluate(
        self,
        live_rainfall: float = 0.0,
        forecast_rainfall: float = 0.0,
        river_level: float = 0.0,
        river_change: float = 0.0,
        discharge: float = 0.0,
    ):
        return evaluate_risk(
            RiskAssessmentRequest(
                live_rainfall_intensity_mm_per_hour=live_rainfall,
                forecast_rainfall_intensity_mm_per_hour=forecast_rainfall,
                river_level_m=river_level,
                river_change_m_per_hour=river_change,
                upstream_discharge_m3_per_s=discharge,
                station_id="demo-station",
            )
        )

    def test_all_green(self):
        result = self.evaluate(
            live_rainfall=10.0,
            forecast_rainfall=10.0,
            river_level=1.2,
            river_change=0.02,
            discharge=100.0,
        )
        self.assertEqual(result.risk_level, RiskLevel.GREEN)
        self.assertEqual(result.risk_score, 0)

    def test_forecast_rainfall_rules(self):
        cases = [
            (10.0, SignalSeverity.GREEN),
            (29.99, SignalSeverity.GREEN),
            (30.00, SignalSeverity.GREEN),
            (30.01, SignalSeverity.YELLOW),
            (40.0, SignalSeverity.YELLOW),
        ]

        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(
                    classify_forecast_rainfall(value),
                    expected,
                )

    def test_live_rainfall_rules(self):
        cases = [
            (10.0, SignalSeverity.GREEN),
            (29.99, SignalSeverity.GREEN),
            (30.00, SignalSeverity.GREEN),
            (30.01, SignalSeverity.ORANGE),
            (50.00, SignalSeverity.ORANGE),
            (50.01, SignalSeverity.RED),
        ]

        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(
                    classify_live_rainfall(value),
                    expected,
                )

    def test_combined_rainfall_severity(self):
        cases = [
            (10.0, 40.0, RiskLevel.YELLOW, 25),
            (35.0, 40.0, RiskLevel.ORANGE, 50),
            (55.0, 40.0, RiskLevel.RED, 75),
            (35.0, 10.0, RiskLevel.ORANGE, 50),
            (50.0, 10.0, RiskLevel.ORANGE, 50),
        ]

        for live, forecast, level, score in cases:
            with self.subTest(live=live, forecast=forecast):
                result = self.evaluate(
                    live_rainfall=live,
                    forecast_rainfall=forecast,
                )

                self.assertEqual(result.risk_level, level)
                self.assertEqual(result.risk_score, score)

    def test_forecast_driven_reason(self):
        result = self.evaluate(
            live_rainfall=10.0,
            forecast_rainfall=40.0,
        )

        joined = " ".join(result.reasons)

        self.assertIn("Forecast rainfall is YELLOW", joined)
        self.assertIn(
            "Derived rainfall severity is YELLOW, driven by forecast rainfall.",
            joined,
        )
        self.assertNotIn("Live rainfall is", joined)

    def test_live_driven_reason(self):
        result = self.evaluate(
            live_rainfall=35.0,
            forecast_rainfall=40.0,
        )

        joined = " ".join(result.reasons)

        self.assertIn("Live rainfall is ORANGE", joined)
        self.assertIn("Forecast rainfall is YELLOW", joined)
        self.assertIn(
            "Derived rainfall severity is ORANGE, driven by live rainfall.",
            joined,
        )

    def test_exact_yellow_boundaries_for_non_rainfall_signals(self):
        cases = [
            (2.0, 0.0, 0.0),
            (0.0, 0.10, 0.0),
            (0.0, 0.0, 200.0),
        ]

        for river_level, river_change, discharge in cases:
            with self.subTest(
                river_level=river_level,
                river_change=river_change,
                discharge=discharge,
            ):
                result = self.evaluate(
                    river_level=river_level,
                    river_change=river_change,
                    discharge=discharge,
                )

                self.assertEqual(result.risk_level, RiskLevel.YELLOW)
                self.assertEqual(result.risk_score, 25)

    def test_exact_orange_boundaries_for_non_rainfall_signals(self):
        cases = [
            (3.0, 0.0, 0.0),
            (0.0, 0.30, 0.0),
            (0.0, 0.0, 400.0),
        ]

        for river_level, river_change, discharge in cases:
            with self.subTest(
                river_level=river_level,
                river_change=river_change,
                discharge=discharge,
            ):
                result = self.evaluate(
                    river_level=river_level,
                    river_change=river_change,
                    discharge=discharge,
                )

                self.assertEqual(result.risk_level, RiskLevel.ORANGE)
                self.assertEqual(result.risk_score, 50)

    def test_exact_red_boundaries_for_non_rainfall_signals(self):
        cases = [
            (4.0, 0.0, 0.0),
            (0.0, 0.60, 0.0),
            (0.0, 0.0, 800.0),
        ]

        for river_level, river_change, discharge in cases:
            with self.subTest(
                river_level=river_level,
                river_change=river_change,
                discharge=discharge,
            ):
                result = self.evaluate(
                    river_level=river_level,
                    river_change=river_change,
                    discharge=discharge,
                )

                self.assertEqual(result.risk_level, RiskLevel.RED)
                self.assertEqual(result.risk_score, 75)

    def test_values_just_below_non_rainfall_thresholds(self):
        cases = [
            ((1.99, 0.0, 0.0), RiskLevel.GREEN, 0),
            ((2.99, 0.0, 0.0), RiskLevel.YELLOW, 25),
            ((3.99, 0.0, 0.0), RiskLevel.ORANGE, 50),
            ((0.0, 0.09, 0.0), RiskLevel.GREEN, 0),
            ((0.0, 0.29, 0.0), RiskLevel.YELLOW, 25),
            ((0.0, 0.59, 0.0), RiskLevel.ORANGE, 50),
            ((0.0, 0.0, 199.99), RiskLevel.GREEN, 0),
            ((0.0, 0.0, 399.99), RiskLevel.YELLOW, 25),
            ((0.0, 0.0, 799.99), RiskLevel.ORANGE, 50),
        ]

        for values, expected_level, expected_score in cases:
            with self.subTest(values=values):
                result = self.evaluate(
                    river_level=values[0],
                    river_change=values[1],
                    discharge=values[2],
                )

                self.assertEqual(result.risk_level, expected_level)
                self.assertEqual(result.risk_score, expected_score)

    def test_values_just_above_non_rainfall_thresholds(self):
        cases = [
            ((2.01, 0.0, 0.0), RiskLevel.YELLOW, 25),
            ((3.01, 0.0, 0.0), RiskLevel.ORANGE, 50),
            ((4.01, 0.0, 0.0), RiskLevel.RED, 75),
            ((0.0, 0.11, 0.0), RiskLevel.YELLOW, 25),
            ((0.0, 0.31, 0.0), RiskLevel.ORANGE, 50),
            ((0.0, 0.61, 0.0), RiskLevel.RED, 75),
            ((0.0, 0.0, 200.01), RiskLevel.YELLOW, 25),
            ((0.0, 0.0, 400.01), RiskLevel.ORANGE, 50),
            ((0.0, 0.0, 800.01), RiskLevel.RED, 75),
        ]

        for values, expected_level, expected_score in cases:
            with self.subTest(values=values):
                result = self.evaluate(
                    river_level=values[0],
                    river_change=values[1],
                    discharge=values[2],
                )

                self.assertEqual(result.risk_level, expected_level)
                self.assertEqual(result.risk_score, expected_score)

    def test_discharge_green(self):
        result = self.evaluate(discharge=199.99)

        self.assertEqual(result.risk_level, RiskLevel.GREEN)
        self.assertEqual(result.risk_score, 0)

    def test_exact_discharge_boundaries(self):
        cases = [
            (200.0, RiskLevel.YELLOW, 25),
            (400.0, RiskLevel.ORANGE, 50),
            (800.0, RiskLevel.RED, 75),
        ]

        for discharge, level, score in cases:
            with self.subTest(discharge=discharge):
                result = self.evaluate(discharge=discharge)

                self.assertEqual(result.risk_level, level)
                self.assertEqual(result.risk_score, score)

    def test_discharge_just_below_boundaries(self):
        cases = [
            (199.99, RiskLevel.GREEN, 0),
            (399.99, RiskLevel.YELLOW, 25),
            (799.99, RiskLevel.ORANGE, 50),
        ]

        for discharge, level, score in cases:
            with self.subTest(discharge=discharge):
                result = self.evaluate(discharge=discharge)

                self.assertEqual(result.risk_level, level)
                self.assertEqual(result.risk_score, score)

    def test_discharge_just_above_boundaries(self):
        cases = [
            (200.01, RiskLevel.YELLOW, 25),
            (400.01, RiskLevel.ORANGE, 50),
            (800.01, RiskLevel.RED, 75),
        ]

        for discharge, level, score in cases:
            with self.subTest(discharge=discharge):
                result = self.evaluate(discharge=discharge)

                self.assertEqual(result.risk_level, level)
                self.assertEqual(result.risk_score, score)

    def test_discharge_only_warning_escalation(self):
        cases = [
            (250.0, RiskLevel.YELLOW, 25),
            (500.0, RiskLevel.ORANGE, 50),
            (900.0, RiskLevel.RED, 75),
        ]

        for discharge, level, score in cases:
            with self.subTest(discharge=discharge):
                result = self.evaluate(discharge=discharge)

                self.assertEqual(result.risk_level, level)
                self.assertEqual(result.risk_score, score)

    def test_existing_orange_mixed_case_remains_62(self):
        result = self.evaluate(
            live_rainfall=35.0,
            forecast_rainfall=10.0,
            river_level=3.2,
            river_change=0.20,
            discharge=100.0,
        )

        self.assertEqual(result.risk_level, RiskLevel.ORANGE)
        self.assertEqual(result.risk_score, 62)

    def test_three_yellow_signals_score_33(self):
        result = self.evaluate(
            river_level=2.2,
            river_change=0.15,
            discharge=250.0,
        )

        self.assertEqual(result.risk_level, RiskLevel.YELLOW)
        self.assertEqual(result.risk_score, 33)

    def test_three_orange_signals_score_66(self):
        result = self.evaluate(
            river_level=3.2,
            river_change=0.35,
            discharge=500.0,
        )

        self.assertEqual(result.risk_level, RiskLevel.ORANGE)
        self.assertEqual(result.risk_score, 66)

    def test_red_mixed_case_scores_87(self):
        result = self.evaluate(
            live_rainfall=55.0,
            forecast_rainfall=10.0,
            river_level=3.2,
            river_change=0.20,
            discharge=100.0,
        )

        self.assertEqual(result.risk_level, RiskLevel.RED)
        self.assertEqual(result.risk_score, 87)

    def test_all_four_scored_signals_red(self):
        result = self.evaluate(
            live_rainfall=55.0,
            forecast_rainfall=40.0,
            river_level=4.5,
            river_change=0.80,
            discharge=900.0,
        )

        self.assertEqual(result.risk_level, RiskLevel.RED)
        self.assertEqual(result.risk_score, 99)

    def test_negative_river_change_is_green_signal(self):
        result = self.evaluate(
            river_change=-0.20,
        )

        self.assertEqual(result.risk_level, RiskLevel.GREEN)
        self.assertEqual(result.risk_score, 0)
        self.assertIn("falling", result.reasons[0].lower())

    def test_repeated_calculations_are_deterministic(self):
        request = RiskAssessmentRequest(
            live_rainfall_intensity_mm_per_hour=35.0,
            forecast_rainfall_intensity_mm_per_hour=40.0,
            river_level_m=3.2,
            river_change_m_per_hour=0.20,
            upstream_discharge_m3_per_s=500.0,
        )

        first = evaluate_risk(request)

        for _ in range(10):
            self.assertEqual(evaluate_risk(request), first)

    def test_score_stays_in_range_for_four_signals(self):
        for severity_1 in SignalSeverity:
            for severity_2 in SignalSeverity:
                for severity_3 in SignalSeverity:
                    for severity_4 in SignalSeverity:
                        score = calculate_risk_score(
                            [
                                severity_1,
                                severity_2,
                                severity_3,
                                severity_4,
                            ]
                        )

                        self.assertGreaterEqual(score, 0)
                        self.assertLessEqual(score, 99)

    def test_discharge_reason_generation(self):
        result = self.evaluate(discharge=900.0)

        joined = " ".join(result.reasons)

        self.assertIn("Upstream discharge is RED", joined)
        self.assertIn("900.00 m3/s", joined)

    def test_reasons_match_actual_signals(self):
        result = self.evaluate(
            live_rainfall=35.0,
            forecast_rainfall=40.0,
            river_level=1.0,
            river_change=0.35,
            discharge=500.0,
        )

        joined = " ".join(result.reasons)

        self.assertIn("Live rainfall is ORANGE", joined)
        self.assertIn("Forecast rainfall is YELLOW", joined)
        self.assertIn("River level rise rate", joined)
        self.assertIn("Upstream discharge", joined)
        self.assertNotIn("River level is", joined)

    def test_action_matches_risk_level(self):
        cases = [
            (
                dict(
                    live_rainfall=10.0,
                    forecast_rainfall=10.0,
                    river_level=1.0,
                ),
                RiskLevel.GREEN,
            ),
            (
                dict(
                    live_rainfall=10.0,
                    forecast_rainfall=40.0,
                    river_level=1.0,
                ),
                RiskLevel.YELLOW,
            ),
            (
                dict(
                    live_rainfall=35.0,
                    forecast_rainfall=10.0,
                    river_level=1.0,
                ),
                RiskLevel.ORANGE,
            ),
            (
                dict(
                    live_rainfall=55.0,
                    forecast_rainfall=10.0,
                    river_level=1.0,
                ),
                RiskLevel.RED,
            ),
        ]

        for values, expected_level in cases:
            with self.subTest(values=values):
                result = self.evaluate(**values)

                self.assertEqual(
                    result.recommended_action,
                    RECOMMENDED_ACTIONS[expected_level],
                )


if __name__ == "__main__":
    unittest.main()
