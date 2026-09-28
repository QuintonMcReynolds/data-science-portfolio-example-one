"""Data Science Portfolio Example One: executive freight analytics on a governed warehouse."""
from __future__ import annotations

import json
from datetime import timedelta

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from lanelens import config
from lanelens.quality import certification, load_contracts
from lanelens.semantic import SemanticLayer

st.set_page_config(page_title="Data Science Portfolio Example One", page_icon="🚚", layout="wide")

# Validated categorical order (blue, orange, aqua) and a blue↔gray↔red diverging scale.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]
MODE_COLORS = {"TL": SERIES[0], "LTL": SERIES[1], "Intermodal": SERIES[2]}
DIVERGING = [[0, "#d03b3b"], [0.5, "#b8b7b2"], [1, "#256abf"]]
GRID = "rgba(128,128,128,0.18)"
FORMATS = {"int": "{:,.0f}", "usd": "${:,.0f}", "usd2": "${:,.2f}", "pct": "{:.1%}", "pct2": "{:.2%}", "dec": "{:.2f}"}


@st.cache_resource
def connect() -> duckdb.DuckDBPyConnection:
    if not config.DB_PATH.exists():
        from lanelens.build import build
        with st.spinner("First run: building the warehouse (~2s)…"):
            build(verbose=False)
    return duckdb.connect(str(config.DB_PATH), read_only=True)


@st.cache_resource
def semantic() -> SemanticLayer:
    return SemanticLayer(config.METRICS_PATH)


con, sl = connect(), semantic()


def q(sql: str, params=None) -> pd.DataFrame:
    return con.execute(sql, params or []).df()


def fmt(metric: str, value) -> str:
    if value is None or pd.isna(value):
        return "–"
    return FORMATS[sl.metrics[metric]["format"]].format(value)


def style(fig: go.Figure, height: int = 360) -> go.Figure:
    fig.update_layout(height=height, margin=dict(l=8, r=8, t=36, b=8), hovermode="x unified",
                      legend=dict(orientation="h", y=1.08, x=0, title=None), font=dict(size=13))
    fig.update_xaxes(showgrid=False, title=None)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, title=None)
    return fig


# ---------- Sidebar filters (one set, applied to every tab) ----------
min_d, max_d = (pd.Timestamp(v).date() for v in q("SELECT min(pickup_date), max(pickup_date) FROM gold.fact_shipment").iloc[0])
with st.sidebar:
    st.title("🚚 Data Science Portfolio Example One")
    st.caption(f"Data as of **{config.AS_OF:%b %d, %Y}** · synthetic freight network")
    period = st.date_input("Pickup date range", (max_d - timedelta(days=89), max_d), min_value=min_d, max_value=max_d)
    modes = st.multiselect("Mode", ["TL", "LTL", "Intermodal"])
    regions = st.multiselect("Origin region", sorted(q("SELECT DISTINCT origin_region FROM gold.dim_lane").origin_region))
    segments = st.multiselect("Customer segment", ["Enterprise", "Mid-Market", "SMB"])
    show_sql = st.toggle("Show governed SQL", help="See the SQL the semantic layer compiled for each view.")

start, end = (period if isinstance(period, tuple) and len(period) == 2 else (period[0], period[0]))
span = (end - start).days + 1
prior_start, prior_end = start - timedelta(days=span), start - timedelta(days=1)
where = {"mode": modes, "origin_region": regions, "segment": segments}


def metric_query(metrics, by=(), s=start, e=end, **kw) -> pd.DataFrame:
    df = sl.query(con, metrics, by, where=where, start=s, end=e, **kw)
    if show_sql:
        with st.expander("Compiled SQL"):
            st.code(sl.compile(metrics, by, where=where, start=s, end=e, **kw)[0], language="sql")
    return df


tabs = st.tabs(["📊 Executive scorecard", "🗺️ Network & lanes", "🚛 Carriers", "🤖 Delivery risk (AI)",
                "🛡️ Data trust", "📚 Metric catalog", "🧭 Operating model"])

# ---------- Executive scorecard ----------
with tabs[0]:
    kpis = ["revenue", "gross_margin_pct", "shipments", "on_time_pct", "otif_pct", "cost_per_mile", "claims_rate"]
    cur = metric_query(kpis).iloc[0]
    prev = sl.query(con, kpis, where=where, start=prior_start, end=prior_end).iloc[0]
    st.subheader(f"{start:%b %d, %Y} – {end:%b %d, %Y}")
    st.caption(f"Compared with the prior {span} days. Status marks show position against target.")
    cols = st.columns(len(kpis))
    for col, k in zip(cols, kpis):
        m = sl.metrics[k]
        delta = None
        if pd.notna(prev[k]) and prev[k]:
            change = cur[k] - prev[k]
            delta = (f"{change * 100:+.1f} pts" if m["format"].startswith("pct") else f"{change / prev[k]:+.1%}")
        label = m["label"]
        if "target" in m and pd.notna(cur[k]):
            hit = cur[k] >= m["target"] if m["direction"] == "up" else cur[k] <= m["target"]
            label += " ✅" if hit else " ⚠️"
        col.metric(label, fmt(k, cur[k]), delta, delta_color="normal" if m["direction"] == "up" else "inverse",
                   help=f"{m['description']}" + (f" Target: {fmt(k, m['target'])}." if "target" in m else ""))

    st.divider()
    left, right = st.columns([2, 1])
    with left:
        choice = st.selectbox("Trend", kpis, index=3, format_func=lambda k: sl.metrics[k]["label"])
        trend = sl.query(con, [choice], ["month", "mode"], where=where, order_by="month", descending=False)
        fig = px.line(trend, x="month", y=choice, color="mode", color_discrete_map=MODE_COLORS, markers=True)
        fig.update_traces(line_width=2, marker_size=8)
        if "target" in sl.metrics[choice]:
            fig.add_hline(y=sl.metrics[choice]["target"], line_dash="dot", line_color="#8a8984",
                          annotation_text="Target", annotation_position="top left")
        if sl.metrics[choice]["format"].startswith("pct"):
            fig.update_yaxes(tickformat=".0%")
        st.plotly_chart(style(fig, 380), width="stretch")
        st.caption("Trend shows full history (all dates) so seasonality is visible; other filters apply.")
    with right:
        st.markdown("**What the data says**")
        by_corr = metric_query(["shipments", "on_time_pct", "gross_margin_pct"], ["corridor"])
        by_corr = by_corr[by_corr.shipments >= 50]
        if not by_corr.empty:
            worst_ot = by_corr.nsmallest(1, "on_time_pct").iloc[0]
            worst_gm = by_corr.nsmallest(1, "gross_margin_pct").iloc[0]
            st.info(f"**Service:** {worst_ot.corridor} runs {worst_ot.on_time_pct:.1%} on-time, "
                    f"lowest corridor with 50+ loads.")
            st.warning(f"**Margin:** {worst_gm.corridor} earns {worst_gm.gross_margin_pct:.1%} gross margin. "
                       f"Candidate for a repricing review.")
        risk_n = q("SELECT count(*) FROM gold.shipment_risk WHERE late_risk >= 0.3").iloc[0, 0]
        st.error(f"**Now:** {risk_n} in-transit loads have ≥30% predicted late risk. See *Delivery risk*.")

# ---------- Network & lanes ----------
with tabs[1]:
    lanes = metric_query(["shipments", "revenue", "gross_margin_pct", "on_time_pct"], ["lane"])
    lanes = lanes.merge(q("SELECT * FROM gold.dim_lane"), left_on="lane", right_on="lane_id")
    target = sl.metrics["gross_margin_pct"]["target"]
    top = lanes.nlargest(60, "shipments")

    fig = go.Figure()
    lo, hi = target - 0.12, target + 0.12
    for _, r in top.iterrows():
        pos = min(max((r.gross_margin_pct - lo) / (hi - lo), 0), 1)
        color = px.colors.sample_colorscale(DIVERGING, pos)[0]
        fig.add_trace(go.Scattergeo(
            lon=[r.origin_lon, r.dest_lon], lat=[r.origin_lat, r.dest_lat], mode="lines",
            line=dict(width=1 + 4 * r.shipments / top.shipments.max(), color=color), opacity=0.8,
            hoverinfo="text", showlegend=False,
            text=f"{r.lane}: {r.shipments:,} loads · margin {r.gross_margin_pct:.1%} · on-time {r.on_time_pct:.1%}"))
    fac = q("""SELECT f.city, f.lat, f.lon, count(*) AS loads FROM gold.fact_shipment s
               JOIN gold.dim_facility f ON split_part(s.lane_id, '-', 1) = f.facility_id
               WHERE s.pickup_date BETWEEN ? AND ? GROUP BY ALL""", [start, end])
    fig.add_trace(go.Scattergeo(lon=fac.lon, lat=fac.lat, text=fac.city, mode="markers+text", textposition="top center",
                                marker=dict(size=8 + 14 * fac.loads / max(fac.loads.max(), 1), color=SERIES[0],
                                            line=dict(width=2, color="white")),
                                hovertemplate="%{text}: %{customdata:,} outbound loads<extra></extra>",
                                customdata=fac.loads, showlegend=False))
    # Legend for the diverging color scale.
    fig.add_trace(go.Scattergeo(lon=[None], lat=[None], mode="markers", showlegend=False, hoverinfo="skip",
                                marker=dict(colorscale=DIVERGING, cmin=lo, cmax=hi, color=[target], showscale=True,
                                            colorbar=dict(title="Margin", tickformat=".0%", len=0.6))))
    fig.update_geos(scope="usa", showland=True, landcolor="rgba(128,128,128,0.08)", bgcolor="rgba(0,0,0,0)",
                    subunitcolor="rgba(128,128,128,0.3)")
    fig.update_layout(height=520, margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor="rgba(0,0,0,0)")
    st.markdown(f"**Top 60 lanes by volume.** Line width = volume; color = gross margin vs the {target:.0%} target "
                "(red below, blue above).")
    st.plotly_chart(fig, width="stretch")

    c1, c2 = st.columns(2)
    cols_show = {"lane": "Lane", "corridor": "Corridor", "shipments": "Loads", "revenue": "Revenue",
                 "gross_margin_pct": "Margin %", "on_time_pct": "On-time %"}
    cfg = {"Revenue": st.column_config.NumberColumn(format="$%,.0f"),
           "Margin %": st.column_config.NumberColumn(format="percent"),
           "On-time %": st.column_config.NumberColumn(format="percent")}
    material = lanes[lanes.shipments >= 30]
    with c1:
        st.markdown("**Reprice or re-source: lowest-margin lanes (30+ loads)**")
        st.dataframe(material.nsmallest(10, "gross_margin_pct")[list(cols_show)].rename(columns=cols_show),
                     hide_index=True, column_config=cfg, width="stretch")
    with c2:
        st.markdown("**Protect and grow: highest-margin lanes (30+ loads)**")
        st.dataframe(material.nlargest(10, "gross_margin_pct")[list(cols_show)].rename(columns=cols_show),
                     hide_index=True, column_config=cfg, width="stretch")

# ---------- Carriers ----------
with tabs[2]:
    car = metric_query(["shipments", "on_time_pct", "otif_pct", "claims_rate", "cost_per_mile", "gross_margin_pct"],
                       ["carrier"], order_by="shipments")
    car = car.merge(q("SELECT carrier_name AS carrier, primary_mode AS mode FROM gold.dim_carrier"), on="carrier")
    ot_target = sl.metrics["on_time_pct"]["target"]
    st.markdown("**Carrier service vs. claims.** Bubble size = loads. Top-left is where volume should move to.")
    fig = px.scatter(car, x="claims_rate", y="on_time_pct", size="shipments", color="mode", text="carrier",
                     color_discrete_map=MODE_COLORS, size_max=40,
                     hover_data={"shipments": ":,", "cost_per_mile": ":$.2f", "claims_rate": ":.2%",
                                 "on_time_pct": ":.1%", "carrier": False})
    fig.update_traces(textposition="top center", marker=dict(line=dict(width=2, color="white")))
    fig.add_hline(y=ot_target, line_dash="dot", line_color="#8a8984", annotation_text=f"On-time target {ot_target:.0%}")
    fig.update_xaxes(tickformat=".1%", title="Claims rate")
    fig.update_yaxes(tickformat=".0%", title="On-time %")
    fig = style(fig, 460)
    fig.update_layout(hovermode="closest")
    st.plotly_chart(fig, width="stretch")
    st.dataframe(car.rename(columns={"carrier": "Carrier", "mode": "Mode", "shipments": "Loads", "on_time_pct": "On-time %",
                                     "otif_pct": "OTIF %", "claims_rate": "Claims rate", "cost_per_mile": "Cost/mi",
                                     "gross_margin_pct": "Margin %"}),
                 hide_index=True, width="stretch",
                 column_config={c: st.column_config.NumberColumn(format="percent")
                                for c in ["On-time %", "OTIF %", "Claims rate", "Margin %"]}
                 | {"Cost/mi": st.column_config.NumberColumn(format="$%.2f")})

# ---------- Delivery risk ----------
with tabs[3]:
    mpath = config.DATA_DIR / "late_risk_metrics.json"
    m = json.loads(mpath.read_text()) if mpath.exists() else {}
    st.markdown("**Which in-transit loads will miss their promised date?** An interpretable model ops can act on "
                "before the customer calls.")
    c = st.columns(4)
    c[0].metric("Holdout AUC", f"{m.get('auc', 0):.3f}", help="Scored on the most recent 90 days, never seen in training.")
    c[1].metric("Base late rate", f"{m.get('base_late_rate', 0):.1%}")
    c[2].metric("Late rate, riskiest 10%", f"{m.get('top_decile_late_rate', 0):.1%}")
    c[3].metric("Lift, riskiest 10%", f"{m.get('top_decile_lift', 0):.1f}×",
                help="How much more often the top-decile flagged loads are late than an average load.")

    left, right = st.columns([3, 2])
    with left:
        threshold = st.slider("Alert threshold", 0.1, 0.6, 0.3, 0.05, format="%.2f")
        risk = q("SELECT * FROM gold.shipment_risk WHERE late_risk >= ? ORDER BY late_risk DESC", [threshold])
        st.markdown(f"**{len(risk)} loads at or above {threshold:.0%} risk**: send to the carrier desk for proactive outreach.")
        st.dataframe(risk.rename(columns={"shipment_id": "Shipment", "pickup_date": "Picked up", "promised_date": "Promised",
                                          "mode": "Mode", "carrier_name": "Carrier", "lane_id": "Lane",
                                          "miles": "Miles", "late_risk": "Late risk"}),
                     hide_index=True, width="stretch", height=380,
                     column_config={"Late risk": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1)})
    with right:
        coefs = q("SELECT * FROM gold.risk_model_coefficients")
        drivers = pd.concat([coefs.nlargest(8, "coefficient"), coefs.nsmallest(6, "coefficient")]).sort_values("coefficient")
        drivers["effect"] = drivers.coefficient.map(lambda v: "Raises risk" if v > 0 else "Lowers risk")
        fig = px.bar(drivers, x="coefficient", y="feature", orientation="h", color="effect",
                     color_discrete_map={"Raises risk": "#e34948", "Lowers risk": SERIES[0]})
        fig = style(fig, 440)
        fig.update_layout(hovermode="closest", title=dict(text="Top risk drivers (log-odds)", x=0, font_size=14))
        fig.update_xaxes(showgrid=True, gridcolor=GRID)
        st.plotly_chart(fig, width="stretch")

    with st.expander("Model card"):
        st.markdown(f"""
- **Intended use:** prioritize proactive outreach on in-transit loads. It is decision *support*; people still make the call.
- **Model:** L2-regularized logistic regression. Chosen over boosted trees for explainability; the coefficients above are the model.
- **Features:** mode, carrier, origin/destination region, pickup month and weekday, customer segment, miles, weight, planned transit days.
- **Excluded by design:** customer identity and contact data (PII). Segment is the only customer attribute.
- **Validation:** time-based split. Trained through {m.get('holdout_start', '?')}, tested on {m.get('test_rows', 0):,} later loads. Brier score {m.get('brier', 0):.3f}.
- **Monitoring:** retrained each build; alert if holdout AUC drops below 0.60 or base late rate shifts more than 3 pts.
- **Known limits:** no live telematics, weather, or appointment data. Adding ELD pings is the next increment on the roadmap.
""")

# ---------- Data trust ----------
with tabs[4]:
    dq = q("SELECT * FROM governance.dq_results")
    cert = certification(dq)
    audit = q("SELECT * FROM silver.load_audit ORDER BY loaded_at DESC LIMIT 1").iloc[0]
    c = st.columns(4)
    c[0].metric("Checks passing", f"{int(dq.passed.sum())}/{len(dq)}")
    c[1].metric("Certified tables", f"{(cert.status == 'Certified').sum()}/{len(cert)}")
    c[2].metric("Duplicates removed", f"{audit.duplicates_removed:,}")
    c[3].metric("Rows quarantined", f"{audit.rejected_rows:,}",
                help=f"{audit.rejected_rows / audit.bronze_rows:.2%} of landed rows. Held for steward review, not dropped.")

    icon = {"Certified": "✅ Certified", "Warning": "⚠️ Warning", "Failed": "⛔ Failed"}
    contracts = load_contracts(config.CONTRACTS_PATH)
    cert["status"] = cert.status.map(icon)
    cert["owner"] = cert.table_name.map(lambda t: contracts[t]["owner"])
    cert["steward"] = cert.table_name.map(lambda t: contracts[t]["steward"])
    cert["classification"] = cert.table_name.map(lambda t: contracts[t]["classification"])
    left, right = st.columns([3, 2])
    with left:
        st.markdown("**Table certification**")
        st.dataframe(cert, hide_index=True, width="stretch")
        st.markdown("**Open issues**")
        issues = dq[~dq.passed][["table_name", "check_name", "severity", "failed_rows", "steward"]]
        if issues.empty:
            st.success("No failing checks.")
        else:
            st.dataframe(issues, hide_index=True, width="stretch")
    with right:
        st.markdown("**Quarantine by reason**")
        rej = q("SELECT reject_reason AS reason, count(*) AS rows FROM silver.shipment_rejects GROUP BY 1 ORDER BY 2")
        fig = px.bar(rej, x="rows", y="reason", orientation="h", color_discrete_sequence=[SERIES[0]], text="rows")
        fig.update_traces(textposition="outside", cliponaxis=False)
        fig = style(fig, 260)
        fig.update_layout(hovermode="closest")
        st.plotly_chart(fig, width="stretch")

    st.markdown("**Lineage**")
    st.graphviz_chart("""
digraph {
  rankdir=LR; node [shape=box, style="rounded", fontname="Helvetica", fontsize=11];
  subgraph cluster_src { label="Sources"; style=dashed; tms [label="TMS export"]; crm [label="CRM export"]; cm [label="Carrier master"]; nm [label="Network master"]; }
  subgraph cluster_b { label="Bronze (raw, as landed)"; style=dashed; b [label="bronze.*"]; }
  subgraph cluster_s { label="Silver (typed, deduped)"; style=dashed; s [label="silver.shipments"]; r [label="silver.shipment_rejects"]; sd [label="silver dims"]; }
  subgraph cluster_g { label="Gold (star schema)"; style=dashed; f [label="fact_shipment"]; d [label="dim_customer (PII masked)\\ndim_carrier · dim_lane\\ndim_facility · dim_date"]; risk [label="shipment_risk"]; }
  q [label="Quality gate\\ncontracts.yml", shape=diamond];
  sem [label="Semantic layer\\nmetrics.yml"];
  app [label="Dashboards · Ad hoc · AI"];
  tms -> b; crm -> b; cm -> b; nm -> b; b -> s; b -> r; b -> sd; s -> f; sd -> d; f -> q; d -> q; q -> sem; f -> risk; sem -> app; risk -> app;
}""")

    with st.expander("Data contracts (governance/contracts.yml)"):
        for table, spec in contracts.items():
            st.markdown(f"**{table}**: {spec['description']}  \nGrain: `{spec['grain']}` · Owner: {spec['owner']} · "
                        f"Steward: {spec['steward']} · Classification: **{spec['classification']}**")
            st.dataframe(pd.DataFrame([{"column": c, **v} for c, v in spec["columns"].items()]),
                         hide_index=True, width="stretch")

# ---------- Metric catalog ----------
with tabs[5]:
    st.markdown("Every number on every page compiles from these definitions. Change a definition once, "
                "and it changes everywhere, with an owner accountable for it.")
    cat = sl.catalog()
    cat["Target"] = [fmt(n, t) if pd.notna(t) else "" for n, t in zip(cat.Name, cat.Target)]
    st.dataframe(cat, hide_index=True, width="stretch")
    st.markdown("**Dimensions available for slicing**")
    st.write(", ".join(d["label"] for d in sl.dimensions.values()))

# ---------- Operating model ----------
with tabs[6]:
    st.markdown((config.ROOT / "docs" / "operating-model.md").read_text())
