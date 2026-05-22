from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any

from app.config import settings


ROLE_PERMISSIONS = {
    "customer": {"ecommerce:read", "ecommerce:write"},
    "viewer": {"dashboard:read", "ecommerce:read", "features:read", "graph:read", "intelligence:read", "ml:read", "streaming:read"},
    "marketing_analyst": {
        "dashboard:read",
        "ecommerce:read",
        "intelligence:read",
        "ml:read",
        "copilot:use",
        "features:read",
        "graph:read",
        "streaming:read",
    },
    "admin": {
        "dashboard:read",
        "ecommerce:read",
        "ecommerce:write",
        "intelligence:read",
        "ml:read",
        "ml:write",
        "copilot:use",
        "features:read",
        "features:write",
        "graph:read",
        "graph:write",
        "streaming:read",
        "ops:read",
    },
}

REGISTRATION_ROLES = {
    "dashboard": "marketing_analyst",
    "shop": "customer",
}

_fallback_registered_users: dict[str, dict[str, Any]] = {}


class AuthError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def get_mongo_client():
    try:
        from pymongo import MongoClient
    except Exception as exc:
        raise AuthError(f"pymongo is not available: {exc}") from exc

    return MongoClient(
        settings.mongodb_uri,
        serverSelectionTimeoutMS=2000,
        connectTimeoutMS=2000,
        socketTimeoutMS=2000,
    )


def auth_status() -> dict:
    try:
        client = get_mongo_client()
        client.admin.command("ping")
    except Exception as exc:
        return {
            "provider": "mongodb",
            "auth_required": settings.auth_required,
            "connected": False,
            "database": settings.mongodb_database,
            "error": str(exc),
            "fallback": "bootstrap_user_only",
        }

    return {
        "provider": "mongodb",
        "auth_required": settings.auth_required,
        "connected": True,
        "database": settings.mongodb_database,
        "roles": {role: sorted(permissions) for role, permissions in ROLE_PERMISSIONS.items()},
    }


def authenticate_user(email: str, password: str) -> dict:
    user = _find_user(email)
    if not user or not verify_password(password, user["password_hash"]):
        raise AuthError("Invalid email or password")

    return _public_user(user)


def register_user(email: str, password: str, site: str) -> dict:
    normalized_email = email.strip().lower()
    normalized_site = site.strip().lower()
    role = REGISTRATION_ROLES.get(normalized_site)
    if not role:
        raise AuthError("Registration site must be dashboard or shop")
    if _find_user(normalized_email):
        raise AuthError("An account with that email already exists")

    now = datetime.now(UTC)
    user = {
        "email": normalized_email,
        "customer_id": _customer_id_from_email(normalized_email) if role == "customer" else None,
        "password_hash": hash_password(password),
        "role": role,
        "website": normalized_site,
        "permissions": sorted(ROLE_PERMISSIONS.get(role, set())),
        "created_at": now,
    }

    try:
        db = get_mongo_client()[settings.mongodb_database]
        db.users.create_index("email", unique=True)
        db.users.insert_one(user)
    except Exception as exc:
        if "duplicate" in str(exc).lower():
            raise AuthError("An account with that email already exists") from exc
        _fallback_registered_users[normalized_email] = user

    return _public_user(user)


def create_access_token(user: dict) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": user["email"],
        "role": user["role"],
        "customer_id": user.get("customer_id"),
        "iss": settings.auth_jwt_issuer,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.auth_token_ttl_minutes)).timestamp()),
    }
    header = {"alg": "HS256", "typ": "JWT"}
    signing_input = f"{_b64_json(header)}.{_b64_json(payload)}"
    signature = _sign(signing_input)
    return f"{signing_input}.{signature}"


def decode_access_token(token: str) -> dict:
    try:
        header_b64, payload_b64, signature = token.split(".", 2)
    except ValueError as exc:
        raise AuthError("Invalid bearer token") from exc

    signing_input = f"{header_b64}.{payload_b64}"
    if not hmac.compare_digest(_sign(signing_input), signature):
        raise AuthError("Invalid token signature")

    payload = _decode_b64_json(payload_b64)
    if payload.get("iss") != settings.auth_jwt_issuer:
        raise AuthError("Invalid token issuer")
    if int(payload.get("exp", 0)) < int(datetime.now(UTC).timestamp()):
        raise AuthError("Token has expired")

    role = payload.get("role", "viewer")
    return {
        "email": payload.get("sub"),
        "role": role,
        "customer_id": payload.get("customer_id"),
        "permissions": sorted(ROLE_PERMISSIONS.get(role, set())),
    }


def list_customer_accounts() -> dict:
    users = []
    db = None
    try:
        db = get_mongo_client()[settings.mongodb_database]
        users = list(db.users.find({"role": "customer"}, {"_id": False, "password_hash": False}).sort("created_at", -1))
    except Exception:
        users = [user for user in _fallback_registered_users.values() if user.get("role") == "customer"]

    customers = [_customer_option_from_user(user, db=db) for user in users]
    return {
        "customers": customers,
        "count": len(customers),
    }


def seed_bootstrap_users() -> dict:
    users = _bootstrap_users()
    created = []
    source = "mongodb"

    try:
        db = get_mongo_client()[settings.mongodb_database]
        db.users.create_index("email", unique=True)
        for user in users:
            db.users.update_one({"email": user["email"]}, {"$setOnInsert": user}, upsert=True)
            created.append({"email": user["email"], "role": user["role"]})
    except Exception:
        source = "bootstrap_fallback"
        created = [{"email": user["email"], "role": user["role"]} for user in users]

    return {
        "users": created,
        "source": source,
    }


def seed_bootstrap_admin() -> dict:
    return seed_bootstrap_users()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 210_000)
    return f"pbkdf2_sha256${salt}${base64.urlsafe_b64encode(digest).decode('ascii')}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, salt, digest = password_hash.split("$", 2)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 210_000)
    return hmac.compare_digest(base64.urlsafe_b64encode(candidate).decode("ascii"), digest)


def _find_user(email: str) -> dict[str, Any] | None:
    normalized = email.strip().lower()
    try:
        db = get_mongo_client()[settings.mongodb_database]
        user = db.users.find_one({"email": normalized}, {"_id": False})
        if user:
            return user
    except Exception:
        pass

    for user in _bootstrap_users():
        if normalized == user["email"]:
            return user
    if normalized in _fallback_registered_users:
        return _fallback_registered_users[normalized]
    return None


def _public_user(user: dict[str, Any]) -> dict:
    return {
        "email": user["email"],
        "customer_id": user.get("customer_id"),
        "role": user["role"],
        "permissions": sorted(ROLE_PERMISSIONS.get(user["role"], set())),
    }


def _bootstrap_users() -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    configured = [
        {
            "email": settings.bootstrap_admin_email,
            "password": settings.bootstrap_admin_password,
            "role": settings.bootstrap_admin_role,
            "website": "admin",
        },
        {
            "email": settings.seed_dashboard_email,
            "password": settings.seed_dashboard_password,
            "role": settings.seed_dashboard_role,
            "website": "dashboard",
        },
        {
            "email": settings.seed_shop_email,
            "password": settings.seed_shop_password,
            "role": settings.seed_shop_role,
            "website": "shop",
            "customer_id": "customer-demo-001",
        },
    ]
    users = []
    seen = set()
    for item in configured:
        email = item["email"].lower()
        if email in seen:
            continue
        seen.add(email)
        users.append(
            {
                "email": email,
                "customer_id": item.get("customer_id"),
                "password_hash": hash_password(item["password"]),
                "role": item["role"],
                "website": item["website"],
                "permissions": sorted(ROLE_PERMISSIONS.get(item["role"], set())),
                "created_at": now,
            }
        )
    return users


def _customer_id_from_email(email: str) -> str:
    local = email.split("@", 1)[0]
    cleaned = "".join(character if character.isalnum() else "-" for character in local.lower()).strip("-")
    return f"cust-{cleaned or secrets.token_hex(4)}"


def _customer_option_from_user(user: dict[str, Any], db=None) -> dict:
    customer_id = user.get("customer_id") or _customer_id_from_email(user["email"])
    label = user["email"].split("@", 1)[0].replace(".", " ").replace("-", " ").replace("_", " ").title()
    order_profile = _customer_order_profile(customer_id, db)
    return {
        "id": customer_id,
        "label": label,
        "email": user["email"],
        "segment": order_profile["segment"],
        "recentCategories": order_profile["recent_categories"],
        "revenueHistory": order_profile["revenue_history"],
        "orderCount": order_profile["order_count"],
        "latestRecommendations": order_profile["latest_recommendations"],
    }


def _customer_order_profile(customer_id: str, db=None) -> dict:
    default_profile = {
        "segment": "Registered customer",
        "recent_categories": [],
        "revenue_history": [],
        "order_count": 0,
        "latest_recommendations": [],
    }
    if db is None:
        return default_profile

    try:
        orders = list(db.orders.find({"customer_id": customer_id}, {"_id": False}).sort("created_at", -1).limit(12))
    except Exception:
        return default_profile

    if not orders:
        return default_profile

    categories = []
    for order in orders:
        category = order.get("category") or order.get("product", {}).get("category")
        if category and category not in categories:
            categories.append(category)

    revenue_values = []
    for order in reversed(orders[:6]):
        revenue = _float_value(order.get("revenue", order.get("total", 0)))
        if revenue > 0:
            revenue_values.append(round(revenue, 2))

    latest = orders[0]
    return {
        "segment": _segment_from_orders(orders, categories),
        "recent_categories": categories[:4],
        "revenue_history": revenue_values,
        "order_count": len(orders),
        "latest_recommendations": latest.get("recommendations", []),
    }


def _segment_from_orders(orders: list[dict[str, Any]], categories: list[str]) -> str:
    if len(orders) >= 5:
        return "Loyal repeat buyer"
    if "wellness" in categories:
        return "Wellness shopper"
    if "commuter" in categories:
        return "Commuter shopper"
    if "smart home" in categories:
        return "Smart home shopper"
    return "Active shopper"


def _float_value(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _b64_json(payload: dict) -> str:
    return _b64(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))


def _decode_b64_json(value: str) -> dict:
    padding = "=" * (-len(value) % 4)
    return json.loads(base64.urlsafe_b64decode(f"{value}{padding}").decode("utf-8"))


def _sign(signing_input: str) -> str:
    digest = hmac.new(settings.auth_jwt_secret.encode("utf-8"), signing_input.encode("utf-8"), hashlib.sha256).digest()
    return _b64(digest)


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
