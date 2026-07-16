import os
from IPython.display import Image, display
from langgraph.graph import StateGraph, START, END
from agents.requirements_agent import requirements_node
from agents.techstack_agent import techstack_node
from agents.architecture_agent import architecture_node
from agents.diagram_agent import diagram_node
from agents.critic_agent import critic_node
import subprocess

from state import DesignState
from typing import TypedDict

graph = StateGraph(DesignState)

MAX_REVISIONS=3
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

#individual nodes corresponding to graphstate intially set null state
graph.add_node("requirements", requirements_node)
graph.add_node("techstack", techstack_node)
graph.add_node("architecture", architecture_node)
graph.add_node("diagram", diagram_node)
graph.add_node("critic", critic_node)    

#conncetion between nodes (startnode->endnode)
graph.add_edge(START, "requirements")
graph.add_edge("requirements", "techstack")
graph.add_edge("techstack", "architecture")
graph.add_edge("architecture", "critic")
graph.add_conditional_edges(
    "critic", #our startnode
    route_after_critic, #function defining condition
    {
        "architecture": "architecture", #run architecture (revision)
        "diagram": "diagram", #run diagram if no revision
    },
)
graph.add_edge("diagram", END)

compiled_graph=graph.compile()

def generate_design(problem_statement: str):
    result = compiled_graph.invoke({
        "problem_statement": problem_statement,
        "critic_history": [],
        "revision_count": 0,
    })
    print(result.keys())
    print(result["diagram"])
    return result

generate_design("notes app")