from __future__ import annotations

import numpy as np
import pandas as pd

from src.models.common import TARGET_COL, binary_metrics


def evaluate_bets(predictions: pd.DataFrame, prob_col: str = "place_prob_final") -> dict[str, float | int]:
    action = predictions["action"] if "action" in predictions else pd.Series("BUY", index=predictions.index)
    bets = predictions[action == "BUY"].copy()
    if "stake" not in bets:
        bets["stake"] = 100
    if bets.empty:
        return {"bet_count": 0, "hit_rate": 0.0, "roi": 0.0, "profit": 0.0, "max_drawdown": 0.0}
    hits = bets[TARGET_COL].astype(int) == 1 if TARGET_COL in bets else bets["payout_place"].notna()
    payout_rate = pd.to_numeric(bets["payout_place"], errors="coerce").fillna(0) / 100.0
    returns = np.where(hits, bets["stake"].astype(float) * payout_rate, 0.0)
    profit = returns - bets["stake"].astype(float).to_numpy()
    equity = pd.Series(profit).cumsum()
    drawdown = equity.cummax() - equity
    total_stake = float(bets["stake"].sum())
    return {
        "bet_count": int(len(bets)),
        "hit_rate": float(hits.mean()),
        "roi": float((returns.sum() - total_stake) / total_stake) if total_stake > 0 else 0.0,
        "profit": float(profit.sum()),
        "max_drawdown": float(drawdown.max()) if len(drawdown) else 0.0,
    }


def evaluate_predictions(predictions: pd.DataFrame, prob_col: str = "place_prob_final") -> dict[str, float | int]:
    metrics = binary_metrics(predictions[TARGET_COL], predictions[prob_col].to_numpy()) if TARGET_COL in predictions else {}
    metrics.update(evaluate_bets(predictions, prob_col))
    return metrics
