from state import CriticVerdict
from llm_client import call_llm
from prompts import CRITIC_PROMPT
import sys
import json


def critic_run(architecture: dict) -> dict:
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

        # enforce exact casing — graph.py conditional edge depends on this
        response["verdict"] = response["verdict"].strip().upper()
        # response["verdict"] = "REVISE"
        if response["verdict"] not in ("APPROVE", "REVISE"):
            response["verdict"] = "REVISE"

        validated = CriticVerdict.model_validate(response)
        return validated.model_dump()
    except Exception as e:
        raise RuntimeError(f"Critic Agent failed: {e}") from e


def critic_node(state: dict) -> dict:
    """
    LangGraph node wrapper for critic_run.
    Reads from GraphState, calls critic_run, returns only the state keys it owns.
    """
    output = critic_run(architecture=state["architecture"])
    revision_count = state.get("revision_count", 0)

    if output["verdict"] == "REVISE":
        revision_count += 1 #only incrementing on revision. not everytime

    return {
        "critic_verdict": output,
        "critic_history": state.get("critic_history", []) + [output],
        "revision_count": revision_count,
    }


if __name__ == "__main__":
    from agents.requirements_agent import req_run
    from agents.techstack_agent import tech_run
    from agents.architecture_agent import arch_run

    problem = "Design a scalable notification system for 10 million users."

    if len(sys.argv) > 1:
        if sys.argv[1] == "--prompt":
            if len(sys.argv) < 3:
                print('Usage: python critic_agent.py --prompt "your problem"')
                sys.exit(1)
            problem = sys.argv[2]

    try:
        requirements = req_run(problem)
        techstack = tech_run(requirements)
        architecture = arch_run(requirements=requirements, techstack=techstack, revision_count=0)
        output = critic_run(architecture=architecture)
        print(json.dumps(output, indent=4))
    except RuntimeError as e:
        print(e)
        sys.exit(1)