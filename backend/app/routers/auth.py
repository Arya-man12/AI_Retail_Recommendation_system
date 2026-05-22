from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from app.security import current_user, require_roles
from app.services.auth_service import (
    AuthError,
    auth_status,
    authenticate_user,
    create_access_token,
    list_customer_accounts,
    register_user,
    seed_bootstrap_admin,
    seed_bootstrap_users,
)

router = APIRouter()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)


class RegistrationRequest(LoginRequest):
    site: str = Field(pattern="^(dashboard|shop)$")


@router.get("/status")
def status() -> dict:
    return auth_status()


@router.post("/login")
def login(payload: LoginRequest) -> dict:
    try:
        user = authenticate_user(payload.email, payload.password)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    return {
        "access_token": create_access_token(user),
        "token_type": "bearer",
        "user": user,
    }


@router.post("/register")
def register(payload: RegistrationRequest) -> dict:
    try:
        user = register_user(payload.email, payload.password, payload.site)
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "access_token": create_access_token(user),
        "token_type": "bearer",
        "user": user,
    }


@router.get("/me")
def me(user: dict = Depends(current_user)) -> dict:
    return user


@router.get("/customers")
def customers(_: dict = Depends(current_user)) -> dict:
    return list_customer_accounts()


@router.post("/bootstrap-admin")
def bootstrap_admin(_: dict = Depends(require_roles({"admin"}))) -> dict:
    return seed_bootstrap_admin()


@router.post("/seed-users")
def seed_users(_: dict = Depends(require_roles({"admin"}))) -> dict:
    return seed_bootstrap_users()
