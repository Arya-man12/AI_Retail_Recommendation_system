import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import auth, copilot, dashboard, ecommerce, features, graph, intelligence, ml, processing, streaming
from app.services.auth_service import auth_status, seed_bootstrap_users
from app.services.feature_store_service import feature_store_status
from app.services.graph_service import graph_status
from app.services.mongo_demo_service import seed_dashboard_demo_data
from app.services.streaming_service import start_subscriber_if_enabled, stop_subscriber

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:5173"],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard.router, prefix="/api", tags=["dashboard"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(copilot.router, prefix="/api/copilot", tags=["copilot"])
app.include_router(ml.router, prefix="/api/ml", tags=["ml"])
app.include_router(processing.router, prefix="/api/processing", tags=["processing"])
app.include_router(ecommerce.router, prefix="/api/ecommerce", tags=["ecommerce"])
app.include_router(streaming.router, prefix="/api/streaming", tags=["streaming"])
app.include_router(intelligence.router, prefix="/api/intelligence", tags=["intelligence"])
app.include_router(features.router, prefix="/api/features", tags=["features"])
app.include_router(graph.router, prefix="/api/graph", tags=["graph"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@app.get("/ready")
def ready() -> dict:
    dependencies = {
        "auth": auth_status(),
        "redis": feature_store_status(),
        "customer_graph": graph_status(),
    }
    ready_status = all(
        dependency.get("connected", False)
        for dependency in dependencies.values()
        if dependency.get("provider") in {"mongodb", "redis", "mongodb_graph"}
    )
    return {
        "status": "ready" if ready_status else "degraded",
        "service": settings.app_name,
        "dependencies": dependencies,
    }


@app.on_event("startup")
def startup() -> None:
    threading.Thread(target=_seed_startup_data, name="startup-demo-seed", daemon=True).start()


@app.on_event("shutdown")
def shutdown() -> None:
    stop_subscriber()


def _seed_startup_data() -> None:
    seed_bootstrap_users()
    seed_dashboard_demo_data()
    start_subscriber_if_enabled()
