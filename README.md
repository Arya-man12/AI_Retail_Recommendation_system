# Real-Time Customer Intelligence Platform

This repository is being built from the frontend inward, matching the requested architecture:

1. Vite dashboard
2. FastAPI backend
3. Controlled LLM orchestration with LangChain and LangSmith tracing
4. ML, feature, vector, graph, geo, streaming, and simulator layers

The current implementation is the first working vertical slice: a Vite frontend wired to a FastAPI API contract with realistic mock data and LangSmith-ready backend tracing.

The backend now also includes:

- PySpark data cleaning/normalization/aggregation endpoints for raw event batches
- EMQX/MQTT ecommerce event publishing hooks
- EMQX/MQTT subscriber hooks for insight detection
- A simple customer-facing ecommerce demo that returns recommendations after purchase
- OpenRouter-hosted NVIDIA Nemotron copilot responses
- MLflow tracking configuration and prototype model run logging
- A policy guardrails service for LLM/copilot prompts and RBAC checks
- Qdrant client configuration for required vector storage and semantic search
- Sentence Transformers embedding generation for Qdrant product search
- Baseline prototype models for forecasting, recommendation, and segmentation

## Project Layout

```text
frontend/   Vite + React dashboard
backend/    FastAPI service with dashboard, ML, graph, geo, and copilot endpoints
```

## Run Locally

Install frontend dependencies:

```bash
cd frontend
npm install
npm run dev
```

Install backend dependencies:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Create `backend/.env` from `backend/.env.example` to enable LangSmith tracing.

Useful backend endpoints:

```text
GET  /api/ml/registry
POST /api/ml/forecast
POST /api/ml/forecast/prophet
POST /api/ml/recommendations
POST /api/ml/segments
GET  /api/vectors/status
POST /api/vectors/products/collection
POST /api/vectors/products/seed
POST /api/vectors/similar-products
POST /api/copilot/ask
GET  /api/processing/spark/status
GET  /api/processing/spark/start-check
GET  /api/processing/sample-events
POST /api/processing/clean-events
GET  /api/ecommerce/products
POST /api/ecommerce/orders
GET  /api/streaming/emqx/status
POST /api/streaming/emqx/drain
GET  /api/streaming/insights
```

## MongoDB RBAC

The backend seeds MongoDB users on startup. For MongoDB Atlas, set `MONGODB_URI` in `backend/.env` to your `mongodb+srv://...` connection string and keep `MONGODB_DATABASE=customer_intelligence` or your chosen database name. If MongoDB is unavailable, those same seed credentials still work through the local bootstrap fallback so demos are not blocked.

Default seeded accounts:

```text
admin@example.com    / ChangeMe123!  / admin
analyst@example.com  / Analyst123!   / marketing_analyst
shopper@example.com  / Shopper123!   / customer
```

The internal dashboard signs in as a dashboard user and sends a bearer token to analytics, intelligence, ML, vector, graph, streaming, and copilot endpoints. The customer-facing shop signs in separately and only receives ecommerce read/write permissions.

## Cloud Databases

This project is configured to use MongoDB Atlas and Neo4j Aura/cloud from `backend/.env`. Docker Compose no longer overrides `MONGODB_URI` or `NEO4J_URI`, so the backend container will honor your cloud connection strings.

Use these URI forms:

```env
MONGODB_URI=mongodb+srv://USER:PASSWORD@CLUSTER.mongodb.net/?retryWrites=true&w=majority
NEO4J_URI=neo4j+s://YOUR-AURA-HOST.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-aura-password
```

Local MongoDB and Neo4j containers are still available only when explicitly requested:

```bash
docker compose --profile local-databases up
```

## Ecommerce Demo

The Vite app includes the internal company dashboard and a lightweight customer-facing shop. The shop calls `POST /api/ecommerce/orders` when a customer buys a product, publishes the purchase event to EMQX over MQTT when configured, and returns similar product recommendations from the recommendation service.

Configure EMQX in `backend/.env`:

```env
EMQX_HOST=localhost
EMQX_PORT=1883
EMQX_ECOMMERCE_TOPIC=customer-intelligence/ecommerce/events
EMQX_PURCHASE_TOPIC=customer-intelligence/purchase/events
ENABLE_EMQX_SUBSCRIBER=true
```

For local demos, `ENABLE_LOCAL_EVENT_MIRROR=true` lets the mock shop also feed the insight engine directly while EMQX is not running. The MQTT path is still present: the shop publishes purchase events to EMQX topics, and the enabled subscriber consumes messages and runs insight detection. Use `/api/streaming/emqx/drain` to inspect messages already received by the subscriber.

## Hosted LLM

The copilot uses OpenRouter for hosted NVIDIA Nemotron inference. The model runs on provider infrastructure, not locally.

Configure the key in `backend/.env`:

```env
OPENROUTER_API_KEY=your-openrouter-key
OPENROUTER_MODEL=nvidia/nemotron-3-super-120b-a12b
```

## Vector Search

Qdrant is required for vector search. The backend does not use local fallback similarity search. Start Qdrant, create the collection, then seed product embeddings:

```bash
curl -X POST http://localhost:8000/api/vectors/products/collection
curl -X POST http://localhost:8000/api/vectors/products/seed
```

The embedding model is configured with `EMBEDDING_MODEL_NAME`. On Windows, Sentence Transformers uses PyTorch and may require the Microsoft Visual C++ Redistributable if `torch` DLL loading fails.

## PySpark Processing

`POST /api/processing/clean-events` accepts raw click, view, cart, and purchase events. It uses PySpark when available and falls back to a matching Python implementation when Spark or Java is unavailable.

PySpark is installed as a backend dependency. For the Spark engine to start, set `JAVA_HOME` to a Spark-supported LTS JDK such as Java 17 or 21 before launching FastAPI.

The cleaning layer performs:

- schema enforcement
- string trimming and lowercasing
- timestamp parsing in UTC
- event type filtering
- negative quantity/price rejection
- revenue derivation for purchases
- coordinate-to-region enrichment
- event count and regional revenue aggregation

## Model Status

The current ML models are baseline prototypes:

- `baseline_revenue_forecaster`: moving-average trend forecast
- `prophet_revenue_forecaster`: Prophet revenue forecast
- `baseline_product_recommender`: content/category affinity recommender
- `baseline_customer_segmenter`: RFM-style rule segmenter

They are wired through MLflow so each call logs a run. The next step is to replace these baselines with trained models such as ALS, Prophet/LSTM, KMeans, and BERT sentiment.
