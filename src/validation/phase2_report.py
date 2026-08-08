from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from src.models.common import PROCESSED_DIR, save_json
from src.validation.ablation import run_ablation
from src.validation.model_compare import run_model_compare
from src.validation.walk_forward import run_walk_forward
from src.utils.logger import get_logger


logger = get_logger(__name__)


def build_phase2_report(output_path: Path | None = None) -> dict[str, Any]:
    compare_path = PROCESSED_DIR / "model_compare_summary.csv"
    ablation_path = PROCESSED_DIR / "ablation_summary.csv"
    wf_path = PROCESSED_DIR / "walk_forward_summary.csv"

    compare = _read_csv_or_empty(compare_path) if compare_path.exists() else run_model_compare()
    ablation = _read_csv_or_empty(ablation_path) if ablation_path.exists() else run_ablation()
    walk_forward, _ = (_read_csv_or_empty(wf_path), pd.DataFrame()) if wf_path.exists() else run_walk_forward()

    report = {
        "best_model_by_auc": _best(compare, "AUC", higher=True),
        "best_model_by_logloss": _best(compare, "LogLoss", higher=False),
        "best_model_by_roi": _best(compare, "ROI", higher=True),
        "ensemble_vs_lgbm": _ensemble_vs_lgbm(compare),
        "walk_forward_avg_roi": float(walk_forward["roi"].mean()) if not walk_forward.empty else None,
        "walk_forward_total_bets": int(walk_forward["bet_count"].sum()) if not walk_forward.empty else 0,
        "ablation_findings": _ablation_findings(ablation),
        "recommendation": _recommendation(compare, walk_forward),
        "disclaimer": "Backtest and model metrics do not guarantee future profit.",
    }
    out = output_path or PROCESSED_DIR / "phase2_report.json"
    save_json(out, report)
    logger.info("Saved Phase2 report: %s", out)
    return report


def _best(df: pd.DataFrame, column: str, higher: bool) -> dict[str, Any] | None:
    if df.empty or column not in df:
        return None
    series = pd.to_numeric(df[column], errors="coerce")
    if series.dropna().empty:
        return None
    idx = series.idxmax() if higher else series.idxmin()
    return {"model_type": str(df.loc[idx, "model_type"]), column: float(series.loc[idx])}


def _read_csv_or_empty(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _ensemble_vs_lgbm(compare: pd.DataFrame) -> dict[str, Any]:
    if compare.empty:
        return {}
    lgbm = compare[compare["model_type"] == "lgbm"]
    ens = compare[compare["model_type"] == "ensemble_simple_average"]
    if lgbm.empty or ens.empty:
        return {}
    return {
        "auc_delta": float(ens["AUC"].iloc[0] - lgbm["AUC"].iloc[0]),
        "logloss_delta": float(ens["LogLoss"].iloc[0] - lgbm["LogLoss"].iloc[0]),
        "roi_delta": float(ens["ROI"].iloc[0] - lgbm["ROI"].iloc[0]),
    }


def _ablation_findings(ablation: pd.DataFrame) -> list[dict[str, Any]]:
    if ablation.empty or "AUC" not in ablation:
        return []
    baseline = ablation[ablation["ablation"] == "all_features"]
    if baseline.empty:
        return []
    base_auc = float(baseline["AUC"].iloc[0])
    findings = []
    for _, row in ablation.iterrows():
        findings.append({"ablation": row["ablation"], "auc_delta_vs_all_features": float(row["AUC"] - base_auc)})
    return findings


def _recommendation(compare: pd.DataFrame, walk_forward: pd.DataFrame) -> str:
    best_roi = _best(compare, "ROI", higher=True)
    avg_roi = float(walk_forward["roi"].mean()) if not walk_forward.empty else None
    if best_roi and best_roi["model_type"].startswith("ensemble") and avg_roi is not None and avg_roi > 0:
        return "Use ensemble predictions with Safe Agent uncertainty filtering, while continuing walk-forward monitoring."
    return "Prefer the most stable calibrated model and keep Safe Agent uncertainty filtering enabled before any live use."


def main() -> None:
    build_phase2_report()


if __name__ == "__main__":
    main()
