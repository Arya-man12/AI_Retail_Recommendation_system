from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import copilot, dashboard, ml, vectors

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard.router, prefix="/api", tags=["dashboard"])
app.include_router(copilot.router, prefix="/api/copilot", tags=["copilot"])
app.include_router(ml.router, prefix="/api/ml", tags=["ml"])
app.include_router(vectors.router, prefix="/api/vectors", tags=["vectors"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}
