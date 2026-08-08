from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.models.common import PROCESSED_DIR
from src.utils.logger import get_logger


logger = get_logger(__name__)


SEGMENT_COLUMNS = (
    "course",
    "distance",
    "ground_condition",
    "popularity_band",
    "odds_band",
    "expected_value_band",
    "year",
    "month",
)


def _numeric_column(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame:
        return pd.Series(float("nan"), index=frame.index)
    return pd.to_numeric(frame[column], errors="coerce")


def add_segment_bins(detail: pd.DataFrame) -> pd.DataFrame:
    work = detail.copy()
    work["race_date"] = pd.to_datetime(work["race_date"], errors="coerce")
    work["year"] = work["race_date"].dt.year.astype("Int64").astype("string")
    work["month"] = work["race_date"].dt.strftime("%Y-%m")
    work["popularity_band"] = pd.cut(
        _numeric_column(work, "popularity"),
        bins=[0, 3, 6, 10, 18], labels=["1-3", "4-6", "7-10", "11+"], include_lowest=True,
    ).astype("string")
    work["odds_band"] = pd.cut(
        _numeric_column(work, "odds_place_min"),
        bins=[0, 1.5, 2.0, 3.0, float("inf")],
        labels=["0-1.5", "1.5-2.0", "2.0-3.0", "3.0+"], include_lowest=True,
    ).astype("string")
    work["expected_value_band"] = pd.cut(
        _numeric_column(work, "expected_value_place"),
        bins=[0, 1.10, 1.25, 1.50, float("inf")],
        labels=["0-1.10", "1.10-1.25", "1.25-1.50", "1.50+"], include_lowest=True,
    ).astype("string")
    return work


def build_segmented_rows(detail: pd.DataFrame) -> pd.DataFrame:
    required = {"stake", "return_amount", "profit", "hit"}
    missing = sorted(required - set(detail.columns))
    if missing:
        raise ValueError(f"detail is missing settled bet columns: {', '.join(missing)}")
    work = add_segment_bins(detail)
    rows: list[dict[str, Any]] = []
    for segment in SEGMENT_COLUMNS:
        if segment not in work:
            continue
        for value, group in work.groupby(segment, dropna=False):
            stake = float(group["stake"].sum())
            returns = float(group["return_amount"].sum())
            rows.append(
                {
                    "segment": segment,
                    "value": str(value),
                    "stake": stake,
                    "return": returns,
                    "profit": float(group["profit"].sum()),
                    "roi": returns / stake if stake else 0.0,
                    "bet_count": int(len(group)),
                    "hit_rate": float(group["hit"].mean()) if len(group) else 0.0,
                }
            )
    return pd.DataFrame(rows)


def run_segmented_backtest_report(
    detail_path: Path | None = None,
    output_csv_path: Path | None = None,
    output_json_path: Path | None = None,
) -> dict[str, Any]:
    detail_file = detail_path or PROCESSED_DIR / "walk_forward_detail.csv"
    if not detail_file.exists():
        raise FileNotFoundError(
            f"Walk-forward detail not found: {detail_file}. Run walk-forward-backtest first."
        )
    detail = pd.read_csv(detail_file)
    if detail.empty:
        raise ValueError(f"Walk-forward detail is empty: {detail_file}")
    rows = build_segmented_rows(detail)
    output_csv = output_csv_path or PROCESSED_DIR / "segmented_backtest_report.csv"
    output_json = output_json_path or PROCESSED_DIR / "segmented_backtest_report.json"
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    rows.sort_values(["segment", "roi", "bet_count"], ascending=[True, True, False]).to_csv(output_csv, index=False)
    report = {
        "source_detail": str(detail_file),
        "segments": list(SEGMENT_COLUMNS),
        "row_count": int(len(rows)),
        "worst_segments": rows.sort_values(["roi", "bet_count"], ascending=[True, False]).head(30).to_dict(orient="records"),
    }
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    logger.info("Saved segmented backtest report: %s and %s", output_csv, output_json)
    return report
