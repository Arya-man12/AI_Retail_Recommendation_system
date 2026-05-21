import json
import ssl
from typing import Any

from app.config import settings


class EmqxPublishError(RuntimeError):
    pass


class EmqxSubscribeError(RuntimeError):
    pass


def publish_event(topic_name: str, event: dict[str, Any]) -> dict:
    if not settings.emqx_host:
        return {
            "published": False,
            "provider": "emqx",
            "reason": "EMQX_HOST is not configured",
        }

    try:
        client = new_mqtt_client(f"{settings.emqx_client_id}-publisher")
        client.connect(settings.emqx_host, settings.emqx_port, settings.emqx_keepalive_seconds)
        client.loop_start()
        result = client.publish(
            topic_name,
            json.dumps(event, default=str),
            qos=settings.emqx_qos,
        )
        result.wait_for_publish(timeout=settings.emqx_connect_timeout_seconds)
        client.loop_stop()
        client.disconnect()
    except Exception as exc:
        return {
            "published": False,
            "provider": "emqx",
            "topic": topic_name,
            "reason": str(exc),
        }

    return {
        "published": result.is_published(),
        "provider": "emqx",
        "topic": topic_name,
        "message_id": result.mid,
        "qos": settings.emqx_qos,
    }


def new_mqtt_client(client_id: str):
    try:
        from paho.mqtt import client as mqtt
    except Exception as exc:
        raise EmqxPublishError(f"paho-mqtt client is not available: {exc}") from exc

    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    except (AttributeError, TypeError):
        client = mqtt.Client(client_id=client_id)

    if settings.emqx_username:
        client.username_pw_set(settings.emqx_username, settings.emqx_password)
    if settings.emqx_tls_enabled:
        client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
        client.tls_insecure_set(False)
    return client


def decode_event_payload(payload: bytes, fallback_event_id: str) -> dict[str, Any]:
    try:
        return json.loads(payload.decode("utf-8"))
    except json.JSONDecodeError:
        return {
            "event_id": fallback_event_id,
            "event_type": "unparseable",
            "raw": payload.decode("utf-8", errors="replace"),
        }
