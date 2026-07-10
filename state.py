# backend/state.py
from typing import Annotated, NotRequired, TypedDict
import operator

from pydantic import BaseModel, Field


# --- Agent output models (validate before returning from each agent) ---

class RequirementsOutput(BaseModel):
    functional_requirements: list[str]
    non_functional_requirements: list[str]
    scale: str
    constraints: list[str]
    assumptions: list[str]


class StackItem(BaseModel):
    component: str
    choice: str
    justification: str


class TechStackOutput(BaseModel):
    stack: list[StackItem]


class ArchitectureComponent(BaseModel):
    name: str
    responsibility: str

# UPDATED---------------------------------
class ArchitectureOutput(BaseModel):
    design_description: str
    components: list[ArchitectureComponent]
    tradeoffs: list[str]
    # mermaid_diagram REMOVED from here


class DiagramOutput(BaseModel):
    mermaid_diagram: str
# ----------------------------------------

class CriticVerdict(BaseModel):
    verdict: str  # exactly "APPROVE" or "REVISE"
    issues: list[str]


class FinalOutput(BaseModel):
    requirements: RequirementsOutput
    techstack: TechStackOutput
    architecture: ArchitectureOutput
    diagram: DiagramOutput              # NEW
    critic_history: list[CriticVerdict]
    revision_count: int

class DesignState(TypedDict):
    problem_statement: str
    requirements: NotRequired[dict]
    techstack: NotRequired[dict]
    architecture: NotRequired[dict]          # now WITHOUT mermaid_diagram
    critic_verdict: NotRequired[dict]
    critic_history: Annotated[list[dict], operator.add]
    revision_count: int
    mermaid: NotRequired[dict]               # NEW — output of the diagram-only step, runs once after critic approves
    final_output: NotRequired[dict]