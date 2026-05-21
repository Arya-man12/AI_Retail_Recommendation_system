import threading

from app.config import settings
from app.services.emqx_service import decode_event_payload, new_mqtt_client
from app.services.insight_engine import get_live_insights, process_event


class EmqxInsightSubscriber:
    def __init__(self) -> None:
        self._client = None
        self._lock = threading.Lock()
        self._buffer: list[dict] = []
        self.last_error: str | None = None
        self.last_batch: dict | None = None
        self.messages_seen = 0

    def start(self) -> dict:
        if not settings.enable_emqx_subscriber:
            return {"running": False, "reason": "ENABLE_EMQX_SUBSCRIBER is false"}
        if self.is_running:
            return self.status()

        try:
            self._client = new_mqtt_client(f"{settings.emqx_client_id}-subscriber")
            self._client.on_connect = self._on_connect
            self._client.on_message = self._on_message
            self._client.connect(settings.emqx_host, settings.emqx_port, settings.emqx_keepalive_seconds)
            self._client.loop_start()
            self.last_error = None
            return self.status()
        except Exception as exc:
            self._client = None
            self.last_error = str(exc)
            return self.status()

    def stop(self) -> dict:
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            self._client = None
        return self.status()

    @property
    def is_running(self) -> bool:
        return self._client is not None

    def status(self) -> dict:
        return {
            "running": self.is_running,
            "enabled": settings.enable_emqx_subscriber,
            "provider": "emqx",
            "host": settings.emqx_host,
            "port": settings.emqx_port,
            "topics": [
                settings.emqx_ecommerce_topic,
                settings.emqx_purchase_topic,
            ],
            "qos": settings.emqx_qos,
            "messages_seen": self.messages_seen,
            "last_error": self.last_error,
            "last_batch": self.last_batch,
        }

    def drain_received(self) -> dict:
        with self._lock:
            events = list(self._buffer)
            self._buffer.clear()
        self.last_batch = {
            "provider": "emqx",
            "drained": len(events),
            "events": events,
        }
        return self.last_batch

    def _on_connect(self, client, userdata, flags, reason_code, properties=None) -> None:
        del userdata, flags, properties
        is_failure = getattr(reason_code, "is_failure", False)
        failed = is_failure() if callable(is_failure) else bool(is_failure)
        if failed or (reason_code != 0 and str(reason_code) != "Success"):
            self.last_error = f"EMQX connection failed with code {reason_code}"
            return
        for topic in [settings.emqx_ecommerce_topic, settings.emqx_purchase_topic]:
            client.subscribe(topic, qos=settings.emqx_qos)

    def _on_message(self, client, userdata, message) -> None:
        del client, userdata
        event = decode_event_payload(message.payload, fallback_event_id=f"mqtt-{message.mid}")
        result = process_event(event, source=f"emqx:{message.topic}")
        with self._lock:
            self.messages_seen += 1
            self._buffer.append(
                {
                    "topic": message.topic,
                    "qos": message.qos,
                    "event": result["event"],
                    "insights": result["insights"],
                }
            )


subscriber = EmqxInsightSubscriber()


def start_subscriber_if_enabled() -> dict:
    return subscriber.start()


def stop_subscriber() -> dict:
    return subscriber.stop()


def subscriber_status() -> dict:
    return subscriber.status()


def drain_received() -> dict:
    return subscriber.drain_received()


def insights_snapshot() -> dict:
    return get_live_insights()
