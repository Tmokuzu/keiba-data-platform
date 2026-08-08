from __future__ import annotations

import itertools
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.models.common import PROCESSED_DIR, load_config, save_json, split_by_time
from src.utils.logger import get_logger


logger = get_logger(__name__)


PARAM_GRID = {
    "min_expected_value_place": (1.00, 1.05, 1.10, 1.15, 1.25),
    "min_value_gap": (0.00, 0.03, 0.05),
    "min_bet_score": (0.00, 0.02, 0.04),
    "max_model_uncertainty": (0.06, 0.10),
}


def evaluate_thresholds(
    predictions: pd.DataFrame,
    params: dict[str, float],
) -> tuple[dict[str, float | int], pd.DataFrame]:
    """Evaluate fixed Safe Agent thresholds against already labelled rows."""
    required = {
        "expected_value_place", "value_gap", "bet_score", "model_uncertainty",
        "target_place", "payout_place",
    }
    missing = sorted(required - set(predictions.columns))
    if missing:
        raise ValueError(f"predictions is missing required columns: {', '.join(missing)}")
    bets = predictions[
        (predictions["expected_value_place"] >= params["min_expected_value_place"])
        & (predictions["value_gap"] >= params["min_value_gap"])
        & (predictions["bet_score"] >= params["min_bet_score"])
        & (predictions["model_uncertainty"] <= params["max_model_uncertainty"])
    ].copy()
    if bets.empty:
        return {**params, "roi": 0.0, "hit_rate": 0.0, "bet_count": 0, "profit": 0.0, "max_drawdown": 0.0}, bets

    bets["stake"] = 100.0
    bets["hit"] = bets["target_place"].astype(int).eq(1)
    bets["return_amount"] = np.where(
        bets["hit"], bets["payout_place"].fillna(0).astype(float), 0.0
    )
    bets["profit"] = bets["return_amount"] - bets["stake"]
    stake = float(bets["stake"].sum())
    returns = float(bets["return_amount"].sum())
    equity = bets["profit"].cumsum()
    drawdown = equity.cummax() - equity
    return {
        **params,
        "roi": returns / stake if stake else 0.0,
        "hit_rate": float(bets["hit"].mean()),
        "bet_count": int(len(bets)),
        "profit": float(bets["profit"].sum()),
        "max_drawdown": float(drawdown.max()) if len(drawdown) else 0.0,
    }, bets


def _grid() -> list[dict[str, float]]:
    keys = list(PARAM_GRID)
    return [dict(zip(keys, values, strict=True)) for values in itertools.product(*(PARAM_GRID[key] for key in keys))]


def run_threshold_optimization(
    predictions_path: Path | None = None,
    output_json_path: Path | None = None,
    output_csv_path: Path | None = None,
    output_test_bets_path: Path | None = None,
) -> dict[str, Any]:
    config = load_config()
    prediction_file = predictions_path or PROCESSED_DIR / "predictions_place.csv"
    if not prediction_file.exists():
        raise FileNotFoundError(f"Predictions not found: {prediction_file}. Run predict-ensemble first.")
    predictions = pd.read_csv(prediction_file)
    if predictions.empty:
        raise ValueError(f"Predictions are empty: {prediction_file}")
    predictions["race_date"] = pd.to_datetime(predictions["race_date"], errors="coerce")
    labelled = predictions.dropna(subset=["race_date", "target_place"]).copy()
    split = split_by_time(
        labelled,
        float(config["modeling"]["valid_size"]),
        float(config["modeling"]["test_size"]),
    )
    grid = pd.DataFrame([evaluate_thresholds(split.valid, params)[0] for params in _grid()])
    minimum_bets = int(config.get("validation", {}).get("threshold_optimization", {}).get("min_validation_bets", 50))
    eligible = grid[grid["bet_count"] >= minimum_bets]
    selected_pool = eligible if not eligible.empty else grid
    selected = selected_pool.sort_values(
        ["roi", "bet_count", "max_drawdown"], ascending=[False, False, True]
    ).iloc[0]
    best_params = {name: float(selected[name]) for name in PARAM_GRID}
    selected_valid_metrics, _ = evaluate_thresholds(split.valid, best_params)
    test_metrics, test_bets = evaluate_thresholds(split.test, best_params)

    output_json = output_json_path or PROCESSED_DIR / "threshold_optimization_report.json"
    output_csv = output_csv_path or PROCESSED_DIR / "threshold_optimization_valid_grid.csv"
    output_test_bets = output_test_bets_path or PROCESSED_DIR / "threshold_optimization_test_bets.csv"
    output_json.parent.mkdir(parents=True, exist_ok=True)
    grid.sort_values(["roi", "bet_count", "max_drawdown"], ascending=[False, False, True]).to_csv(output_csv, index=False)
    test_bets.to_csv(output_test_bets, index=False)
    report = {
        "selection_policy": "Thresholds are selected on validation only; the selected fixed thresholds are evaluated once on test.",
        "minimum_validation_bets": minimum_bets,
        "best_params_from_valid": best_params,
        "selected_valid_metrics": selected_valid_metrics,
        "test_metrics": test_metrics,
        "split_race_counts": {"train": int(split.train["race_id"].nunique()), "valid": int(split.valid["race_id"].nunique()), "test": int(split.test["race_id"].nunique())},
    }
    save_json(output_json, report)
    logger.info("Saved threshold optimization report: %s", output_json)
    return report
