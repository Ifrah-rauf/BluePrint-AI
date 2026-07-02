from agents.requirements_agent import run as requirements_run
from agents.techstack_agent import run as techstack_run
from agents.architecture_agent import run as architecture_run
from agents.critic_agent import run as critic_run
from agents.diagram_agent import run as diagram_run
import json

problem = "Design a notification service for 10 million users."

requirements = requirements_run(problem)
print("===== REQUIREMENTS =====")
print(json.dumps(requirements, indent=4))

techstack = techstack_run(requirements)
print("\n===== TECH STACK =====")
print(json.dumps(techstack, indent=4))

architecture = architecture_run(requirements=requirements, techstack=techstack, revision_count=0)
print("\n===== ARCHITECTURE (first pass) =====")
print(json.dumps(architecture, indent=4))

critic_output = critic_run(architecture=architecture)
print("\n===== CRITIC =====")
print(json.dumps(critic_output, indent=4))

if critic_output["verdict"] == "REVISE":
    architecture = architecture_run(
        requirements=requirements,
        techstack=techstack,
        revision_notes=critic_output["issues"],
        revision_count=1,
    )
    print("\n===== ARCHITECTURE (revised) =====")
    print(json.dumps(architecture, indent=4))

diagram = diagram_run(architecture=architecture)
print("\n===== DIAGRAM =====")
print(json.dumps(diagram, indent=4))
print("\n--- paste into mermaid.live ---\n")
print(diagram["mermaid"])