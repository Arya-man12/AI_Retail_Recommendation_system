from collections.abc import Iterable

from fastapi import Depends, Header, HTTPException

from app.config import settings
from app.services.auth_service import AuthError, ROLE_PERMISSIONS, decode_access_token


def current_user(
    authorization: str | None = Header(default=None),
    x_user_role: str = Header(default="viewer"),
) -> dict:
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(status_code=401, detail="Use a Bearer token")
        try:
            return decode_access_token(token)
        except AuthError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

    if settings.auth_required:
        raise HTTPException(status_code=401, detail="Authentication is required")

    role = x_user_role if x_user_role in ROLE_PERMISSIONS else "viewer"
    return {
        "email": "local-dev@example.com",
        "role": role,
        "permissions": sorted(ROLE_PERMISSIONS.get(role, set())),
    }


def require_permissions(required: Iterable[str]):
    required_set = set(required)

    def dependency(user: dict = Depends(current_user)) -> dict:
        permissions = set(user.get("permissions", []))
        if not required_set.issubset(permissions):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return dependency


def require_roles(roles: Iterable[str]):
    allowed = set(roles)

    def dependency(user: dict = Depends(current_user)) -> dict:
        if user.get("role") not in allowed:
            raise HTTPException(status_code=403, detail="Role is not allowed")
        return user

    return dependency
