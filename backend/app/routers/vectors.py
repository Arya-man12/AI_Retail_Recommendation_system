from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.security import require_permissions
from app.services.vector_service import (
    VectorServiceError,
    ensure_product_collection,
    search_similar_customers,
    search_similar_products,
    seed_all_embeddings,
    seed_customer_embeddings,
    seed_product_embeddings,
    semantic_search,
    vector_store_status,
)

router = APIRouter()


class SimilarityRequest(BaseModel):
    query: str = Field(min_length=2, max_length=400)
    limit: int = Field(default=5, ge=1, le=20)
    entity_type: str | None = Field(default=None, pattern="^(product|customer)$")


@router.get("/status")
def status(_: dict = Depends(require_permissions({"vectors:read"}))) -> dict:
    try:
        return vector_store_status()
    except VectorServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/products/collection")
def create_product_collection(_: dict = Depends(require_permissions({"vectors:write"}))) -> dict:
    try:
        return ensure_product_collection()
    except VectorServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/products/seed")
def seed_products(_: dict = Depends(require_permissions({"vectors:write"}))) -> dict:
    try:
        return seed_product_embeddings()
    except VectorServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/customers/seed")
def seed_customers(_: dict = Depends(require_permissions({"vectors:write"}))) -> dict:
    try:
        return seed_customer_embeddings()
    except VectorServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/seed")
def seed_everything(_: dict = Depends(require_permissions({"vectors:write"}))) -> dict:
    try:
        return seed_all_embeddings()
    except VectorServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/similar-products")
def similar_products(payload: SimilarityRequest, _: dict = Depends(require_permissions({"vectors:read"}))) -> dict:
    try:
        return search_similar_products(query=payload.query, limit=payload.limit)
    except VectorServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/similar-customers")
def similar_customers(payload: SimilarityRequest, _: dict = Depends(require_permissions({"vectors:read"}))) -> dict:
    try:
        return search_similar_customers(query=payload.query, limit=payload.limit)
    except VectorServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/semantic-search")
def search_semantic_index(payload: SimilarityRequest, _: dict = Depends(require_permissions({"vectors:read"}))) -> dict:
    try:
        return semantic_search(query=payload.query, limit=payload.limit, entity_type=payload.entity_type)
    except VectorServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
