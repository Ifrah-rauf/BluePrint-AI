from state import CriticVerdict
from llm_client import call_llm
from prompts import CRITIC_PROMPT
import sys
import json


def run(architecture: dict) -> dict:
    """
    Reviews an architecture and returns a verdict with specific issues.

    Args:
        architecture (dict): Output from Architecture Agent.

    Returns:
        dict: Validated critic verdict with "APPROVE" or "REVISE" and list of issues.

    Raises:
        RuntimeError: If the LLM call or validation fails.
    """
    try:
        response = call_llm(CRITIC_PROMPT, architecture)

        # enforce exact casing — pipeline.py conditional check depends on this
        response["verdict"] = response["verdict"].strip().upper()
        if response["verdict"] not in ("APPROVE", "REVISE"):
            response["verdict"] = "REVISE"

        validated = CriticVerdict.model_validate(response)
        return validated.model_dump()
    except Exception as e:
        raise RuntimeError(f"Critic Agent failed: {e}") from e


if __name__ == "__main__":
    from agents.requirements_agent import run as requirements_run
    from agents.techstack_agent import run as techstack_run
    from agents.architecture_agent import run as architecture_run

    problem = "Design a scalable notification system for 10 million users."

    if len(sys.argv) > 1:
        if sys.argv[1] == "--prompt":
            if len(sys.argv) < 3:
                print('Usage: python critic_agent.py --prompt "your problem"')
                sys.exit(1)
            problem = sys.argv[2]

    try:
        requirements = requirements_run(problem)
        techstack = techstack_run(requirements)
        architecture = architecture_run(requirements=requirements, techstack=techstack, revision_count=0)
        output = run(architecture=architecture)
        print(json.dumps(output, indent=4))
    except RuntimeError as e:
        print(e)
        sys.exit(1)