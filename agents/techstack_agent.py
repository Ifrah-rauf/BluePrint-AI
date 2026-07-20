from state import TechStackOutput, DesignState
from llm_client import call_llm
from prompts import TECHSTACK_PROMPT
from rag.query import build_combined_rag_context
import sys
import json
#run fuction
def tech_run(
    requirements: dict,
    collection: str | None = "system_design",
    user_id: str | None = None,
    profile_id: int | None = None,
    session_id: str | None = None,
) -> dict:
    """
    Recommend a technology stack based on structured requirements.
    Args:
        requirements (dict): Output from Requirements Agent.
    Returns:
        dict: Validated tech stack recommendation.
    Raises:
        RuntimeError: If the LLM call or validation fails.
    """
    try:
        rag_context = build_combined_rag_context(
            user_query=json.dumps(requirements, ensure_ascii=False),
            user_id=user_id,
            profile_id=profile_id,
            session_id=session_id,
        )
        response = call_llm(
            TECHSTACK_PROMPT,
            {
                "requirements": requirements,
                "rag_context": rag_context,
            },
        )
        validated = TechStackOutput.model_validate(response)
        return validated.model_dump()
    except Exception as e:
        raise RuntimeError(
            f"Tech Stack Agent failed: {e}"
        ) from e
        
def techstack_node(state: DesignState) -> dict:
    """
    LangGraph wrapper for the Tech Stack Agent.

    Reads:
        state["requirements"]

    Writes:
        state["techstack"]
    """
    techstack = tech_run(
        state["requirements"],
        user_id=state.get("user_id"),
        profile_id=state.get("profile_id"),
        session_id=state.get("session_id"),
    )

    return {
        "techstack": techstack
    }

#test block
if __name__ == "__main__":
    sample_requirements = {
        "functional_requirements": [
            "URL shortening",
            "URL redirection"
        ],
        "non_functional_requirements": [
            "High availability",
            "Low latency"
        ],
        "scale": "100M users",
        "constraints": [],
        "assumptions": []
    }
    try:
        output = tech_run(sample_requirements)
        print(json.dumps(output, indent=4))
    except RuntimeError as e:
        print(e)
        sys.exit(1)
