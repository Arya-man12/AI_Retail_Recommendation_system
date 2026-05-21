from fastapi import APIRouter, Depends

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
    return feature_explanation()


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
