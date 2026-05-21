from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.security import require_permissions
from app.services.ecommerce_service import list_products, place_order, seed_product_catalog

router = APIRouter()


class OrderRequest(BaseModel):
    customer_id: str = Field(default="customer-demo-001", min_length=3, max_length=80)
    product_id: str
    quantity: int = Field(default=1, ge=1, le=10)


@router.get("/products")
def products(_: dict = Depends(require_permissions({"ecommerce:read"}))) -> dict:
    return list_products()


@router.post("/orders")
def orders(payload: OrderRequest, _: dict = Depends(require_permissions({"ecommerce:write"}))) -> dict:
    try:
        return place_order(
            customer_id=payload.customer_id,
            product_id=payload.product_id,
            quantity=payload.quantity,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/products/seed")
def seed_products(_: dict = Depends(require_permissions({"ecommerce:write"}))) -> dict:
    return seed_product_catalog()
