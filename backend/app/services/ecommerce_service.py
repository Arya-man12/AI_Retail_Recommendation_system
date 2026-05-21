from datetime import UTC, datetime
from functools import lru_cache
from uuid import uuid4

from app.config import settings
from app.services.emqx_service import publish_event
from app.services.auth_service import get_mongo_client
from app.services.graph_service import sync_purchase_to_graph
from app.services.insight_engine import process_event
from app.services.ml_service import predict_churn_risk, recommend_products


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

ORDER_FALLBACK: list[dict] = []

DEMO_ORDER_IDS = ("demo-ord-hydration", "demo-ord-air", "demo-ord-power")


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
    emqx_status = {
        "ecommerce": ecommerce_publish,
        "purchase": purchase_publish,
    }
    insight_status = {
        "local_mirror_enabled": settings.enable_local_event_mirror,
        "local_result": local_insight,
    }
    churn_prediction = predict_churn_risk(
        {
            "recency_days": 0,
            "frequency": 1,
            "monetary_value": event["revenue"],
            "discount_sensitivity": 0.3,
            "engagement_depth": 0.35,
        }
    )
    graph_sync = sync_purchase_to_graph(event, product, churn=churn_prediction)
    mongo_write = _store_order(
        event=event,
        product=product,
        recommendations=filtered_recommendations,
        emqx_status=emqx_status,
        insight_status=insight_status,
        graph_status=graph_sync,
        churn_prediction=churn_prediction,
    )

    return {
        "order": {
            "order_id": order_id,
            "customer_id": customer_id,
            "product": product,
            "quantity": quantity,
            "total": event["revenue"],
        },
        "recommendations": filtered_recommendations,
        "emqx": emqx_status,
        "mongodb": mongo_write,
        "customer_graph": graph_sync,
        "churn": churn_prediction,
        "insight_engine": insight_status,
    }


def list_customer_orders(customer_id: str) -> dict:
    try:
        db = get_mongo_client()[settings.mongodb_database]
        orders = list(
            db.orders.find(
                {"customer_id": customer_id},
                {"_id": False},
            ).sort("created_at", -1)
        )
        return {
            "orders": orders,
            "count": len(orders),
            "customer_id": customer_id,
            "source": "mongodb",
        }
    except Exception as exc:
        orders = [order for order in ORDER_FALLBACK if order["customer_id"] == customer_id]
        return {
            "orders": orders,
            "count": len(orders),
            "customer_id": customer_id,
            "source": "in_memory_fallback",
            "warning": str(exc),
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


def seed_ecommerce_demo_data() -> dict:
    products = seed_product_catalog()
    orders = seed_demo_orders()
    return {
        "products": products,
        "orders": orders,
    }


def seed_demo_orders() -> dict:
    now = datetime.now(UTC)
    demo_specs = [
        ("demo-ord-hydration", "customer-demo-001", "sku-hydration", 1),
        ("demo-ord-air", "customer-demo-001", "sku-air", 1),
        ("demo-ord-power", "cust-urban-commuter", "sku-power", 2),
    ]
    demo_orders = []
    for order_id, customer_id, product_id, quantity in demo_specs:
        product = _find_product(product_id)
        event = {
            "event_id": f"demo-evt-{product_id}",
            "event_type": "purchase",
            "order_id": order_id,
            "customer_id": customer_id,
            "product_id": product["id"],
            "product_name": product["name"],
            "category": product["category"],
            "quantity": quantity,
            "price": product["price"],
            "revenue": round(product["price"] * quantity, 2),
            "event_time": now.isoformat(),
        }
        demo_orders.append(
            {
                **event,
                "product": product,
                "recommendations": recommend_products(
                    customer_id=customer_id,
                    segment="High-LTV wellness buyer" if product["category"] == "wellness" else "Active shopper",
                    recent_categories=[product["category"]],
                )["recommendations"],
                "pipeline": {
                    "seeded": True,
                    "source": "startup_demo_seed",
                },
                "created_at": now,
                "updated_at": now,
            }
        )

    try:
        db = get_mongo_client()[settings.mongodb_database]
        db.orders.create_index("order_id", unique=True)
        db.ecommerce_events.create_index("event_id", unique=True)
        for order in demo_orders:
            db.orders.update_one(
                {"order_id": order["order_id"]},
                {"$setOnInsert": order, "$set": {"updated_at": now}},
                upsert=True,
            )
            db.ecommerce_events.update_one(
                {"event_id": order["event_id"]},
                {"$setOnInsert": order, "$set": {"updated_at": now}},
                upsert=True,
            )
    except Exception as exc:
        return {
            "provider": "mongodb",
            "seeded": False,
            "collection": "orders",
            "error": str(exc),
        }

    return {
        "provider": "mongodb",
        "seeded": True,
        "collection": "orders",
        "count": len(demo_orders),
        "order_ids": list(DEMO_ORDER_IDS),
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


def _store_order(
    event: dict,
    product: dict,
    recommendations: list[dict],
    emqx_status: dict,
    insight_status: dict,
    graph_status: dict,
    churn_prediction: dict,
) -> dict:
    now = datetime.now(UTC)
    order = {
        **event,
        "product": product,
        "recommendations": recommendations,
        "pipeline": {
            "emqx": emqx_status,
            "insight_engine": insight_status,
            "recommendations": recommendations,
            "customer_graph": graph_status,
            "churn": churn_prediction,
        },
        "created_at": now,
        "updated_at": now,
    }
    try:
        db = get_mongo_client()[settings.mongodb_database]
        db.orders.create_index("order_id", unique=True)
        db.ecommerce_events.create_index("event_id", unique=True)
        db.orders.insert_one(order)
        db.ecommerce_events.insert_one(
            {
                **event,
                "pipeline": order["pipeline"],
                "created_at": now,
            }
        )
        feature_update = _update_customer_feature_document(db, event["customer_id"])
    except Exception as exc:
        _store_order_fallback(order)
        return {
            "stored": False,
            "database": settings.mongodb_database,
            "collections": ["orders", "ecommerce_events"],
            "error": str(exc),
            "fallback": "in_memory_orders",
        }
    return {
        "stored": True,
        "database": settings.mongodb_database,
        "collections": ["orders", "ecommerce_events"],
        "feature_update": feature_update,
    }


def _products_collection():
    return get_mongo_client()[settings.mongodb_database].products


def _store_order_fallback(order: dict) -> None:
    ORDER_FALLBACK.insert(0, order)
    del ORDER_FALLBACK[50:]


def _update_customer_feature_document(db, customer_id: str) -> dict:
    orders = list(db.orders.find({"customer_id": customer_id}, {"_id": False}))
    if not orders:
        return {"updated": False, "reason": "no_orders"}
    revenue = sum(float(order.get("revenue", 0)) for order in orders)
    categories = {}
    latest = None
    for order in orders:
        category = order.get("category")
        if category:
            categories[category] = categories.get(category, 0) + 1
        created_at = order.get("created_at")
        created_at = _aware_datetime(created_at)
        if created_at and (latest is None or created_at > latest):
            latest = created_at
    recency_days = max(0, (datetime.now(UTC) - latest).days) if latest else 90
    preferred_category = max(categories, key=categories.get) if categories else "unknown"
    db.customer_features.update_one(
        {"customer_id": customer_id},
        {
            "$set": {
                "customer_id": customer_id,
                "features": {
                    "recency_days": recency_days,
                    "frequency": len(orders),
                    "monetary_value": round(revenue, 2),
                    "preferred_category": preferred_category,
                    "engagement_depth": min(len(orders) / 12, 1),
                },
                "updated_at": datetime.now(UTC),
            }
        },
        upsert=True,
    )
    return {"updated": True, "collection": "customer_features"}


def _aware_datetime(value) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)
