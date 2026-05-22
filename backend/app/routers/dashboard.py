from fastapi import APIRouter, Depends, HTTPException

from app.security import require_permissions
from app.services.mongo_demo_service import DashboardDataError, get_dashboard_payload

router = APIRouter()


@router.get("/dashboard")
def get_dashboard(_: dict = Depends(require_permissions({"dashboard:read"}))) -> dict:
    try:
        return get_dashboard_payload()
    except DashboardDataError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
