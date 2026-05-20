from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.vector_service import search_similar_products, vector_store_status

router = APIRouter()


class SimilarityRequest(BaseModel):
    query: str = Field(min_length=2, max_length=400)
    limit: int = Field(default=5, ge=1, le=20)


@router.get("/status")
def status() -> dict:
    return vector_store_status()


@router.post("/similar-products")
def similar_products(payload: SimilarityRequest) -> dict:
    return search_similar_products(query=payload.query, limit=payload.limit)

