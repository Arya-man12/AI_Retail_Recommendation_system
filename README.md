# Real-Time Customer Intelligence Platform

This repository is being built from the frontend inward, matching the requested architecture:

1. Vite dashboard
2. FastAPI backend
3. Controlled LLM orchestration with LangChain and LangSmith tracing
4. ML, feature, vector, graph, geo, streaming, and simulator layers

The current implementation is the first working vertical slice: a Vite frontend wired to a FastAPI API contract with realistic mock data and LangSmith-ready backend tracing.

The backend now also includes:

- MLflow tracking configuration and prototype model run logging
- A policy guardrails service for LLM/copilot prompts and RBAC checks
- Qdrant client configuration with an in-memory fallback similarity search
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
POST /api/ml/recommendations
POST /api/ml/segments
GET  /api/vectors/status
POST /api/vectors/similar-products
POST /api/copilot/ask
```

## Model Status

The current ML models are baseline prototypes:

- `baseline_revenue_forecaster`: moving-average trend forecast
- `baseline_product_recommender`: content/category affinity recommender
- `baseline_customer_segmenter`: RFM-style rule segmenter

They are wired through MLflow so each call logs a run. The next step is to replace these baselines with trained models such as ALS, Prophet/LSTM, KMeans, and BERT sentiment.
