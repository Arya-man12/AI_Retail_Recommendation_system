from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.security import require_roles
from app.services.copilot_service import answer_question
from app.services.openrouter_service import OpenRouterError

router = APIRouter()


class CopilotQuestion(BaseModel):
    question: str = Field(min_length=3, max_length=1000)


class CopilotAnswer(BaseModel):
    answer: str
    tools_used: list[str]
    trace_enabled: bool
    policy_decision: dict
    tool_outputs: dict | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_usage: dict | None = None


@router.post("/ask", response_model=CopilotAnswer)
def ask_copilot(
    payload: CopilotQuestion,
    user: dict = Depends(require_roles({"marketing_analyst", "admin"})),
) -> CopilotAnswer:
    try:
        result = answer_question(payload.question, role=user["role"])
    except OpenRouterError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return CopilotAnswer(**result)
