# 🚚 Data Science Portfolio Example One: Enterprise Freight Analytics Platform

This project is a small, working version of the data and analytics platform a VP of Data Analytics & BI builds at a transportation and logistics company. The pieces are the ones that job needs: a layered enterprise data warehouse, data contracts with a quality gate, a governed semantic layer, executive BI, an explainable AI model, and a written operating model for the team that runs it.

It runs on a laptop in about two seconds. Each local component maps one-to-one to its enterprise equivalent (see [Architecture](#architecture)).

## The business problem

A 20-terminal freight network moves about 60,000 shipments a year across TL, LTL, and intermodal, using 14 carriers and 180 customers. Leadership has three questions:

1. **Service:** Where and why are we missing on-time and OTIF, and which loads in transit right now are about to be late?
2. **Profitability:** Which lanes and carriers are eroding margin, and where should we reprice or re-source?
3. **Trust:** Can the executive team rely on these numbers, and who is accountable when they're wrong?

## What's in the app

| Tab | What it answers |
|---|---|
| 📊 **Executive scorecard** | 7 KPIs vs. target and vs. the prior period, trend by mode, auto-generated call-outs |
| 🗺️ **Network & lanes** | US lane map colored by margin vs. target; lanes to reprice and lanes to protect |
| 🚛 **Carriers** | Service vs. claims quadrant; a full carrier scorecard for quarterly business reviews |
| 🤖 **Delivery risk (AI)** | In-transit loads ranked by predicted late risk, top risk drivers, and a model card |
| 🛡️ **Data trust** | Table certification, open data-quality issues, quarantine reasons, lineage, and data contracts |
| 📚 **Metric catalog** | Every KPI's definition, SQL, target, and owner, from a single source |
| 🧭 **Operating model** | A 90-day plan, org design for about 28 FTE, intake and WSJF prioritization, RACI, budget, and D&A org KPIs |

Turn on **Show governed SQL** in the sidebar to see the exact SQL the semantic layer compiled for each view.

## Architecture

```
 Sources           Bronze              Silver                        Gold                    Consumption
 ─────────         ──────────          ──────────────────            ───────────────         ─────────────────
 TMS export   ─┐                       typed, deduped (latest wins)  fact_shipment           Semantic layer
 CRM export   ─┼─► raw, all-text  ─►   quarantine w/ reason     ─►   dim_customer (PII ▒)  ─► (metrics.yml)  ─► Dashboards
 Carrier mstr ─┤   + lineage cols      load audit                    dim_carrier/lane/date        │              Ad hoc SQL
 Network mstr ─┘                                                     shipment_risk ◄── ML         ▼
                                                    Quality gate (contracts.yml) ── blocks certification on error
```

| Here | Enterprise equivalent |
|---|---|
| DuckDB with `bronze` / `silver` / `gold` schemas | Snowflake, Microsoft Fabric Lakehouse, or Databricks medallion architecture |
| `sql/*.sql` layer scripts | dbt models / Fabric notebooks, orchestrated by ADF or Airflow |
| `governance/contracts.yml` + `quality.py` | dbt tests, Great Expectations, Purview / Unity Catalog, data contracts |
| `semantic/metrics.yml` + `semantic.py` | Power BI semantic model, dbt Semantic Layer, or Snowflake semantic views |
| Streamlit app | Power BI / Tableau executive workspace |
| `risk.py` (logistic regression + model card) | Azure ML / Databricks MLflow with a model registry |
| GitHub Actions CI | Azure DevOps / GitHub CI/CD for data (DataOps) |

## Design decisions

- **Quarantine, don't drop.** Bad rows land in `silver.shipment_rejects` with a reason, so stewards can fix the source instead of losing revenue silently.
- **One definition per KPI.** Dashboards can't write their own SQL for "on-time %". The semantic layer only accepts catalog names and binds filter values as parameters.
- **A quality gate with teeth.** An error-severity failure stops the build. Warnings go to the named steward (for example, a fat-fingered rate entry).
- **PII masked by default.** Customer contact email is clear-text only in the restricted silver layer.
- **Explainable AI.** The late-risk model is logistic regression, validated on the most recent 90 days it never saw. It shows its drivers and excludes customer identity.

## Run it

```bash
git clone https://github.com/QuintonMcReynolds/data-science-portfolio-example-one.git
cd data-science-portfolio-example-one
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m lanelens.build      # generate sources → warehouse → quality gate → model
streamlit run app.py
```

The app builds the warehouse on first launch if you skip the build step, so it deploys to Streamlit Community Cloud as-is.

```bash
pytest -q                     # pipeline, governance, semantic-layer, and model tests
```

## Project structure

```
app.py                     Streamlit executive app
lanelens/generate.py       synthetic source extracts, with realistic signal and injected defects
lanelens/warehouse.py      runs the bronze → silver → gold SQL
lanelens/quality.py        executes data contracts and certifies tables
lanelens/semantic.py       compiles governed metrics to parameterized SQL
lanelens/risk.py           late-delivery risk model, holdout validation, scoring
lanelens/build.py          end-to-end build CLI
sql/                       layer SQL (readable on its own)
governance/contracts.yml   owners, stewards, classification, checks
semantic/metrics.yml       KPI catalog
docs/operating-model.md    how the D&A org runs: people, process, budget
```

*All data is synthetic, generated by `lanelens/generate.py`. Company, carrier, and customer names are fictional.*
