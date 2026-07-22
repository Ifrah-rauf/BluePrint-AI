from langgraph.graph import StateGraph, START, END
from agents.requirements_agent import requirements_node
from agents.techstack_agent import techstack_node
from agents.architecture_agent import architecture_node
from agents.diagram_agent import diagram_node
from agents.critic_agent import critic_node

from state import DesignState

graph = StateGraph(DesignState)

MAX_REVISIONS = 3


def route_after_critic(state):
    print("Verdict:", state["critic_verdict"]["verdict"])
    print("Revision count:", state["revision_count"])

    if (
        state["critic_verdict"]["verdict"] == "REVISE"
        and state["revision_count"] < MAX_REVISIONS
    ):
        print("→ Routing to architecture")
        return "architecture"

    print("→ Routing to diagram")
    return "diagram"

# Individual nodes corresponding to the graph state.
graph.add_node("requirements", requirements_node)
graph.add_node("techstack", techstack_node)
graph.add_node("architecture", architecture_node)
graph.add_node("diagram", diagram_node)
graph.add_node("critic", critic_node)

# Connections between nodes.
graph.add_edge(START, "requirements")
graph.add_edge("requirements", "techstack")
graph.add_edge("techstack", "architecture")
graph.add_edge("architecture", "critic")
graph.add_conditional_edges(
    "critic",
    route_after_critic,
    {
        "architecture": "architecture",
        "diagram": "diagram",
    },
)
graph.add_edge("diagram", END)

compiled_graph = graph.compile()

def generate_design(
    problem_statement: str,
    user_id: str | None = None,
    profile_id: int | None = None,
    session_id: str | None = None,
):
    result = compiled_graph.invoke({
        "problem_statement": problem_statement,
        "critic_history": [],
        "revision_count": 0,
        "user_id": user_id,
        "profile_id": profile_id,
        "session_id": session_id,
    })
    print(result.keys())
    print(result["diagram"])
    return result

def generate_design_stream(
    problem_statement: str,
    user_id: str | None = None,
    profile_id: int | None = None,
    session_id: str | None = None,
):
    """
    Yields one update per node completion: {node_name: {partial state dict}}.
    Use this from Streamlit to render progress as each agent finishes.
    """
    yield from compiled_graph.stream(
        {
            "problem_statement": problem_statement,
            "critic_history": [],
            "revision_count": 0,
            "user_id": user_id,
            "profile_id": profile_id,
            "session_id": session_id,
        },
        stream_mode="updates",
    )


if __name__ == "__main__":
    generate_design("notes app")
