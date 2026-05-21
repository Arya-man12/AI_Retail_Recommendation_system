from fastapi import APIRouter, Depends, HTTPException

from app.security import require_permissions
from app.services.graph_service import GraphServiceError, customer_graph, graph_status, seed_demo_graph

router = APIRouter()


@router.get("/status")
def status() -> dict:
    return graph_status()


@router.post("/seed")
def seed(_: dict = Depends(require_permissions({"graph:write"}))) -> dict:
    try:
        return seed_demo_graph()
    except GraphServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Unable to seed Neo4j graph: {exc}") from exc


@router.get("/customers/{customer_id}")
def customer(customer_id: str, _: dict = Depends(require_permissions({"graph:read"}))) -> dict:
    return customer_graph(customer_id)
