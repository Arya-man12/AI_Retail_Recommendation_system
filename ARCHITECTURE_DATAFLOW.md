# Architecture / Data Flow Diagram (Text)

This system is a customer-intelligence API that wires together:
- **MongoDB** (orders, browse events, customer features, and a generated customer graph)
- **EMQX** (MQTT broker for ecommerce/purchase events)
- **Streaming / Insight Engine** (in-memory real-time insights)
- **MLflow** (tracking of ML model experiments/metrics)
- **Transparent recommendation scoring** (local product scoring with explainability drivers)
- **Frontend** (calls API endpoints)

---

## Legend
- `->` = data flow
- `[API]` = HTTP endpoint / FastAPI route
- `[Service]` = backend logic module
- `(DB)` = persistence / external service

---

## 1) Order / Purchase Event Flow (MongoDB Graph + EMQX + Insights)

### A. User places an order in the frontend

`[Frontend] -> [API: POST /api/ecommerce/...place_order (router)]`

### B. Backend creates an event payload
In `backend/app/services/ecommerce_service.py`:
- builds an `event` dict with:
  - `event_type='purchase'`
  - `customer_id`, `product_id`, `product_name`, `category`
  - `quantity`, `price`, `revenue`
  - `order_id`, `event_time`, `event_id`

### C. Publish to EMQX (optional integration)
In `place_order()`:
- `[Service: emqx_service.publish_event] -> (EMQX MQTT broker)`
  - publishes JSON to:
    - topic: `customer-intelligence/ecommerce/events`
    - topic: `customer-intelligence/purchase/events`

> Repo setting: `enable_emqx_subscriber = False` by default, so the backend usually **does not** consume MQTT live.

### D. Local mirror into Insight Engine (used when subscriber is off)
In `place_order()`:
- if `enable_local_event_mirror=True`:
  - `[Service: insight_engine.process_event]`
  - updates in-memory deques:
    - `_events`, `_insights`

### E. Persist order to MongoDB + update customer features
In `ecommerce_service._store_order()`:
- `[Service] -> (MongoDB)` writes:
  - `orders` collection (order + pipeline)
  - `ecommerce_events` collection (event + pipeline)
- `[Service] -> (MongoDB)` updates:
  - `customer_features` with computed values:
    - `recency_days`, `frequency`, `monetary_value`, `preferred_category`, `engagement_depth`

### F. Update MongoDB “customer graph edges” (incremental graph)
Also in `place_order()`:
- computes churn via `[Service: ml_service.predict_churn_risk]`
- calls `[Service: graph_service.sync_purchase_to_graph]`
- that performs an upsert into:
  - `customer_graph_edges` with `relationship='PURCHASED'`
  - stores `target=<product_id>`, quantity, revenue, churn_percent, etc.

---

## 2) Browsing Event Flow (Graph edges + derived graph)

When a browse/view event exists (analogous logic):
- `[Service: graph_service.sync_browse_to_graph]`
  - writes/upserts to `(MongoDB) customer_graph_edges` with `relationship='VIEWED'`

Then the graph is served by reading:
- `orders` (purchases)
- `browse_events` (views)
- `customer_graph_edges` (extra/derived edges)
- `customer_features` (profile/churn)

---

## 3) How the “MongoDB Graph” response is generated

### A. Frontend requests the graph / dashboard
- `[Frontend] -> [API: GET /api/graph/... (or dashboard)]`

### B. GraphService builds a JSON graph model
In `backend/app/services/graph_service.py`:

1. Try dynamic build from MongoDB:
   - `_customer_graph_from_mongo(customer_id)`
   - reads from:
     - `orders`
     - `browse_events`
     - `customer_graph_edges`
     - `customer_features`

2. Construct:
   - `graph.nodes`:
     - customer node
     - product nodes
     - optional segment/category nodes (`PREFERS`)
   - `graph.edges`:
     - `PURCHASED` edges from orders
     - `VIEWED` edges from browse_events
     - `PREFERS` edges derived from top categories
     - plus positioning metadata

3. If no edges exist:
   - fall back to `(MongoDB) customer_graph_snapshots`

4. If snapshot missing:
   - use hardcoded demo fallback graph

---

## 4) Live EMQX Subscriber Flow (optional)
If enabled (`enable_emqx_subscriber=True`):

`[API: POST /api/streaming/...start_subscriber (implicitly at startup)]`

In `backend/app/services/streaming_service.py`:
- connects to EMQX via MQTT
- subscribes to both topics
- on each message:
  - decode payload
  - `[Service: insight_engine.process_event]`
  - buffers events + insights in memory

Endpoints:
- `GET /api/streaming/emqx/status` (status)
- `POST /api/streaming/emqx/drain` (drains buffered events)
- `GET /api/streaming/insights` (live insights snapshot)

---

## 5) Recommendation + Explainability Flow

In `backend/app/services/ml_service.py`:
- `recommend_products()` scores each product with transparent components:
  - base product fit
  - recent category match
  - customer segment fit
  - product keyword match
  - optional win-back/sleep boost

The recommendation response includes `drivers` for each product. In
`backend/app/services/intelligence_service.py`, `feature_explanation()` combines
those recommendation drivers with customer features such as:
- bundle affinity / engagement depth
- purchase frequency
- discount sensitivity
- churn risk

This produces real, per-customer feature attribution without requiring an external vector database.

---

## 6) MLflow Flow (experiment tracking)

In `backend/app/services/mlflow_service.py` + `ml_service.py`:
- `mlflow.set_tracking_uri(settings.mlflow_tracking_uri)`
- experiment name: `customer-intelligence-baselines`
- within `ml_service.py` each model run uses:
  - `tracked_run(<run_name>, tags=...)`
  - `mlflow.log_param(...)`
  - `mlflow.log_metric(...)`

Where it lands:
- local filesystem `backend/mlruns/...` (your `mlruns` folder)

> MLflow is purely tracking experiments; the production serving graph/recommendation path does not read MLflow outputs.

---

## End-to-End Summary (One-liner)
**Frontend order -> EMQX publish + local insight mirror + MongoDB writes + MongoDB graph edges -> GraphService builds graph JSON -> transparent recommender scores products -> explainability reads the score drivers -> Frontend renders it; MLflow logs experiments separately.**

---

## Quick Mermaid Diagram (optional)
Copy/paste into a Mermaid renderer:

```mermaid
flowchart TD
  UI[Frontend] -->|place order| API[Ecommerce API / ecommerce_service]

  API -->|publish JSON| EMQX[(EMQX MQTT Broker)]
  API -->|local mirror| INS[Insight Engine (in-memory)]

  API -->|insert order/event| M[MongoDB: orders + ecommerce_events]
  API -->|update features| M2[MongoDB: customer_features]
  API -->|upsert edge| G[MongoDB: customer_graph_edges]

  UI -->|request graph/dashboard| GRAPHA[Graph Service]
  GRAPHA -->|read orders/views/edges/features| M
  GRAPHA -->|fallback to snapshot| SNAP[MongoDB: customer_graph_snapshots]
  GRAPHA -->|or demo fallback| DEMO[Hardcoded demo graph]

  UI -->|request recommendations| REC[ML Service: transparent scoring]
  REC -->|product score drivers| EXP[Feature Attribution]

  ML[ML Models] -->|metrics/params| MLFLOW[(MLflow mlruns folder)]
```

