from state import DiagramOutput

import sys
import json


def _build_mermaid_from_depends_on(components: list[dict]) -> str:
    """
    Fully deterministic Mermaid generation from depends_on.
    No LLM involved — Architecture Agent owns the topology, this just renders it.

    depends_on means: this component initiates requests TO these components.
    Edges are always: this --> dependency (never reverse).
    Standalone components (empty depends_on) are rendered as isolated nodes.

    Raises:
        RuntimeError: If components list is empty.
    """
    if not components:
        raise RuntimeError("Diagram Agent failed: components list is empty.")

    id_map = {}
    for i, comp in enumerate(components):
        words = comp["name"].replace("(", "").replace(")", "").split()
        short_id = "".join(w[0] for w in words).upper()[:6]
        if short_id in id_map.values():
            short_id = short_id + str(i)
        id_map[comp["name"]] = short_id

    lines = ["graph TD"]
    seen_edges = set()
    seen_nodes = set()  # tracks which nodes already appear in an edge line

    for comp in components:
        src_id = id_map[comp["name"]]
        for target_name in comp.get("depends_on", []):
            if target_name in id_map:
                tgt_id = id_map[target_name]
                edge = f"    {src_id}[{comp['name']}] --> {tgt_id}[{target_name}]"
                if edge not in seen_edges:
                    lines.append(edge)
                    seen_edges.add(edge)
                    seen_nodes.add(comp["name"])
                    seen_nodes.add(target_name)

    # render standalone components that had no edges
    for comp in components:
        if comp["name"] not in seen_nodes:
            node_id = id_map[comp["name"]]
            lines.append(f"    {node_id}[{comp['name']}]")

    return "\n".join(lines)


def diagram_run(architecture: dict) -> dict:
    """
    Generates a Mermaid diagram deterministically from approved architecture.
    Architecture Agent owns the topology via depends_on — this agent only renders it.
    No LLM call — no hallucinations, no invalid diagrams, same output every run.

    Args:
        architecture (dict): Approved output from Architecture Agent.
                             Components must have depends_on populated.

    Returns:
        dict: Validated diagram output with mermaid_diagram string.

    Raises:
        RuntimeError: If components is empty or diagram generation fails.
    """
    try:
        components = architecture.get("components", [])
        mermaid = _build_mermaid_from_depends_on(components)
        response = {"mermaid_diagram": mermaid}
        print("Diagram response:", response)
        validated = DiagramOutput.model_validate(response)
        return validated.model_dump()
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Diagram Agent failed: {e}") from e


def diagram_node(state: dict) -> dict:
    """
    LangGraph node wrapper for diagram_run.
    Reads from GraphState, calls diagram_run, returns only the state key it owns.
    """
    print("Diagram node executed")
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
        print(output["mermaid_diagram"])
    except RuntimeError as e:
        print(e)
        sys.exit(1)