from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from functools import lru_cache
import os
import subprocess
import sys
from typing import Any, Literal

from app.config import settings


VALID_EVENT_TYPES = {"click", "purchase", "view", "cart"}
SPARK_START_ERROR: str | None = None


def sample_raw_events() -> list[dict[str, Any]]:
    return [
        {
            "event_id": " EVT-001 ",
            "customer_id": " CUST-100 ",
            "product_id": " SKU-HYDRATION ",
            "event_type": " Purchase ",
            "event_time": "2026-05-21T10:15:00Z",
            "quantity": 2,
            "price": 49.99,
            "lat": 42.3601,
            "lon": -71.0589,
        },
        {
            "event_id": "EVT-002",
            "customer_id": "cust-101",
            "product_id": "sku-air",
            "event_type": "click",
            "event_time": "2026-05-21T10:16:20Z",
            "quantity": None,
            "price": None,
            "lat": 34.0522,
            "lon": -118.2437,
        },
        {
            "event_id": "EVT-003",
            "customer_id": "cust-102",
            "product_id": "sku-power",
            "event_type": "purchase",
            "event_time": "2026-05-21T10:18:42Z",
            "quantity": 1,
            "price": 79.0,
            "lat": 41.8781,
            "lon": -87.6298,
        },
        {
            "event_id": "EVT-BAD",
            "customer_id": "",
            "product_id": "sku-unknown",
            "event_type": "bot",
            "event_time": "bad-timestamp",
            "quantity": -1,
            "price": -10,
            "lat": None,
            "lon": None,
        },
    ]


def spark_status() -> dict:
    try:
        import pyspark
    except Exception as exc:
        return {
            "installed": False,
            "available": False,
            "engine": "python_fallback",
            "error": _summarize_error(exc),
            "hint": "Install pyspark and set JAVA_HOME before using the Spark engine.",
            "app_name": settings.spark_app_name,
            "master": settings.spark_master,
        }

    java_version = _java_version()
    java_major = _java_major(java_version)
    java_supported = java_major is None or java_major <= 21
    status = {
        "installed": True,
        "available": SPARK_START_ERROR is None and java_supported,
        "engine": "pyspark",
        "version": pyspark.__version__,
        "java": java_version,
        "app_name": settings.spark_app_name,
        "master": settings.spark_master,
    }
    if SPARK_START_ERROR:
        status["available"] = False
        status["engine"] = "python_fallback"
        status["error"] = SPARK_START_ERROR
        status["hint"] = "Spark is installed, but the last startup attempt failed. Use a Spark-supported LTS JDK such as Java 17 or 21."
    elif not java_supported:
        status["available"] = False
        status["engine"] = "python_fallback"
        status["hint"] = "Spark is installed, but Java is newer than the supported LTS range. Use Java 17 or 21 for local Spark jobs."
    return status


def spark_start_check() -> dict:
    try:
        spark = get_spark_session()
    except Exception as exc:
        _remember_spark_error(exc)
        return {
            "installed": True,
            "available": False,
            "engine": "python_fallback",
            "error": _summarize_error(exc),
            "hint": _spark_error_hint(exc),
            "app_name": settings.spark_app_name,
            "master": settings.spark_master,
        }

    return {
        "installed": True,
        "available": True,
        "engine": "pyspark",
        "version": spark.version,
        "app_name": settings.spark_app_name,
        "master": settings.spark_master,
    }


def clean_events(events: list[dict[str, Any]], engine: Literal["auto", "spark", "python"] = "auto") -> dict:
    if engine == "python":
        return _clean_events_python(events, fallback_reason=None)
    if engine == "auto" and not _spark_runtime_supported():
        return _clean_events_python(
            events,
            fallback_reason="Spark is installed, but Java is newer than the supported LTS range.",
        )
    if engine == "auto" and SPARK_START_ERROR:
        return _clean_events_python(events, fallback_reason=SPARK_START_ERROR)

    try:
        return _clean_events_spark(events)
    except Exception as exc:
        _remember_spark_error(exc)
        if engine == "spark":
            raise
        return _clean_events_python(events, fallback_reason=_summarize_error(exc))


@lru_cache(maxsize=1)
def get_spark_session():
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)

    from pyspark.sql import SparkSession

    return (
        SparkSession.builder.appName(settings.spark_app_name)
        .master(settings.spark_master)
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )


def _clean_events_spark(events: list[dict[str, Any]]) -> dict:
    from pyspark.sql import functions as fn
    from pyspark.sql.types import DoubleType, IntegerType, StringType, StructField, StructType

    spark = get_spark_session()
    schema = StructType(
        [
            StructField("event_id", StringType(), True),
            StructField("customer_id", StringType(), True),
            StructField("product_id", StringType(), True),
            StructField("event_type", StringType(), True),
            StructField("event_time", StringType(), True),
            StructField("quantity", IntegerType(), True),
            StructField("price", DoubleType(), True),
            StructField("lat", DoubleType(), True),
            StructField("lon", DoubleType(), True),
        ]
    )
    raw_df = spark.createDataFrame(events, schema=schema)

    normalized_df = (
        raw_df.select(
            fn.lower(fn.trim("event_id")).alias("event_id"),
            fn.lower(fn.trim("customer_id")).alias("customer_id"),
            fn.lower(fn.trim("product_id")).alias("product_id"),
            fn.lower(fn.trim("event_type")).alias("event_type"),
            fn.to_timestamp("event_time").alias("event_time"),
            fn.coalesce("quantity", fn.lit(0)).alias("quantity"),
            fn.coalesce("price", fn.lit(0.0)).alias("price"),
            "lat",
            "lon",
        )
        .withColumn(
            "region",
            fn.when(fn.col("lon") <= -105, "West")
            .when((fn.col("lon") > -105) & (fn.col("lon") <= -87), "Midwest")
            .when((fn.col("lon") > -87) & (fn.col("lat") < 37), "South")
            .when(fn.col("lon") > -87, "Northeast")
            .otherwise("Unknown"),
        )
        .withColumn(
            "revenue",
            fn.when(
                fn.col("event_type") == "purchase",
                fn.greatest(fn.col("quantity"), fn.lit(0)) * fn.greatest(fn.col("price"), fn.lit(0.0)),
            ).otherwise(fn.lit(0.0)),
        )
    )

    clean_df = normalized_df.filter(
        (fn.col("event_id") != "")
        & (fn.col("customer_id") != "")
        & (fn.col("event_time").isNotNull())
        & (fn.col("event_type").isin(sorted(VALID_EVENT_TYPES)))
        & (fn.col("quantity") >= 0)
        & (fn.col("price") >= 0)
    )

    event_counts = {
        row["event_type"]: row["count"]
        for row in clean_df.groupBy("event_type").count().orderBy("event_type").collect()
    }
    region_revenue = {
        row["region"]: round(float(row["revenue"]), 2)
        for row in clean_df.groupBy("region").agg(fn.sum("revenue").alias("revenue")).orderBy("region").collect()
    }
    cleaned_records = [_serialize_record(row.asDict()) for row in clean_df.orderBy("event_time").collect()]

    return {
        "engine": "pyspark",
        "input_count": len(events),
        "clean_count": len(cleaned_records),
        "dropped_count": len(events) - len(cleaned_records),
        "event_counts": event_counts,
        "region_revenue": region_revenue,
        "records": cleaned_records,
    }


def _clean_events_python(events: list[dict[str, Any]], fallback_reason: str | None) -> dict:
    records = []
    event_counts: Counter[str] = Counter()
    region_revenue: defaultdict[str, float] = defaultdict(float)

    for event in events:
        normalized = _normalize_event(event)
        if not normalized:
            continue
        records.append(normalized)
        event_counts[normalized["event_type"]] += 1
        region_revenue[normalized["region"]] += normalized["revenue"]

    records.sort(key=lambda item: item["event_time"])
    response = {
        "engine": "python_fallback" if fallback_reason else "python",
        "input_count": len(events),
        "clean_count": len(records),
        "dropped_count": len(events) - len(records),
        "event_counts": dict(sorted(event_counts.items())),
        "region_revenue": {key: round(value, 2) for key, value in sorted(region_revenue.items())},
        "records": records,
    }
    if fallback_reason:
        response["fallback_reason"] = fallback_reason
    return response


def _normalize_event(event: dict[str, Any]) -> dict[str, Any] | None:
    event_id = _clean_text(event.get("event_id"))
    customer_id = _clean_text(event.get("customer_id"))
    product_id = _clean_text(event.get("product_id"))
    event_type = _clean_text(event.get("event_type"))
    event_time = _parse_timestamp(event.get("event_time"))
    quantity = _safe_int(event.get("quantity"), default=0)
    price = _safe_float(event.get("price"), default=0.0)

    if (
        not event_id
        or not customer_id
        or event_type not in VALID_EVENT_TYPES
        or event_time is None
        or quantity < 0
        or price < 0
    ):
        return None

    revenue = quantity * price if event_type == "purchase" else 0.0
    lat = _safe_float(event.get("lat"), default=None)
    lon = _safe_float(event.get("lon"), default=None)

    return {
        "event_id": event_id,
        "customer_id": customer_id,
        "product_id": product_id,
        "event_type": event_type,
        "event_time": event_time.isoformat().replace("+00:00", "Z"),
        "quantity": quantity,
        "price": round(price, 2),
        "revenue": round(revenue, 2),
        "lat": lat,
        "lon": lon,
        "region": _region_from_coordinates(lat, lon),
    }


def _clean_text(value: Any) -> str:
    return str(value or "").strip().lower()


def _parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _safe_int(value: Any, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float | None) -> float | None:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _region_from_coordinates(lat: float | None, lon: float | None) -> str:
    if lat is None or lon is None:
        return "Unknown"
    if lon <= -105:
        return "West"
    if lon <= -87:
        return "Midwest"
    if lat < 37:
        return "South"
    return "Northeast"


def _serialize_record(record: dict[str, Any]) -> dict[str, Any]:
    serialized = dict(record)
    event_time = serialized.get("event_time")
    if hasattr(event_time, "isoformat"):
        serialized["event_time"] = event_time.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
    serialized["price"] = round(float(serialized.get("price") or 0), 2)
    serialized["revenue"] = round(float(serialized.get("revenue") or 0), 2)
    return serialized


def _summarize_error(exc: Exception) -> str:
    message = str(exc).strip().splitlines()
    return message[0] if message else exc.__class__.__name__


def _spark_error_hint(exc: Exception) -> str:
    message = str(exc)
    if "getSubject is not supported" in message:
        return "Spark is installed, but the active Java runtime is incompatible. Use a Spark-supported LTS JDK such as Java 17 or 21."
    if "JAVA_HOME" in message or "Java gateway process exited" in message:
        return "Set JAVA_HOME to a Spark-supported JDK and restart the backend."
    return "The API will use the Python fallback until Spark can start successfully."


def _remember_spark_error(exc: Exception) -> None:
    global SPARK_START_ERROR
    SPARK_START_ERROR = _summarize_error(exc)


def _java_version() -> str | None:
    try:
        result = subprocess.run(["java", "-version"], capture_output=True, text=True, timeout=5)
    except Exception:
        return None
    output = result.stderr or result.stdout
    return output.splitlines()[0] if output else None


def _java_major(version_line: str | None) -> int | None:
    if not version_line:
        return None
    marker = 'version "'
    if marker not in version_line:
        return None
    version = version_line.split(marker, 1)[1].split('"', 1)[0]
    first = version.split(".", 1)[0]
    try:
        return int(first)
    except ValueError:
        return None


def _spark_runtime_supported() -> bool:
    java_major = _java_major(_java_version())
    return java_major is None or java_major <= 21
