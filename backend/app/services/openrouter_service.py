import json
import urllib.error
import urllib.request
from typing import Any

from app.config import settings


class OpenRouterError(RuntimeError):
    pass


def complete_with_openrouter(messages: list[dict[str, str]]) -> dict[str, Any]:
    if not settings.openrouter_api_key:
        raise OpenRouterError("OPENROUTER_API_KEY is not configured")

    url = f"{settings.openrouter_base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": settings.openrouter_model,
        "messages": messages,
        "temperature": settings.openrouter_temperature,
        "max_tokens": settings.openrouter_max_tokens,
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": settings.openrouter_site_url,
            "X-Title": settings.openrouter_app_name,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=settings.openrouter_timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise OpenRouterError(f"OpenRouter request failed with HTTP {exc.code}: {detail}") from exc
    except Exception as exc:
        raise OpenRouterError(f"OpenRouter request failed: {exc}") from exc

    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise OpenRouterError(f"OpenRouter response did not include a chat message: {body}") from exc

    return {
        "content": content,
        "model": body.get("model", settings.openrouter_model),
        "usage": body.get("usage", {}),
        "provider": "openrouter",
    }

