from app.services.demo_data import dashboard_payload
from app.services.feature_store_service import feature_store_status, get_customer_features
from app.services.graph_service import customer_graph, graph_status
from app.services.ml_service import forecast_revenue, recommend_products, segment_customer
from app.services.retail_intelligence_service import basket_analysis, churn_risk, demand_forecast, review_intelligence


def customer_360(customer_id: str = "cust-maya-chen") -> dict:
    payload = dashboard_payload()
    graph_payload = customer_graph(customer_id)
    customer = graph_payload.get("profile") or payload["customers"][0]
    return {
        "customer_id": customer_id,
        "profile": customer,
        "graph": graph_payload["graph"],
        "relationship_count": graph_payload["relationship_count"],
        "data_source": graph_payload["source"],
        "graph_error": graph_payload.get("error"),
    }


def geo_analytics() -> dict:
    regions = dashboard_payload()["geo"]
    top_region = max(regions, key=lambda region: region["heat"])
    return {
        "provider": "demo_geo_enrichment",
        "regions": regions,
        "top_region": top_region,
        "method": "lat_lon_region_rules",
    }


def feature_explanation(
    customer_id: str = "cust-maya-chen",
    segment: str = "High-LTV wellness buyer",
    recent_categories: list[str] | None = None,
) -> dict:
    recent_categories = recent_categories or ["wellness", "smart home"]
    recommendation = recommend_products(
        customer_id=customer_id,
        segment=segment,
        recent_categories=recent_categories,
    )
    top_recommendation = recommendation["recommendations"][0]
    feature_payload = get_customer_features(customer_id)
    raw_features = feature_payload.get("features") or {}
    source = feature_payload.get("source")
    if source == "demo_features":
        raw_features = {}
        source = "unavailable"

    features = _recommendation_attributions(
        top_recommendation=top_recommendation,
        segment=segment,
        recent_categories=recent_categories,
        customer_features=raw_features,
    )
    strongest = features[0]
    return {
        "provider": "computed_feature_attribution",
        "status": "computed",
        "model": "transparent_product_recommender",
        "customer_id": customer_id,
        "recommended_product": top_recommendation["product"],
        "recommendation_score": top_recommendation["score"],
        "recommendation_source": recommendation.get("source"),
        "feature_source": source,
        "features": features,
        "explanation": (
            f"{top_recommendation['product']} is recommended primarily because "
            f"{strongest['name'].lower()} contributed {strongest['impact']:+.2f}. "
            "Positive values increase recommendation confidence; negative values reduce it."
        ),
    }


def recommendation_insight() -> dict:
    recommendations = recommend_products(
        customer_id="demo-customer-001",
        segment="High-LTV wellness buyer",
        recent_categories=["wellness", "smart home"],
    )
    return {
        **recommendations,
        "explanation": feature_explanation(
            customer_id="demo-customer-001",
            segment="High-LTV wellness buyer",
            recent_categories=["wellness", "smart home"],
        ),
    }


def layer_status() -> dict:
    return {
        "layers": [
            {
                "id": 4,
                "name": "Feature + Customer 360 Layer",
                "status": "implemented",
                "details": "MongoDB-backed Customer 360 graph and feature data are exposed through intelligence APIs.",
            },
            {
                "id": 5,
                "name": "ML Intelligence Layer",
                "status": "partial",
                "details": "Configurable forecasting, recommendation, and KMeans segmentation models are exposed through ML APIs.",
            },
            {
                "id": 8,
                "name": "Transparent Recommendation Layer",
                "status": "implemented",
                "details": "Local weighted recommendation scoring exposes per-feature drivers for explainability.",
            },
            {
                "id": 9,
                "name": "Controlled LLM Orchestration Layer",
                "status": "partial",
                "details": "Governed tool dispatcher, RBAC checks, OpenRouter LLM call, and local evidence-based fallback.",
            },
            {
                "id": 10,
                "name": "Backend API Layer",
                "status": "implemented",
                "details": "FastAPI routers expose dashboard, ML, ecommerce, streaming, processing, and intelligence APIs.",
            },
            {
                "id": 11,
                "name": "Frontend Dashboard",
                "status": "implemented",
                "details": "Vite dashboard consumes backend APIs for analytics, transparent recommendations, forecasting, explainability, graph, and copilot.",
            },
        ]
    }


def intelligence_snapshot() -> dict:
    forecast = forecast_revenue([220, 236, 251, 268, 294, 318])
    feature_payload = get_customer_features("cust-maya-chen")
    features = feature_payload["features"]
    segment = segment_customer(
        recency_days=int(features.get("recency_days", 14)),
        frequency=int(features.get("frequency", 9)),
        monetary_value=float(features.get("monetary_value", 18420)),
    )
    return {
        "infrastructure": {
            "feature_store": feature_store_status(),
            "graph": graph_status(),
        },
        "features": feature_payload,
        "forecast": forecast,
        "segment": segment,
        "churn": churn_risk("cust-maya-chen"),
        "basket_analysis": basket_analysis(),
        "demand_forecast": demand_forecast(periods=7),
        "review_intelligence": review_intelligence(),
        "customer360": customer_360(),
        "geo": geo_analytics(),
        "layer_status": layer_status()["layers"],
    }


def _recommendation_attributions(
    top_recommendation: dict,
    segment: str,
    recent_categories: list[str],
    customer_features: dict,
) -> list[dict]:
    score = _clamp(float(top_recommendation.get("score", 0)), 0, 1)
    drivers = top_recommendation.get("drivers") or {}
    product_category = str(top_recommendation.get("category") or "").replace("_", " ").lower()
    recent_category_set = {category.lower().replace("_", " ") for category in recent_categories if category}
    category_overlap = 1.0 if product_category and product_category in recent_category_set else 0.0
    bundle_affinity = _clamp(_float_feature(customer_features, "bundle_affinity", "engagement_depth", default=0.0), 0, 1)
    frequency = _clamp(_float_feature(customer_features, "frequency", default=0.0) / 10, 0, 1)
    discount_sensitivity = _clamp(_float_feature(customer_features, "discount_sensitivity", default=0.0), 0, 1)
    churn_value = _float_feature(customer_features, "churn_risk", default=0.0)
    if churn_value > 1:
        churn_value = churn_value / 100
    churn_value = _clamp(churn_value, 0, 1)
    segment_match = _segment_category_match(segment, product_category)

    attributions = [
        {
            "name": "Recommendation score",
            "impact": round(score * 0.24, 3),
            "value": round(score, 3),
        },
        {
            "name": "Recent category match",
            "impact": round(float(drivers.get("recent_category_match", category_overlap * 0.34)), 3),
            "value": product_category or "unknown",
        },
        {
            "name": "Bundle affinity",
            "impact": round(bundle_affinity * 0.16, 3),
            "value": round(bundle_affinity, 3),
        },
        {
            "name": "Purchase frequency",
            "impact": round(frequency * 0.12, 3),
            "value": _float_feature(customer_features, "frequency", default=0.0),
        },
        {
            "name": "Segment fit",
            "impact": round(float(drivers.get("segment_fit", segment_match * 0.24)), 3),
            "value": segment,
        },
        {
            "name": "Product keyword match",
            "impact": round(float(drivers.get("keyword_match", 0)), 3),
            "value": round(float(drivers.get("keyword_match", 0)), 3),
        },
        {
            "name": "Base product fit",
            "impact": round(float(drivers.get("base_product_fit", 0)), 3),
            "value": round(float(drivers.get("base_product_fit", 0)), 3),
        },
        {
            "name": "Discount sensitivity",
            "impact": round(discount_sensitivity * -0.12, 3),
            "value": round(discount_sensitivity, 3),
        },
        {
            "name": "Churn risk",
            "impact": round(churn_value * -0.14, 3),
            "value": round(churn_value, 3),
        },
    ]
    return sorted(attributions, key=lambda feature: abs(feature["impact"]), reverse=True)


def _segment_category_match(segment: str, product_category: str) -> float:
    normalized_segment = segment.lower().replace("_", " ")
    if not product_category:
        return 0.0
    if product_category in normalized_segment:
        return 1.0
    if "wellness" in normalized_segment and product_category in {"wellness", "sleep"}:
        return 1.0
    if "home" in normalized_segment and product_category == "smart home":
        return 1.0
    if "commuter" in normalized_segment and product_category in {"commuter", "travel"}:
        return 1.0
    return 0.0


def _float_feature(features: dict, *names: str, default: float = 0.0) -> float:
    for name in names:
        if name in features:
            try:
                return float(features[name] or 0)
            except (TypeError, ValueError):
                return default
    return default


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))
