from fastapi import APIRouter

from app.services.demo_data import dashboard_payload

router = APIRouter()


@router.get("/dashboard")
def get_dashboard() -> dict:
    return dashboard_payload()

