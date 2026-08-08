from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from src.database.connection import get_engine
from src.utils.config import PROJECT_ROOT, configured_path, load_yaml_config
from src.utils.logger import get_logger


logger = get_logger(__name__)
MODELS_DIR = PROJECT_ROOT / "models"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

TARGET_COL = "target_place"
MODEL_NAMES = ("lgbm", "catboost", "xgboost")


@dataclass(frozen=True)
class DatasetSplit:
    train: pd.DataFrame
    valid: pd.DataFrame
    test: pd.DataFrame


@dataclass(frozen=True)
class FeatureSpec:
    feature_cols: list[str]
    numeric_cols: list[str]
    categorical_cols: list[str]


def place_target(finish_position: object, field_size: object) -> float:
    """Return the JRA place target, or NaN when the race is not eligible."""
    finish = pd.to_numeric(pd.Series([finish_position]), errors="coerce").iloc[0]
    field = pd.to_numeric(pd.Series([field_size]), errors="coerce").iloc[0]
    if pd.isna(finish) or pd.isna(field) or field < 5:
        return float("nan")
    slots = 3 if field >= 8 else 2
    return float(int(finish <= slots))


def load_config() -> dict[str, Any]:
    config = load_yaml_config()
    config.setdefault("paths", {})
    config["paths"].setdefault("raw_data_dir", config.get("raw_data_dir", "data/raw"))
    config["paths"].setdefault("temp_data_dir", config.get("temp_data_dir", "temp"))
    config["paths"].setdefault("processed_data_dir", "data/processed")
    config["paths"].setdefault("model_dir", "models")
    config.setdefault("modeling", {})
    config["modeling"].setdefault("random_state", 42)
    config["modeling"].setdefault("valid_size", 0.2)
    config["modeling"].setdefault("test_size", 0.2)
    config["modeling"].setdefault("min_train_rows", 50)
    config["modeling"].setdefault("accelerator", "auto")
    config["modeling"].setdefault("gpu_devices", "0")
    config.setdefault("ensemble", {})
    config["ensemble"].setdefault("method", "simple_average")
    config["ensemble"].setdefault("weights", {"lgbm": 0.34, "catboost": 0.33, "xgboost": 0.33})
    config.setdefault("safe_agent", {})
    config["safe_agent"].setdefault("max_model_uncertainty", 0.10)
    return config


def accelerator_mode(config: dict[str, Any]) -> str:
    """Return the requested learning accelerator: auto, cpu, or gpu."""
    mode = str(config["modeling"].get("accelerator", "auto")).lower()
    if mode not in {"auto", "cpu", "gpu"}:
        raise ValueError("modeling.accelerator must be one of: auto, cpu, gpu")
    return mode


def fit_with_accelerator_fallback(
    model_name: str,
    config: dict[str, Any],
    make_gpu_model: Callable[[], Any],
    make_cpu_model: Callable[[], Any],
    fit_model: Callable[[Any], None],
) -> tuple[Any, str]:
    """Fit on GPU when requested, with an automatic safe CPU fallback.

    ``accelerator: gpu`` is strict and reports a configuration error.  The
    default ``auto`` mode retries on CPU for hosts without a compatible GPU
    build, CUDA driver, or device.
    """
    mode = accelerator_mode(config)
    if mode == "cpu":
        model = make_cpu_model()
        fit_model(model)
        return model, "cpu"

    try:
        model = make_gpu_model()
        fit_model(model)
        logger.info("Trained %s on GPU.", model_name)
        return model, "gpu"
    except Exception as exc:
        if mode == "gpu":
            raise RuntimeError(f"{model_name} GPU training failed; check GPU runtime and driver settings.") from exc
        logger.warning("%s GPU training is unavailable; retrying on CPU: %s", model_name, exc)
        model = make_cpu_model()
        fit_model(model)
        return model, "cpu"


def ensure_dirs() -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def load_ai_race_entries() -> pd.DataFrame:
    try:
        engine = get_engine()
        df = pd.read_sql("SELECT * FROM ai_race_entries", engine)
        logger.info("Loaded %s rows from ai_race_entries", len(df))
        return df
    except Exception as exc:
        logger.warning("Falling back to raw CSV data because DB read failed: %s", exc)
        return _load_raw_csv_fallback()


def _load_raw_csv_fallback() -> pd.DataFrame:
    raw_dir = configured_path(load_config(), "raw_data_dir", "data/raw")
    races = pd.read_csv(raw_dir / "races.csv")
    entries = pd.read_csv(raw_dir / "entries.csv")
    results = pd.read_csv(raw_dir / "results.csv")
    payouts = pd.read_csv(raw_dir / "payouts.csv")

    df = races.merge(entries, on="race_id", how="inner", suffixes=("", "_entry"))
    df = df.merge(results, on=["race_id", "horse_id"], how="left", suffixes=("", "_result"))
    df["target_place"] = [
        place_target(finish, field_size)
        for finish, field_size in zip(df["finish_position"], df["field_size"], strict=False)
    ]
    place = payouts[payouts["ticket_type"].isin(["place", "複勝"])].copy()
    place["horse_no"] = pd.to_numeric(place["combination"], errors="coerce")
    df = df.merge(place[["race_id", "horse_no", "payout"]], on=["race_id", "horse_no"], how="left")
    df = df.rename(columns={"payout": "payout_place"})
    logger.info("Loaded %s rows from raw CSV fallback", len(df))
    return df


def prepare_model_frame(
    df: pd.DataFrame,
    excluded_feature_groups: list[str] | None = None,
    require_target: bool = True,
) -> pd.DataFrame:
    excluded = set(excluded_feature_groups or [])
    frame = df.copy()
    frame.attrs["excluded_feature_groups"] = list(excluded)
    frame["race_date"] = pd.to_datetime(frame["race_date"], errors="coerce")
    if require_target:
        frame = frame[frame[TARGET_COL].notna()].copy()
        frame[TARGET_COL] = frame[TARGET_COL].astype(int)

    for col in ["odds_win", "odds_place_min", "odds_place_max", "popularity", "field_size", "horse_no"]:
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")

    frame = _add_market_features(frame)
    if "horse_no" in frame.columns and "field_size" in frame.columns:
        frame["relative_gate_position"] = frame["horse_no"] / frame["field_size"].replace(0, np.nan)
    else:
        frame["relative_gate_position"] = np.nan

    frame = _add_shifted_history_features(frame)

    return frame.sort_values(["race_date", "race_id", "horse_no"], kind="mergesort").reset_index(drop=True)


def prepare_prediction_frame(
    prediction_rows: pd.DataFrame,
    confirmed_history: pd.DataFrame,
) -> pd.DataFrame:
    """Build prediction features without adding unconfirmed rows to the core DB."""
    if prediction_rows.empty:
        raise ValueError("prediction_rows is empty")
    if "race_id" not in prediction_rows or "horse_id" not in prediction_rows:
        raise ValueError("prediction_rows must include race_id and horse_id")

    current = prediction_rows.copy()
    if TARGET_COL not in current:
        current[TARGET_COL] = np.nan
    current["_prediction_row"] = True
    history = confirmed_history.copy()
    history["_prediction_row"] = False
    combined = pd.concat([history, current], ignore_index=True, sort=False)
    prepared = prepare_model_frame(combined, require_target=False)
    result = prepared[prepared["_prediction_row"]].copy()
    return result.drop(columns=["_prediction_row"])


def _add_shifted_history_features(frame: pd.DataFrame) -> pd.DataFrame:
    sort_cols = ["horse_id", "race_date", "race_id"]
    frame = frame.sort_values(sort_cols, kind="mergesort").copy()
    if "finish_position" in frame.columns:
        finish = pd.to_numeric(frame["finish_position"], errors="coerce")
        frame["hist_runs"] = frame.groupby("horse_id").cumcount()
        frame["hist_avg_finish"] = _prior_group_mean(finish, frame["horse_id"])
        place_hits = pd.Series(
            [
                place_target(position, field_size)
                for position, field_size in zip(finish, frame["field_size"], strict=False)
            ],
            index=frame.index,
        )
        frame["hist_place_rate"] = _prior_group_mean(place_hits, frame["horse_id"])
        frame["hist_recent3_place_rate"] = _prior_rolling_mean(place_hits, frame["horse_id"], 3)
        frame["hist_recent5_place_rate"] = _prior_rolling_mean(place_hits, frame["horse_id"], 5)
        frame["hist_recent3_avg_finish"] = _prior_rolling_mean(finish, frame["horse_id"], 3)
        _add_condition_history_features(frame, place_hits)
    if "last_3f" in frame.columns:
        last_3f = pd.to_numeric(frame["last_3f"], errors="coerce")
        frame["hist_avg_last_3f"] = _prior_group_mean(last_3f, frame["horse_id"])
        frame["hist_recent3_avg_last_3f"] = _prior_rolling_mean(last_3f, frame["horse_id"], 3)
    frame["hist_days_since_last_race"] = frame.groupby("horse_id")["race_date"].diff().dt.days
    return frame


def _add_market_features(frame: pd.DataFrame) -> pd.DataFrame:
    if "odds_place_min" not in frame.columns:
        frame["market_place_prob"] = np.nan
        frame["market_place_prob_normalized"] = np.nan
        frame["market_place_rank"] = np.nan
        frame["market_place_overround"] = np.nan
        return frame

    odds = pd.to_numeric(frame["odds_place_min"], errors="coerce")
    inverse_odds = (1.0 / odds.clip(lower=1.01)).replace([np.inf, -np.inf], np.nan)
    total = inverse_odds.groupby(frame["race_id"]).transform("sum")
    frame["market_place_prob"] = inverse_odds
    frame["market_place_prob_normalized"] = inverse_odds / total.replace(0, np.nan)
    frame["market_place_rank"] = odds.groupby(frame["race_id"]).rank(method="min", ascending=True)
    frame["market_place_overround"] = total
    return frame


def _add_condition_history_features(frame: pd.DataFrame, place_hits: pd.Series) -> None:
    distance = (
        pd.to_numeric(frame["distance"], errors="coerce")
        if "distance" in frame.columns
        else pd.Series(np.nan, index=frame.index)
    )
    frame["distance_bucket"] = pd.cut(
        distance,
        bins=[0, 1200, 1600, 2000, np.inf],
        labels=["sprint", "mile", "middle", "long"],
        include_lowest=True,
    ).astype("string")
    for column in ["surface", "course", "ground_condition", "distance_bucket"]:
        if column not in frame:
            continue
        groups = [frame["horse_id"], frame[column]]
        prefix = "hist_distance_bucket" if column == "distance_bucket" else f"hist_{column}"
        frame[f"{prefix}_runs"] = frame.groupby(["horse_id", column], dropna=False).cumcount()
        frame[f"{prefix}_place_rate"] = _prior_group_mean(place_hits, groups)


def _prior_group_mean(values: pd.Series, groups: object) -> pd.Series:
    """Mean of each group's observations strictly before the current row.

    This is equivalent to ``shift().expanding().mean()`` but uses cumulative
    aggregates, avoiding a Python callback per horse/condition group.
    """
    valid = values.notna().astype("int64")
    cumulative_sum = values.fillna(0.0).groupby(groups, dropna=False).cumsum()
    cumulative_count = valid.groupby(groups, dropna=False).cumsum()
    return (cumulative_sum - values.fillna(0.0)) / (cumulative_count - valid).replace(0, np.nan)


def _prior_rolling_mean(values: pd.Series, group: pd.Series, window: int) -> pd.Series:
    """Rolling mean over the previous ``window`` starts for each horse."""
    shifted = values.groupby(group, dropna=False).shift()
    return (
        shifted.groupby(group, dropna=False)
        .rolling(window, min_periods=1)
        .mean()
        .reset_index(level=0, drop=True)
        .reindex(values.index)
    )


def make_feature_spec(frame: pd.DataFrame, include_high_cardinality_ids: bool = False) -> FeatureSpec:
    excluded = {
        TARGET_COL,
        "finish_position",
        "finish_time",
        "margin",
        "corner_order",
        "last_3f",
        "payout_place",
        "race_date",
        "race_name",
        "start_time",
        "source",
    }
    id_cols = ["race_id", "horse_name", "jockey_name", "trainer_name"]
    if not include_high_cardinality_ids:
        # One-hot encoding every horse creates tens of thousands of columns and
        # is both memory-prohibitive and a poor generalization feature. CatBoost
        # can opt in to its native categorical treatment instead.
        id_cols.append("horse_id")
    excluded.update(id_cols)
    ablations = set(frame.attrs.get("excluded_feature_groups", []))
    if "no_odds" in ablations:
        excluded.update(["odds_win", "odds_place_min", "odds_place_max", "popularity"])
        excluded.update([c for c in frame.columns if c.startswith("market_")])
    if "no_market_features" in ablations:
        excluded.update([c for c in frame.columns if c.startswith("market_")])
    if "no_recent_form" in ablations:
        excluded.update([c for c in frame.columns if c.startswith("hist_")])
    if "no_jockey_trainer_id" in ablations:
        excluded.update(["jockey_id", "trainer_id", "jockey_name", "trainer_name"])
    if "no_suitability" in ablations:
        excluded.update(["course", "surface", "distance", "direction"])
        excluded.update(
            [
                c
                for c in frame.columns
                if c.startswith(("hist_surface_", "hist_course_", "hist_ground_condition_", "hist_distance_bucket_"))
            ]
        )
    if "no_race_grade_ground_condition" in ablations:
        excluded.update(["race_class", "race_grade", "ground_condition", "weather"])
    known_categorical = {
        "course",
        "surface",
        "direction",
        "weather",
        "ground_condition",
        "race_class",
        "race_grade",
        "age_condition",
        "sex_condition",
        "horse_id",
        "jockey_id",
        "trainer_id",
        "horse_sex",
    }
    candidate_cols = [c for c in frame.columns if c not in excluded]
    categorical_cols = [c for c in candidate_cols if c in known_categorical or not pd.api.types.is_numeric_dtype(frame[c])]
    numeric_cols = [c for c in candidate_cols if c not in categorical_cols]
    return FeatureSpec(feature_cols=numeric_cols + categorical_cols, numeric_cols=numeric_cols, categorical_cols=categorical_cols)


def split_by_time(frame: pd.DataFrame, valid_size: float = 0.2, test_size: float = 0.2) -> DatasetSplit:
    races = frame[["race_id", "race_date"]].drop_duplicates().sort_values(["race_date", "race_id"])
    if len(races) < 3:
        raise ValueError("At least three races are required for train/valid/test splitting.")
    n_races = len(races)
    test_n = max(1, int(round(n_races * test_size)))
    valid_n = max(1, int(round(n_races * valid_size)))
    if n_races - test_n - valid_n < 1:
        valid_n = 1
        test_n = 1
    train_ids = set(races.iloc[: n_races - valid_n - test_n]["race_id"])
    valid_ids = set(races.iloc[n_races - valid_n - test_n : n_races - test_n]["race_id"])
    test_ids = set(races.iloc[n_races - test_n :]["race_id"])
    train = frame[frame["race_id"].isin(train_ids)].copy()
    valid = frame[frame["race_id"].isin(valid_ids)].copy()
    test = frame[frame["race_id"].isin(test_ids)].copy()
    for part in [train, valid, test]:
        part.attrs.update(frame.attrs)
    return DatasetSplit(train=train, valid=valid, test=test)


def split_by_years(frame: pd.DataFrame, train_start: int, train_end: int, valid_start: int, valid_end: int, test_start: int, test_end: int) -> DatasetSplit:
    years = frame["race_date"].dt.year
    train = frame[(years >= train_start) & (years <= train_end)].copy()
    valid = frame[(years >= valid_start) & (years <= valid_end)].copy()
    test = frame[(years >= test_start) & (years <= test_end)].copy()
    for part in [train, valid, test]:
        part.attrs.update(frame.attrs)
    return DatasetSplit(train=train, valid=valid, test=test)


def make_preprocessor(spec: FeatureSpec) -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("num", SimpleImputer(strategy="median", keep_empty_features=True), spec.numeric_cols),
            (
                "cat",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="constant", fill_value="missing", keep_empty_features=True)),
                        ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=True, dtype=np.float32)),
                    ]
                ),
                spec.categorical_cols,
            ),
        ],
        remainder="drop",
        sparse_threshold=1.0,
        verbose_feature_names_out=False,
    )


def fit_isotonic_calibrator(valid_probs: np.ndarray, y_valid: pd.Series) -> CalibratedClassifierCV | None:
    if len(np.unique(y_valid)) < 2:
        logger.warning("Skipping isotonic calibration because validation target has one class.")
        return None
    from sklearn.isotonic import IsotonicRegression

    calibrator = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    calibrator.fit(valid_probs, y_valid.astype(int))
    return calibrator


def apply_calibrator(probs: np.ndarray, calibrator: Any | None) -> np.ndarray:
    if calibrator is None:
        return np.asarray(probs, dtype=float)
    return np.asarray(calibrator.predict(probs), dtype=float)


def binary_metrics(y_true: pd.Series, probs: np.ndarray) -> dict[str, float]:
    y = y_true.astype(int)
    clipped = np.clip(probs, 1e-6, 1 - 1e-6)
    auc = float(roc_auc_score(y, clipped)) if len(np.unique(y)) > 1 else float("nan")
    return {
        "auc": auc,
        "logloss": float(log_loss(y, clipped, labels=[0, 1])),
        "brier": float(np.mean((clipped - y.to_numpy()) ** 2)),
    }


def race_probability_correction(df: pd.DataFrame, prob_col: str = "place_prob_calibrated") -> pd.Series:
    corrected = []
    for _, group in df.groupby("race_id", sort=False):
        field_size = int(group["field_size"].iloc[0]) if "field_size" in group else len(group)
        place_slots = 3 if field_size >= 8 else 2 if field_size >= 5 else max(1, min(3, field_size))
        total = float(group[prob_col].sum())
        scale = place_slots / total if total > 0 else 1.0
        corrected.append(group[prob_col].mul(scale).clip(0.01, 0.95))
    return pd.concat(corrected).sort_index()


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")


def _json_default(value: Any) -> Any:
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def save_artifact(path: Path, artifact: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, path)
    logger.info("Saved artifact: %s", path)


def load_artifact(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Model artifact not found: {path}")
    return joblib.load(path)
