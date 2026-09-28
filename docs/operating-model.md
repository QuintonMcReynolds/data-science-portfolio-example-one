## Data & Analytics Operating Model

How I would run a 25–30 person Data Analytics & BI organization at a transportation and logistics company. This project is the working prototype of the platform; this page covers the people, process, and money around it.

### 1. Strategy on a page

| | |
|---|---|
| **Vision** | Every operating and commercial decision is made on one trusted set of numbers, and the most important ones are anticipated, not reported. |
| **Business outcomes** | +2 pts OTIF · +1.5 pts gross margin via lane pricing · –20% analyst time spent reconciling numbers · exec decisions on certified data only |
| **Platform bets** | Cloud lakehouse (Snowflake or Fabric) · medallion layers · one semantic layer · data contracts with owners · CI/CD for data |
| **Operating bets** | Product teams aligned to business domains · single intake and WSJF prioritization · quarterly roadmap reviewed with the executive team |

### 2. First 90 days

| Days | Focus | Deliverables |
|---|---|---|
| **1–30 · Listen** | 1:1s with every direct report and each executive stakeholder. Inventory reports, pipelines, licenses, contracts, and spend. | Current-state assessment · top-10 "numbers that don't match" list · skills map |
| **31–60 · Decide** | Pick the target architecture and operating model. Stand up intake and a governance council. | Target-state architecture · 4-quarter roadmap · KPI dictionary v1 (the 10 metrics in this app) |
| **61–90 · Deliver** | Ship one visible win on certified data. Start retiring duplicate reports. | Executive scorecard on the governed layer · first certified domain (Shipments) · budget re-plan |

### 3. Organization (≈28 FTE)

```
VP, Data Analytics & BI
├── Director, Data Platform & Engineering (10)
│   ├── Data Engineering: ingestion & pipelines (5)
│   ├── Analytics Engineering: models & semantic layer (3)
│   └── Platform / DataOps: CI/CD, cost, reliability (2)
├── Director, Business Intelligence & Analytics (11)
│   ├── Operations & Network pod (4)       ← SVP Operations
│   ├── Commercial & Pricing pod (4)       ← CCO
│   └── Finance & Executive Reporting (3)  ← CFO
├── Manager, Data Science & AI (4)
└── Manager, Data Governance & Quality (3): stewards, MDM, catalog
```

Pods are aligned to the executive who owns the outcome, so the roadmap is argued in business terms, not ticket counts.

### 4. Demand intake & prioritization

1. **One front door.** Every request comes through a single intake form: problem, decision it supports, sponsor, deadline, value estimate.
2. **Triage weekly.** Break-fix goes to the run team, questions answerable by self-service go to enablement, and everything else is scored.
3. **Score with WSJF.** (Business value + time criticality + risk reduction) ÷ effort. Scores are visible to everyone.
4. **Commit quarterly, plan in 2-week sprints.** The executive steering group approves the quarter's top items. Capacity is split roughly 60% roadmap, 25% run and maintenance, 15% tech debt.
5. **Measure outcomes.** Every shipped product states the metric it should move, and we check it 60 days later.

### 5. Governance (RACI)

| Activity | VP D&A | Data Eng | BI | Governance | Business steward | IT Security |
|---|---|---|---|---|---|---|
| Define KPI (metrics.yml) | A | C | R | C | R | – |
| Data contract & checks | A | R | C | R | C | I |
| PII classification & masking | A | R | I | R | C | C |
| Certify a dataset | I | R | C | A | R | – |
| Access & retention policy | A | C | I | R | C | R |

### 6. Annual budget (illustrative, ≈$6.2M)

| Line | $ | Notes |
|---|---|---|
| Personnel (28 FTE, loaded) | 4.40M | 71% of spend |
| Cloud platform (compute + storage) | 0.75M | FinOps target: –15% via auto-suspend, clustering, and workload tagging |
| BI & tooling licenses | 0.35M | Consolidate to one BI tool; retire duplicate seats |
| Consulting / contractors | 0.40M | Migration surge only; shrinks in year 2 |
| Training & certification | 0.12M | Every engineer gets one platform certification per year |
| Travel, events, contingency | 0.18M | |

### 7. How the D&A org itself is measured

| Metric | Target |
|---|---|
| Certified-table coverage of executive KPIs | 100% by end of Q3 |
| Pipeline success rate / data freshness SLA met | ≥ 99% |
| Lead time from approved request to production | ≤ 3 sprints |
| Weekly active BI users ÷ licensed users | ≥ 60% |
| Stakeholder NPS (quarterly survey) | ≥ +30 |
| Reports retired vs. created | ≥ 1 : 1 in year 1 |

### 8. Responsible AI principles

- Explainability over marginal accuracy when an operator acts on the output.
- No PII in features unless there is a documented need and approval from Privacy.
- Every model ships with a model card, a time-based validation, a monitoring threshold, and a named owner.
- A person decides. Models rank the work; they don't close it.
