from collections import Counter
from datetime import UTC, datetime

from app.config import settings
from app.services.auth_service import get_mongo_client
from app.services.demo_data import dashboard_payload


class GraphServiceError(RuntimeError):
    pass


def graph_status() -> dict:
    try:
        db = _db()
        db.command("ping")
        orders = db.orders.estimated_document_count()
        views = db.browse_events.estimated_document_count()
    except Exception as exc:
        return {
            "provider": "mongodb_graph",
            "connected": False,
            "database": settings.mongodb_database,
            "error": str(exc),
            "fallback": "demo_customer_360_graph",
        }

    return {
        "provider": "mongodb_graph",
        "connected": True,
        "database": settings.mongodb_database,
        "collections": ["orders", "browse_events", "customer_features", "product_reviews"],
        "orders": orders,
        "browse_events": views,
    }


def seed_demo_graph() -> dict:
    payload = dashboard_payload()
    now = datetime.now(UTC)
    try:
        db = _db()
        db.customer_graph_snapshots.update_one(
            {"customer_id": "cust-maya-chen"},
            {
                "$set": {
                    "customer_id": "cust-maya-chen",
                    "profile": payload["customers"][0],
                    "graph": payload["graph"],
                    "source": "mongodb_seed_snapshot",
                    "updated_at": now,
                }
            },
            upsert=True,
        )
    except Exception as exc:
        raise GraphServiceError(str(exc)) from exc

    return {
        "provider": "mongodb_graph",
        "database": settings.mongodb_database,
        "seeded": True,
        "collection": "customer_graph_snapshots",
    }


def seed_demo_graph_if_configured() -> dict:
    try:
        return seed_demo_graph()
    except Exception as exc:
        return {
            "provider": "mongodb_graph",
            "seeded": False,
            "error": str(exc),
        }


def sync_purchase_to_graph(event: dict, product: dict, churn: dict | None = None) -> dict:
    edge = {
        "customer_id": event["customer_id"],
        "source": event["customer_id"],
        "target": event["product_id"],
        "target_name": event["product_name"],
        "target_kind": "product",
        "relationship": "PURCHASED",
        "category": event.get("category"),
        "order_id": event.get("order_id"),
        "quantity": event.get("quantity"),
        "revenue": event.get("revenue"),
        "event_time": event.get("event_time"),
        "churn_percent": churn.get("percent") if churn else None,
        "updated_at": datetime.now(UTC),
    }
    try:
        db = _db()
        db.customer_graph_edges.update_one(
            {
                "customer_id": edge["customer_id"],
                "target": edge["target"],
                "relationship": edge["relationship"],
                "order_id": edge["order_id"],
            },
            {"$set": edge},
            upsert=True,
        )
    except Exception as exc:
        return {"synced": False, "provider": "mongodb_graph", "error": str(exc)}

    return {"synced": True, "provider": "mongodb_graph", "relationship": "PURCHASED"}


def sync_browse_to_graph(event: dict) -> dict:
    edge = {
        "customer_id": event["customer_id"],
        "source": event["customer_id"],
        "target": event["product_id"],
        "target_name": event.get("product_name"),
        "target_kind": "product",
        "relationship": "VIEWED",
        "category": event.get("category"),
        "dwell_seconds": event.get("dwell_seconds", 0),
        "event_time": event.get("event_time"),
        "updated_at": datetime.now(UTC),
    }
    try:
        db = _db()
        db.customer_graph_edges.update_one(
            {
                "customer_id": edge["customer_id"],
                "target": edge["target"],
                "relationship": edge["relationship"],
            },
            {"$set": edge, "$inc": {"view_count": 1}},
            upsert=True,
        )
    except Exception as exc:
        return {"synced": False, "provider": "mongodb_graph", "error": str(exc)}

    return {"synced": True, "provider": "mongodb_graph", "relationship": "VIEWED"}


def customer_graph(customer_id: str = "cust-maya-chen") -> dict:
    try:
        graph = _customer_graph_from_mongo(customer_id)
        if graph["relationship_count"] > 0:
            return graph
        snapshot = _snapshot(customer_id)
        if snapshot:
            return snapshot
    except Exception as exc:
        return _empty_customer_graph(customer_id, error=str(exc))

    return _empty_customer_graph(customer_id)


def _customer_graph_from_mongo(customer_id: str) -> dict:
    db = _db()
    orders = list(db.orders.find({"customer_id": customer_id}, {"_id": False}).sort("created_at", -1))
    views = list(db.browse_events.find({"customer_id": customer_id}, {"_id": False}).sort("created_at", -1))
    stored_edges = list(db.customer_graph_edges.find({"customer_id": customer_id}, {"_id": False}))
    feature_doc = db.customer_features.find_one({"customer_id": customer_id}, {"_id": False}) or {}
    features = feature_doc.get("features") or {}

    node_map = {
        customer_id: {
            "id": customer_id,
            "label": _short_label(customer_id),
            "kind": "customer",
            "x": 45,
            "y": 44,
        }
    }
    edges = []
    positions = [(16, 22), (73, 21), (22, 73), (75, 72), (54, 18), (84, 52), (30, 84)]
    product_counts = Counter()
    categories = Counter()

    for order in orders:
        product_id = order.get("product_id")
        if not product_id:
            continue
        product_counts[product_id] += int(order.get("quantity", 1))
        categories[order.get("category")] += 1
        _add_product_node(node_map, product_id, order.get("product_name"), order.get("category"), positions)
        edges.append(_edge_payload(edges, "PURCHASED", customer_id, product_id, order.get("revenue")))

    for view in views:
        product_id = view.get("product_id")
        if not product_id:
            continue
        categories[view.get("category")] += 1
        _add_product_node(node_map, product_id, view.get("product_name"), view.get("category"), positions)
        edges.append(_edge_payload(edges, "VIEWED", customer_id, product_id, view.get("dwell_seconds")))

    for stored in stored_edges:
        target = stored.get("target")
        if not target or target in node_map:
            continue
        _add_product_node(node_map, target, stored.get("target_name"), stored.get("category"), positions)

    for category, _ in categories.most_common(3):
        if not category:
            continue
        category_id = f"category-{category}".replace(" ", "-").lower()
        if category_id not in node_map:
            x, y = positions[len(node_map) % len(positions)]
            node_map[category_id] = {
                "id": category_id,
                "label": str(category).split(" ", 1)[0],
                "kind": "segment",
                "x": x,
                "y": y,
            }
        edges.append(_edge_payload(edges, "PREFERS", customer_id, category_id, categories[category]))

    revenue = sum(float(order.get("revenue", 0)) for order in orders)
    churn = features.get("churn_risk")
    if churn is None and features:
        churn = "Calculated"

    return {
        "customer_id": customer_id,
        "profile": {
            "name": _customer_name(customer_id),
            "segment": _segment_label(categories, len(orders)),
            "ltv": _currency(revenue or features.get("monetary_value")),
            "churnRisk": _churn_label(churn),
            "lastEvent": _last_event(orders, views),
            "initials": _initials(_customer_name(customer_id)),
        },
        "graph": {
            "nodes": list(node_map.values()),
            "edges": _position_edges(edges[:14], node_map),
        },
        "relationship_count": len(edges),
        "source": "mongodb_graph",
    }


def _snapshot(customer_id: str) -> dict | None:
    document = _db().customer_graph_snapshots.find_one({"customer_id": customer_id}, {"_id": False})
    if not document:
        return None
    return {
        "customer_id": customer_id,
        "profile": document.get("profile"),
        "graph": document.get("graph"),
        "relationship_count": len((document.get("graph") or {}).get("edges", [])),
        "source": document.get("source", "mongodb_seed_snapshot"),
    }


def _add_product_node(node_map: dict, product_id: str, name: str | None, category: str | None, positions: list[tuple[int, int]]) -> None:
    if product_id in node_map:
        return
    x, y = positions[len(node_map) % len(positions)]
    node_map[product_id] = {
        "id": product_id,
        "label": _short_label(name or product_id),
        "kind": "product",
        "category": category,
        "x": x,
        "y": y,
    }


def _edge_payload(edges: list, relationship: str, source: str, target: str, weight) -> dict:
    return {
        "id": f"edge-{len(edges)}",
        "type": relationship,
        "source": source,
        "target": target,
        "weight": weight,
        "source_position": None,
        "target_position": None,
    }


def _position_edges(edges: list[dict], node_map: dict) -> list[dict]:
    positioned = []
    for edge in edges:
        source = node_map.get(edge["source"])
        target = node_map.get(edge["target"])
        positioned.append(
            {
                **edge,
                "source_position": {"x": source["x"], "y": source["y"]} if source else None,
                "target_position": {"x": target["x"], "y": target["y"]} if target else None,
            }
        )
    return positioned


def _customer_name(customer_id: str) -> str:
    names = {
        "cust-maya-chen": "Maya Chen",
        "customer-demo-001": "Demo Shopper",
        "cust-urban-commuter": "Urban Commuter",
        "cust-home-premium": "Premium Home Accounts",
        "cust-winback": "Dormant Wellness Buyers",
    }
    return names.get(customer_id, customer_id.replace("-", " ").title())


def _fallback_customer_graph(customer_id: str) -> dict:
    profile = _fallback_customer_profile(customer_id)
    product = _fallback_product_for_customer(customer_id)
    region = _fallback_region_for_customer(customer_id)
    segment = profile["segment"].split(" ", 1)[0]
    short_name = _short_label(profile["name"])
    graph = {
        "nodes": [
            {"id": customer_id, "label": short_name, "kind": "customer", "x": 45, "y": 44},
            {"id": product["id"], "label": _short_label(product["label"]), "kind": "product", "x": 16, "y": 22},
            {"id": f"region-{region.lower()}", "label": region, "kind": "region", "x": 73, "y": 21},
            {"id": f"campaign-{customer_id}", "label": product["campaign"], "kind": "campaign", "x": 22, "y": 73},
            {"id": f"segment-{customer_id}", "label": segment, "kind": "segment", "x": 75, "y": 72},
        ],
        "edges": [
            {"id": "a", "type": product["event"], "source_position": {"x": 45, "y": 44}, "target_position": {"x": 16, "y": 22}},
            {"id": "b", "type": "LOCATED_IN", "source_position": {"x": 45, "y": 44}, "target_position": {"x": 73, "y": 21}},
            {"id": "c", "type": "TARGETED", "source_position": {"x": 45, "y": 44}, "target_position": {"x": 22, "y": 73}},
            {"id": "d", "type": "BELONGS_TO", "source_position": {"x": 45, "y": 44}, "target_position": {"x": 75, "y": 72}},
        ],
    }


def _empty_customer_graph(customer_id: str, error: str | None = None) -> dict:
    return {
        "customer_id": customer_id,
        "profile": {
            "name": _customer_name(customer_id),
            "initials": _initials(_customer_name(customer_id)),
            "segment": "No activity yet",
            "ltv": "$0",
            "churnRisk": "Unknown",
            "lastEvent": "No purchases or browse events",
        },
        "graph": {"nodes": [], "edges": []},
        "relationship_count": 0,
        "source": "no_customer_graph",
        "error": error,
    }
    return {
        "customer_id": customer_id,
        "profile": profile,
        "graph": graph,
        "relationship_count": len(graph["edges"]),
        "source": "demo_customer_360_graph",
    }


def _fallback_customer_profile(customer_id: str) -> dict:
    profiles = {
        "cust-maya-chen": {
            "segment": "High-LTV wellness buyer",
            "ltv": "$18,420",
            "churnRisk": "Low",
            "lastEvent": "Viewed hydration bundle",
        },
        "customer-demo-001": {
            "segment": "Active shop customer",
            "ltv": "$640",
            "churnRisk": "Medium",
            "lastEvent": "Purchased Air Quality Monitor Pro",
        },
        "cust-urban-commuter": {
            "segment": "Urban commuter cohort",
            "ltv": "$8,600",
            "churnRisk": "Low",
            "lastEvent": "Purchased compact power kit",
        },
        "cust-home-premium": {
            "segment": "Premium home accounts",
            "ltv": "$12,650",
            "churnRisk": "Low",
            "lastEvent": "Opened smart home campaign",
        },
        "cust-winback": {
            "segment": "Dormant wellness buyers",
            "ltv": "$4,200",
            "churnRisk": "High",
            "lastEvent": "Ignored winback email",
        },
    }
    profile = profiles.get(
        customer_id,
        {
            "segment": "Emerging customer",
            "ltv": "$0",
            "churnRisk": "Unknown",
            "lastEvent": "No recent activity",
        },
    )
    name = _customer_name(customer_id)
    return {
        "name": name,
        "initials": _initials(name),
        **profile,
    }


def _fallback_product_for_customer(customer_id: str) -> dict:
    products = {
        "cust-maya-chen": {"id": "sku-hydration", "label": "Hydration Bundle", "event": "VIEWED", "campaign": "Email"},
        "customer-demo-001": {"id": "sku-air", "label": "Air Quality Monitor", "event": "PURCHASED", "campaign": "Shop"},
        "cust-urban-commuter": {"id": "sku-power", "label": "Power Kit", "event": "PURCHASED", "campaign": "Mobile"},
        "cust-home-premium": {"id": "sku-air", "label": "Air Quality Monitor", "event": "VIEWED", "campaign": "Smart Home"},
        "cust-winback": {"id": "sku-sleep", "label": "Sleep Sensor", "event": "VIEWED", "campaign": "Winback"},
    }
    return products.get(customer_id, {"id": "sku-unknown", "label": "Product", "event": "RELATED", "campaign": "Demo"})


def _fallback_region_for_customer(customer_id: str) -> str:
    regions = {
        "cust-maya-chen": "NE",
        "customer-demo-001": "South",
        "cust-urban-commuter": "West",
        "cust-home-premium": "South",
        "cust-winback": "Midwest",
    }
    return regions.get(customer_id, "NA")


def _segment_label(categories: Counter, order_count: int) -> str:
    if order_count >= 5:
        return "Loyal active buyer"
    if categories:
        return f"{categories.most_common(1)[0][0]} affinity"
    return "Emerging customer"


def _last_event(orders: list[dict], views: list[dict]) -> str:
    if orders:
        return f"Purchased {orders[0].get('product_name', 'product')}"
    if views:
        return f"Viewed {views[0].get('product_name', 'product')}"
    return "No recent activity"


def _short_label(value: str) -> str:
    return str(value).split(" ", 1)[0]


def _currency(value) -> str:
    try:
        return f"${float(value):,.0f}"
    except (TypeError, ValueError):
        return "$0"


def _churn_label(value) -> str:
    if isinstance(value, (int, float)):
        return f"{float(value) * 100:.1f}%" if value <= 1 else f"{float(value):.1f}%"
    return str(value or "Unknown")


def _initials(value: str) -> str:
    parts = [part for part in value.replace("-", " ").split() if part]
    return "".join(part[0].upper() for part in parts[:2]) or "C"


def _db():
    return get_mongo_client()[settings.mongodb_database]
