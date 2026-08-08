from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd

from src.agents.safe_agent import apply_safe_agent
from src.backtesting.metrics import evaluate_predictions, settle_bets
from src.models.common import MODELS_DIR, MODEL_NAMES, PROCESSED_DIR, load_ai_race_entries, load_config, prepare_model_frame, race_probability_correction, split_by_years
from src.models.ensemble import apply_ensemble_calibration, ensemble_probabilities, fit_ensemble_calibrator, model_uncertainty
from src.models.predict import _add_value_columns, _predict_with_artifact
from src.models.train_catboost_place import train_catboost_place
from src.models.train_place_model import train_lightgbm_place
from src.models.train_xgboost_place import train_xgboost_place
from src.utils.logger import get_logger


logger = get_logger(__name__)


DEFAULT_FOLDS = [
    {"train_start": 2016, "train_end": 2019, "valid_start": 2020, "valid_end": 2020, "test_start": 2021, "test_end": 2021},
    {"train_start": 2016, "train_end": 2020, "valid_start": 2021, "valid_end": 2021, "test_start": 2022, "test_end": 2022},
    {"train_start": 2016, "train_end": 2021, "valid_start": 2022, "valid_end": 2022, "test_start": 2023, "test_end": 2023},
    {"train_start": 2016, "train_end": 2022, "valid_start": 2023, "valid_end": 2023, "test_start": 2024, "test_end": 2024},
    {"train_start": 2016, "train_end": 2023, "valid_start": 2024, "valid_end": 2024, "test_start": 2025, "test_end": 2025},
]


def run_walk_forward(output_summary_path: Path | None = None, output_detail_path: Path | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = prepare_model_frame(load_ai_race_entries())
    summary_rows: list[dict] = []
    details: list[pd.DataFrame] = []

    for fold_config in _configured_folds():
        train_start = int(fold_config["train_start"])
        train_end = int(fold_config["train_end"])
        valid_start = int(fold_config["valid_start"])
        valid_end = int(fold_config["valid_end"])
        test_start = int(fold_config["test_start"])
        test_end = int(fold_config["test_end"])
        fold = (train_start, train_end, valid_start, valid_end, test_start, test_end)
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
        test["place_prob_final"] = race_probability_correction(test, "place_prob_calibrated")
        test = _add_value_columns(test)
        safe_agent_output = apply_safe_agent(test)
        metrics = evaluate_predictions(safe_agent_output)
        bets = settle_bets(safe_agent_output)
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
        bets = bets.assign(**{k: v for k, v in row.items() if k != "profit"})
        details.append(bets)

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


def _configured_folds() -> list[dict[str, int]]:
    config = load_config()
    return config.get("validation", {}).get("walk_forward", {}).get("folds", DEFAULT_FOLDS)


if __name__ == "__main__":
    main()
