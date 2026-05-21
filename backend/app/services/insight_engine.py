from collections import Counter, deque
from datetime import UTC, datetime
from threading import Lock
from typing import Any


MAX_EVENTS = 200
MAX_INSIGHTS = 80

_lock = Lock()
_events: deque[dict[str, Any]] = deque(maxlen=MAX_EVENTS)
_insights: deque[dict[str, Any]] = deque(maxlen=MAX_INSIGHTS)
_category_counts: Counter[str] = Counter()
_revenue_by_category: Counter[str] = Counter()
_customer_purchase_counts: Counter[str] = Counter()


def process_event(event: dict[str, Any], source: str = "stream") -> dict:
    normalized = _normalize_event(event, source)
    generated = _detect_insights(normalized)

    with _lock:
        _events.appendleft(normalized)
        for insight in generated:
            _insights.appendleft(insight)

    return {
        "event": normalized,
        "insights": generated,
    }


def process_events(events: list[dict[str, Any]], source: str = "stream") -> dict:
    results = [process_event(event, source=source) for event in events]
    return {
        "processed": len(results),
        "insights_created": sum(len(result["insights"]) for result in results),
    }


def get_live_insights() -> dict:
    with _lock:
        return {
            "recent_events": list(_events)[:30],
            "insights": list(_insights)[:30],
            "summary": {
                "events_seen": len(_events),
                "top_categories": _category_counts.most_common(5),
                "revenue_by_category": dict(_revenue_by_category),
                "customer_purchase_counts": dict(_customer_purchase_counts),
            },
        }


def _normalize_event(event: dict[str, Any], source: str) -> dict:
    event_type = str(event.get("event_type", "unknown")).strip().lower()
    category = str(event.get("category", "unknown")).strip().lower()
    revenue = _safe_float(event.get("revenue"), 0.0)
    quantity = _safe_int(event.get("quantity"), 0)
    customer_id = str(event.get("customer_id", "unknown")).strip() or "unknown"
    product_name = str(event.get("product_name") or event.get("product_id") or "unknown")
    event_time = event.get("event_time") or datetime.now(UTC).isoformat()

    normalized = {
        "event_id": str(event.get("event_id", "unknown")),
        "event_type": event_type,
        "customer_id": customer_id,
        "product_id": event.get("product_id"),
        "product_name": product_name,
        "category": category,
        "quantity": quantity,
        "revenue": round(revenue, 2),
        "event_time": event_time,
        "source": source,
        "received_at": datetime.now(UTC).isoformat(),
    }

    _category_counts[category] += 1
    if event_type == "purchase":
        _revenue_by_category[category] += revenue
        _customer_purchase_counts[customer_id] += 1

    return normalized


def _detect_insights(event: dict[str, Any]) -> list[dict[str, Any]]:
    insights = []
    if event["event_type"] == "purchase":
        insights.append(
            _insight(
                "purchase_detected",
                "Purchase event detected",
                f"{event['customer_id']} bought {event['product_name']} for ${event['revenue']:.2f}.",
                "info",
                event,
            )
        )

    if event["revenue"] >= 100:
        insights.append(
            _insight(
                "high_value_order",
                "High-value order",
                f"{event['product_name']} generated ${event['revenue']:.2f} in one order.",
                "positive",
                event,
            )
        )

    if _category_counts[event["category"]] >= 3:
        insights.append(
            _insight(
                "category_momentum",
                "Category momentum",
                f"{event['category']} has {_category_counts[event['category']]} recent events.",
                "positive",
                event,
            )
        )

    if _customer_purchase_counts[event["customer_id"]] >= 2:
        insights.append(
            _insight(
                "repeat_buyer",
                "Repeat buyer activity",
                f"{event['customer_id']} has {_customer_purchase_counts[event['customer_id']]} recent purchases.",
                "positive",
                event,
            )
        )

    return insights


def _insight(kind: str, title: str, detail: str, severity: str, event: dict[str, Any]) -> dict:
    return {
        "kind": kind,
        "title": title,
        "detail": detail,
        "severity": severity,
        "event_id": event["event_id"],
        "created_at": datetime.now(UTC).isoformat(),
    }


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
