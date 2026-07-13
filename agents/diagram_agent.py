from state import DiagramOutput
from llm_client import call_llm
from prompts import DIAGRAM_PROMPT
import sys
import json


def _build_mermaid_from_connects_to(components: list[dict]) -> str | None:
    """
    Deterministic Mermaid generation directly from connects_to — no LLM call needed.
    Returns None if connects_to is empty for all components (triggers LLM fallback).
    """
    id_map = {}
    for i, comp in enumerate(components):
        words = comp["name"].replace("(", "").replace(")", "").split()
        short_id = "".join(w[0] for w in words).upper()[:6]
        if short_id in id_map.values():
            short_id = short_id + str(i)
        id_map[comp["name"]] = short_id

    lines = ["graph TD"]
    seen_edges = set()

    for comp in components:
        src_id = id_map[comp["name"]]
        for target_name in comp.get("connects_to", []):
            if target_name in id_map:
                tgt_id = id_map[target_name]
                edge = f"    {src_id}[{comp['name']}] --> {tgt_id}[{target_name}]"
                if edge not in seen_edges:
                    lines.append(edge)
                    seen_edges.add(edge)

    return "\n".join(lines) if len(lines) > 1 else None


def diagram_run(architecture: dict) -> dict:
    """
    Generates a Mermaid diagram from an approved architecture.
    Uses connects_to for deterministic generation — falls back to LLM if missing.

    Args:
        architecture (dict): Approved output from Architecture Agent.

    Returns:
        dict: Validated diagram output with mermaid string and explanation.

    Raises:
        RuntimeError: If the LLM call or validation fails.
    """
    try:
        components = architecture.get("components", [])
        mermaid = _build_mermaid_from_connects_to(components)

        if mermaid:
            explanation = architecture.get("design_description", "")[:120]
            response = {"mermaid": mermaid, "explanation": explanation}
        else:
            print("[diagram_agent] connects_to missing — falling back to LLM")
            response = call_llm(DIAGRAM_PROMPT, architecture)

        validated = DiagramOutput.model_validate(response)
        return validated.model_dump()
    except Exception as e:
        raise RuntimeError(f"Diagram Agent failed: {e}") from e


def diagram_node(state: dict) -> dict:
    """
    LangGraph node wrapper for diagram_run.
    Reads from GraphState, calls diagram_run, returns only the state key it owns.
    """
    output = diagram_run(architecture=state["architecture"])
    return {"diagram": output}


if __name__ == "__main__":
    from agents.requirements_agent import req_run
    from agents.techstack_agent import tech_run
    from agents.architecture_agent import arch_run
    from agents.critic_agent import critic_run

    problem = "Design a scalable notification system for 10 million users."

    if len(sys.argv) > 1:
        if sys.argv[1] == "--prompt":
            if len(sys.argv) < 3:
                print('Usage: python diagram_agent.py --prompt "your problem"')
                sys.exit(1)
            problem = sys.argv[2]

    try:
        requirements = req_run(problem)
        techstack = tech_run(requirements)
        architecture = arch_run(requirements=requirements, techstack=techstack, revision_count=0)
        critic_output = critic_run(architecture=architecture)

        if critic_output["verdict"] == "REVISE":
            architecture = arch_run(
                requirements=requirements,
                techstack=techstack,
                revision_notes=critic_output["issues"],
                revision_count=1,
            )

        output = diagram_run(architecture=architecture)
        print(json.dumps(output, indent=4))
        print("\n--- paste into mermaid.live ---\n")
        print(output["mermaid"])
    except RuntimeError as e:
        print(e)
        sys.exit(1)