"""Project paths and run-wide constants."""
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
DB_PATH = DATA_DIR / "lanelens.duckdb"
SQL_DIR = ROOT / "sql"
CONTRACTS_PATH = ROOT / "governance" / "contracts.yml"
METRICS_PATH = ROOT / "semantic" / "metrics.yml"

# The synthetic "today". Shipments picked up recently are still in transit.
AS_OF = date(2026, 9, 27)
START = date(2024, 10, 1)
