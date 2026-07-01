from state import TechStackOutput
from llm_client import call_llm
from prompts import TECHSTACK_PROMPT
import sys
import json
#run fuction
def run(requirements: dict) -> dict:
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
        response = call_llm(
            TECHSTACK_PROMPT,
            requirements,
        )
        validated = TechStackOutput.model_validate(response)
        return validated.model_dump()
    except Exception as e:
        raise RuntimeError(
            f"Tech Stack Agent failed: {e}"
        ) from e
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
        output = run(sample_requirements)
        print(json.dumps(output, indent=4))
    except RuntimeError as e:
        print(e)
        sys.exit(1)