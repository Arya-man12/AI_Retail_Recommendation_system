from fastapi import APIRouter, Depends

from app.security import require_permissions
from app.services.mongo_demo_service import get_dashboard_payload

router = APIRouter()


@router.get("/dashboard")
def get_dashboard(_: dict = Depends(require_permissions({"dashboard:read"}))) -> dict:
    return get_dashboard_payload()
