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
