"""Run the bronze → silver → gold SQL layers against DuckDB."""
from __future__ import annotations

from pathlib import Path

import duckdb

from .config import SQL_DIR

LAYERS = ["01_bronze.sql", "02_silver.sql", "03_gold.sql"]


def build_warehouse(con: duckdb.DuckDBPyConnection, raw_dir: Path) -> dict[str, int]:
    for name in LAYERS:
        sql = (SQL_DIR / name).read_text().replace("{raw_dir}", raw_dir.as_posix())
        con.execute(sql)
    return table_counts(con)


def table_counts(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    rows = con.execute("""
        SELECT table_schema || '.' || table_name FROM information_schema.tables
        WHERE table_schema IN ('bronze', 'silver', 'gold') AND table_type = 'BASE TABLE'
        ORDER BY 1
    """).fetchall()
    return {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for (t,) in rows}
