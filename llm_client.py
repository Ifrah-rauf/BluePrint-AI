import os
import json
from groq import Groq
from openai import OpenAI
import dotenv

dotenv.load_dotenv()

# client = OpenAI(
#         base_url="https://openrouter.ai/api/v1",
#         api_key=os.getenv("GROQ_API_KEY"),
#     )
client = Groq(api_key=os.environ["GROQ_API_KEY"])

def _format_payload(payload) -> str:
    if isinstance(payload, dict):
        lines = []
        for key, value in payload.items():
            if isinstance(value, (dict, list)):
                rendered = json.dumps(value, indent=2, ensure_ascii=False)
            else:
                rendered = str(value)
            lines.append(f"{key}:\n{rendered}")
        return "\n\n".join(lines)
    return json.dumps(payload, ensure_ascii=False)


def call_llm(system_prompt: str, *inputs) -> dict:
    if len(inputs) == 1:
        user_content = _format_payload(inputs[0])
    else:
        user_content = _format_payload(inputs)
    try:
        response = client.chat.completions.create(
           model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("LLM returned an empty message content.")
        return json.loads(content)
    except Exception as e:
        raise RuntimeError(
            f"LLM call failed for model {e}"
        ) from e

def get_client():
    return client
