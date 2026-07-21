from __future__ import annotations

import json
import re
from typing import Any

from llm_client import call_llm
from prompts import INTENT_PROMPT


def _extract_json_like_answer(response: dict[str, Any]) -> dict[str, Any]:
    return {
        "intent": response.get("intent") or "ambiguous",
        "understanding": response.get("understanding") or "I understand your request.",
        "generate": bool(response.get("generate", False)),
        "question": response.get("question") or "Do you want me to generate the design now? (yes/no)",
    }


def preflight_run(user_input: str) -> dict[str, Any]:
    """
    Understand the user's request before routing it to the design graph.
    This step never generates the architecture itself.
    """
    try:
        response = call_llm(
            INTENT_PROMPT,
            {
                "user_input": user_input,
            },
        )
        return _extract_json_like_answer(response)
    except Exception:
        lowered = user_input.lower()
        if any(term in lowered for term in ("document", "documents", "file", "files", "upload", "attachment")):
            return {
                "intent": "document_lookup",
                "understanding": "You want me to search your attached documents.",
                "generate": False,
                "question": "Do you want me to search the documents now? (yes/no)",
            }
        if any(term in lowered for term in ("architecture", "architectural", "design", "blueprint", "system")):
            return {
                "intent": "architecture_generation",
                "understanding": "You want me to generate a system design for your request.",
                "generate": False,
                "question": "Do you want me to generate the design now? (yes/no)",
            }
        return {
            "intent": "ambiguous",
            "understanding": "I’m not fully sure what you want yet.",
            "generate": False,
            "question": "Can you clarify the request?",
        }


def is_affirmative(user_input: str) -> bool:
    text = user_input.strip().lower()
    if not text:
        return False

    yes_patterns = (
        r"^(yes|yep|yeah|y|sure|ok|okay)\b",
        r"\bgo ahead\b",
        r"\bgenerate\b",
        r"\bproceed\b",
        r"\bdo it\b",
        r"\brun it\b",
    )
    return any(re.search(pattern, text) for pattern in yes_patterns)


def is_negative(user_input: str) -> bool:
    text = user_input.strip().lower()
    if not text:
        return False

    no_patterns = (
        r"^(no|nope|n)\b",
        r"\bnot now\b",
        r"\blater\b",
        r"\bstop\b",
        r"\bdon't\b",
        r"\bdo not\b",
    )
    return any(re.search(pattern, text) for pattern in no_patterns)
