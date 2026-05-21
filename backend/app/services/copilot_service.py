from langsmith import traceable

from app.config import settings
from app.services.feature_store_service import get_customer_features
from app.services.intelligence_service import customer_360, feature_explanation
from app.services.ml_service import forecast_revenue, recommend_products
from app.services.openrouter_service import OpenRouterError, complete_with_openrouter
from app.services.policy_guardrails import evaluate_prompt
from app.services.retail_intelligence_service import basket_analysis, churn_risk, customer_behavior, demand_forecast, review_intelligence
from app.services.spark_processing import clean_events, sample_raw_events, spark_status


ALLOWED_TOOLS_BY_ROLE = {
    "marketing_analyst": [
        "forecast",
        "recommendation",
        "explainability",
        "features",
        "behavior",
        "churn",
        "basket",
        "demand",
        "reviews",
        "processing",
    ],
    "admin": [
        "forecast",
        "recommendation",
        "explainability",
        "features",
        "behavior",
        "churn",
        "basket",
        "demand",
        "reviews",
        "customer360",
        "processing",
    ],
}

TOOL_ALIASES = {
    "forecast": ("forecast", "next", "predict", "revenue"),
    "recommendation": ("recommend", "product", "bundle", "offer"),
    "explainability": ("why", "explain", "driver", "attribution", "influence"),
    "features": ("feature", "redis", "rfm", "recency", "frequency", "monetary"),
    "behavior": ("behaviour", "behavior", "buying pattern", "preferred categor", "purchase frequency"),
    "churn": ("churn", "retention", "disengage", "risk"),
    "basket": ("basket", "frequently bought", "purchased together", "combination", "affinity"),
    "demand": ("demand", "inventory", "stock", "shortage", "seasonal"),
    "reviews": ("review", "sentiment", "feedback", "rating"),
    "processing": ("spark", "pyspark", "clean", "processing", "event", "pipeline", "etl"),
    "customer360": ("graph", "relationship", "customer 360", "customer"),
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

    allowed_tools = ALLOWED_TOOLS_BY_ROLE.get(role, [])
    requested_tools = _select_tools(question)
    authorized = [tool for tool in requested_tools if tool in allowed_tools] or allowed_tools[:3]
    tool_outputs = _run_tools(authorized, question)

    messages = [
        {
            "role": "system",
            "content": (
                "You are the governed customer intelligence copilot for an ecommerce analytics platform. "
                "Use only the supplied tool evidence. Be concise, business-focused, and avoid exposing raw PII. "
                "If evidence is incomplete, state what is missing."
            ),
        },
        {
            "role": "user",
            "content": (
                f"User role: {role}\n"
                f"Question: {question}\n"
                f"Authorized tools: {authorized}\n"
                f"Policy decision: {policy_decision.as_dict()}\n"
                f"Tool evidence: {tool_outputs}\n"
                "Answer the question for an internal business user."
            ),
        },
    ]

    try:
        llm_response = complete_with_openrouter(messages)
        answer = llm_response["content"]
        provider = llm_response["provider"]
        model = llm_response["model"]
        usage = llm_response["usage"]
    except OpenRouterError as exc:
        answer = _local_answer(question, tool_outputs, str(exc))
        provider = "local_governed_fallback"
        model = "deterministic_tool_summary"
        usage = {"fallback_reason": str(exc)}

    return {
        "answer": answer,
        "tools_used": authorized,
        "trace_enabled": settings.langsmith_tracing,
        "policy_decision": policy_decision.as_dict(),
        "tool_outputs": tool_outputs,
        "llm_provider": provider,
        "llm_model": model,
        "llm_usage": usage,
    }


def _select_tools(question: str) -> list[str]:
    lower_question = question.lower()
    selected = []
    for tool, aliases in TOOL_ALIASES.items():
        if any(alias in lower_question for alias in aliases):
            selected.append(tool)
    return selected


def _run_tools(tools: list[str], question: str) -> dict:
    outputs = {}
    if "forecast" in tools:
        outputs["forecast"] = forecast_revenue([220, 236, 251, 268, 294, 318])
    if "recommendation" in tools:
        outputs["recommendation"] = recommend_products(
            customer_id="demo-customer-001",
            segment="High-LTV wellness buyer",
            recent_categories=["wellness", "smart home"],
        )
    if "explainability" in tools:
        outputs["explainability"] = feature_explanation()
    if "features" in tools:
        outputs["features"] = get_customer_features("cust-maya-chen")
    if "behavior" in tools:
        outputs["behavior"] = customer_behavior("cust-maya-chen")
    if "churn" in tools:
        outputs["churn"] = churn_risk("cust-maya-chen")
    if "basket" in tools:
        outputs["basket"] = basket_analysis()
    if "demand" in tools:
        outputs["demand"] = demand_forecast(periods=7)
    if "reviews" in tools:
        outputs["reviews"] = review_intelligence()
    if "processing" in tools:
        outputs["processing"] = {
            "spark": spark_status(),
            "sample_cleaning": clean_events(sample_raw_events(), engine="auto"),
        }
    if "customer360" in tools:
        outputs["customer360"] = customer_360()
    return outputs


def _local_answer(question: str, tool_outputs: dict, fallback_reason: str) -> str:
    parts = [f"I used the governed tools available for: {question}"]
    forecast = tool_outputs.get("forecast")
    if forecast:
        parts.append(
            f"Revenue is projected at ${forecast['prediction']:,.2f} with {forecast['confidence']:.0%} confidence."
        )
    recommendation = tool_outputs.get("recommendation")
    if recommendation:
        top = recommendation["recommendations"][0]
        parts.append(f"The top recommendation is {top['product']} with a {top['score']:.0%} affinity score.")
    explanation = tool_outputs.get("explainability")
    if explanation:
        driver = explanation["features"][0]
        parts.append(f"The strongest explanation driver is {driver['name']} ({driver['impact']:+.2f}).")
    processing = tool_outputs.get("processing")
    if processing:
        cleaned = processing["sample_cleaning"]
        parts.append(
            f"The processing pipeline used {cleaned['engine']} and retained {cleaned['clean_count']} of {cleaned['input_count']} sample events."
        )
    graph = tool_outputs.get("customer360")
    if graph:
        parts.append(f"Customer 360 currently shows {graph['relationship_count']} demo relationships.")
    features = tool_outputs.get("features")
    if features and features.get("features"):
        parts.append(f"Feature store source: {features['source']}.")
    churn = tool_outputs.get("churn")
    if churn:
        score = churn["churn"]
        parts.append(
            f"Current churn risk is {score['percent']:.1f}% ({score['risk_band']}), based on {churn['feature_source']} features."
        )
    basket = tool_outputs.get("basket")
    if basket:
        parts.append(f"Basket analysis found {len(basket['pairs'])} product affinities across {basket['basket_count']} baskets.")
    demand = tool_outputs.get("demand")
    if demand:
        parts.append(f"Demand forecasting returned {len(demand['forecasts'])} product forecasts.")
    reviews = tool_outputs.get("reviews")
    if reviews:
        parts.append(f"Review intelligence analyzed {reviews['review_count']} reviews.")
    parts.append(f"LLM fallback was used because: {fallback_reason}")
    return " ".join(parts)
