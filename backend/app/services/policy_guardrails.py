import re
from dataclasses import dataclass

from app.config import settings


PII_PATTERNS = {
    "email": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    "phone": re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "card": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
}

SENSITIVE_TERMS = {
    "export customer emails",
    "show raw pii",
    "ignore rbac",
    "bypass policy",
    "leak prompt",
}


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str
    checks: list[str]

    def as_dict(self) -> dict:
        return {"allowed": self.allowed, "reason": self.reason, "checks": self.checks}


def evaluate_prompt(question: str, role: str) -> PolicyDecision:
    checks = ["role_present", "prompt_length"]
    normalized = question.lower()

    if settings.policy_block_pii:
        for name, pattern in PII_PATTERNS.items():
            if pattern.search(question):
                return PolicyDecision(False, f"Blocked possible {name} in prompt", checks + ["pii_block"])
        checks.append("pii_block")

    if any(term in normalized for term in SENSITIVE_TERMS):
        return PolicyDecision(False, "Blocked sensitive data or policy bypass request", checks + ["sensitive_intent"])
    checks.append("sensitive_intent")

    if settings.policy_require_tool_rbac and role not in {"marketing_analyst", "admin"}:
        return PolicyDecision(False, "Role is not authorized for copilot tools", checks + ["tool_rbac"])
    checks.append("tool_rbac")

    return PolicyDecision(True, "Allowed", checks)

