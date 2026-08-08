from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.models.common import (
    MODELS_DIR,
    PROCESSED_DIR,
    MODEL_NAMES,
    load_ai_race_entries,
    load_artifact,
    load_config,
    prepare_model_frame,
    race_probability_correction,
)
from src.models.ensemble import apply_ensemble_calibration, ensemble_probabilities, fit_ensemble_calibrator, model_uncertainty
from src.utils.logger import get_logger


logger = get_logger(__name__)


def predict_ensemble(
    frame: pd.DataFrame | None = None,
    output_path: Path | None = None,
    calibrator_frame: pd.DataFrame | None = None,
    frame_is_prepared: bool = False,
) -> pd.DataFrame:
    raw = load_ai_race_entries() if frame is None else frame
    data = raw.copy() if frame_is_prepared else prepare_model_frame(raw)
    predictions = data.copy()
    artifacts = {name: load_artifact(MODELS_DIR / f"{name}_place_model.pkl") for name in MODEL_NAMES}

    for name, artifact in artifacts.items():
        predictions[f"place_prob_{name}"] = _predict_with_artifact(artifact, data)

    config = load_config()
    predictions["place_prob_ensemble_raw"] = ensemble_probabilities(predictions, config["ensemble"]["method"], config["ensemble"]["weights"])
    predictions["model_uncertainty"] = model_uncertainty(predictions)

    calibrator = _load_or_fit_ensemble_calibrator(predictions, calibrator_frame)
    predictions["place_prob_calibrated"] = apply_ensemble_calibration(predictions, calibrator)
    predictions["place_prob_final"] = race_probability_correction(predictions, "place_prob_calibrated")
    predictions = _add_value_columns(predictions)

    columns = _prediction_columns(predictions)
    result = predictions[columns].copy()
    out = output_path or PROCESSED_DIR / "predictions_place.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(out, index=False)
    logger.info("Saved ensemble predictions: %s rows -> %s", len(result), out)
    return result


def predict_lgbm(
    frame: pd.DataFrame | None = None,
    output_path: Path | None = None,
    frame_is_prepared: bool = False,
) -> pd.DataFrame:
    raw = load_ai_race_entries() if frame is None else frame
    data = raw.copy() if frame_is_prepared else prepare_model_frame(raw)
    artifact = load_artifact(MODELS_DIR / "lgbm_place_model.pkl")
    predictions = data.copy()
    predictions["place_prob_lgbm"] = _predict_with_artifact(artifact, data, calibrated=True)
    predictions["place_prob_catboost"] = predictions["place_prob_lgbm"]
    predictions["place_prob_xgboost"] = predictions["place_prob_lgbm"]
    predictions["place_prob_ensemble_raw"] = predictions["place_prob_lgbm"]
    predictions["model_uncertainty"] = 0.0
    predictions["place_prob_calibrated"] = predictions["place_prob_lgbm"]
    predictions["place_prob_final"] = race_probability_correction(predictions, "place_prob_calibrated")
    predictions = _add_value_columns(predictions)
    result = predictions[_prediction_columns(predictions)].copy()
    out = output_path or PROCESSED_DIR / "predictions_place_lgbm.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(out, index=False)
    logger.info("Saved LightGBM predictions: %s rows -> %s", len(result), out)
    return result


def _predict_with_artifact(artifact: dict[str, Any], frame: pd.DataFrame, calibrated: bool = False) -> np.ndarray:
    features = frame.reindex(columns=artifact["feature_cols"]).copy()
    if artifact["model_type"] == "catboost":
        for col in artifact.get("categorical_cols", []):
            features[col] = features[col].fillna("missing").astype(str)
        probs = artifact["model"].predict_proba(features)[:, 1]
    else:
        transformed = artifact["preprocessor"].transform(features)
        probs = artifact["model"].predict_proba(transformed)[:, 1]
    if calibrated and artifact.get("calibrator") is not None:
        probs = artifact["calibrator"].predict(probs)
    return np.clip(np.asarray(probs, dtype=float), 0.0, 1.0)


def _load_or_fit_ensemble_calibrator(predictions: pd.DataFrame, calibrator_frame: pd.DataFrame | None) -> Any | None:
    path = MODELS_DIR / "ensemble_place_calibrator.pkl"
    if path.exists() and calibrator_frame is None:
        import joblib

        return joblib.load(path)
    if calibrator_frame is None:
        logger.warning("Ensemble calibrator is not available; using raw ensemble probabilities.")
        return None
    calibrator = fit_ensemble_calibrator(calibrator_frame)
    if calibrator is not None:
        import joblib

        joblib.dump(calibrator, path)
    return calibrator


def _add_value_columns(predictions: pd.DataFrame) -> pd.DataFrame:
    df = predictions.copy()
    df["market_place_prob"] = (1.0 / pd.to_numeric(df["odds_place_min"], errors="coerce").clip(lower=1.01)).clip(0, 1)
    df["expected_value_place"] = df["place_prob_final"] * pd.to_numeric(df["odds_place_min"], errors="coerce")
    df["value_gap"] = df["place_prob_final"] - df["market_place_prob"]
    df["bet_score"] = df["value_gap"] * df["expected_value_place"] * (1.0 - df["model_uncertainty"].clip(0, 1))
    return df


def _prediction_columns(df: pd.DataFrame) -> list[str]:
    base = [
        "race_id",
        "race_date",
        "course",
        "race_no",
        "horse_id",
        "horse_name",
        "horse_no",
        "field_size",
        "target_place",
        "payout_place",
        "odds_place_min",
        "place_prob_lgbm",
        "place_prob_catboost",
        "place_prob_xgboost",
        "place_prob_ensemble_raw",
        "place_prob_calibrated",
        "place_prob_final",
        "model_uncertainty",
        "expected_value_place",
        "market_place_prob",
        "value_gap",
        "bet_score",
    ]
    return [col for col in base if col in df.columns]


def main() -> None:
    predict_ensemble()


if __name__ == "__main__":
    main()
