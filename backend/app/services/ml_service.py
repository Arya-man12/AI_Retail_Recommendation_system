import os
from pathlib import Path
from statistics import mean

import mlflow

from app.config import settings
from app.services.mlflow_service import registry_status, tracked_run


PRODUCT_CATALOG = [
    {"product": "Smart Hydration Bundle", "categories": {"wellness", "fitness"}, "base_score": 0.88},
    {"product": "Air Quality Monitor Pro", "categories": {"smart home", "wellness"}, "base_score": 0.78},
    {"product": "Compact Power Kit", "categories": {"travel", "commuter"}, "base_score": 0.74},
    {"product": "Sleep Recovery Sensor", "categories": {"wellness", "sleep"}, "base_score": 0.7},
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
            "framework": "content_similarity",
        },
        {
            "name": settings.ml_segmentation_model,
            "stage": "configured",
            "family": "segmentation",
            "framework": "scikit-learn" if settings.ml_segmentation_model == "kmeans" else "rfm_rules",
        },
    ]
    status["configuration"] = {
        "forecast_model": settings.ml_forecast_model,
        "recommender_model": settings.ml_recommender_model,
        "segmentation_model": settings.ml_segmentation_model,
        "kmeans_clusters": settings.ml_kmeans_clusters,
    }
    return status


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
