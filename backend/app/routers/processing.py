from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.security import require_permissions
from app.services.spark_processing import clean_events, sample_raw_events, spark_start_check, spark_status

router = APIRouter()


class RawEvent(BaseModel):
    event_id: str
    customer_id: str | None = None
    product_id: str | None = None
    event_type: str
    event_time: str
    quantity: int | None = None
    price: float | None = None
    lat: float | None = None
    lon: float | None = None


class CleaningRequest(BaseModel):
    events: list[RawEvent] = Field(min_length=1, max_length=500)
    engine: Literal["auto", "spark", "python"] = "auto"


@router.get("/spark/status")
def get_spark_status(_: dict = Depends(require_permissions({"ops:read"}))) -> dict:
    return spark_status()


@router.get("/spark/start-check")
def check_spark_startup(_: dict = Depends(require_permissions({"ops:read"}))) -> dict:
    return spark_start_check()


@router.get("/sample-events")
def get_sample_events(_: dict = Depends(require_permissions({"ops:read"}))) -> dict:
    return {"events": sample_raw_events()}


@router.post("/clean-events")
def clean_raw_events(payload: CleaningRequest, _: dict = Depends(require_permissions({"ops:read"}))) -> dict:
    events = [event.model_dump() for event in payload.events]
    return clean_events(events, engine=payload.engine)
