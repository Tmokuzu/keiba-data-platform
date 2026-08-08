from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import yaml
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from src.database.connection import get_engine
from src.utils.logger import get_logger


logger = get_logger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
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


def load_config() -> dict[str, Any]:
    path = PROJECT_ROOT / "config.yaml"
    config = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    config.setdefault("modeling", {})
    config["modeling"].setdefault("random_state", 42)
    config["modeling"].setdefault("valid_size", 0.2)
    config["modeling"].setdefault("test_size", 0.2)
    config["modeling"].setdefault("min_train_rows", 50)
    config.setdefault("ensemble", {})
    config["ensemble"].setdefault("method", "simple_average")
    config["ensemble"].setdefault("weights", {"lgbm": 0.34, "catboost": 0.33, "xgboost": 0.33})
    config.setdefault("safe_agent", {})
    config["safe_agent"].setdefault("max_model_uncertainty", 0.10)
    return config


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
    raw_dir = PROJECT_ROOT / "data" / "raw"
    races = pd.read_csv(raw_dir / "races.csv")
    entries = pd.read_csv(raw_dir / "entries.csv")
    results = pd.read_csv(raw_dir / "results.csv")
    payouts = pd.read_csv(raw_dir / "payouts.csv")

    df = races.merge(entries, on="race_id", how="inner", suffixes=("", "_entry"))
    df = df.merge(results, on=["race_id", "horse_id"], how="left", suffixes=("", "_result"))
    df["target_place"] = np.where(
        df["finish_position"].between(1, 3, inclusive="both"),
        1,
        np.where(df["finish_position"].notna(), 0, np.nan),
    )
    place = payouts[payouts["ticket_type"].isin(["place", "複勝"])].copy()
    place["horse_no"] = pd.to_numeric(place["combination"], errors="coerce")
    df = df.merge(place[["race_id", "horse_no", "payout"]], on=["race_id", "horse_no"], how="left")
    df = df.rename(columns={"payout": "payout_place"})
    logger.info("Loaded %s rows from raw CSV fallback", len(df))
    return df


def prepare_model_frame(df: pd.DataFrame, excluded_feature_groups: list[str] | None = None) -> pd.DataFrame:
    excluded = set(excluded_feature_groups or [])
    frame = df.copy()
    frame.attrs["excluded_feature_groups"] = list(excluded)
    frame["race_date"] = pd.to_datetime(frame["race_date"], errors="coerce")
    frame = frame[frame[TARGET_COL].notna()].copy()
    frame[TARGET_COL] = frame[TARGET_COL].astype(int)

    for col in ["odds_win", "odds_place_min", "odds_place_max", "popularity", "field_size"]:
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")

    if "odds_place_min" in frame.columns:
        frame["market_place_prob"] = (1.0 / frame["odds_place_min"].clip(lower=1.01)).replace([np.inf, -np.inf], np.nan)
    else:
        frame["market_place_prob"] = np.nan

    frame = _add_shifted_history_features(frame)

    return frame.sort_values(["race_date", "race_id", "horse_no"], kind="mergesort").reset_index(drop=True)


def _add_shifted_history_features(frame: pd.DataFrame) -> pd.DataFrame:
    sort_cols = ["horse_id", "race_date", "race_id"]
    frame = frame.sort_values(sort_cols, kind="mergesort").copy()
    if "finish_position" in frame.columns:
        finish = pd.to_numeric(frame["finish_position"], errors="coerce")
        frame["hist_runs"] = frame.groupby("horse_id").cumcount()
        frame["hist_avg_finish"] = finish.groupby(frame["horse_id"]).transform(lambda s: s.shift().expanding().mean())
        frame["hist_place_rate"] = (finish <= 3).astype(float).groupby(frame["horse_id"]).transform(lambda s: s.shift().expanding().mean())
    if "last_3f" in frame.columns:
        last_3f = pd.to_numeric(frame["last_3f"], errors="coerce")
        frame["hist_avg_last_3f"] = last_3f.groupby(frame["horse_id"]).transform(lambda s: s.shift().expanding().mean())
    return frame


def make_feature_spec(frame: pd.DataFrame) -> FeatureSpec:
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
    excluded.update(id_cols)
    ablations = set(frame.attrs.get("excluded_feature_groups", []))
    if "no_odds" in ablations:
        excluded.update(["odds_win", "odds_place_min", "odds_place_max", "popularity"])
    if "no_market_features" in ablations:
        excluded.add("market_place_prob")
    if "no_recent_form" in ablations:
        excluded.update([c for c in frame.columns if c.startswith("hist_")])
    if "no_jockey_trainer_id" in ablations:
        excluded.update(["jockey_id", "trainer_id", "jockey_name", "trainer_name"])
    if "no_suitability" in ablations:
        excluded.update(["course", "surface", "distance", "direction"])
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
                        ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
                    ]
                ),
                spec.categorical_cols,
            ),
        ],
        remainder="drop",
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
