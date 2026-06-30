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


class ArchitectureOutput(BaseModel):
    design_description: str
    components: list[ArchitectureComponent]
    mermaid_diagram: str
    tradeoffs: list[str]


class CriticVerdict(BaseModel):
    verdict: str  # exactly "APPROVE" or "REVISE"
    issues: list[str]


class FinalOutput(BaseModel):
    requirements: RequirementsOutput
    techstack: TechStackOutput
    architecture: ArchitectureOutput
    critic_history: list[CriticVerdict]
    revision_count: int

class DesignState(TypedDict):
    problem_statement: str
    requirements: NotRequired[dict]
    techstack: NotRequired[dict]
    architecture: NotRequired[dict]
    critic_verdict: NotRequired[dict]
    critic_history: Annotated[list[dict], operator.add]  # append across REVISE loops
    revision_count: int
    final_output: NotRequired[dict]