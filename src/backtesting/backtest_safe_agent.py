from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.agents.safe_agent import apply_safe_agent
from src.backtesting.metrics import evaluate_predictions, settle_bets
from src.models.common import PROCESSED_DIR, save_json
from src.models.predict import predict_ensemble
from src.utils.logger import get_logger


logger = get_logger(__name__)


def backtest_safe_agent(predictions: pd.DataFrame | None = None, output_path: Path | None = None) -> dict[str, float | int]:
    preds = predict_ensemble() if predictions is None else predictions
    bets = apply_safe_agent(preds, PROCESSED_DIR / "safe_agent_bets.csv")
    metrics = evaluate_predictions(bets)
    settled = settle_bets(bets)
    settled.to_csv(PROCESSED_DIR / "backtest_safe_agent_detail.csv", index=False)
    out = output_path or PROCESSED_DIR / "backtest_safe_agent_metrics.json"
    save_json(out, metrics)
    logger.info("Backtest metrics: %s", metrics)
    return metrics


def main() -> None:
    backtest_safe_agent()


if __name__ == "__main__":
    main()
