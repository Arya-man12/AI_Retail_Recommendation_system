from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from itertools import combinations

from app.config import settings
from app.services.auth_service import get_mongo_client
from app.services.ecommerce_service import SHOP_PRODUCTS
from app.services.feature_store_service import get_customer_features
from app.services.graph_service import sync_browse_to_graph
from app.services.ml_service import forecast_product_demand, predict_churn_risk, score_review_sentiment


DEMO_REVIEWS = [
    {
        "review_id": "rev-hydration-001",
        "product_id": "sku-hydration",
        "customer_id": "cust-maya-chen",
        "rating": 5,
        "text": "Great quality and useful hydration reminders. I love the bundle.",
    },
    {
        "review_id": "rev-air-001",
        "product_id": "sku-air",
        "customer_id": "customer-demo-001",
        "rating": 4,
        "text": "Excellent monitor, setup was easy and the alerts are useful.",
    },
    {
        "review_id": "rev-power-001",
        "product_id": "sku-power",
        "customer_id": "cust-urban-commuter",
        "rating": 3,
        "text": "Good battery but delivery was late and the cable had an issue.",
    },
]


def seed_review_demo_data() -> dict:
    now = datetime.now(UTC)
    try:
        db = _db()
        db.product_reviews.create_index("review_id", unique=True)
        for review in DEMO_REVIEWS:
            sentiment = score_review_sentiment(review["text"])
            db.product_reviews.update_one(
                {"review_id": review["review_id"]},
                {
                    "$setOnInsert": {
                        **review,
                        "sentiment": sentiment,
                        "created_at": now,
                    },
                    "$set": {"updated_at": now},
                },
                upsert=True,
            )
    except Exception as exc:
        return {"provider": "mongodb", "seeded": False, "collection": "product_reviews", "error": str(exc)}

    return {"provider": "mongodb", "seeded": True, "collection": "product_reviews", "count": len(DEMO_REVIEWS)}


def record_browse_event(customer_id: str, product_id: str, dwell_seconds: int = 8) -> dict:
    product = _product_by_id(product_id)
    event = {
        "event_id": f"browse-{customer_id}-{product_id}-{datetime.now(UTC).timestamp()}",
        "event_type": "product_view",
        "customer_id": customer_id,
        "product_id": product_id,
        "product_name": product.get("name"),
        "category": product.get("category"),
        "dwell_seconds": dwell_seconds,
        "event_time": datetime.now(UTC).isoformat(),
        "created_at": datetime.now(UTC),
    }
    try:
        db = _db()
        db.browse_events.insert_one(event)
        _update_customer_features(customer_id)
        graph_status = sync_browse_to_graph(event)
    except Exception as exc:
        return {"stored": False, "event": event, "error": str(exc)}
    return {
        "stored": True,
        "event": {key: value for key, value in event.items() if key != "created_at"},
        "customer_graph": graph_status,
    }


def customer_behavior(customer_id: str) -> dict:
    orders = _orders(customer_id=customer_id)
    views = _browse_events(customer_id=customer_id)
    categories = Counter(order.get("category") for order in orders if order.get("category"))
    categories.update(view.get("category") for view in views if view.get("category"))
    product_counts = Counter(order.get("product_id") for order in orders if order.get("product_id"))
    revenue = sum(float(order.get("revenue", 0)) for order in orders)
    last_purchase = _latest_time([order.get("created_at") or order.get("event_time") for order in orders])
    recency_days = _days_since(last_purchase)

    return {
        "customer_id": customer_id,
        "orders": len(orders),
        "browse_events": len(views),
        "purchase_frequency": len(orders),
        "monetary_value": round(revenue, 2),
        "recency_days": recency_days,
        "preferred_categories": _top_items(categories),
        "top_products": _top_items(product_counts),
        "behavior_segment": _behavior_segment(categories, len(orders), recency_days),
        "source": "mongodb" if orders or views else "demo_or_empty",
    }


def churn_risk(customer_id: str) -> dict:
    behavior = customer_behavior(customer_id)
    feature_payload = get_customer_features(customer_id)
    features = {
        **(feature_payload.get("features") or {}),
        "recency_days": behavior["recency_days"],
        "frequency": behavior["purchase_frequency"] or (feature_payload.get("features") or {}).get("frequency", 1),
        "monetary_value": behavior["monetary_value"] or (feature_payload.get("features") or {}).get("monetary_value", 0),
        "engagement_depth": min((behavior["browse_events"] + behavior["orders"]) / 12, 1),
    }
    prediction = predict_churn_risk(features)
    return {
        "customer_id": customer_id,
        "churn": prediction,
        "behavior": behavior,
        "feature_source": feature_payload.get("source"),
    }


def basket_analysis(limit: int = 10) -> dict:
    grouped = defaultdict(set)
    for order in _orders():
        customer_id = order.get("customer_id")
        product_id = order.get("product_id")
        if customer_id and product_id:
            grouped[customer_id].add(product_id)

    pair_counts = Counter()
    product_counts = Counter()
    for basket in grouped.values():
        product_counts.update(basket)
        for left, right in combinations(sorted(basket), 2):
            pair_counts[(left, right)] += 1

    total_baskets = max(len(grouped), 1)
    pairs = []
    for (left, right), count in pair_counts.most_common(limit):
        support = count / total_baskets
        confidence = count / max(product_counts[left], 1)
        expected = (product_counts[left] / total_baskets) * (product_counts[right] / total_baskets)
        lift = support / expected if expected else 0
        pairs.append(
            {
                "products": [_product_name(left), _product_name(right)],
                "product_ids": [left, right],
                "support": round(support, 3),
                "confidence": round(confidence, 3),
                "lift": round(lift, 3),
                "basket_count": count,
            }
        )

    return {
        "model": "basket_affinity_rules",
        "basket_count": len(grouped),
        "pairs": pairs,
        "source": "mongodb_orders",
    }


def demand_forecast(product_id: str | None = None, periods: int = 7) -> dict:
    orders = _orders(product_id=product_id)
    grouped = defaultdict(int)
    for order in orders:
        product = order.get("product_id")
        timestamp = order.get("created_at") or order.get("event_time")
        day = _coerce_datetime(timestamp).date().isoformat() if timestamp else datetime.now(UTC).date().isoformat()
        grouped[(product, day)] += int(order.get("quantity", 1))

    forecasts = []
    product_ids = {product_id} if product_id else {key[0] for key in grouped if key[0]}
    for current_product_id in sorted(product_ids):
        history = [
            {"date": day, "quantity": quantity}
            for (history_product_id, day), quantity in sorted(grouped.items())
            if history_product_id == current_product_id
        ]
        forecasts.append(
            {
                "product_id": current_product_id,
                "product": _product_name(current_product_id),
                **forecast_product_demand(history, periods=periods),
            }
        )

    return {"source": "mongodb_orders", "forecasts": forecasts}


def review_intelligence(product_id: str | None = None) -> dict:
    reviews = _reviews(product_id=product_id)
    enriched = []
    counts = Counter()
    for review in reviews:
        sentiment = review.get("sentiment") or score_review_sentiment(review.get("text", ""))
        counts[sentiment["label"]] += 1
        enriched.append(
            {
                "review_id": review.get("review_id"),
                "product_id": review.get("product_id"),
                "product": _product_name(review.get("product_id")),
                "rating": review.get("rating"),
                "sentiment": sentiment,
                "text": review.get("text"),
            }
        )

    total = max(len(enriched), 1)
    return {
        "model": "lexicon_review_sentiment",
        "review_count": len(enriched),
        "sentiment_mix": {label: round(count / total, 3) for label, count in counts.items()},
        "reviews": enriched[:20],
        "source": "mongodb_reviews" if reviews else "demo_or_empty",
    }


def _update_customer_features(customer_id: str) -> None:
    behavior = customer_behavior(customer_id)
    db = _db()
    db.customer_features.update_one(
        {"customer_id": customer_id},
        {
            "$set": {
                "customer_id": customer_id,
                "features": {
                    "recency_days": behavior["recency_days"],
                    "frequency": behavior["purchase_frequency"],
                    "monetary_value": behavior["monetary_value"],
                    "engagement_depth": min((behavior["browse_events"] + behavior["orders"]) / 12, 1),
                },
                "updated_at": datetime.now(UTC),
            }
        },
        upsert=True,
    )


def _orders(customer_id: str | None = None, product_id: str | None = None) -> list[dict]:
    query = {}
    if customer_id:
        query["customer_id"] = customer_id
    if product_id:
        query["product_id"] = product_id
    try:
        return list(_db().orders.find(query, {"_id": False}).sort("created_at", -1))
    except Exception:
        return []


def _browse_events(customer_id: str | None = None) -> list[dict]:
    query = {"customer_id": customer_id} if customer_id else {}
    try:
        return list(_db().browse_events.find(query, {"_id": False}).sort("created_at", -1))
    except Exception:
        return []


def _reviews(product_id: str | None = None) -> list[dict]:
    query = {"product_id": product_id} if product_id else {}
    try:
        return list(_db().product_reviews.find(query, {"_id": False}).sort("created_at", -1))
    except Exception:
        return DEMO_REVIEWS


def _product_by_id(product_id: str) -> dict:
    try:
        product = _db().products.find_one({"id": product_id}, {"_id": False})
        if product:
            return product
    except Exception:
        pass
    return next((product for product in SHOP_PRODUCTS if product["id"] == product_id), {"id": product_id, "name": product_id})


def _product_name(product_id: str | None) -> str:
    if not product_id:
        return "Unknown product"
    return _product_by_id(product_id).get("name", product_id)


def _top_items(counter: Counter, limit: int = 3) -> list[dict]:
    return [{"name": name, "count": count} for name, count in counter.most_common(limit) if name]


def _behavior_segment(categories: Counter, order_count: int, recency_days: int) -> str:
    if order_count >= 5 and recency_days <= 30:
        return "loyal_active_buyer"
    if categories:
        return f"{categories.most_common(1)[0][0]}_affinity"
    if recency_days >= 90:
        return "winback_risk"
    return "emerging_customer"


def _latest_time(values: list) -> datetime | None:
    parsed = [_coerce_datetime(value) for value in values if value]
    parsed = [value for value in parsed if value]
    return max(parsed) if parsed else None


def _days_since(value: datetime | None) -> int:
    if not value:
        return 90
    return max(0, (datetime.now(UTC) - value).days)


def _coerce_datetime(value) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _db():
    return get_mongo_client()[settings.mongodb_database]
