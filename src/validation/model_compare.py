from __future__ import annotations

import math
from pathlib import Path

import joblib
import pandas as pd

from src.agents.safe_agent import apply_safe_agent
from src.backtesting.metrics import evaluate_predictions
from src.models.common import MODELS_DIR, MODEL_NAMES, PROCESSED_DIR, TARGET_COL, binary_metrics, load_ai_race_entries, load_config, prepare_model_frame, race_probability_correction, split_by_time
from src.models.ensemble import apply_ensemble_calibration, ensemble_probabilities, model_uncertainty
from src.models.predict import _add_value_columns, _predict_with_artifact
from src.models.train_all import train_all_models
from src.utils.logger import get_logger


logger = get_logger(__name__)


def run_model_compare(output_path: Path | None = None, train_if_missing: bool = True) -> pd.DataFrame:
    if train_if_missing and not all((MODELS_DIR / f"{name}_place_model.pkl").exists() for name in MODEL_NAMES):
        train_all_models()

    config = load_config()
    data = prepare_model_frame(load_ai_race_entries())
    split = split_by_time(data, config["modeling"]["valid_size"], config["modeling"]["test_size"])
    test = split.test.copy()
    artifacts = {name: joblib.load(MODELS_DIR / f"{name}_place_model.pkl") for name in MODEL_NAMES}
    rows: list[dict] = []

    for name, artifact in artifacts.items():
        preds = test.copy()
        preds["place_prob_final"] = _predict_with_artifact(artifact, test, calibrated=True)
        preds = _add_value_columns_for_compare(preds)
        rows.append(_summary_row(name, preds))

    base = test.copy()
    for name, artifact in artifacts.items():
        base[f"place_prob_{name}"] = _predict_with_artifact(artifact, test)
    base["model_uncertainty"] = model_uncertainty(base)
    calibrator = joblib.load(MODELS_DIR / "ensemble_place_calibrator.pkl") if (MODELS_DIR / "ensemble_place_calibrator.pkl").exists() else None
    for method in ["simple_average", "weighted_average"]:
        preds = base.copy()
        preds["place_prob_ensemble_raw"] = ensemble_probabilities(preds, method, config["ensemble"]["weights"])
        preds["place_prob_calibrated"] = apply_ensemble_calibration(preds, calibrator)
        preds["place_prob_final"] = race_probability_correction(preds, "place_prob_calibrated")
        preds = _add_value_columns_for_compare(preds)
        rows.append(_summary_row(f"ensemble_{method}", preds))

    summary = pd.DataFrame(rows)
    out = output_path or PROCESSED_DIR / "model_compare_summary.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(out, index=False)
    logger.info("Saved model comparison: %s", out)
    return summary


def _summary_row(model_type: str, predictions: pd.DataFrame) -> dict:
    metrics = binary_metrics(predictions[TARGET_COL], predictions["place_prob_final"].to_numpy())
    bets = apply_safe_agent(predictions)
    metrics.update(evaluate_predictions(bets))
    return {
        "model_type": model_type,
        "AUC": metrics.get("auc", math.nan),
        "LogLoss": metrics.get("logloss", math.nan),
        "Brier Score": metrics.get("brier", math.nan),
        "ROI": metrics.get("roi", 0.0),
        "Hit Rate": metrics.get("hit_rate", 0.0),
        "Bet Count": metrics.get("bet_count", 0),
        "Max Drawdown": metrics.get("max_drawdown", 0.0),
    }


def _add_value_columns_for_compare(df: pd.DataFrame) -> pd.DataFrame:
    if "place_prob_lgbm" not in df:
        df["place_prob_lgbm"] = df["place_prob_final"]
    if "place_prob_catboost" not in df:
        df["place_prob_catboost"] = df["place_prob_final"]
    if "place_prob_xgboost" not in df:
        df["place_prob_xgboost"] = df["place_prob_final"]
    if "model_uncertainty" not in df:
        df["model_uncertainty"] = 0.0
    return _add_value_columns(df)


def main() -> None:
    run_model_compare()


if __name__ == "__main__":
    main()
