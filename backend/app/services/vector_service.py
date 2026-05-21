from functools import lru_cache
from uuid import uuid5, NAMESPACE_URL

from qdrant_client import QdrantClient, models

from app.config import settings


DEMO_PRODUCTS = [
    {
        "id": "sku-hydration",
        "name": "Smart Hydration Bundle",
        "text": "wellness fitness hydration bottle sensor premium replenishment",
        "category": "wellness",
    },
    {
        "id": "sku-air",
        "name": "Air Quality Monitor Pro",
        "text": "smart home air quality wellness monitor premium home",
        "category": "smart_home",
    },
    {
        "id": "sku-power",
        "name": "Compact Power Kit",
        "text": "commuter travel battery charger compact urban mobility",
        "category": "commuter",
    },
    {
        "id": "sku-sleep",
        "name": "Sleep Recovery Sensor",
        "text": "sleep recovery wellness sensor bedroom health",
        "category": "wellness",
    },
]

DEMO_CUSTOMERS = [
    {
        "id": "cust-maya-chen",
        "name": "Maya Chen",
        "segment": "high_ltv_wellness",
        "text": "high ltv wellness buyer hydration smart home active northeast low churn premium bundles",
        "region": "Northeast",
        "ltv": 18420,
    },
    {
        "id": "cust-urban-commuter",
        "name": "Urban commuter cohort",
        "segment": "loyal_growth",
        "text": "urban commuter travel power kit battery accessories repeat buyer mobile workday",
        "region": "West",
        "ltv": 8600,
    },
    {
        "id": "cust-home-premium",
        "name": "Premium home accounts",
        "segment": "premium_home",
        "text": "premium smart home air quality monitor family wellness campaign responsive",
        "region": "South",
        "ltv": 12650,
    },
    {
        "id": "cust-winback",
        "name": "Dormant wellness buyers",
        "segment": "winback_risk",
        "text": "inactive wellness buyer previous sleep recovery sensor high recency churn risk winback",
        "region": "Midwest",
        "ltv": 4200,
    },
]


class VectorServiceError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def get_embedding_model():
    try:
        from sentence_transformers import SentenceTransformer
    except Exception as exc:
        raise VectorServiceError(f"Sentence Transformers is not available: {exc}") from exc

    try:
        return SentenceTransformer(settings.embedding_model_name)
    except Exception as exc:
        raise VectorServiceError(
            f"Unable to load embedding model '{settings.embedding_model_name}': {exc}"
        ) from exc


def embed_text(text: str) -> list[float]:
    model = get_embedding_model()
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()


def get_qdrant_client() -> QdrantClient:
    return QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)


def vector_store_status() -> dict:
    try:
        client = get_qdrant_client()
        collections = client.get_collections()
        names = [collection.name for collection in collections.collections]
    except Exception as exc:
        raise VectorServiceError(f"Unable to connect to Qdrant at {settings.qdrant_url}: {exc}") from exc

    return {
        "provider": "qdrant",
        "url": settings.qdrant_url,
        "collection": settings.qdrant_collection,
        "connected": True,
        "collections": names,
        "embedding_model": settings.embedding_model_name,
    }


def ensure_product_collection() -> dict:
    return ensure_collection()


def ensure_collection() -> dict:
    client = get_qdrant_client()
    vector_size = len(embed_text("dimension probe"))

    try:
        exists = client.collection_exists(settings.qdrant_collection)
        if not exists:
            client.create_collection(
                collection_name=settings.qdrant_collection,
                vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
            )
    except Exception as exc:
        raise VectorServiceError(f"Unable to create or inspect Qdrant collection: {exc}") from exc

    return {
        "collection": settings.qdrant_collection,
        "vector_size": vector_size,
        "distance": "cosine",
        "status": "ready",
    }


def seed_product_embeddings() -> dict:
    ensure_collection()
    client = get_qdrant_client()
    points = []
    for product in DEMO_PRODUCTS:
        points.append(
            models.PointStruct(
                id=_point_id("product", product["id"]),
                vector=embed_text(product["text"]),
                payload={
                    "entity_type": "product",
                    "product_id": product["id"],
                    "name": product["name"],
                    "text": product["text"],
                    "category": product["category"],
                },
            )
        )

    try:
        client.upsert(collection_name=settings.qdrant_collection, points=points)
    except Exception as exc:
        raise VectorServiceError(f"Unable to upsert product embeddings into Qdrant: {exc}") from exc

    return {
        "collection": settings.qdrant_collection,
        "embedding_model": settings.embedding_model_name,
        "upserted": len(points),
    }


def seed_customer_embeddings() -> dict:
    ensure_collection()
    client = get_qdrant_client()
    points = []
    for customer in DEMO_CUSTOMERS:
        points.append(
            models.PointStruct(
                id=_point_id("customer", customer["id"]),
                vector=embed_text(customer["text"]),
                payload={
                    "entity_type": "customer",
                    "customer_id": customer["id"],
                    "name": customer["name"],
                    "segment": customer["segment"],
                    "region": customer["region"],
                    "ltv": customer["ltv"],
                    "text": customer["text"],
                },
            )
        )

    try:
        client.upsert(collection_name=settings.qdrant_collection, points=points)
    except Exception as exc:
        raise VectorServiceError(f"Unable to upsert customer embeddings into Qdrant: {exc}") from exc

    return {
        "collection": settings.qdrant_collection,
        "embedding_model": settings.embedding_model_name,
        "upserted": len(points),
    }


def seed_all_embeddings() -> dict:
    products = seed_product_embeddings()
    customers = seed_customer_embeddings()
    return {
        "collection": settings.qdrant_collection,
        "embedding_model": settings.embedding_model_name,
        "upserted": products["upserted"] + customers["upserted"],
        "entities": {
            "products": products["upserted"],
            "customers": customers["upserted"],
        },
    }


def search_similar_products(query: str, limit: int = 5) -> dict:
    return semantic_search(query=query, limit=limit, entity_type="product")


def search_similar_customers(query: str, limit: int = 5) -> dict:
    return semantic_search(query=query, limit=limit, entity_type="customer")


def semantic_search(query: str, limit: int = 5, entity_type: str | None = None) -> dict:
    client = get_qdrant_client()
    query_vector = embed_text(query)
    query_filter = None
    if entity_type:
        query_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="entity_type",
                    match=models.MatchValue(value=entity_type),
                )
            ]
        )

    try:
        response = client.query_points(
            collection_name=settings.qdrant_collection,
            query=query_vector,
            limit=limit,
            with_payload=True,
            query_filter=query_filter,
        )
    except Exception as exc:
        raise VectorServiceError(
            f"Unable to search Qdrant collection '{settings.qdrant_collection}'. "
            "Make sure Qdrant is running and product embeddings have been seeded. "
            f"Details: {exc}"
        ) from exc

    matches = []
    for point in response.points:
        payload = point.payload or {}
        matches.append(_match_from_point(point.id, point.score, payload))

    return {
        "collection": settings.qdrant_collection,
        "embedding_model": settings.embedding_model_name,
        "source": "qdrant",
        "entity_type": entity_type or "all",
        "matches": matches,
    }


def _point_id(entity_type: str, raw_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"{entity_type}:{raw_id}"))


def _match_from_point(point_id: str, score: float, payload: dict) -> dict:
    entity_type = payload.get("entity_type", "product")
    if entity_type == "customer":
        return {
            "id": payload.get("customer_id", str(point_id)),
            "entity_type": "customer",
            "name": payload.get("name", "Unknown customer"),
            "segment": payload.get("segment"),
            "region": payload.get("region"),
            "ltv": payload.get("ltv"),
            "score": round(float(score), 4),
        }

    return {
        "id": payload.get("product_id", str(point_id)),
        "entity_type": "product",
        "name": payload.get("name", "Unknown product"),
        "category": payload.get("category"),
        "score": round(float(score), 4),
    }
