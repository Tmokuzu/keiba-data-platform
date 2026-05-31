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
        "run-all",
    ]

    for name in commands:
        subparsers.add_parser(name)
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
    elif args.command == "run-all":
        run_all()

    logger.info("Finished command: %s", args.command)


if __name__ == "__main__":
    main()
