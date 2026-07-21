from state import DiagramOutput

import sys
import json


def _sanitize_mermaid_label(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", " ")
        .strip()
    )


def _build_mermaid_from_depends_on(components: list[dict]) -> str:
    if not components:
        raise RuntimeError("Diagram Agent failed: components list is empty.")

    # 1. Standardize component tracking mapping dictionaries
    id_map = {}
    normalized_components = []
    
    for i, comp in enumerate(components):
        name = comp.get("name", "").strip()
        if not name:
            continue
        # Use stable numeric IDs to avoid Mermaid parsing issues caused by
        # repeated initials or punctuation in component names.
        node_id = f"N{i + 1}"
        id_map[name] = node_id
        normalized_components.append(comp)

    lines = ["flowchart TD"]
    seen_edges = set()
    seen_nodes = set()


    # 2. Extract edge configurations and fall back to sequential links if dependencies are missing
    for comp in normalized_components:
        src_name = comp["name"]
        src_id = id_map[src_name]

        # ArchitectureOutput uses `connects_to`; keep `depends_on` as a fallback
        # so older payloads still render.
        dependencies = comp.get("connects_to", comp.get("depends_on", []))

        for tgt_raw in dependencies:
            tgt_name = tgt_raw.strip()
            if tgt_name in id_map:
                tgt_id = id_map[tgt_name]

                clean_src = _sanitize_mermaid_label(src_name)
                clean_tgt = _sanitize_mermaid_label(tgt_name)

                edge = f'    {src_id}["{clean_src}"] --> {tgt_id}["{clean_tgt}"]'

                if edge not in seen_edges:
                    lines.append(edge)
                    seen_edges.add(edge)
                    seen_nodes.add(src_name)
                    seen_nodes.add(tgt_name)
    # 🔄 FALLBACK TOPOLOGY: If no edges were discovered, build a clean structural chain flow
    if not seen_edges and len(normalized_components) > 1:
        for i in range(len(normalized_components) - 1):
            c1, c2 = normalized_components[i]["name"], normalized_components[i+1]["name"]
            id1, id2 = id_map[c1], id_map[c2]
            clean1 = _sanitize_mermaid_label(c1)
            clean2 = _sanitize_mermaid_label(c2)
            lines.append(f'    {id1}["{clean1}"] --> {id2}["{clean2}"]')
            seen_nodes.add(c1)
            seen_nodes.add(c2)

    # Render remaining isolated parts so components still appear even if they have
    # no outgoing connections.
    for comp in normalized_components:
        name = comp["name"]
        if name not in seen_nodes:
            node_id = id_map[name]
            clean_name = _sanitize_mermaid_label(name)
            lines.append(f'    {node_id}["{clean_name}"]')

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

        print("\n===== COMPONENTS =====")
        print(json.dumps(components, indent=2))


        mermaid = _build_mermaid_from_depends_on(components)
        response = {"mermaid_diagram": mermaid}
        print("Diagram response:", response)
        validated = DiagramOutput.model_validate(response)
        print("\n========== GENERATED MERMAID ==========")
        print(mermaid)
        print("=======================================\n")
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
