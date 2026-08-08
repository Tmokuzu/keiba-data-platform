from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.models.common import MODEL_NAMES, TARGET_COL, apply_calibrator, fit_isotonic_calibrator, load_config


def ensemble_probabilities(predictions: pd.DataFrame, method: str | None = None, weights: dict[str, float] | None = None) -> pd.Series:
    config = load_config()
    method = method or config["ensemble"]["method"]
    weights = weights or config["ensemble"]["weights"]
    cols = [f"place_prob_{name}" for name in MODEL_NAMES]
    missing = [col for col in cols if col not in predictions.columns]
    if missing:
        raise ValueError(f"Missing model probability columns for ensemble: {missing}")

    if method == "simple_average":
        return predictions[cols].mean(axis=1)
    if method == "weighted_average":
        raw_weights = np.array([float(weights.get(name, 0.0)) for name in MODEL_NAMES], dtype=float)
        if raw_weights.sum() <= 0:
            raise ValueError("Ensemble weights must sum to a positive value.")
        normalized = raw_weights / raw_weights.sum()
        return pd.Series(predictions[cols].to_numpy().dot(normalized), index=predictions.index)
    raise ValueError(f"Unsupported ensemble method: {method}")


def model_uncertainty(predictions: pd.DataFrame) -> pd.Series:
    cols = [f"place_prob_{name}" for name in MODEL_NAMES]
    return predictions[cols].std(axis=1, ddof=0)


def fit_ensemble_calibrator(valid_frame: pd.DataFrame, raw_prob_col: str = "place_prob_ensemble_raw") -> Any | None:
    if TARGET_COL not in valid_frame:
        return None
    return fit_isotonic_calibrator(valid_frame[raw_prob_col].to_numpy(), valid_frame[TARGET_COL].astype(int))


def apply_ensemble_calibration(frame: pd.DataFrame, calibrator: Any | None, raw_prob_col: str = "place_prob_ensemble_raw") -> pd.Series:
    return pd.Series(apply_calibrator(frame[raw_prob_col].to_numpy(), calibrator), index=frame.index).clip(0.0, 1.0)
