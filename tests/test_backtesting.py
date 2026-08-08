import unittest

import pandas as pd

from src.backtesting.metrics import evaluate_bets, settle_bets
from src.validation.segmented_report import build_segmented_rows
from src.validation.threshold_optimization import evaluate_thresholds


class BacktestingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.predictions = pd.DataFrame(
            [
                {
                    "action": "BUY",
                    "stake": 100,
                    "target_place": 1,
                    "payout_place": 200,
                    "race_date": "2026-01-01",
                    "course": "東京",
                    "distance": 1600,
                    "ground_condition": "良",
                    "popularity": 2,
                    "odds_place_min": 2.0,
                    "expected_value_place": 1.2,
                },
                {
                    "action": "BUY",
                    "stake": 100,
                    "target_place": 0,
                    "payout_place": 0,
                    "race_date": "2026-01-02",
                    "course": "中山",
                    "distance": 1200,
                    "ground_condition": "稍重",
                    "popularity": 8,
                    "odds_place_min": 3.2,
                    "expected_value_place": 1.3,
                },
            ]
        )

    def test_roi_is_gross_return_over_stake(self) -> None:
        metrics = evaluate_bets(self.predictions)

        self.assertEqual(metrics["roi"], 1.0)
        self.assertEqual(metrics["profit"], 0.0)
        self.assertEqual(metrics["bet_count"], 2)

    def test_segmented_rows_use_settled_bet_outcomes(self) -> None:
        rows = build_segmented_rows(settle_bets(self.predictions))
        tokyo = rows[(rows["segment"] == "course") & (rows["value"] == "東京")].iloc[0]

        self.assertEqual(tokyo["roi"], 2.0)
        self.assertEqual(tokyo["profit"], 100.0)

    def test_threshold_evaluation_only_settles_rows_matching_fixed_rules(self) -> None:
        predictions = self.predictions.assign(
            expected_value_place=[1.20, 1.01],
            value_gap=[0.04, 0.01],
            bet_score=[0.03, 0.01],
            model_uncertainty=[0.05, 0.05],
        )
        metrics, bets = evaluate_thresholds(
            predictions,
            {
                "min_expected_value_place": 1.05,
                "min_value_gap": 0.03,
                "min_bet_score": 0.02,
                "max_model_uncertainty": 0.10,
            },
        )

        self.assertEqual(metrics["bet_count"], 1)
        self.assertEqual(metrics["roi"], 2.0)
        self.assertEqual(bets["return_amount"].tolist(), [200.0])
