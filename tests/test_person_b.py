from agents.requirements_agent import run as requirements_run
from agents.techstack_agent import run as techstack_run
import json

problem = "Design a notification service for 10 million users."

requirements = requirements_run(problem)

print("===== REQUIREMENTS =====")
print(json.dumps(requirements, indent=4))

techstack = techstack_run(requirements)

print("\n===== TECH STACK =====")
print(json.dumps(techstack, indent=4))