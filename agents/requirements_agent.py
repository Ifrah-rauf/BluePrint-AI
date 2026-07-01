from state import RequirementsOutput
from llm_client import call_llm
from prompts import REQUIREMENTS_PROMPT
import sys
import json
#run fuction
def run(problem_statement: str) -> dict:
    """
    Extract structured requirements from a software system design problem.
    Args:
        problem_statement (str): User's system design problem.
    Returns:
        dict: Validated requirements dictionary.
    Raises:
        RuntimeError: If the LLM call or validation fails.
    """
    try:
        response = call_llm(
            REQUIREMENTS_PROMPT,
            problem_statement,
        )
        validated = RequirementsOutput.model_validate(response)
        return validated.model_dump()
    except Exception as e:
        raise RuntimeError(
            f"Requirements Agent failed: {e}"
        ) from e
#test block
if __name__ == "__main__":
    # 1. Setting the default fallback text
    problem_statement = "Design a scalable URL shortener for 100 million users."
    
    # 2. Check if '--prompt' was passed in the terminal command
    if len(sys.argv) > 1:
        if sys.argv[1] == "--prompt":
            if len(sys.argv) < 3:
                print("Usage: python requirements_agent.py --prompt \"your problem\"")
                sys.exit(1)
            problem_statement = sys.argv[2]
    try:
        # 3. Pass the dynamic statement into your agent execution
        output = run(problem_statement)
        print(json.dumps(output, indent=4))
    except RuntimeError as e:
        print(e)
        sys.exit(1)