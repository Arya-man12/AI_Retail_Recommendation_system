from app.services.demo_data import dashboard_payload
from app.services.feature_store_service import feature_store_status, get_customer_features
from app.services.graph_service import customer_graph, graph_status
from app.services.ml_service import forecast_revenue, recommend_products, segment_customer


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


def feature_explanation() -> dict:
    explanation = dashboard_payload()["explainability"]
    ranked_features = sorted(explanation["features"], key=lambda feature: abs(feature["impact"]), reverse=True)
    return {
        "provider": "prototype_feature_attribution",
        "explanation": explanation["explanation"],
        "features": ranked_features,
        "model": "baseline_product_recommender",
        "status": "demo_feature_attribution",
    }


def recommendation_insight() -> dict:
    recommendations = recommend_products(
        customer_id="demo-customer-001",
        segment="High-LTV wellness buyer",
        recent_categories=["wellness", "smart home"],
    )
    return {
        **recommendations,
        "explanation": feature_explanation(),
    }


def layer_status() -> dict:
    return {
        "layers": [
            {
                "id": 4,
                "name": "Geo + Feature + Customer 360 Layer",
                "status": "partial",
                "details": "Redis feature store and Neo4j Customer 360 graph adapters are configured with demo fallbacks.",
            },
            {
                "id": 5,
                "name": "ML Intelligence Layer",
                "status": "partial",
                "details": "Configurable forecasting, recommendation, and KMeans segmentation models are exposed through ML APIs.",
            },
            {
                "id": 8,
                "name": "Vector + Embedding Layer",
                "status": "implemented",
                "details": "Qdrant-backed product and customer embeddings with semantic search endpoints.",
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
                "details": "FastAPI routers expose dashboard, ML, vectors, ecommerce, streaming, processing, and intelligence APIs.",
            },
            {
                "id": 11,
                "name": "Frontend Dashboard",
                "status": "implemented",
                "details": "Vite dashboard consumes backend APIs for analytics, recommendations, forecasting, explainability, graph, geo, and copilot.",
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
        "recommendation": recommendation_insight(),
        "explainability": feature_explanation(),
        "customer360": customer_360(),
        "geo": geo_analytics(),
        "layer_status": layer_status()["layers"],
    }
