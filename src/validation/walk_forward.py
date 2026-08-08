from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd

from src.agents.safe_agent import apply_safe_agent
from src.backtesting.metrics import evaluate_predictions
from src.models.common import MODELS_DIR, MODEL_NAMES, PROCESSED_DIR, load_ai_race_entries, prepare_model_frame, split_by_years
from src.models.ensemble import apply_ensemble_calibration, ensemble_probabilities, fit_ensemble_calibrator, model_uncertainty
from src.models.predict import _add_value_columns, _predict_with_artifact
from src.models.train_catboost_place import train_catboost_place
from src.models.train_place_model import train_lightgbm_place
from src.models.train_xgboost_place import train_xgboost_place
from src.utils.logger import get_logger


logger = get_logger(__name__)


FOLDS = [
    (2016, 2019, 2020, 2020, 2021, 2021),
    (2016, 2020, 2021, 2021, 2022, 2022),
    (2016, 2021, 2022, 2022, 2023, 2023),
    (2016, 2022, 2023, 2023, 2024, 2024),
    (2016, 2023, 2024, 2024, 2025, 2025),
]


def run_walk_forward(output_summary_path: Path | None = None, output_detail_path: Path | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = prepare_model_frame(load_ai_race_entries())
    summary_rows: list[dict] = []
    details: list[pd.DataFrame] = []

    for fold in FOLDS:
        train_start, train_end, valid_start, valid_end, test_start, test_end = fold
        split = split_by_years(data, train_start, train_end, valid_start, valid_end, test_start, test_end)
        if split.train.empty or split.valid.empty or split.test.empty:
            logger.warning("Skipping empty walk-forward fold: %s", fold)
            continue

        fold_frame = pd.concat([split.train, split.valid, split.test], ignore_index=True)
        artifacts = {
            "lgbm": train_lightgbm_place(fold_frame, MODELS_DIR / "wf_lgbm_place_model.pkl", MODELS_DIR / "wf_lgbm_place_metrics.json", split_override=split),
            "catboost": train_catboost_place(fold_frame, MODELS_DIR / "wf_catboost_place_model.pkl", MODELS_DIR / "wf_catboost_place_metrics.json", split_override=split),
            "xgboost": train_xgboost_place(fold_frame, MODELS_DIR / "wf_xgboost_place_model.pkl", MODELS_DIR / "wf_xgboost_place_metrics.json", split_override=split),
        }
        valid = split.valid.copy()
        test = split.test.copy()
        for name, artifact in artifacts.items():
            valid[f"place_prob_{name}"] = _predict_with_artifact(artifact, valid)
            test[f"place_prob_{name}"] = _predict_with_artifact(artifact, test)
        valid["place_prob_ensemble_raw"] = ensemble_probabilities(valid)
        calibrator = fit_ensemble_calibrator(valid)
        test["model_uncertainty"] = model_uncertainty(test)
        test["place_prob_ensemble_raw"] = ensemble_probabilities(test)
        test["place_prob_calibrated"] = apply_ensemble_calibration(test, calibrator)
        test["place_prob_final"] = test["place_prob_calibrated"]
        test = _add_value_columns(test)
        bets = apply_safe_agent(test)
        metrics = evaluate_predictions(bets)
        row = {
            "train_start": train_start,
            "train_end": train_end,
            "valid_start": valid_start,
            "valid_end": valid_end,
            "test_start": test_start,
            "test_end": test_end,
            "model_type": "ensemble_simple_average",
            "bet_count": metrics["bet_count"],
            "hit_rate": metrics["hit_rate"],
            "roi": metrics["roi"],
            "profit": metrics["profit"],
            "max_drawdown": metrics["max_drawdown"],
            "auc": metrics.get("auc"),
            "logloss": metrics.get("logloss"),
            "brier": metrics.get("brier"),
        }
        summary_rows.append(row)
        test = test.assign(**{k: v for k, v in row.items() if k != "profit"})
        details.append(test)

    summary = pd.DataFrame(summary_rows)
    detail = pd.concat(details, ignore_index=True) if details else pd.DataFrame()
    summary_path = output_summary_path or PROCESSED_DIR / "walk_forward_summary.csv"
    detail_path = output_detail_path or PROCESSED_DIR / "walk_forward_detail.csv"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(summary_path, index=False)
    detail.to_csv(detail_path, index=False)
    logger.info("Saved walk-forward outputs: %s, %s", summary_path, detail_path)
    return summary, detail


def main() -> None:
    run_walk_forward()


if __name__ == "__main__":
    main()
