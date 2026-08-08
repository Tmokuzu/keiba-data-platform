from __future__ import annotations

import joblib

from src.models.common import MODELS_DIR, MODEL_NAMES, load_ai_race_entries, load_config, prepare_model_frame, split_by_time
from src.models.ensemble import ensemble_probabilities, fit_ensemble_calibrator, model_uncertainty
from src.models.predict import _predict_with_artifact, predict_ensemble
from src.models.train_catboost_place import train_catboost_place
from src.models.train_place_model import train_lightgbm_place
from src.models.train_xgboost_place import train_xgboost_place
from src.utils.logger import get_logger


logger = get_logger(__name__)


def train_all_models() -> None:
    raw = load_ai_race_entries()
    train_lightgbm_place(raw)
    train_catboost_place(raw)
    train_xgboost_place(raw)
    fit_and_save_ensemble_calibrator(raw)
    predict_ensemble(raw)


def fit_and_save_ensemble_calibrator(raw_frame: object | None = None) -> object | None:
    config = load_config()
    raw = load_ai_race_entries() if raw_frame is None else raw_frame
    data = prepare_model_frame(raw)
    split = split_by_time(data, config["modeling"]["valid_size"], config["modeling"]["test_size"])
    valid = split.valid.copy()
    artifacts = {name: joblib.load(MODELS_DIR / f"{name}_place_model.pkl") for name in MODEL_NAMES}
    for name, artifact in artifacts.items():
        valid[f"place_prob_{name}"] = _predict_with_artifact(artifact, valid)
    valid["place_prob_ensemble_raw"] = ensemble_probabilities(valid, config["ensemble"]["method"], config["ensemble"]["weights"])
    valid["model_uncertainty"] = model_uncertainty(valid)
    calibrator = fit_ensemble_calibrator(valid)
    if calibrator is not None:
        path = MODELS_DIR / "ensemble_place_calibrator.pkl"
        joblib.dump(calibrator, path)
        logger.info("Saved ensemble calibrator fit on validation rows only: %s", path)
    return calibrator


def main() -> None:
    train_all_models()


if __name__ == "__main__":
    main()
