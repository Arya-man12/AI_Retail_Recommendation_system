from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.security import require_permissions
from app.services.ml_service import (
    forecast_revenue,
    forecast_revenue_with_prophet,
    get_model_registry_status,
    recommend_products,
    segment_customer,
)
from app.services.feature_store_service import get_customer_features

router = APIRouter()


class ForecastRequest(BaseModel):
    recent_revenue: list[float] = Field(min_length=3, max_length=30)


class ProphetPoint(BaseModel):
    ds: str
    y: float


class ProphetForecastRequest(BaseModel):
    history: list[ProphetPoint] = Field(min_length=3, max_length=500)
    periods: int = Field(default=7, ge=1, le=90)
    frequency: str = Field(default="D", min_length=1, max_length=12)


class RecommendationRequest(BaseModel):
    customer_id: str
    segment: str
    recent_categories: list[str] = Field(default_factory=list)


class SegmentationRequest(BaseModel):
    recency_days: int
    frequency: int
    monetary_value: float


@router.get("/registry")
def registry_status(_: dict = Depends(require_permissions({"ml:read"}))) -> dict:
    return get_model_registry_status()


@router.post("/forecast")
def forecast(payload: ForecastRequest, _: dict = Depends(require_permissions({"ml:read"}))) -> dict:
    return forecast_revenue(payload.recent_revenue)


@router.post("/forecast/prophet")
def prophet_forecast(payload: ProphetForecastRequest, _: dict = Depends(require_permissions({"ml:read"}))) -> dict:
    try:
        return forecast_revenue_with_prophet(
            history=[point.model_dump() for point in payload.history],
            periods=payload.periods,
            frequency=payload.frequency,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/recommendations")
def recommendations(payload: RecommendationRequest, _: dict = Depends(require_permissions({"ml:read"}))) -> dict:
    return recommend_products(
        customer_id=payload.customer_id,
        segment=payload.segment,
        recent_categories=payload.recent_categories,
    )


@router.post("/segments")
def segments(payload: SegmentationRequest, _: dict = Depends(require_permissions({"ml:read"}))) -> dict:
    return segment_customer(
        recency_days=payload.recency_days,
        frequency=payload.frequency,
        monetary_value=payload.monetary_value,
    )


@router.post("/segments/from-features/{customer_id}")
def segments_from_features(customer_id: str, _: dict = Depends(require_permissions({"ml:read"}))) -> dict:
    feature_payload = get_customer_features(customer_id)
    features = feature_payload.get("features") or {}
    return {
        "feature_store": feature_payload,
        "segment": segment_customer(
            recency_days=int(features.get("recency_days", 30)),
            frequency=int(features.get("frequency", 1)),
            monetary_value=float(features.get("monetary_value", 0.0)),
        ),
    }
