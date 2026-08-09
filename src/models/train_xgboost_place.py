from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from src.models.common import (
    DatasetSplit,
    MODELS_DIR,
    TARGET_COL,
    binary_metrics,
    ensure_dirs,
    fit_isotonic_calibrator,
    fit_with_accelerator_fallback,
    load_ai_race_entries,
    load_config,
    make_feature_spec,
    make_preprocessor,
    prepare_model_frame_if_needed,
    save_artifact,
    save_json,
    split_by_time,
)
from src.utils.logger import get_logger


logger = get_logger(__name__)


def train_xgboost_place(
    frame: Any | None = None,
    output_model_path: Path | None = None,
    output_metrics_path: Path | None = None,
    excluded_feature_groups: list[str] | None = None,
    split_override: DatasetSplit | None = None,
) -> dict[str, Any]:
    try:
        from xgboost import XGBClassifier
    except ImportError as exc:
        raise RuntimeError("xgboost is required. Run `uv sync` after updating requirements.") from exc

    ensure_dirs()
    config = load_config()
    raw = load_ai_race_entries() if frame is None else frame
    data = prepare_model_frame_if_needed(raw, excluded_feature_groups)
    split = split_override or split_by_time(data, config["modeling"]["valid_size"], config["modeling"]["test_size"])
    spec = make_feature_spec(split.train)
    preprocessor = make_preprocessor(spec)

    x_train = preprocessor.fit_transform(split.train[spec.feature_cols])
    x_valid = preprocessor.transform(split.valid[spec.feature_cols])
    x_test = preprocessor.transform(split.test[spec.feature_cols])
    y_train = split.train[TARGET_COL].astype(int)

    common_params = {
        "n_estimators": 300,
        "learning_rate": 0.04,
        "max_depth": 4,
        "subsample": 0.9,
        "colsample_bytree": 0.9,
        "objective": "binary:logistic",
        "eval_metric": "logloss",
        "random_state": int(config["modeling"]["random_state"]),
        "n_jobs": 1,
    }
    model, training_device = fit_with_accelerator_fallback(
        "XGBoost",
        config,
        lambda: XGBClassifier(**common_params, tree_method="hist", device=f"cuda:{config['modeling'].get('gpu_devices', '0').split(',')[0]}"),
        lambda: XGBClassifier(**common_params, tree_method="hist", device="cpu"),
        lambda candidate: candidate.fit(x_train, y_train),
    )
    valid_probs = model.predict_proba(x_valid)[:, 1]
    calibrator = fit_isotonic_calibrator(valid_probs, split.valid[TARGET_COL].astype(int))
    test_raw = model.predict_proba(x_test)[:, 1]
    test_probs = np.clip(test_raw if calibrator is None else calibrator.predict(test_raw), 0.0, 1.0)
    metrics = binary_metrics(split.test[TARGET_COL], test_probs)
    metrics.update({"model_type": "xgboost", "training_device": training_device, "train_rows": len(split.train), "valid_rows": len(split.valid), "test_rows": len(split.test)})

    artifact = {
        "model_type": "xgboost",
        "model": model,
        "preprocessor": preprocessor,
        "feature_cols": spec.feature_cols,
        "numeric_cols": spec.numeric_cols,
        "categorical_cols": spec.categorical_cols,
        "calibrator": calibrator,
        "metrics": metrics,
    }
    save_artifact(output_model_path or MODELS_DIR / "xgboost_place_model.pkl", artifact)
    save_json(output_metrics_path or MODELS_DIR / "xgboost_place_metrics.json", metrics)
    logger.info("XGBoost place model metrics: %s", metrics)
    return artifact


def main() -> None:
    train_xgboost_place()


if __name__ == "__main__":
    main()
