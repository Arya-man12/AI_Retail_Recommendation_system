from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.ml_service import (
    forecast_revenue,
    get_model_registry_status,
    recommend_products,
    segment_customer,
)

router = APIRouter()


class ForecastRequest(BaseModel):
    recent_revenue: list[float] = Field(min_length=3, max_length=30)


class RecommendationRequest(BaseModel):
    customer_id: str
    segment: str
    recent_categories: list[str] = Field(default_factory=list)


class SegmentationRequest(BaseModel):
    recency_days: int
    frequency: int
    monetary_value: float


@router.get("/registry")
def registry_status() -> dict:
    return get_model_registry_status()


@router.post("/forecast")
def forecast(payload: ForecastRequest) -> dict:
    return forecast_revenue(payload.recent_revenue)


@router.post("/recommendations")
def recommendations(payload: RecommendationRequest) -> dict:
    return recommend_products(
        customer_id=payload.customer_id,
        segment=payload.segment,
        recent_categories=payload.recent_categories,
    )


@router.post("/segments")
def segments(payload: SegmentationRequest) -> dict:
    return segment_customer(
        recency_days=payload.recency_days,
        frequency=payload.frequency,
        monetary_value=payload.monetary_value,
    )

