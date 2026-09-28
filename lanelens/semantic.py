"""Compile governed metric requests into SQL.

Only metric and dimension names from the catalog are accepted, and filter
values are bound as parameters, so consumers can't write their own
definitions or inject SQL.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Iterable

import duckdb
import pandas as pd
import yaml


class SemanticLayer:
    def __init__(self, path: Path):
        spec = yaml.safe_load(path.read_text())
        self.from_sql = spec["model"]["from"].strip()
        self.date_column = spec["model"]["date_column"]
        self.dimensions: dict[str, dict] = spec["dimensions"]
        self.metrics: dict[str, dict] = {m["name"]: m for m in spec["metrics"]}

    def compile(self, metrics: Iterable[str], by: Iterable[str] = (), where: dict[str, list] | None = None,
                start: date | None = None, end: date | None = None,
                order_by: str | None = None, descending: bool = True, limit: int | None = None) -> tuple[str, list]:
        metrics, by = list(metrics), list(by)
        select = [f"{self.dimensions[b]['sql']} AS {b}" for b in by]
        select += [f"{self.metrics[m]['sql']} AS {m}" for m in metrics]

        clauses, params = [], []
        if start:
            clauses.append(f"{self.date_column} >= ?")
            params.append(start)
        if end:
            clauses.append(f"{self.date_column} <= ?")
            params.append(end)
        for dim, values in (where or {}).items():
            if values:
                clauses.append(f"{self.dimensions[dim]['sql']} IN ({', '.join('?' * len(values))})")
                params.extend(values)

        sql = f"SELECT {', '.join(select)}\nFROM {self.from_sql}"
        if clauses:
            sql += "\nWHERE " + "\n  AND ".join(clauses)
        if by:
            sql += "\nGROUP BY ALL"
        if order_by:
            if order_by not in self.metrics and order_by not in self.dimensions:
                raise KeyError(order_by)
            sql += f"\nORDER BY {order_by} {'DESC' if descending else 'ASC'} NULLS LAST"
        if limit:
            sql += f"\nLIMIT {int(limit)}"
        return sql, params

    def query(self, con: duckdb.DuckDBPyConnection, metrics, by=(), **kwargs) -> pd.DataFrame:
        sql, params = self.compile(metrics, by, **kwargs)
        return con.execute(sql, params).df()

    def catalog(self) -> pd.DataFrame:
        return pd.DataFrame([
            {"Metric": m["label"], "Name": m["name"], "Definition": m["description"], "SQL": m["sql"],
             "Target": m.get("target"), "Better when": "higher" if m["direction"] == "up" else "lower",
             "Owner": m["owner"]}
            for m in self.metrics.values()
        ])
