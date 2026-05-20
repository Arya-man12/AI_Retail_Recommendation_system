import hashlib
import math

from qdrant_client import QdrantClient

from app.config import settings


DEMO_PRODUCTS = [
    {"id": "sku-hydration", "name": "Smart Hydration Bundle", "text": "wellness fitness hydration bottle sensor"},
    {"id": "sku-air", "name": "Air Quality Monitor Pro", "text": "smart home air quality wellness monitor"},
    {"id": "sku-power", "name": "Compact Power Kit", "text": "commuter travel battery charger compact"},
    {"id": "sku-sleep", "name": "Sleep Recovery Sensor", "text": "sleep recovery wellness sensor bedroom"},
]


def _embedding(text: str, dimensions: int = 32) -> list[float]:
    vector = [0.0] * dimensions
    for token in text.lower().split():
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = digest[0] % dimensions
        vector[index] += 1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def _cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def get_qdrant_client() -> QdrantClient:
    return QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)


def vector_store_status() -> dict:
    try:
        client = get_qdrant_client()
        collections = client.get_collections()
        names = [collection.name for collection in collections.collections]
        connected = True
    except Exception as exc:
        names = []
        connected = False
        error = str(exc)
    else:
        error = None

    return {
        "provider": "qdrant",
        "url": settings.qdrant_url,
        "collection": settings.qdrant_collection,
        "connected": connected,
        "collections": names,
        "error": error,
        "fallback": "in_memory_hash_embeddings",
    }


def search_similar_products(query: str, limit: int = 5) -> dict:
    query_vector = _embedding(query)
    scored = []
    for product in DEMO_PRODUCTS:
        score = _cosine(query_vector, _embedding(product["text"]))
        scored.append({"id": product["id"], "name": product["name"], "score": round(score, 3)})

    return {
        "collection": settings.qdrant_collection,
        "source": "qdrant_ready_fallback",
        "matches": sorted(scored, key=lambda item: item["score"], reverse=True)[:limit],
    }

