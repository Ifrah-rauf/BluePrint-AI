from state import ArchitectureOutput
from llm_client import call_llm
from prompts import ARCHITECTURE_PROMPT
from rag.query import build_combined_rag_context
import sys
import json

def arch_run(
    
    requirements: dict,
    techstack: dict,
    previous_architecture=None,
    revision_notes: list | None = None,
    revision_count: int = 0,
    problem_statement: str | None = None,
    collection: str | None = "system_design",
    user_id: str | None = None,
    profile_id: int | None = None,
    session_id: str | None = None,
) -> dict:
    """
    Produces a component-level architecture from requirements and tech stack.
    If previous_architecture is null:
    Generate a fresh architecture.
    Otherwise:
    Modify only the parts necessary to resolve the issues.
    Preserve all correct design decisions.
    Do not redesign the system from scratch.
    On revision loops, accepts revision_notes from the Critic Agent. If revision notes are provided,
    they override previous architectural decisions.
    Do not regenerate the first draft. Modify the previous design to resolve the review issues while 
    preserving everything that is already correct.

    Args:
        requirements (dict): Output from Requirements Agent.
        techstack (dict): Output from Tech Stack Agent.
        revision_notes (list | None): Issues from Critic Agent, passed only on revision loops.
        revision_count (int): Owned by LangGraph state — passed through unchanged.

    Returns:
        dict: Validated architecture dictionary.

    Raises:
        RuntimeError: If the LLM call or validation fails.
    """
    try:
        rag_query_parts = [
            problem_statement or "",
            json.dumps(requirements, ensure_ascii=False),
            json.dumps(techstack, ensure_ascii=False),
            json.dumps(revision_notes or [], ensure_ascii=False),
        ]
        rag_context = build_combined_rag_context(
            user_query="\n".join(part for part in rag_query_parts if part).strip(),
            user_id=user_id,
            profile_id=profile_id,
            session_id=session_id,
        )
        response = call_llm(
            ARCHITECTURE_PROMPT,
            {
                "problem_statement": problem_statement,
                "requirements": requirements,
                "techstack": techstack,
                "revision_notes": revision_notes,
                "rag_context": rag_context,
            },
        )
        response["revision_count"] = revision_count
        validated = ArchitectureOutput.model_validate(response)
        return validated.model_dump()
    except Exception as e:
        raise RuntimeError(f"Architecture Agent failed: {e}") from e


def architecture_node(state: dict) -> dict:
    """
    LangGraph node wrapper for arch_run.
    Reads from GraphState, calls arch_run, returns only the state key it owns.
    """
    critic_verdict = state.get("critic_verdict")
    revision_notes = critic_verdict.get("issues") if critic_verdict else None

    output = arch_run(
        requirements=state["requirements"],
        techstack=state["techstack"],
        previous_architecture=state.get("architecture"),
        #on first run returns none, after that it returns the architecture from the previous iteration.
        revision_notes=(
            state["critic_verdict"]["issues"]
            if state.get("critic_verdict")
            else None
        ),
        revision_count=state["revision_count"],
        problem_statement=state.get("problem_statement"),
        user_id=state.get("user_id"),
        profile_id=state.get("profile_id"),
        session_id=state.get("session_id"),
    )
    return {"architecture": output}


if __name__ == "__main__":
    from agents.requirements_agent import req_run
    from agents.techstack_agent import tech_run

    problem = "Design a scalable notification system for 10 million users."

    if len(sys.argv) > 1:
        if sys.argv[1] == "--prompt":
            if len(sys.argv) < 3:
                print('Usage: python architecture_agent.py --prompt "your problem"')
                sys.exit(1)
            problem = sys.argv[2]

    try:
        requirements = req_run(problem)
        techstack = tech_run(requirements)
        output = arch_run(requirements=requirements, techstack=techstack, revision_count=0)
        print(json.dumps(output, indent=4))
    except RuntimeError as e:
        print(e)
        sys.exit(1)
