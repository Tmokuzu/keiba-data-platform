from __future__ import annotations

from collections.abc import Sequence

import pandas as pd
from sqlalchemy import MetaData, Table
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine


def upsert_dataframe(
    engine: Engine,
    df: pd.DataFrame,
    table_name: str,
    conflict_columns: Sequence[str],
) -> int:
    if df.empty:
        return 0

    metadata = MetaData()
    table = Table(table_name, metadata, autoload_with=engine)
    table_columns = [column.name for column in table.columns]
    insert_columns = [column for column in df.columns if column in table_columns]
    missing_conflict_columns = [column for column in conflict_columns if column not in insert_columns]
    if missing_conflict_columns:
        raise ValueError(
            f"{table_name} CSV is missing required key columns: {missing_conflict_columns}"
        )

    records = df[insert_columns].where(pd.notna(df[insert_columns]), None).to_dict("records")
    if not records:
        return 0

    stmt = insert(table).values(records)
    update_columns = {
        column.name: stmt.excluded[column.name]
        for column in table.columns
        if column.name in insert_columns
        and column.name not in conflict_columns
        and column.name not in {"created_at", "imported_at"}
    }
    if "updated_at" in table_columns:
        update_columns["updated_at"] = stmt.excluded.updated_at

    if update_columns:
        stmt = stmt.on_conflict_do_update(
            index_elements=list(conflict_columns),
            set_=update_columns,
        )
    else:
        stmt = stmt.on_conflict_do_nothing(index_elements=list(conflict_columns))

    with engine.begin() as connection:
        result = connection.execute(stmt)
    return result.rowcount or 0
