from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from uuid import uuid4

import pandas as pd

from src.agents.safe_agent import apply_safe_agent
from src.ingestion.temp_data import save_temp_parquet
from src.models.common import PROCESSED_DIR, load_ai_race_entries, prepare_prediction_frame
from src.models.predict import predict_ensemble
from src.utils.logger import get_logger


logger = get_logger(__name__)


def _load_today_csv(path: str | Path, race_date: str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    required = {"race_id", "horse_id"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"today CSV is missing required columns: {', '.join(missing)}")
    if "race_date" not in frame:
        frame["race_date"] = race_date
    frame["race_date"] = pd.to_datetime(frame["race_date"].fillna(race_date), errors="coerce")
    if frame["race_date"].isna().any():
        raise ValueError("today CSV contains an unparseable race_date")
    if "field_size" not in frame:
        frame["field_size"] = frame.groupby("race_id")["horse_id"].transform("count")
    else:
        frame["field_size"] = frame["field_size"].fillna(
            frame.groupby("race_id")["horse_id"].transform("count")
        )
    return frame


def run_predict_today(race_date: str | None, today_csv_path: str | Path) -> dict[str, str]:
    """Create a Phase 2 ensemble prediction run from unconfirmed CSV input."""
    target_date = race_date or date.today().isoformat()
    run_id = f"{target_date.replace('-', '')}_{uuid4().hex[:12]}"
    run_dir = PROCESSED_DIR / "prediction_logs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    today = _load_today_csv(today_csv_path, target_date)
    temp_path = save_temp_parquet(today, f"today_{run_id}")
    confirmed_history = load_ai_race_entries()
    confirmed_history = confirmed_history[confirmed_history["target_place"].notna()].copy()
    features = prepare_prediction_frame(today, confirmed_history)

    input_snapshot_path = run_dir / "today_input.csv"
    features_path = run_dir / "features.csv"
    predictions_path = run_dir / "predictions.csv"
    bets_path = run_dir / "bets.csv"
    metadata_path = run_dir / "metadata.json"
    today.to_csv(input_snapshot_path, index=False)
    features.to_csv(features_path, index=False)
    predictions = predict_ensemble(
        frame=features,
        output_path=predictions_path,
        frame_is_prepared=True,
    )
    apply_safe_agent(predictions, output_path=bets_path)

    metadata = {
        "run_id": run_id,
        "race_date": target_date,
        "input_mode": "temporary_csv",
        "today_csv_path": str(today_csv_path),
        "temp_parquet_path": str(temp_path),
        "input_snapshot_path": str(input_snapshot_path),
        "features_path": str(features_path),
        "predictions_path": str(predictions_path),
        "bets_path": str(bets_path),
        "note": "Unconfirmed input remains in temp and prediction logs; it is not inserted into core tables.",
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    logger.info("Completed today prediction run: %s", run_id)
    return {**metadata, "metadata_path": str(metadata_path)}
