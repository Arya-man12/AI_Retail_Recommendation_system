from fastapi import APIRouter, Depends, HTTPException

from app.security import require_permissions
from app.services.emqx_service import EmqxSubscribeError
from app.services.streaming_service import drain_received, insights_snapshot, subscriber_status

router = APIRouter()


@router.get("/emqx/status")
def emqx_status(_: dict = Depends(require_permissions({"streaming:read"}))) -> dict:
    return subscriber_status()


@router.post("/emqx/drain")
def emqx_drain(_: dict = Depends(require_permissions({"streaming:read"}))) -> dict:
    try:
        return drain_received()
    except EmqxSubscribeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/insights")
def live_insights(_: dict = Depends(require_permissions({"streaming:read"}))) -> dict:
    return insights_snapshot()
