import os
import json
from groq import Groq

client = Groq(api_key=os.environ["GROQ_API_KEY"])

def call_llm(system_prompt: str, *inputs) -> dict:
    user_content = json.dumps(inputs)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)