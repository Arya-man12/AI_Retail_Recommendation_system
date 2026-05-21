from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.security import require_permissions
from app.services.feature_store_service import (
    FeatureStoreError,
    feature_store_status,
    get_customer_features,
    seed_demo_features,
    set_customer_features,
)

router = APIRouter()


class FeatureWriteRequest(BaseModel):
    features: dict[str, Any] = Field(default_factory=dict)


@router.get("/status")
def status() -> dict:
    return feature_store_status()


@router.post("/seed")
def seed() -> dict:
    try:
        return seed_demo_features()
    except FeatureStoreError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Unable to seed Redis feature store: {exc}") from exc


@router.get("/customers/{customer_id}")
def customer_features(customer_id: str, _: dict = Depends(require_permissions({"features:read"}))) -> dict:
    try:
        return get_customer_features(customer_id)
    except FeatureStoreError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.put("/customers/{customer_id}")
def write_customer_features(
    customer_id: str,
    payload: FeatureWriteRequest,
    _: dict = Depends(require_permissions({"features:write"})),
) -> dict:
    try:
        return set_customer_features(customer_id, payload.features)
    except FeatureStoreError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Unable to write Redis feature store: {exc}") from exc
