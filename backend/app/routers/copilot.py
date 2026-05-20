from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.services.copilot_service import answer_question

router = APIRouter()


class CopilotQuestion(BaseModel):
    question: str = Field(min_length=3, max_length=1000)


class CopilotAnswer(BaseModel):
    answer: str
    tools_used: list[str]
    trace_enabled: bool
    policy_decision: dict


@router.post("/ask", response_model=CopilotAnswer)
def ask_copilot(payload: CopilotQuestion, x_user_role: str = Header(default="viewer")) -> CopilotAnswer:
    if x_user_role not in {"marketing_analyst", "admin"}:
        raise HTTPException(status_code=403, detail="Role is not allowed to use copilot tools")

    result = answer_question(payload.question, role=x_user_role)
    return CopilotAnswer(**result)
