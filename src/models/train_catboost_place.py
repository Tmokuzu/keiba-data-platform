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
    prepare_model_frame_if_needed,
    save_artifact,
    save_json,
    split_by_time,
)
from src.utils.logger import get_logger


logger = get_logger(__name__)


def train_catboost_place(
    frame: Any | None = None,
    output_model_path: Path | None = None,
    output_metrics_path: Path | None = None,
    excluded_feature_groups: list[str] | None = None,
    split_override: DatasetSplit | None = None,
) -> dict[str, Any]:
    try:
        from catboost import CatBoostClassifier
    except ImportError as exc:
        raise RuntimeError("catboost is required. Run `uv sync` after updating requirements.") from exc

    ensure_dirs()
    config = load_config()
    raw = load_ai_race_entries() if frame is None else frame
    data = prepare_model_frame_if_needed(raw, excluded_feature_groups)
    split = split_override or split_by_time(data, config["modeling"]["valid_size"], config["modeling"]["test_size"])
    # CatBoost handles horse IDs natively as categorical values; do not turn
    # them into the very large one-hot representation used by other models.
    spec = make_feature_spec(split.train, include_high_cardinality_ids=True)

    train_x = _catboost_frame(split.train, spec.feature_cols, spec.categorical_cols)
    valid_x = _catboost_frame(split.valid, spec.feature_cols, spec.categorical_cols)
    test_x = _catboost_frame(split.test, spec.feature_cols, spec.categorical_cols)
    cat_indices = [spec.feature_cols.index(col) for col in spec.categorical_cols]

    common_params = {
        "iterations": 300,
        "learning_rate": 0.04,
        "depth": 6,
        "loss_function": "Logloss",
        "eval_metric": "AUC",
        "random_seed": int(config["modeling"]["random_state"]),
        "verbose": False,
        "allow_writing_files": False,
    }
    fit = lambda candidate: candidate.fit(
        train_x,
        split.train[TARGET_COL].astype(int),
        cat_features=cat_indices,
        eval_set=(valid_x, split.valid[TARGET_COL].astype(int)),
    )
    model, training_device = fit_with_accelerator_fallback(
        "CatBoost",
        config,
        lambda: CatBoostClassifier(**common_params, task_type="GPU", devices=str(config["modeling"].get("gpu_devices", "0"))),
        lambda: CatBoostClassifier(**common_params, task_type="CPU"),
        fit,
    )
    valid_probs = model.predict_proba(valid_x)[:, 1]
    calibrator = fit_isotonic_calibrator(valid_probs, split.valid[TARGET_COL].astype(int))
    test_raw = model.predict_proba(test_x)[:, 1]
    test_probs = np.clip(test_raw if calibrator is None else calibrator.predict(test_raw), 0.0, 1.0)
    metrics = binary_metrics(split.test[TARGET_COL], test_probs)
    metrics.update({"model_type": "catboost", "training_device": training_device, "train_rows": len(split.train), "valid_rows": len(split.valid), "test_rows": len(split.test)})

    artifact = {
        "model_type": "catboost",
        "model": model,
        "feature_cols": spec.feature_cols,
        "numeric_cols": spec.numeric_cols,
        "categorical_cols": spec.categorical_cols,
        "cat_feature_indices": cat_indices,
        "calibrator": calibrator,
        "metrics": metrics,
    }
    save_artifact(output_model_path or MODELS_DIR / "catboost_place_model.pkl", artifact)
    save_json(output_metrics_path or MODELS_DIR / "catboost_place_metrics.json", metrics)
    logger.info("CatBoost place model metrics: %s", metrics)
    return artifact


def _catboost_frame(frame: Any, feature_cols: list[str], categorical_cols: list[str]) -> Any:
    x = frame.reindex(columns=feature_cols).copy()
    for col in categorical_cols:
        x[col] = x[col].fillna("missing").astype(str)
    return x


def main() -> None:
    train_catboost_place()


if __name__ == "__main__":
    main()
