from __future__ import annotations

import argparse

from src.utils.logger import get_logger


logger = get_logger(__name__)


def run_all() -> None:
    from src.database.connection import test_connection
    from src.database.schema import init_db
    from src.ingestion.csv_loader import import_csv_files
    from src.pipelines.build_ai_views import build_ai_views
    from src.pipelines.sync_ended import sync_ended
    from src.validators.data_quality import run_data_quality_checks

    test_connection()
    init_db()
    import_csv_files()
    sync_ended()
    build_ai_views()
    run_data_quality_checks()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Keiba data platform CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    commands = [
        "check-db",
        "init-db",
        "import-csv",
        "sync-ended",
        "build-core",
        "build-ai-views",
        "validate",
        "check-odds-snapshots",
        "predict-today",
        "run-all",
        "train-place-model",
        "train-catboost-place",
        "train-xgboost-place",
        "train-all-models",
        "predict",
        "predict-ensemble",
        "safe-agent",
        "backtest-safe-agent",
        "model-compare",
        "walk-forward-backtest",
        "ablation-test",
        "phase2-report",
        "segmented-backtest-report",
        "optimize-thresholds",
    ]

    for name in commands:
        command_parser = subparsers.add_parser(name)
        if name == "check-odds-snapshots":
            command_parser.add_argument("--date", required=True, help="Race date in YYYY-MM-DD format")
        if name == "predict-today":
            command_parser.add_argument("--date", help="Race date in YYYY-MM-DD format")
            command_parser.add_argument("--today-csv", required=True, help="Unconfirmed race entry CSV")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    logger.info("Starting command: %s", args.command)

    if args.command == "check-db":
        from src.database.connection import test_connection

        test_connection()
    elif args.command == "init-db":
        from src.database.schema import init_db

        init_db()
    elif args.command == "import-csv":
        from src.ingestion.csv_loader import import_csv_files

        import_csv_files()
    elif args.command == "sync-ended":
        from src.pipelines.sync_ended import sync_ended

        sync_ended()
    elif args.command == "build-core":
        from src.pipelines.build_core import build_core

        build_core()
    elif args.command == "build-ai-views":
        from src.pipelines.build_ai_views import build_ai_views

        build_ai_views()
    elif args.command == "validate":
        from src.validators.data_quality import run_data_quality_checks

        run_data_quality_checks()
    elif args.command == "check-odds-snapshots":
        from src.validators.odds_snapshots import check_odds_snapshot_coverage

        check_odds_snapshot_coverage(args.date)
    elif args.command == "predict-today":
        from src.prediction.predict_today import run_predict_today

        run_predict_today(args.date, args.today_csv)
    elif args.command == "run-all":
        run_all()
    elif args.command == "train-place-model":
        from src.models.train_place_model import train_lightgbm_place

        train_lightgbm_place()
    elif args.command == "train-catboost-place":
        from src.models.train_catboost_place import train_catboost_place

        train_catboost_place()
    elif args.command == "train-xgboost-place":
        from src.models.train_xgboost_place import train_xgboost_place

        train_xgboost_place()
    elif args.command == "train-all-models":
        from src.models.train_all import train_all_models

        train_all_models()
    elif args.command == "predict":
        from src.models.predict import predict_lgbm

        predict_lgbm()
    elif args.command == "predict-ensemble":
        from src.models.predict import predict_ensemble

        predict_ensemble()
    elif args.command == "safe-agent":
        from src.agents.safe_agent import run_safe_agent

        run_safe_agent()
    elif args.command == "backtest-safe-agent":
        from src.backtesting.backtest_safe_agent import backtest_safe_agent

        backtest_safe_agent()
    elif args.command == "model-compare":
        from src.validation.model_compare import run_model_compare

        run_model_compare()
    elif args.command == "walk-forward-backtest":
        from src.validation.walk_forward import run_walk_forward

        run_walk_forward()
    elif args.command == "ablation-test":
        from src.validation.ablation import run_ablation

        run_ablation()
    elif args.command == "phase2-report":
        from src.validation.phase2_report import build_phase2_report

        build_phase2_report()
    elif args.command == "segmented-backtest-report":
        from src.validation.segmented_report import run_segmented_backtest_report

        run_segmented_backtest_report()
    elif args.command == "optimize-thresholds":
        from src.validation.threshold_optimization import run_threshold_optimization

        run_threshold_optimization()

    logger.info("Finished command: %s", args.command)


if __name__ == "__main__":
    main()
