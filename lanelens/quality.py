"""Execute data-contract checks and persist a certification scorecard."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd
import yaml

from .config import AS_OF


def load_contracts(path: Path) -> dict:
    return yaml.safe_load(path.read_text())["tables"]


def _failed_rows(con, table: str, check: dict) -> tuple[str, int]:
    """Return (check name, number of rows that violate it)."""
    t, col = check["type"], check.get("column")
    if t == "unique":
        sql = f"SELECT count(*) - count(DISTINCT {col}) FROM {table}"
    elif t == "not_null":
        sql = f"SELECT count(*) FROM {table} WHERE {col} IS NULL"
    elif t == "accepted_values":
        values = ", ".join(f"'{v}'" for v in check["values"])
        sql = f"SELECT count(*) FROM {table} WHERE {col} IS NOT NULL AND {col} NOT IN ({values})"
    elif t == "range":
        sql = f"SELECT count(*) FROM {table} WHERE {col} < {check['min']} OR {col} > {check['max']}"
    elif t == "relationships":
        ref_table, ref_col = check["to"].rsplit(".", 1)
        sql = (f"SELECT count(*) FROM {table} x WHERE x.{col} IS NOT NULL "
               f"AND NOT EXISTS (SELECT 1 FROM {ref_table} r WHERE r.{ref_col} = x.{col})")
    elif t == "expression":
        return check["name"], con.execute(f"SELECT count(*) FROM {table} WHERE NOT ({check['sql']})").fetchone()[0]
    elif t == "freshness":
        latest = con.execute(f"SELECT max({col}) FROM {table}").fetchone()[0]
        stale = latest is None or (AS_OF - latest).days > check["max_age_days"]
        return f"freshness({col} ≤ {check['max_age_days']}d)", int(stale)
    elif t == "quarantine_rate":
        rejected = con.execute("SELECT count(*) FROM silver.shipment_rejects").fetchone()[0]
        total = rejected + con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        return f"quarantine_rate ≤ {check['max_rate']:.0%}", int(rejected / max(total, 1) > check["max_rate"])
    else:
        raise ValueError(f"Unknown check type: {t}")
    return f"{t}({col})", con.execute(sql).fetchone()[0]


def run_checks(con: duckdb.DuckDBPyConnection, contracts: dict) -> pd.DataFrame:
    rows = []
    for table, spec in contracts.items():
        total = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for check in spec["checks"]:
            name, failed = _failed_rows(con, table, check)
            rows.append({
                "table_name": table,
                "check_name": name,
                "check_type": check["type"],
                "severity": check.get("severity", "error"),
                "failed_rows": int(failed),
                "total_rows": int(total),
                "passed": failed == 0,
                "owner": spec["owner"],
                "steward": spec["steward"],
                "run_at": datetime.now(),
            })
    results = pd.DataFrame(rows)
    con.execute("CREATE SCHEMA IF NOT EXISTS governance")
    con.register("dq_df", results)
    con.execute("CREATE OR REPLACE TABLE governance.dq_results AS SELECT * FROM dq_df")
    con.unregister("dq_df")
    return results


def certification(results: pd.DataFrame) -> pd.DataFrame:
    """A table is Certified if all error checks pass; Warning if only warns fail."""
    def status(g):
        if (~g.passed & (g.severity == "error")).any():
            return "Failed"
        return "Warning" if (~g.passed).any() else "Certified"
    return (results.groupby("table_name")
            .apply(lambda g: pd.Series({"checks": len(g), "passed": int(g.passed.sum()), "status": status(g)}),
                   include_groups=False)
            .reset_index())

