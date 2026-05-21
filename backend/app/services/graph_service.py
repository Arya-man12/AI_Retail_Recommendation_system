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
        payload = dashboard_payload()
        return {
            "customer_id": customer_id,
            "profile": payload["customers"][0],
            "graph": payload["graph"],
            "relationship_count": len(payload["graph"]["edges"]),
            "source": "demo_customer_360_graph",
            "error": str(exc),
        }

    payload = dashboard_payload()
    return {
        "customer_id": customer_id,
        "profile": payload["customers"][0],
        "graph": payload["graph"],
        "relationship_count": len(payload["graph"]["edges"]),
        "source": "demo_customer_360_graph",
    }


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
    }
    return names.get(customer_id, customer_id.replace("-", " ").title())


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
