from langsmith import traceable

from app.config import settings
from app.services.ml_service import forecast_revenue, recommend_products
from app.services.policy_guardrails import evaluate_prompt
from app.services.vector_service import search_similar_products


ALLOWED_TOOLS_BY_ROLE = {
    "marketing_analyst": ["forecast", "recommendation", "shap", "geo"],
    "admin": ["forecast", "recommendation", "shap", "neo4j", "geo"],
}


@traceable(name="customer_intelligence_copilot")
def answer_question(question: str, role: str) -> dict:
    policy_decision = evaluate_prompt(question, role)
    if not policy_decision.allowed:
        return {
            "answer": "I cannot complete that request because it violates the configured policy guardrails.",
            "tools_used": [],
            "trace_enabled": settings.langsmith_tracing,
            "policy_decision": policy_decision.as_dict(),
        }

    tools = ALLOWED_TOOLS_BY_ROLE.get(role, [])
    lower_question = question.lower()
    used = []

    if "forecast" in lower_question or "next" in lower_question:
        used.append("forecast")
    if "recommend" in lower_question or "product" in lower_question:
        used.append("recommendation")
    if "why" in lower_question or "explain" in lower_question:
        used.append("shap")
    if "region" in lower_question or "northeast" in lower_question or "geo" in lower_question:
        used.append("geo")
    if "graph" in lower_question or "relationship" in lower_question:
        used.append("neo4j")

    authorized = [tool for tool in used if tool in tools] or tools[:2]
    tool_outputs = {}
    if "forecast" in authorized:
        tool_outputs["forecast"] = forecast_revenue([220, 236, 251, 268, 294, 318])
    if "recommendation" in authorized:
        tool_outputs["recommendation"] = recommend_products(
            customer_id="demo-customer-001",
            segment="High-LTV wellness buyer",
            recent_categories=["wellness", "smart home"],
        )
    if "geo" in authorized or "recommendation" in authorized:
        tool_outputs["vector_search"] = search_similar_products(question, limit=3)

    answer = (
        "The governed analysis points to recent category engagement, regional demand, "
        "and campaign response as the strongest drivers. I would prioritize premium bundles "
        "in the Northeast, monitor inventory for the top recommended SKUs, and keep the SHAP "
        "drivers visible before approving automated outreach. "
        f"Policy status: {policy_decision.reason}. Tool evidence keys: {', '.join(tool_outputs) or 'none'}."
    )

    return {
        "answer": answer,
        "tools_used": authorized,
        "trace_enabled": settings.langsmith_tracing,
        "policy_decision": policy_decision.as_dict(),
    }

