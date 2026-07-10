import os
from IPython.display import Image, display
from langgraph.graph import StateGraph, START, END
from agents.requirements_agent import req_run
from agents.techstack_agent import tech_run
from agents.architecture_agent import arch_run
from agents.diagram_agent import diagram_run
from agents.critic_agent import critic_run
import subprocess

from state import RequirementsOutput, TechStackOutput, ArchitectureOutput, DiagramOutput, CriticVerdict
from typing import TypedDict

class GraphState(TypedDict):
    problem_statement: str
    requirements: RequirementsOutput | None
    techstack: TechStackOutput | None
    architecture: ArchitectureOutput | None
    diagram: DiagramOutput | None
    critic_verdict: CriticVerdict | None
    critic_history: list[CriticVerdict] 
    revision_count: int


graph = StateGraph(GraphState)

graph.add_node("requirements", req_run)
graph.add_node("techstack", tech_run)
graph.add_node("architecture", arch_run)
graph.add_node("diagram", diagram_run)
graph.add_node("critic", critic_run)    

graph.add_edge(START, "requirements")
graph.add_edge("requirements", "techstack")
graph.add_edge("techstack", "architecture")
graph.add_edge("architecture", "critic")
graph.add_edge("critic", "diagram")
graph.add_edge("diagram", END)

compiled_graph=graph.compile()


def generate_design(problem_statement: str):
    return compiled_graph.invoke({
        "problem_statement": problem_statement,
        "critic_history": [],
        "revision_count": 0,
    })