# generate_design() — orchestration
from llm_client import call_llm
from prompts import REQUIREMENTS_PROMPT, TECHSTACK_PROMPT, ARCHITECTURE_PROMPT

def generate_design(problem_statement: str) -> dict:
    requirements = call_llm(REQUIREMENTS_PROMPT, problem_statement)
    techstack = call_llm(TECHSTACK_PROMPT, requirements)
    architecture = call_llm(ARCHITECTURE_PROMPT, requirements, techstack)
    # ... critique loop here later
    return {
        "requirements": requirements,
        "techstack": techstack,
        "architecture": architecture
    }
