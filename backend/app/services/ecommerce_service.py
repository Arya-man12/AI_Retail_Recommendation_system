from datetime import UTC, datetime
from functools import lru_cache
from uuid import uuid4

from app.config import settings
from app.services.emqx_service import publish_event
from app.services.auth_service import get_mongo_client
from app.services.insight_engine import process_event
from app.services.ml_service import recommend_products


SHOP_PRODUCTS = [
    {
        "id": "sku-hydration",
        "name": "Smart Hydration Bundle",
        "category": "wellness",
        "price": 49.99,
        "description": "Connected bottle, filter set, and hydration reminders.",
        "accent": "#0f766e",
    },
    {
        "id": "sku-air",
        "name": "Air Quality Monitor Pro",
        "category": "smart home",
        "price": 129.0,
        "description": "Room-level air quality readings with trend alerts.",
        "accent": "#2563eb",
    },
    {
        "id": "sku-power",
        "name": "Compact Power Kit",
        "category": "commuter",
        "price": 79.0,
        "description": "Slim battery, fast charger, and cable organizer.",
        "accent": "#db2777",
    },
    {
        "id": "sku-sleep",
        "name": "Sleep Recovery Sensor",
        "category": "wellness",
        "price": 99.0,
        "description": "Bedside sensor for rest, recovery, and sleep quality.",
        "accent": "#7c3aed",
    },
    {
        "id": "sku-focus-lamp",
        "name": "Adaptive Focus Lamp",
        "category": "smart home",
        "price": 89.0,
        "description": "Desk lighting that shifts color temperature through the day.",
        "accent": "#f59e0b",
    },
    {
        "id": "sku-commuter-pack",
        "name": "Weatherproof Commuter Pack",
        "category": "commuter",
        "price": 118.0,
        "description": "Slim daily backpack with laptop, cable, and bottle storage.",
        "accent": "#334155",
    },
    {
        "id": "sku-recovery-band",
        "name": "Recovery Mobility Band Set",
        "category": "wellness",
        "price": 34.0,
        "description": "Resistance bands and guided recovery routines for travel days.",
        "accent": "#16a34a",
    },
    {
        "id": "sku-desk-hub",
        "name": "Modular Desk Hub",
        "category": "productivity",
        "price": 149.0,
        "description": "USB-C hub, charging dock, and desktop organizer in one unit.",
        "accent": "#0891b2",
    },
    {
        "id": "sku-travel-filter",
        "name": "Portable Water Filter",
        "category": "travel",
        "price": 42.0,
        "description": "Compact purifier bottle attachment for trips and commutes.",
        "accent": "#0284c7",
    },
    {
        "id": "sku-air-mini",
        "name": "Air Quality Monitor Mini",
        "category": "smart home",
        "price": 69.0,
        "description": "Small-space air sensor with app alerts and room history.",
        "accent": "#4f46e5",
    },
    {
        "id": "sku-cable-roll",
        "name": "Tech Cable Roll",
        "category": "commuter",
        "price": 29.0,
        "description": "Organized roll pouch for chargers, adapters, and earbuds.",
        "accent": "#be123c",
    },
    {
        "id": "sku-mindful-kit",
        "name": "Mindful Break Kit",
        "category": "wellness",
        "price": 58.0,
        "description": "Timer, scent tabs, and desk cards for short reset routines.",
        "accent": "#9333ea",
    },
    {
        "id": "sku-ergonomic-stand",
        "name": "Foldable Ergonomic Stand",
        "category": "productivity",
        "price": 64.0,
        "description": "Portable laptop stand with angle markers and cable channel.",
        "accent": "#0d9488",
    },
    {
        "id": "sku-cold-brew",
        "name": "Smart Cold Brew Tumbler",
        "category": "travel",
        "price": 54.0,
        "description": "Insulated tumbler with brew basket and temperature indicator.",
        "accent": "#92400e",
    },
    {
        "id": "sku-sunrise-clock",
        "name": "Sunrise Routine Clock",
        "category": "smart home",
        "price": 76.0,
        "description": "Gentle wake lighting, soundscapes, and sleep wind-down modes.",
        "accent": "#ea580c",
    },
    {
        "id": "sku-fitness-scale",
        "name": "Connected Fitness Scale",
        "category": "wellness",
        "price": 88.0,
        "description": "Household health metrics with privacy-first profile controls.",
        "accent": "#2563eb",
    },
]


def list_products() -> dict:
    products, source = _products_from_mongo()
    return {"products": products, "count": len(products), "source": source}


def place_order(customer_id: str, product_id: str, quantity: int) -> dict:
    product = _find_product(product_id)
    order_id = f"ord-{uuid4().hex[:10]}"
    event = {
        "event_id": f"evt-{uuid4().hex[:12]}",
        "event_type": "purchase",
        "order_id": order_id,
        "customer_id": customer_id,
        "product_id": product["id"],
        "product_name": product["name"],
        "category": product["category"],
        "quantity": quantity,
        "price": product["price"],
        "revenue": round(product["price"] * quantity, 2),
        "event_time": datetime.now(UTC).isoformat(),
    }

    ecommerce_publish = publish_event(settings.emqx_ecommerce_topic, event)
    purchase_publish = publish_event(settings.emqx_purchase_topic, event)
    mongo_write = _store_order(event, product)
    local_insight = None
    if settings.enable_local_event_mirror:
        local_insight = process_event(event, source="local_dev_shop")
    recommendations = recommend_products(
        customer_id=customer_id,
        segment="High-LTV wellness buyer" if product["category"] == "wellness" else "Active shopper",
        recent_categories=[product["category"]],
    )
    filtered_recommendations = [
        item for item in recommendations["recommendations"] if item["product"] != product["name"]
    ][:3]

    return {
        "order": {
            "order_id": order_id,
            "customer_id": customer_id,
            "product": product,
            "quantity": quantity,
            "total": event["revenue"],
        },
        "recommendations": filtered_recommendations,
        "emqx": {
            "ecommerce": ecommerce_publish,
            "purchase": purchase_publish,
        },
        "mongodb": mongo_write,
        "insight_engine": {
            "local_mirror_enabled": settings.enable_local_event_mirror,
            "local_result": local_insight,
        },
    }


def seed_product_catalog() -> dict:
    try:
        collection = _products_collection()
        collection.create_index("id", unique=True)
        for product in SHOP_PRODUCTS:
            collection.update_one(
                {"id": product["id"]},
                {
                    "$setOnInsert": {
                        **product,
                        "active": True,
                        "created_at": datetime.now(UTC),
                    },
                    "$set": {"updated_at": datetime.now(UTC)},
                },
                upsert=True,
            )
    except Exception as exc:
        return {
            "provider": "mongodb",
            "seeded": False,
            "count": len(SHOP_PRODUCTS),
            "error": str(exc),
            "fallback": "in_memory_catalog",
        }

    return {
        "provider": "mongodb",
        "seeded": True,
        "count": len(SHOP_PRODUCTS),
        "database": settings.mongodb_database,
        "collection": "products",
    }


@lru_cache(maxsize=1)
def _ensure_product_catalog_seeded() -> bool:
    return seed_product_catalog().get("seeded", False)


def _find_product(product_id: str) -> dict:
    products, _ = _products_from_mongo()
    for product in products:
        if product["id"] == product_id:
            return product
    raise ValueError(f"Unknown product_id '{product_id}'")


def _products_from_mongo() -> tuple[list[dict], str]:
    try:
        _ensure_product_catalog_seeded()
        products = list(
            _products_collection().find(
                {"active": {"$ne": False}},
                {"_id": False, "created_at": False, "updated_at": False},
            ).sort("name", 1)
        )
        if products:
            return products, "mongodb"
    except Exception:
        pass
    return SHOP_PRODUCTS, "in_memory_catalog"


def _store_order(event: dict, product: dict) -> dict:
    order = {
        **event,
        "product": product,
        "created_at": datetime.now(UTC),
    }
    try:
        db = get_mongo_client()[settings.mongodb_database]
        db.orders.create_index("order_id", unique=True)
        db.orders.insert_one(order)
    except Exception as exc:
        return {
            "stored": False,
            "database": settings.mongodb_database,
            "collection": "orders",
            "error": str(exc),
        }
    return {
        "stored": True,
        "database": settings.mongodb_database,
        "collection": "orders",
    }


def _products_collection():
    return get_mongo_client()[settings.mongodb_database].products
