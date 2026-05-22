import json
from functools import lru_cache
from typing import Any

from app.config import settings
from app.services.auth_service import get_mongo_client


DEMO_FEATURES = {
    "cust-maya-chen": {
        "recency_days": 14,
        "frequency": 9,
        "monetary_value": 18420.0,
        "discount_sensitivity": 0.22,
        "bundle_affinity": 0.86,
        "churn_risk": 0.08,
    },
    "cust-urban-commuter": {
        "recency_days": 22,
        "frequency": 6,
        "monetary_value": 8600.0,
        "discount_sensitivity": 0.35,
        "bundle_affinity": 0.62,
        "churn_risk": 0.18,
    },
    "cust-winback": {
        "recency_days": 118,
        "frequency": 2,
        "monetary_value": 4200.0,
        "discount_sensitivity": 0.71,
        "bundle_affinity": 0.44,
        "churn_risk": 0.72,
    },
}


class FeatureStoreError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def get_redis_client():
    try:
        import redis
    except Exception as exc:
        raise FeatureStoreError(f"Redis client is not available: {exc}") from exc

    return redis.Redis.from_url(
        settings.redis_url,
        socket_timeout=settings.redis_socket_timeout_seconds,
        decode_responses=True,
    )


def feature_key(customer_id: str) -> str:
    return f"{settings.redis_feature_prefix}:customer:{customer_id}"


def feature_store_status() -> dict:
    try:
        client = get_redis_client()
        ping = client.ping()
    except Exception as exc:
        return {
            "provider": "redis",
            "configured": bool(settings.redis_url),
            "connected": False,
            "url": settings.redis_url,
            "prefix": settings.redis_feature_prefix,
            "error": str(exc),
            "fallback": "demo_features",
        }

    return {
        "provider": "redis",
        "configured": True,
        "connected": bool(ping),
        "url": settings.redis_url,
        "prefix": settings.redis_feature_prefix,
    }


def seed_demo_features() -> dict:
    client = get_redis_client()
    written = 0
    for customer_id, features in DEMO_FEATURES.items():
        client.set(feature_key(customer_id), json.dumps(features))
        written += 1
    return {
        "provider": "redis",
        "prefix": settings.redis_feature_prefix,
        "written": written,
    }


def set_customer_features(customer_id: str, features: dict[str, Any]) -> dict:
    client = get_redis_client()
    normalized = _normalize_features(features)
    client.set(feature_key(customer_id), json.dumps(normalized))
    return {
        "customer_id": customer_id,
        "features": normalized,
        "source": "redis",
    }


def get_customer_features(customer_id: str) -> dict:
    mongo_payload = _get_mongo_customer_features(customer_id)
    if mongo_payload:
        return mongo_payload

    try:
        client = get_redis_client()
        raw = client.get(feature_key(customer_id))
    except Exception as exc:
        fallback = DEMO_FEATURES.get(customer_id, DEMO_FEATURES["cust-maya-chen"])
        return {
            "customer_id": customer_id,
            "features": fallback,
            "source": "demo_features",
            "error": str(exc),
        }

    if not raw:
        fallback = DEMO_FEATURES.get(customer_id)
        return {
            "customer_id": customer_id,
            "features": fallback or {},
            "source": "demo_features" if fallback else "redis_miss",
        }

    try:
        features = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise FeatureStoreError(f"Stored feature payload for '{customer_id}' is not valid JSON") from exc

    return {
        "customer_id": customer_id,
        "features": features,
        "source": "redis",
    }


def _get_mongo_customer_features(customer_id: str) -> dict | None:
    try:
        db = get_mongo_client()[settings.mongodb_database]
        document = db.customer_features.find_one({"customer_id": customer_id}, {"_id": False})
    except Exception:
        return None

    if not document:
        return None

    return {
        "customer_id": customer_id,
        "features": document.get("features") or {},
        "source": "mongodb",
    }


def _normalize_features(features: dict[str, Any]) -> dict[str, float | str | int | bool]:
    normalized = {}
    for key, value in features.items():
        if isinstance(value, (str, bool, int, float)):
            normalized[key] = value
    return normalized
