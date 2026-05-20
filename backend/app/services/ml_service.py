from statistics import mean

import mlflow

from app.services.mlflow_service import registry_status, tracked_run


PRODUCT_CATALOG = [
    {"product": "Smart Hydration Bundle", "categories": {"wellness", "fitness"}, "base_score": 0.88},
    {"product": "Air Quality Monitor Pro", "categories": {"smart home", "wellness"}, "base_score": 0.78},
    {"product": "Compact Power Kit", "categories": {"travel", "commuter"}, "base_score": 0.74},
    {"product": "Sleep Recovery Sensor", "categories": {"wellness", "sleep"}, "base_score": 0.7},
]


def get_model_registry_status() -> dict:
    status = registry_status()
    status["models"] = [
        {"name": "baseline_revenue_forecaster", "stage": "prototype", "framework": "heuristic"},
        {"name": "baseline_product_recommender", "stage": "prototype", "framework": "content_similarity"},
        {"name": "baseline_customer_segmenter", "stage": "prototype", "framework": "rfm_rules"},
    ]
    return status


def forecast_revenue(recent_revenue: list[float]) -> dict:
    deltas = [current - previous for previous, current in zip(recent_revenue, recent_revenue[1:])]
    trend = mean(deltas) if deltas else 0
    next_value = max(0, recent_revenue[-1] + trend)
    confidence = max(0.55, min(0.93, 1 - (abs(trend) / max(mean(recent_revenue), 1))))

    with tracked_run("baseline_revenue_forecast", {"model_family": "forecasting"}):
        mlflow.log_metric("input_points", len(recent_revenue))
        mlflow.log_metric("mean_recent_revenue", mean(recent_revenue))
        mlflow.log_metric("predicted_next_revenue", next_value)

    return {
        "model": "baseline_revenue_forecaster",
        "prediction": round(next_value, 2),
        "confidence": round(confidence, 3),
        "method": "moving-average trend baseline",
    }


def recommend_products(customer_id: str, segment: str, recent_categories: list[str]) -> dict:
    category_set = {category.lower() for category in recent_categories}
    scored = []
    for product in PRODUCT_CATALOG:
        overlap = len(category_set.intersection(product["categories"]))
        score = product["base_score"] + (overlap * 0.07)
        if "high-ltv" in segment.lower():
            score += 0.04
        scored.append({"product": product["product"], "score": round(min(score, 0.99), 3)})

    recommendations = sorted(scored, key=lambda item: item["score"], reverse=True)[:3]
    with tracked_run("baseline_product_recommendation", {"model_family": "recommendation"}):
        mlflow.log_param("customer_id", customer_id)
        mlflow.log_param("segment", segment)
        mlflow.log_metric("top_score", recommendations[0]["score"])

    return {
        "model": "baseline_product_recommender",
        "customer_id": customer_id,
        "recommendations": recommendations,
    }


def segment_customer(recency_days: int, frequency: int, monetary_value: float) -> dict:
    if monetary_value >= 10000 and frequency >= 8 and recency_days <= 30:
        segment = "high_ltv_active"
    elif recency_days > 90:
        segment = "winback_risk"
    elif frequency >= 5:
        segment = "loyal_growth"
    else:
        segment = "emerging"

    with tracked_run("baseline_customer_segmentation", {"model_family": "segmentation"}):
        mlflow.log_param("recency_days", recency_days)
        mlflow.log_param("frequency", frequency)
        mlflow.log_metric("monetary_value", monetary_value)

    return {
        "model": "baseline_customer_segmenter",
        "segment": segment,
        "features": {
            "recency_days": recency_days,
            "frequency": frequency,
            "monetary_value": monetary_value,
        },
    }

