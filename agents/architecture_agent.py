from state import ArchitectureOutput
from llm_client import call_llm
from prompts import ARCHITECTURE_PROMPT
import sys
import json


def arch_run(
    requirements: dict,
    techstack: dict,
    revision_notes: list | None = None,
    revision_count: int = 0,
) -> dict:
    """
    Produces a component-level architecture from requirements and tech stack.
    On revision loops, accepts revision_notes from the Critic Agent.

    Args:
        requirements (dict): Output from Requirements Agent.
        techstack (dict): Output from Tech Stack Agent.
        revision_notes (list | None): Issues from Critic Agent, passed only on revision loops.
        revision_count (int): Owned by pipeline.py — passed through unchanged.

    Returns:
        dict: Validated architecture dictionary.

    Raises:
        RuntimeError: If the LLM call or validation fails.
    """
    try:
        response = call_llm(
            ARCHITECTURE_PROMPT,
            requirements,
            techstack,
            revision_notes,
        )
        response["revision_count"] = revision_count
        validated = ArchitectureOutput.model_validate(response)
        return validated.model_dump()
    except Exception as e:
        raise RuntimeError(f"Architecture Agent failed: {e}") from e


if __name__ == "__main__":
    from agents.requirements_agent import run as requirements_run
    from agents.techstack_agent import run as techstack_run

    problem = "Design a scalable notification system for 10 million users."

    if len(sys.argv) > 1:
        if sys.argv[1] == "--prompt":
            if len(sys.argv) < 3:
                print('Usage: python architecture_agent.py --prompt "your problem"')
                sys.exit(1)
            problem = sys.argv[2]

    try:
        requirements = requirements_run(problem)
        techstack = techstack_run(requirements)
        output = arch_run(requirements=requirements, techstack=techstack, revision_count=0)
        print(json.dumps(output, indent=4))
    except RuntimeError as e:
        print(e)
        sys.exit(1)