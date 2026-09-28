"""Late-delivery risk model.

A deliberately interpretable logistic regression: operations leaders need to
see *why* a load is flagged, and the coefficients map to levers they own
(carrier selection, Friday tenders, winter lanes). Trained on a time-based
split so the reported accuracy reflects how it would do on future loads.
Customer identity and contact data are excluded by design.
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

CATEGORICAL = ["mode", "carrier_name", "origin_region", "dest_region", "pickup_month", "pickup_dow", "segment"]
NUMERIC = ["miles", "weight_lbs", "transit_days"]
HOLDOUT_DAYS = 90

FEATURE_SQL = """
SELECT f.shipment_id, f.status, f.pickup_date, f.promised_date, f.is_on_time,
       f.mode, c.carrier_name, l.origin_region, l.dest_region, l.lane_id,
       strftime(f.pickup_date, '%b') AS pickup_month,
       strftime(f.pickup_date, '%a') AS pickup_dow,
       cu.segment, f.miles, f.weight_lbs,
       date_diff('day', f.pickup_date, f.promised_date) AS transit_days
FROM gold.fact_shipment f
JOIN gold.dim_lane l USING (lane_id)
JOIN gold.dim_carrier c USING (carrier_id)
JOIN gold.dim_customer cu USING (customer_id)
"""


def _pipeline() -> Pipeline:
    pre = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
        ("num", StandardScaler(), NUMERIC),
    ])
    return Pipeline([("pre", pre), ("clf", LogisticRegression(max_iter=2000, C=0.5))])


def train(con: duckdb.DuckDBPyConnection, out_dir: Path) -> dict:
    df = con.execute(FEATURE_SQL).df()
    hist = df[df.status == "Delivered"].copy()
    hist["late"] = (~hist.is_on_time.astype(bool)).astype(int)

    cutoff = hist.pickup_date.max() - pd.Timedelta(days=HOLDOUT_DAYS)
    train_df, test_df = hist[hist.pickup_date <= cutoff], hist[hist.pickup_date > cutoff]

    model = _pipeline().fit(train_df[CATEGORICAL + NUMERIC], train_df.late)
    p = model.predict_proba(test_df[CATEGORICAL + NUMERIC])[:, 1]
    y = test_df.late.to_numpy()

    top = p >= np.quantile(p, 0.9)
    metrics = {
        "train_rows": int(len(train_df)),
        "test_rows": int(len(test_df)),
        "holdout_start": str((cutoff + pd.Timedelta(days=1)).date()),
        "base_late_rate": float(y.mean()),
        "auc": float(roc_auc_score(y, p)),
        "brier": float(brier_score_loss(y, p)),
        "top_decile_late_rate": float(y[top].mean()),
        "top_decile_lift": float(y[top].mean() / y.mean()),
    }

    # Final model uses all history; the holdout numbers above are the honest estimate.
    model = _pipeline().fit(hist[CATEGORICAL + NUMERIC], hist.late)
    names = model.named_steps["pre"].get_feature_names_out()
    coefs = pd.DataFrame({"feature": names, "coefficient": model.named_steps["clf"].coef_[0]})
    coefs["feature"] = coefs.feature.str.replace(r"^(cat|num)__", "", regex=True)

    open_loads = df[df.status == "In Transit"].copy()
    open_loads["late_risk"] = model.predict_proba(open_loads[CATEGORICAL + NUMERIC])[:, 1]
    scored = open_loads[["shipment_id", "pickup_date", "promised_date", "mode", "carrier_name",
                         "lane_id", "miles", "late_risk"]]

    con.register("risk_df", scored)
    con.execute("CREATE OR REPLACE TABLE gold.shipment_risk AS SELECT * FROM risk_df")
    con.unregister("risk_df")
    con.register("coef_df", coefs)
    con.execute("CREATE OR REPLACE TABLE gold.risk_model_coefficients AS SELECT * FROM coef_df")
    con.unregister("coef_df")

    out_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, out_dir / "late_risk_model.joblib")
    (out_dir / "late_risk_metrics.json").write_text(json.dumps(metrics, indent=2))
    return metrics
