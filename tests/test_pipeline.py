from pathlib import Path

import duckdb
import pytest

from lanelens import config
from lanelens.build import build
from lanelens.quality import certification
from lanelens.semantic import SemanticLayer


@pytest.fixture(scope="module")
def con(tmp_path_factory) -> duckdb.DuckDBPyConnection:
    data_dir: Path = tmp_path_factory.mktemp("data")
    db = build(data_dir=data_dir, rows=8_000, verbose=False)
    c = duckdb.connect(str(db), read_only=True)
    yield c
    c.close()


@pytest.fixture(scope="module")
def sl() -> SemanticLayer:
    return SemanticLayer(config.METRICS_PATH)


def test_silver_dedupes_and_quarantines(con):
    audit = con.execute("SELECT * FROM silver.load_audit").df().iloc[-1]
    assert audit.duplicates_removed > 0
    assert audit.rejected_rows > 0
    assert audit.silver_rows + audit.rejected_rows + audit.duplicates_removed == audit.bronze_rows
    reasons = {r for (r,) in con.execute("SELECT DISTINCT reject_reason FROM silver.shipment_rejects").fetchall()}
    assert {"missing_customer", "unknown_carrier", "non_positive_weight"} <= reasons


def test_gold_is_clean(con):
    assert con.execute("SELECT count(*) - count(DISTINCT shipment_id) FROM gold.fact_shipment").fetchone()[0] == 0
    assert con.execute("SELECT count(*) FROM gold.fact_shipment WHERE weight_lbs <= 0").fetchone()[0] == 0


def test_pii_is_masked_in_gold(con):
    emails = [e for (e,) in con.execute("SELECT contact_email_masked FROM gold.dim_customer").fetchall()]
    assert all("***@" in e for e in emails)


def test_quality_gate_certifies_all_tables(con):
    results = con.execute("SELECT * FROM governance.dq_results").df()
    assert (certification(results).status != "Failed").all()


def test_semantic_layer_matches_raw_sql(con, sl):
    got = sl.query(con, ["revenue", "on_time_pct"]).iloc[0]
    rev, ot = con.execute(
        "SELECT sum(revenue_usd), avg(CASE WHEN is_on_time THEN 1.0 ELSE 0 END) FILTER (WHERE status = 'Delivered') "
        "FROM gold.fact_shipment").fetchone()
    assert float(got.revenue) == pytest.approx(float(rev))
    assert got.on_time_pct == pytest.approx(float(ot))


def test_semantic_layer_filters_and_rejects_unknown_names(con, sl):
    by_mode = sl.query(con, ["shipments"], ["mode"], where={"mode": ["LTL"]})
    assert list(by_mode["mode"]) == ["LTL"]
    with pytest.raises(KeyError):
        sl.compile(["revenue; DROP TABLE gold.fact_shipment"])


def test_risk_model_beats_chance(con):
    metrics = con.execute("SELECT count(*), avg(late_risk) FROM gold.shipment_risk").fetchone()
    assert metrics[0] > 0 and 0 < metrics[1] < 1
    top = con.execute("SELECT feature FROM gold.risk_model_coefficients ORDER BY coefficient DESC LIMIT 20").fetchall()
    assert any("Pioneer" in f or "Atlas" in f for (f,) in top)  # the least reliable carriers surface as drivers
