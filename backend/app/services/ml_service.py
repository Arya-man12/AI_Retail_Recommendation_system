import os
from pathlib import Path
from statistics import mean

import mlflow

from app.config import settings
from app.services.mlflow_service import registry_status, tracked_run


PRODUCT_CATALOG = [
    {"product_id": "sku-hydration", "product": "Smart Hydration Bundle", "categories": {"wellness", "fitness"}, "keywords": {"hydration", "bottle", "filter", "reminder", "fitness"}, "base_score": 0.74},
    {"product_id": "sku-air", "product": "Air Quality Monitor Pro", "categories": {"smart home", "wellness"}, "keywords": {"air", "quality", "monitor", "home", "sensor"}, "base_score": 0.69},
    {"product_id": "sku-power", "product": "Compact Power Kit", "categories": {"travel", "commuter"}, "keywords": {"battery", "charger", "cable", "travel", "commuter"}, "base_score": 0.66},
    {"product_id": "sku-sleep", "product": "Sleep Recovery Sensor", "categories": {"wellness", "sleep"}, "keywords": {"sleep", "recovery", "sensor", "health", "bedside"}, "base_score": 0.64},
    {"product_id": "sku-focus-lamp", "product": "Adaptive Focus Lamp", "categories": {"smart home", "productivity"}, "keywords": {"lamp", "lighting", "desk", "focus", "productivity"}, "base_score": 0.58},
    {"product_id": "sku-commuter-pack", "product": "Weatherproof Commuter Pack", "categories": {"commuter", "travel"}, "keywords": {"backpack", "laptop", "weatherproof", "commuter", "storage"}, "base_score": 0.6},
    {"product_id": "sku-recovery-band", "product": "Recovery Mobility Band Set", "categories": {"wellness", "fitness"}, "keywords": {"recovery", "mobility", "resistance", "bands", "fitness"}, "base_score": 0.57},
    {"product_id": "sku-desk-hub", "product": "Modular Desk Hub", "categories": {"productivity"}, "keywords": {"desk", "usb", "charging", "dock", "organizer"}, "base_score": 0.56},
    {"product_id": "sku-travel-filter", "product": "Portable Water Filter", "categories": {"travel", "wellness"}, "keywords": {"water", "filter", "purifier", "travel", "bottle"}, "base_score": 0.56},
    {"product_id": "sku-air-mini", "product": "Air Quality Monitor Mini", "categories": {"smart home"}, "keywords": {"air", "quality", "mini", "sensor", "alerts"}, "base_score": 0.55},
    {"product_id": "sku-cable-roll", "product": "Tech Cable Roll", "categories": {"commuter", "productivity"}, "keywords": {"cable", "organizer", "chargers", "adapters", "pouch"}, "base_score": 0.53},
    {"product_id": "sku-mindful-kit", "product": "Mindful Break Kit", "categories": {"wellness", "productivity"}, "keywords": {"mindful", "break", "timer", "reset", "desk"}, "base_score": 0.54},
    {"product_id": "sku-ergonomic-stand", "product": "Foldable Ergonomic Stand", "categories": {"productivity", "commuter"}, "keywords": {"laptop", "stand", "ergonomic", "portable", "desk"}, "base_score": 0.52},
    {"product_id": "sku-cold-brew", "product": "Smart Cold Brew Tumbler", "categories": {"travel"}, "keywords": {"cold", "brew", "tumbler", "temperature", "travel"}, "base_score": 0.51},
    {"product_id": "sku-sunrise-clock", "product": "Sunrise Routine Clock", "categories": {"smart home", "sleep"}, "keywords": {"sunrise", "clock", "sleep", "lighting", "routine"}, "base_score": 0.52},
    {"product_id": "sku-fitness-scale", "product": "Connected Fitness Scale", "categories": {"wellness", "fitness"}, "keywords": {"fitness", "scale", "health", "metrics", "profile"}, "base_score": 0.53},
]

SEGMENT_TRAINING_POINTS = [
    [8, 12, 22000],
    [14, 9, 18420],
    [24, 6, 8600],
    [42, 4, 5200],
    [95, 2, 3100],
    [130, 1, 900],
    [21, 7, 12650],
    [64, 3, 4200],
]

SEGMENT_LABELS = {
    0: "high_ltv_active",
    1: "loyal_growth",
    2: "emerging",
    3: "winback_risk",
}


def get_model_registry_status() -> dict:
    status = registry_status()
    status["models"] = [
        {
            "name": settings.ml_forecast_model,
            "stage": "configured",
            "family": "forecasting",
            "framework": "prophet" if settings.ml_forecast_model == "prophet" else "heuristic",
        },
        {
            "name": settings.ml_recommender_model,
            "stage": "configured",
            "family": "recommendation",
            "framework": "transparent_weighted_rules",
        },
        {
            "name": settings.ml_segmentation_model,
            "stage": "configured",
            "family": "segmentation",
            "framework": "scikit-learn" if settings.ml_segmentation_model == "kmeans" else "rfm_rules",
        },
        {
            "name": "rfm_churn_risk",
            "stage": "configured",
            "family": "retention",
            "framework": "logistic_rules",
        },
        {
            "name": "basket_affinity_rules",
            "stage": "configured",
            "family": "basket_analysis",
            "framework": "co_occurrence_lift",
        },
        {
            "name": "product_demand_moving_average",
            "stage": "configured",
            "family": "demand_forecasting",
            "framework": "moving_average",
        },
        {
            "name": "lexicon_review_sentiment",
            "stage": "configured",
            "family": "review_intelligence",
            "framework": "sentiment_lexicon",
        },
    ]
    status["configuration"] = {
        "forecast_model": settings.ml_forecast_model,
        "recommender_model": settings.ml_recommender_model,
        "segmentation_model": settings.ml_segmentation_model,
        "kmeans_clusters": settings.ml_kmeans_clusters,
    }
    return status


def predict_churn_risk(features: dict) -> dict:
    recency_days = float(features.get("recency_days", 30))
    frequency = float(features.get("frequency", 1))
    monetary_value = float(features.get("monetary_value", 0))
    discount_sensitivity = float(features.get("discount_sensitivity", 0.35))
    engagement_depth = float(features.get("engagement_depth", features.get("bundle_affinity", 0.5)))

    recency_component = min(recency_days / 120, 1) * 0.42
    frequency_component = max(0, 1 - min(frequency / 12, 1)) * 0.24
    value_component = max(0, 1 - min(monetary_value / 20000, 1)) * 0.12
    discount_component = min(discount_sensitivity, 1) * 0.14
    engagement_component = max(0, 1 - min(engagement_depth, 1)) * 0.08
    risk = recency_component + frequency_component + value_component + discount_component + engagement_component
    probability = round(max(0.02, min(risk, 0.96)), 3)

    if probability >= 0.65:
        band = "high"
        action = "Trigger win-back offer and human review."
    elif probability >= 0.35:
        band = "medium"
        action = "Send personalized retention offer."
    else:
        band = "low"
        action = "Maintain normal personalized recommendations."

    with tracked_run("rfm_churn_risk_prediction", {"model_family": "retention"}):
        mlflow.log_metric("recency_days", recency_days)
        mlflow.log_metric("frequency", frequency)
        mlflow.log_metric("monetary_value", monetary_value)
        mlflow.log_metric("churn_probability", probability)

    return {
        "model": "rfm_churn_risk",
        "probability": probability,
        "percent": round(probability * 100, 1),
        "risk_band": band,
        "recommended_action": action,
        "features": {
            "recency_days": recency_days,
            "frequency": frequency,
            "monetary_value": monetary_value,
            "discount_sensitivity": discount_sensitivity,
            "engagement_depth": engagement_depth,
        },
        "drivers": [
            {"feature": "recency_days", "contribution": round(recency_component, 3)},
            {"feature": "frequency", "contribution": round(frequency_component, 3)},
            {"feature": "monetary_value", "contribution": round(value_component, 3)},
            {"feature": "discount_sensitivity", "contribution": round(discount_component, 3)},
            {"feature": "engagement_depth", "contribution": round(engagement_component, 3)},
        ],
    }


def forecast_product_demand(history: list[dict], periods: int = 7) -> dict:
    if not history:
        return {
            "model": "product_demand_moving_average",
            "forecast": [],
            "method": "no history",
        }

    quantities = [max(0, int(item.get("quantity", 0))) for item in history]
    window = quantities[-7:] or quantities
    daily_average = mean(window)
    trend = mean([current - previous for previous, current in zip(window, window[1:])]) if len(window) > 1 else 0
    forecast = []
    for day in range(1, periods + 1):
        forecast.append(
            {
                "period": day,
                "predicted_units": round(max(0, daily_average + (trend * day)), 2),
            }
        )

    with tracked_run("product_demand_forecast", {"model_family": "demand_forecasting"}):
        mlflow.log_metric("history_points", len(history))
        mlflow.log_metric("daily_average_units", daily_average)
        mlflow.log_metric("trend_units", trend)

    return {
        "model": "product_demand_moving_average",
        "history_points": len(history),
        "daily_average_units": round(daily_average, 2),
        "trend_units": round(trend, 2),
        "forecast": forecast,
    }


def score_review_sentiment(text: str) -> dict:
    positive = {
        "great", "love", "excellent", "fast", "easy", "useful", "quality", "perfect", "recommend", "happy",
    }
    negative = {
        "bad", "slow", "broken", "poor", "return", "expensive", "late", "hard", "issue", "problem",
    }
    words = [word.strip(".,!?;:()[]{}\"'").lower() for word in text.split()]
    positive_hits = [word for word in words if word in positive]
    negative_hits = [word for word in words if word in negative]
    raw = len(positive_hits) - len(negative_hits)
    score = round(max(-1, min(1, raw / max(len(words) ** 0.5, 1))), 3)
    label = "positive" if score > 0.12 else "negative" if score < -0.12 else "neutral"

    with tracked_run("review_sentiment_scoring", {"model_family": "review_intelligence"}):
        mlflow.log_metric("sentiment_score", score)
        mlflow.log_metric("positive_hits", len(positive_hits))
        mlflow.log_metric("negative_hits", len(negative_hits))

    return {
        "model": "lexicon_review_sentiment",
        "score": score,
        "label": label,
        "positive_terms": positive_hits,
        "negative_terms": negative_hits,
    }


def forecast_revenue(recent_revenue: list[float]) -> dict:
    if settings.ml_forecast_model == "weighted_moving_average":
        return forecast_revenue_weighted(recent_revenue)

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


def forecast_revenue_weighted(recent_revenue: list[float]) -> dict:
    weights = list(range(1, len(recent_revenue) + 1))
    weighted_average = sum(value * weight for value, weight in zip(recent_revenue, weights)) / sum(weights)
    recent_delta = recent_revenue[-1] - recent_revenue[-2]
    prediction = max(0, weighted_average + (recent_delta * 0.35))
    confidence = max(0.58, min(0.91, 1 - abs(recent_delta) / max(weighted_average, 1)))

    with tracked_run("weighted_revenue_forecast", {"model_family": "forecasting"}):
        mlflow.log_param("framework", "weighted_moving_average")
        mlflow.log_metric("input_points", len(recent_revenue))
        mlflow.log_metric("predicted_next_revenue", prediction)

    return {
        "model": "weighted_moving_average_forecaster",
        "prediction": round(prediction, 2),
        "confidence": round(confidence, 3),
        "method": "weighted moving average with recent trend adjustment",
    }


def forecast_revenue_with_prophet(history: list[dict], periods: int = 7, frequency: str = "D") -> dict:
    matplotlib_cache = Path(__file__).resolve().parents[2] / ".cache" / "matplotlib"
    matplotlib_cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(matplotlib_cache))

    try:
        import pandas as pd
        from prophet import Prophet
    except Exception as exc:
        raise RuntimeError(f"Prophet is not available: {exc}") from exc

    frame = pd.DataFrame(history)
    if not {"ds", "y"}.issubset(frame.columns):
        raise ValueError("Prophet history must contain 'ds' date and 'y' value fields")

    frame = frame[["ds", "y"]].copy()
    frame["ds"] = pd.to_datetime(frame["ds"], utc=False).dt.tz_localize(None)
    frame["y"] = pd.to_numeric(frame["y"], errors="coerce")
    frame = frame.dropna().sort_values("ds")
    if len(frame) < 3:
        raise ValueError("Prophet requires at least 3 valid history points")

    with tracked_run("prophet_revenue_forecast", {"model_family": "forecasting", "framework": "prophet"}):
        model = Prophet(
            yearly_seasonality=False,
            weekly_seasonality=True,
            daily_seasonality=False,
            interval_width=0.8,
        )
        model.fit(frame)
        future = model.make_future_dataframe(periods=periods, freq=frequency)
        forecast = model.predict(future)
        tail = forecast.tail(periods)[["ds", "yhat", "yhat_lower", "yhat_upper"]]

        mlflow.log_param("framework", "prophet")
        mlflow.log_param("periods", periods)
        mlflow.log_param("frequency", frequency)
        mlflow.log_metric("history_points", len(frame))
        mlflow.log_metric("last_prediction", float(tail.iloc[-1]["yhat"]))

    return {
        "model": "prophet_revenue_forecaster",
        "framework": "prophet",
        "history_points": len(frame),
        "forecast": [
            {
                "ds": row["ds"].date().isoformat(),
                "yhat": round(float(row["yhat"]), 2),
                "yhat_lower": round(float(row["yhat_lower"]), 2),
                "yhat_upper": round(float(row["yhat_upper"]), 2),
            }
            for _, row in tail.iterrows()
        ],
    }


def recommend_products(customer_id: str, segment: str, recent_categories: list[str]) -> dict:
    scored = [_score_product(product, segment, recent_categories) for product in PRODUCT_CATALOG]
    recommendations = sorted(scored, key=lambda item: item["score"], reverse=True)[:3]

    with tracked_run("transparent_product_recommendation", {"model_family": "recommendation"}):
        mlflow.log_param("customer_id", customer_id)
        mlflow.log_param("segment", segment)
        mlflow.log_param("recent_categories", ",".join(recent_categories))
        mlflow.log_param("source", "transparent_rules")
        mlflow.log_metric("top_score", recommendations[0]["score"])

    return {
        "model": "transparent_product_recommender",
        "source": "transparent_rules",
        "customer_id": customer_id,
        "recommendations": recommendations,
    }


def _score_product(product: dict, segment: str, recent_categories: list[str]) -> dict:
    normalized_segment = segment.lower().replace("_", " ")
    recent_category_set = {category.lower().replace("_", " ") for category in recent_categories if category}
    matched_categories = recent_category_set.intersection(product["categories"])
    category_overlap = len(matched_categories) / max(len(product["categories"]), 1)
    keyword_overlap = len(set(normalized_segment.split()).intersection(product["keywords"])) / max(len(product["keywords"]), 1)
    segment_fit = _segment_fit(normalized_segment, product["categories"])
    base_component = product["base_score"] * 0.22
    category_component = category_overlap * 0.34
    segment_component = segment_fit * 0.24
    keyword_component = keyword_overlap * 0.12
    winback_component = 0.08 if "winback" in normalized_segment and "sleep" in product["categories"] else 0
    score = min(base_component + category_component + segment_component + keyword_component + winback_component, 0.99)
    drivers = {
        "base_product_fit": round(base_component, 3),
        "recent_category_match": round(category_component, 3),
        "segment_fit": round(segment_component, 3),
        "keyword_match": round(keyword_component, 3),
        "winback_sleep_boost": round(winback_component, 3),
    }
    return {
        "product": product["product"],
        "product_id": product["product_id"],
        "category": sorted(matched_categories or product["categories"])[0],
        "score": round(score, 3),
        "drivers": drivers,
    }


def _segment_fit(normalized_segment: str, categories: set[str]) -> float:
    if "wellness" in normalized_segment and categories.intersection({"wellness", "fitness", "sleep"}):
        return 1.0
    if "commuter" in normalized_segment and categories.intersection({"commuter", "travel"}):
        return 1.0
    if "home" in normalized_segment and "smart home" in categories:
        return 1.0
    if "productivity" in normalized_segment and "productivity" in categories:
        return 1.0
    if "active shopper" in normalized_segment:
        return 0.5
    return 0.0


def segment_customer(recency_days: int, frequency: int, monetary_value: float) -> dict:
    if settings.ml_segmentation_model == "kmeans":
        try:
            return segment_customer_kmeans(recency_days, frequency, monetary_value)
        except Exception as exc:
            fallback = segment_customer_rules(recency_days, frequency, monetary_value)
            fallback["fallback_reason"] = str(exc)
            return fallback

    return segment_customer_rules(recency_days, frequency, monetary_value)


def segment_customer_rules(recency_days: int, frequency: int, monetary_value: float) -> dict:
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
        "framework": "rfm_rules",
        "segment": segment,
        "features": {
            "recency_days": recency_days,
            "frequency": frequency,
            "monetary_value": monetary_value,
        },
    }


def segment_customer_kmeans(recency_days: int, frequency: int, monetary_value: float) -> dict:
    try:
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler
    except Exception as exc:
        raise RuntimeError(f"scikit-learn is not available: {exc}") from exc

    cluster_count = max(2, min(settings.ml_kmeans_clusters, len(SEGMENT_TRAINING_POINTS)))
    scaler = StandardScaler()
    training = scaler.fit_transform(SEGMENT_TRAINING_POINTS)
    model = KMeans(n_clusters=cluster_count, random_state=42, n_init=10)
    model.fit(training)

    cluster_profiles = _cluster_profiles(model.labels_, cluster_count)
    point = scaler.transform([[recency_days, frequency, monetary_value]])
    cluster = int(model.predict(point)[0])
    segment = cluster_profiles.get(cluster, SEGMENT_LABELS.get(cluster, "emerging"))

    with tracked_run("kmeans_customer_segmentation", {"model_family": "segmentation", "framework": "scikit-learn"}):
        mlflow.log_param("framework", "kmeans")
        mlflow.log_param("clusters", cluster_count)
        mlflow.log_param("recency_days", recency_days)
        mlflow.log_param("frequency", frequency)
        mlflow.log_metric("monetary_value", monetary_value)
        mlflow.log_metric("assigned_cluster", cluster)

    return {
        "model": "kmeans_customer_segmenter",
        "framework": "scikit-learn KMeans",
        "segment": segment,
        "cluster": cluster,
        "features": {
            "recency_days": recency_days,
            "frequency": frequency,
            "monetary_value": monetary_value,
        },
    }


def _cluster_profiles(labels, cluster_count: int) -> dict[int, str]:
    profiles = {}
    for cluster in range(cluster_count):
        members = [point for point, label in zip(SEGMENT_TRAINING_POINTS, labels) if label == cluster]
        if not members:
            continue
        avg_recency = mean(point[0] for point in members)
        avg_frequency = mean(point[1] for point in members)
        avg_monetary = mean(point[2] for point in members)
        if avg_monetary >= 12000 and avg_frequency >= 7 and avg_recency <= 30:
            profiles[cluster] = "high_ltv_active"
        elif avg_recency >= 90:
            profiles[cluster] = "winback_risk"
        elif avg_frequency >= 5:
            profiles[cluster] = "loyal_growth"
        else:
            profiles[cluster] = "emerging"
    return profiles
