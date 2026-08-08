import math
import unittest

import pandas as pd

from src.models.common import make_feature_spec, place_target, prepare_model_frame, prepare_prediction_frame


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

    def test_recent_and_condition_features_use_only_prior_races(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "race_id": "race-1", "race_date": "2026-01-01", "horse_id": "horse-a",
                    "horse_no": 1, "field_size": 8, "finish_position": 2, "target_place": 1,
                    "course": "東京", "surface": "芝", "ground_condition": "良", "distance": 1600,
                    "odds_place_min": 2.0,
                },
                {
                    "race_id": "race-2", "race_date": "2026-02-01", "horse_id": "horse-a",
                    "horse_no": 1, "field_size": 8, "finish_position": 4, "target_place": 0,
                    "course": "東京", "surface": "芝", "ground_condition": "良", "distance": 1600,
                    "odds_place_min": 3.0,
                },
                {
                    "race_id": "race-3", "race_date": "2026-03-01", "horse_id": "horse-a",
                    "horse_no": 1, "field_size": 8, "finish_position": 1, "target_place": 1,
                    "course": "東京", "surface": "芝", "ground_condition": "良", "distance": 1600,
                    "odds_place_min": 2.5,
                },
            ]
        )

        result = prepare_model_frame(frame)
        third = result[result["race_id"] == "race-3"].iloc[0]

        self.assertEqual(third["hist_recent3_place_rate"], 0.5)
        self.assertEqual(third["hist_course_place_rate"], 0.5)
        self.assertEqual(third["hist_distance_bucket_place_rate"], 0.5)
        self.assertEqual(third["hist_days_since_last_race"], 28)

    def test_market_features_are_normalized_within_each_race(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "race_id": "race-1", "race_date": "2026-01-01", "horse_id": "horse-a",
                    "horse_no": 1, "field_size": 8, "finish_position": 1, "target_place": 1,
                    "odds_place_min": 2.0,
                },
                {
                    "race_id": "race-1", "race_date": "2026-01-01", "horse_id": "horse-b",
                    "horse_no": 2, "field_size": 8, "finish_position": 4, "target_place": 0,
                    "odds_place_min": 4.0,
                },
            ]
        )

        result = prepare_model_frame(frame)
        favorite = result[result["horse_id"] == "horse-a"].iloc[0]
        outsider = result[result["horse_id"] == "horse-b"].iloc[0]

        self.assertAlmostEqual(favorite["market_place_prob_normalized"], 2 / 3)
        self.assertAlmostEqual(outsider["market_place_prob_normalized"], 1 / 3)
        self.assertEqual(favorite["market_place_rank"], 1.0)
        self.assertEqual(outsider["market_place_rank"], 2.0)

    def test_horse_id_is_not_one_hot_encoded_for_tree_preprocessors(self) -> None:
        frame = pd.DataFrame(
            [{"horse_id": "horse-a", "jockey_id": "jockey-a", "target_place": 1, "feature": 1.0}]
        )

        standard = make_feature_spec(frame)
        catboost = make_feature_spec(frame, include_high_cardinality_ids=True)

        self.assertNotIn("horse_id", standard.feature_cols)
        self.assertIn("horse_id", catboost.feature_cols)
