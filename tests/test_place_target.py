import math
import unittest

import pandas as pd

from src.models.common import place_target, prepare_prediction_frame


class PlaceTargetTests(unittest.TestCase):
    def test_place_target_uses_jra_field_size_rules(self) -> None:
        cases = [
            (3, 8, 1.0),
            (4, 8, 0.0),
            (2, 7, 1.0),
            (3, 7, 0.0),
            (1, 4, float("nan")),
            (None, 8, float("nan")),
        ]
        for finish_position, field_size, expected in cases:
            with self.subTest(finish_position=finish_position, field_size=field_size):
                actual = place_target(finish_position, field_size)
                if math.isnan(expected):
                    self.assertTrue(math.isnan(actual))
                else:
                    self.assertEqual(actual, expected)

    def test_prediction_rows_use_confirmed_history_without_becoming_training_rows(self) -> None:
        history = pd.DataFrame(
            [
                {
                    "race_id": "past-1",
                    "race_date": "2026-01-01",
                    "horse_id": "horse-a",
                    "horse_no": 1,
                    "field_size": 8,
                    "finish_position": 2,
                    "target_place": 1,
                },
                {
                    "race_id": "past-2",
                    "race_date": "2026-02-01",
                    "horse_id": "horse-a",
                    "horse_no": 1,
                    "field_size": 8,
                    "finish_position": 4,
                    "target_place": 0,
                },
            ]
        )
        today = pd.DataFrame(
            [
                {
                    "race_id": "today-1",
                    "race_date": "2026-03-01",
                    "horse_id": "horse-a",
                    "horse_no": 3,
                    "field_size": 8,
                }
            ]
        )

        result = prepare_prediction_frame(today, history)

        self.assertEqual(result["race_id"].tolist(), ["today-1"])
        self.assertTrue(pd.isna(result["target_place"].iloc[0]))
        self.assertEqual(result["hist_runs"].iloc[0], 2)
        self.assertEqual(result["hist_place_rate"].iloc[0], 0.5)
