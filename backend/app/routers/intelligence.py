from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.security import require_permissions
from app.services.intelligence_service import (
    customer_360,
    geo_analytics,
    feature_explanation,
    intelligence_snapshot,
    layer_status,
    recommendation_insight,
)
from app.services.retail_intelligence_service import (
    basket_analysis,
    churn_risk,
    customer_behavior,
    demand_forecast,
    review_intelligence,
)

router = APIRouter()


class FeatureAttributionRequest(BaseModel):
    customer_id: str = Field(min_length=3, max_length=80)
    segment: str = Field(min_length=1, max_length=120)
    recent_categories: list[str] = Field(default_factory=list)


@router.get("/snapshot")
def snapshot(_: dict = Depends(require_permissions({"intelligence:read"}))) -> dict:
    return intelligence_snapshot()


@router.get("/layers/status")
def layers(_: dict = Depends(require_permissions({"intelligence:read"}))) -> dict:
    return layer_status()


@router.get("/customer360")
def customer360(_: dict = Depends(require_permissions({"intelligence:read"}))) -> dict:
    return customer_360()


@router.get("/geo")
def geo(_: dict = Depends(require_permissions({"intelligence:read"}))) -> dict:
    return geo_analytics()


@router.get("/explainability")
def explainability(_: dict = Depends(require_permissions({"intelligence:read"}))) -> dict:
    try:
        return feature_explanation()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/explainability")
def explainability_for_customer(
    payload: FeatureAttributionRequest,
    _: dict = Depends(require_permissions({"intelligence:read"})),
) -> dict:
    try:
        return feature_explanation(
            customer_id=payload.customer_id,
            segment=payload.segment,
            recent_categories=payload.recent_categories,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/recommendation-insight")
def recommendations(_: dict = Depends(require_permissions({"intelligence:read"}))) -> dict:
    return recommendation_insight()


@router.get("/customers/{customer_id}/behavior")
def behavior(customer_id: str, _: dict = Depends(require_permissions({"intelligence:read"}))) -> dict:
    return customer_behavior(customer_id)


@router.get("/customers/{customer_id}/churn-risk")
def churn(customer_id: str, _: dict = Depends(require_permissions({"intelligence:read"}))) -> dict:
    return churn_risk(customer_id)


@router.get("/basket-analysis")
def baskets(_: dict = Depends(require_permissions({"intelligence:read"}))) -> dict:
    return basket_analysis()


@router.get("/demand-forecast")
def demand(product_id: str | None = None, periods: int = 7, _: dict = Depends(require_permissions({"intelligence:read"}))) -> dict:
    return demand_forecast(product_id=product_id, periods=periods)


@router.get("/review-intelligence")
def reviews(product_id: str | None = None, _: dict = Depends(require_permissions({"intelligence:read"}))) -> dict:
    return review_intelligence(product_id=product_id)
