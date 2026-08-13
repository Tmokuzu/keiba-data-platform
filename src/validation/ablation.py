from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.agents.safe_agent import apply_safe_agent
from src.backtesting.metrics import evaluate_predictions
from src.models.common import MODELS_DIR, PROCESSED_DIR, load_ai_race_entries
from src.models.predict import _add_value_columns, _predict_with_artifact
from src.models.train_place_model import train_lightgbm_place
from src.validation.model_compare import _summary_row
from src.utils.logger import get_logger


logger = get_logger(__name__)


ABLATIONS = {
    "all_features": [],
    "no_jv_ck": ["no_jv_ck"],
    "no_training": ["no_training"],
    "no_jockey_trainer_id": ["no_jockey_trainer_id"],
    "no_odds": ["no_odds"],
    "no_market_features": ["no_market_features"],
    "no_recent_form": ["no_recent_form"],
    "no_suitability": ["no_suitability"],
    "no_race_grade_ground_condition": ["no_race_grade_ground_condition"],
}


def run_ablation(output_path: Path | None = None) -> pd.DataFrame:
    raw = load_ai_race_entries()
    rows: list[dict] = []
    for name, groups in ABLATIONS.items():
        # Ablations are experiments: never overwrite the production artifact.
        artifact = train_lightgbm_place(
            raw,
            output_model_path=MODELS_DIR / "ablation" / f"{name}_lgbm_place_model.pkl",
            output_metrics_path=MODELS_DIR / "ablation" / f"{name}_lgbm_place_metrics.json",
            excluded_feature_groups=groups,
        )
        frame = artifact_test_frame(raw, groups)
        frame["place_prob_final"] = _predict_with_artifact(artifact, frame, calibrated=True)
        frame["model_uncertainty"] = 0.0
        frame = _add_value_columns(frame)
        bets = apply_safe_agent(frame)
        metrics = evaluate_predictions(bets)
        rows.append(
            {
                "ablation": name,
                "AUC": metrics.get("auc"),
                "LogLoss": metrics.get("logloss"),
                "Brier Score": metrics.get("brier"),
                "ROI": metrics.get("roi"),
                "Hit Rate": metrics.get("hit_rate"),
                "Bet Count": metrics.get("bet_count"),
                "Max Drawdown": metrics.get("max_drawdown"),
            }
        )
    summary = pd.DataFrame(rows)
    out = output_path or PROCESSED_DIR / "ablation_summary.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(out, index=False)
    logger.info("Saved ablation summary: %s", out)
    return summary


def artifact_test_frame(raw: pd.DataFrame, groups: list[str]) -> pd.DataFrame:
    from src.models.common import load_config, prepare_model_frame, split_by_time

    config = load_config()
    data = prepare_model_frame(raw, groups)
    return split_by_time(data, config["modeling"]["valid_size"], config["modeling"]["test_size"]).test.copy()


def main() -> None:
    run_ablation()


if __name__ == "__main__":
    main()
