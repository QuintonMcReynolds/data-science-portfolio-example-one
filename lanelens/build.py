"""End-to-end build: generate sources → warehouse → quality gate → model.

    python -m lanelens.build            # full dataset
    python -m lanelens.build --rows 5000
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import duckdb

from . import config
from .generate import generate
from .quality import certification, load_contracts, run_checks
from .risk import train
from .warehouse import build_warehouse


def build(data_dir: Path = config.DATA_DIR, rows: int = 60_000, seed: int = 42, verbose: bool = True) -> Path:
    log = print if verbose else (lambda *a, **k: None)
    raw_dir, db_path = data_dir / "raw", data_dir / "lanelens.duckdb"
    t0 = time.time()

    counts = generate(raw_dir, n_shipments=rows, seed=seed)
    log(f"[extract]   source files: {counts}")

    db_path.unlink(missing_ok=True)
    con = duckdb.connect(str(db_path))
    try:
        tables = build_warehouse(con, raw_dir)
        log(f"[warehouse] built {len(tables)} tables; gold.fact_shipment = {tables['gold.fact_shipment']:,} rows")
        audit = con.execute("SELECT * FROM silver.load_audit ORDER BY loaded_at DESC LIMIT 1").df().iloc[0]
        log(f"[silver]    removed {audit.duplicates_removed} duplicates, quarantined {audit.rejected_rows} rows")

        results = run_checks(con, load_contracts(config.CONTRACTS_PATH))
        cert = certification(results)
        log(f"[quality]   {int(results.passed.sum())}/{len(results)} checks passed")
        for _, r in cert.iterrows():
            log(f"            {r.table_name:<22} {r.status}")
        if (cert.status == "Failed").any():
            raise SystemExit("Quality gate failed: at least one table has a failing error-severity check.")

        m = train(con, data_dir)
        log(f"[model]     late-risk AUC {m['auc']:.3f}, top-decile lift {m['top_decile_lift']:.1f}x")
    finally:
        con.close()
    log(f"[done]      {db_path} in {time.time() - t0:.1f}s")
    return db_path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", type=int, default=60_000)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    build(rows=args.rows, seed=args.seed)


if __name__ == "__main__":
    main()
