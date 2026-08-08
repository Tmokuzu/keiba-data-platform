from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.models.common import PROCESSED_DIR, load_config
from src.utils.logger import get_logger


logger = get_logger(__name__)


STAKE_DOWN = {1000: 500, 500: 300, 300: 100}


def apply_safe_agent(predictions: pd.DataFrame, output_path: Path | None = None) -> pd.DataFrame:
    config = load_config()["safe_agent"]
    df = predictions.copy()
    max_uncertainty = float(config["max_model_uncertainty"])
    buy_mask = (
        (df["expected_value_place"] >= float(config["min_expected_value_place"]))
        & (df["value_gap"] >= float(config["min_value_gap"]))
        & (df["bet_score"] >= float(config["min_bet_score"]))
        & (df["model_uncertainty"] <= max_uncertainty)
    )
    df["action"] = "SKIP"
    df.loc[buy_mask, "action"] = "BUY"
    df["stake"] = 0
    base_stake = _base_stake(df, config)
    df.loc[buy_mask, "stake"] = base_stake[buy_mask]

    reduce_mask = buy_mask & (df["model_uncertainty"] > 0.06) & (df["model_uncertainty"] <= max_uncertainty)
    df.loc[reduce_mask, "stake"] = df.loc[reduce_mask, "stake"].map(lambda stake: STAKE_DOWN.get(int(stake), 100))
    df.loc[df["model_uncertainty"] > max_uncertainty, ["action", "stake"]] = ["SKIP", 0]

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)
        logger.info("Saved safe-agent output: %s", output_path)
    return df


def run_safe_agent(predictions_path: Path | None = None) -> pd.DataFrame:
    path = predictions_path or PROCESSED_DIR / "predictions_place.csv"
    predictions = pd.read_csv(path)
    return apply_safe_agent(predictions, PROCESSED_DIR / "safe_agent_bets.csv")


def _base_stake(df: pd.DataFrame, config: dict) -> pd.Series:
    high = int(config["stake_high"])
    mid = int(config["stake_mid"])
    low = int(config["stake_low"])
    stake = pd.Series(low, index=df.index)
    stake[df["bet_score"] >= df["bet_score"].quantile(0.75)] = mid
    stake[df["bet_score"] >= df["bet_score"].quantile(0.90)] = high
    return stake
